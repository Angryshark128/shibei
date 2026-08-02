#!/usr/bin/env python3
"""拾贝 · 分析模块（单一入口）：自动爬取所需数据 → 调 LLM → 输出报告。

用法：
    python3 analyzer.py          # 默认：自动增量爬取 + 增量分析（数据为空时自动全量）
    python3 analyzer.py --full   # 强制全量：自动爬取 + 重分析全部帖子
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from crawler import run_crawl
from models import MAX_REPLIES, Post, post_from_dict

DATA_DIR = Path("data")
CACHE_DIR = DATA_DIR / ".cache"
STATE_FILE = DATA_DIR / "state.json"
REPORT_DIR = DATA_DIR / "analysis"
CONFIG_FILE = "config.json"

BATCH_SIZE = 15
MERGE_SIZE = 3
MAX_BACKOFF = 60  # 指数退避上限（秒）

# (key, 标题, 定义) —— 四个分析维度，互不干扰
CATEGORIES = [
    ("ideas", "好的创意/产品点子", "帖子中提到或暗示的有价值的想法、工具需求、产品方向"),
    ("pain", "用户痛点", "用户反复抱怨、求助、表达不满的问题"),
    ("indie", "个人开发者机会", "对独立开发者/小团队友好的方向，侧重低门槛、可快速验证"),
    ("trend", "趋势洞察", "社区关注的技术趋势或话题走向"),
]

# 来源链接锚点：最终输出时由代码还原为可点击链接（不经过 LLM）
LINK_RE = re.compile(r"\[#([^\]]+)\]")

# LLM 配置（main 里从 config/环境变量解析后填充），call_api 读取
_LLM: dict[str, str] = {"base_url": "", "model": "", "max_tokens": "4096"}


# ---------- 配置 / 状态 ----------


def load_config(path: str = CONFIG_FILE) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_state(path: Path | None = None) -> dict[str, dict[str, int]]:
    path = path or STATE_FILE
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict[str, dict[str, int]], path: Path | None = None) -> None:
    path = path or STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_llm_config(config: dict[str, Any]) -> dict[str, str]:
    """解析 LLM 配置。

    URL 与模型均必填（环境变量或 config.json 二选一），缺失即退出——
    避免误发到错误的端点或模型。max_tokens 可选，兜底 4096。
    """
    base_url = os.environ.get("OPENAI_BASE_URL") or config.get("llm", {}).get("base_url")
    if not base_url:
        raise SystemExit(
            "未设置 OPENAI_BASE_URL。\n"
            "拾贝需要用户自带的 OpenAI 兼容 API 地址：\n"
            "  export OPENAI_BASE_URL=https://api.deepseek.com/v1\n"
            "  或写入 config.json 的 llm.base_url"
        )
    model = os.environ.get("ANALYZE_MODEL") or config.get("llm", {}).get("model")
    if not model:
        raise SystemExit(
            "未设置 ANALYZE_MODEL。\n"
            "拾贝需要指定模型名（不同厂商支持的模型各不相同）：\n"
            "  export ANALYZE_MODEL=deepseek-v4-flash\n"
            "  或写入 config.json 的 llm.model"
        )
    max_tokens = str(os.environ.get("ANALYZE_MAX_TOKENS") or config.get("llm", {}).get("max_tokens") or "4096")
    return {"base_url": base_url.rstrip("/"), "model": model, "max_tokens": max_tokens}


def check_env() -> str:
    """检查 OPENAI_API_KEY，缺失则打印配置说明并退出。"""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("未设置 OPENAI_API_KEY。", file=sys.stderr)
        print("拾贝使用 OpenAI 兼容 API，请自行提供 base_url、api_key 与模型名：", file=sys.stderr)
        print("  export OPENAI_API_KEY=sk-xxx   # 必填", file=sys.stderr)
        print(
            "  export OPENAI_BASE_URL=https://api.deepseek.com/v1   # 必填（或用 config.json 的 llm.base_url）",
            file=sys.stderr,
        )
        print("  export ANALYZE_MODEL=deepseek-v4-flash   # 必填（或用 config.json 的 llm.model）", file=sys.stderr)
        raise SystemExit(1)
    return api_key


# ---------- API 调用 ----------


def _http_error_detail(e: urllib.error.HTTPError) -> str:
    """从 OpenAI 兼容 API 的错误响应中提取可读的 message。"""
    try:
        data = json.loads(e.read().decode("utf-8"))
    except (ValueError, OSError):
        return str(e)
    err = data.get("error", {})
    if isinstance(err, dict):
        return str(err.get("message") or err)
    return str(err)


def call_api(prompt: str, *, timeout: int = 120, retries: int = 3) -> str:
    """调用 OpenAI 协议 chat/completions，返回 assistant 文本。失败时 raise（附服务端原因）。"""
    body = json.dumps(
        {
            "model": _LLM["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": int(_LLM.get("max_tokens", "4096")),
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{_LLM['base_url']}/chat/completions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', '')}",
            "Content-Type": "application/json",
        },
    )
    last_error = ""
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            detail = _http_error_detail(e)
            if 400 <= e.code < 500 and e.code != 429:
                # 客户端错误（模型名/参数/鉴权），重试无用，立即终止并给出原因
                raise RuntimeError(f"LLM API 返回 {e.code}：{detail}") from e
            last_error = f"HTTP {e.code}：{detail}"
        except (urllib.error.URLError, OSError, ValueError) as e:
            last_error = str(e)
        if attempt < retries:
            time.sleep(min(5 * (2**attempt), MAX_BACKOFF))
    raise RuntimeError(f"LLM API 调用失败（重试 {retries} 次后）：{last_error}")


# ---------- Prompt ----------


def format_post(p: Post) -> str:
    """帖子文本格式：正文截断 500 字符，每帖最多 10 条回复，每条回复截断 200 字符。"""
    lines = [
        f"## [#{p.id}] {p.title}",
        f"来源: {p.source} | 节点: {p.node} | 作者: {p.author} | 回复数: {p.replies_count}",
    ]
    if p.content:
        lines.append(p.content[:500])
    for r in p.reply_list[:MAX_REPLIES]:
        if r.content:
            lines.append(f"  - {r.author}: {r.content[:200]}")
    return "\n".join(lines)


def format_batch(batch: list[Post]) -> str:
    return "\n---\n".join(format_post(p) for p in batch)


def build_batch_prompt(batch_text: str, idx: int, total: int, title: str, desc: str) -> str:
    return f"""分析以下社区帖子，只提炼「{title}」类信息。

定义：{desc}

要求：
- 只输出这一类，不要输出其他类别
- 不要限制条数，尽可能多地提炼有价值的信息
- 每条用 `[#帖子ID]` 标注来源帖子，ID 必须与上文的帖子标注完全一致，不得改写
- 用中文回答

---（第 {idx + 1}/{total} 批）

{batch_text}"""


def build_merge_prompt(results: list[str], incremental: bool) -> str:
    note = "（本次为今日新增分析）" if incremental else ""
    body = "\n\n---\n\n".join(results)
    return f"""以下是多批次的分析结果，请合并去重，输出一份最终报告{note}。

要求：
- 去除重复条目，保留最有代表性的描述
- 不要限制条数，尽可能保留所有有价值的信息
- 每条保留 `[#帖子ID]` 来源标注，不得删除或改写
- 按价值从高到低排列
- 用中文回答

{body}"""


# ---------- 合并与链接还原 ----------


def merge_results(results: list[str], incremental: bool) -> str:
    """层级合并：每 MERGE_SIZE 个一组，递归直到只剩 1 个结果。"""
    if not results:
        return ""
    if len(results) == 1:
        return results[0]
    current = list(results)
    while len(current) > 1:
        chunks = [current[i : i + MERGE_SIZE] for i in range(0, len(current), MERGE_SIZE)]
        nxt: list[str] = []
        for chunk in chunks:
            if len(chunk) == 1:
                nxt.append(chunk[0])
            else:
                nxt.append(call_api(build_merge_prompt(chunk, incremental), timeout=300))
        current = nxt
    return current[0]


def restore_links(text: str, id2link: dict[str, tuple[str, str]]) -> str:
    """把 `[#帖子ID]` 还原为 `[帖子标题](原帖URL)`（代码层，URL 不经过 LLM）。"""

    def _repl(m: re.Match[str]) -> str:
        pid = m.group(1)
        info = id2link.get(pid)
        if info is None:
            print(f"[!] 链接还原：未找到帖子 {pid} 的来源映射，保留原文", file=sys.stderr)
            return m.group(0)
        title, url = info
        return f"[{title}]({url})"

    return LINK_RE.sub(_repl, text)


def cleanup_cache(run_id: str) -> None:
    for f in CACHE_DIR.glob(f"{run_id}_*.json"):
        f.unlink(missing_ok=True)


# ---------- 分析主流程 ----------


def analyze(topics: list[Post], incremental: bool = False) -> dict[str, str]:
    """分析所有帖子，返回 {类别标题: 合并后文本}。"""
    run_id = hashlib.md5("".join(p.id for p in topics).encode("utf-8")).hexdigest()[:12]
    id2link = {p.id: (p.title, p.url) for p in topics}
    batches = [topics[i : i + BATCH_SIZE] for i in range(0, len(topics), BATCH_SIZE)]
    total_batches = len(batches)

    def analyze_category(bi: int, batch_text: str, key: str, title: str, desc: str) -> str:
        """分析单个批次单个类别，带 run_id 缓存。"""
        cache_file = CACHE_DIR / f"{run_id}_b{bi}_{key}.json"
        cached = load_json(cache_file)
        if isinstance(cached, dict) and cached.get("result"):
            return cached["result"]
        result = call_api(build_batch_prompt(batch_text, bi, total_batches, title, desc))
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"key": key, "result": result}, f, ensure_ascii=False)
        return result

    per_key: dict[str, list[str]] = {key: [] for key, _, _ in CATEGORIES}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        # 批次 × 类别 并行分析
        futures = []
        for bi, batch in enumerate(batches):
            batch_text = format_batch(batch)
            for key, title, desc in CATEGORIES:
                futures.append((ex.submit(analyze_category, bi, batch_text, key, title, desc), key))
        for fut, key in futures:
            per_key[key].append(fut.result())

        # 各类别独立层级合并（并行）
        merged_raw = {
            key: fut.result()
            for fut, key in ((ex.submit(merge_results, per_key[key], incremental), key) for key, _, _ in CATEGORIES)
        }

    result: dict[str, str] = {}
    for key, title, _ in CATEGORIES:
        result[title] = restore_links(merged_raw[key], id2link)

    cleanup_cache(run_id)
    return result


# ---------- 帖子加载 / 报告 ----------


def load_topics(data_dir: Path, since: int | None = None) -> list[Post]:
    """遍历目录下所有 *.json，按文件名排序；since 过滤 created < since 的帖子。"""
    if not data_dir.is_dir():
        return []
    posts: list[Post] = []
    for f in sorted(data_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        p = post_from_dict(d)
        if since is not None and p.created < since:
            continue
        posts.append(p)
    return posts


def build_report(merged: dict[str, str], total: int, summary: str) -> str:
    lines = [
        "# 拾贝 · 多来源分析",
        "",
        f"来源: {summary}",
        "",
        f"基于 {total} 个帖子自动生成",
        "",
    ]
    for title, text in merged.items():
        lines += [f"## {title}", "", text.strip(), ""]
    return "\n".join(lines)


def write_report(report: str, incremental: bool) -> None:
    target = REPORT_DIR / ("analysis_today.md" if incremental else "analysis.md")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(f"\n报告已写入：{target.resolve()}")


# ---------- CLI ----------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="analyzer.py",
        description="拾贝分析（单一入口）：自动爬取所需数据 → LLM 提炼 → 输出报告并打印绝对路径。",
    )
    parser.add_argument("--full", action="store_true", help="强制全量分析（重分析全部帖子；数据为空时自动全量爬取）")
    return parser


def _enabled_sources(config: dict[str, Any]) -> list[str]:
    return [name for name, conf in config.get("sources", {}).items() if conf.get("enabled", True)]


def _has_data(config: dict[str, Any]) -> bool:
    """配置的 enabled 来源下是否存在任何帖子 JSON。"""
    for name in _enabled_sources(config):
        source_dir = DATA_DIR / name
        if source_dir.is_dir() and any(source_dir.rglob("*.json")):
            return True
    return False


def _load_topics(
    config: dict[str, Any], since_by_source: dict[str, int | None]
) -> tuple[list[Post], dict[str, set[str]]]:
    """按来源加载帖子；返回 (帖子列表, {来源: 节点集合})。"""
    topics: list[Post] = []
    source_nodes: dict[str, set[str]] = {}
    for name in _enabled_sources(config):
        since = since_by_source.get(name)
        source_dir = DATA_DIR / name
        if not source_dir.is_dir():
            continue
        for node_dir in sorted(source_dir.iterdir()):
            if not node_dir.is_dir():
                continue
            node_posts = load_topics(node_dir, since=since)
            if node_posts:
                source_nodes.setdefault(name, set()).add(node_dir.name)
            topics.extend(node_posts)
    return topics, source_nodes


def _show_no_new(config: dict[str, Any]) -> None:
    for name in ("analysis_today.md", "analysis.md"):
        p = REPORT_DIR / name
        if p.exists():
            print(f"没有新增帖子，无需分析。最近一次报告：{p.resolve()}")
            return
    if _has_data(config):
        print("没有新增帖子，无需分析。")
    else:
        print("没有可分析的帖子。自动爬取未获取到数据——")
        print("可能是来源 API 限流或暂时不可用（如 V2EX 403），请稍后重试或检查网络。")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    check_env()  # 校验 OPENAI_API_KEY，缺失即退出
    config = load_config()
    _LLM.update(resolve_llm_config(config))

    # 自动爬取：数据为空时重置该来源状态，让增量爬取退化为全量；否则只抓新增
    if not _has_data(config):
        state = load_state()
        for name in _enabled_sources(config):
            state.pop(name, None)
        save_state(state)
        print("首次运行或数据为空，自动全量爬取 ...")
    run_crawl(config, today=True)

    # 加载待分析帖子
    state = load_state()
    since_by_source: dict[str, int | None]
    if args.full:
        since_by_source = {name: None for name in _enabled_sources(config)}
    else:
        since_by_source = {
            name: state.get(name, {}).get("last_analysis") or state.get(name, {}).get("last_crawl")
            for name in _enabled_sources(config)
        }
    incremental = not args.full
    topics, source_nodes = _load_topics(config, since_by_source)

    if not topics:
        _show_no_new(config)
        return 0

    summary = ", ".join(f"{name}({', '.join(sorted(nodes))})" for name, nodes in source_nodes.items())
    print(f"共 {len(topics)} 个帖子待分析（来源: {summary}）...")
    merged = analyze(topics, incremental=incremental)

    report = build_report(merged, len(topics), summary)
    write_report(report, incremental=incremental)

    now = int(time.time())
    for name in source_nodes:
        state.setdefault(name, {})["last_analysis"] = now
    save_state(state)

    print("\n" + report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
