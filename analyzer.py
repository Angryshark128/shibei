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

# 批次分析：每批帖子一次调用即输出全部类别（避免每类各发一次正文，省 2/3 输入 token）。
# 批内帖数越大，批次间重复的提示词开销越小；单次输出上限相应放大（MULTI_MAX_TOKENS）。
BATCH_SIZE = 20
MERGE_SIZE = 3  # 合并回退路径的层级合并宽度
MULTI_MAX_TOKENS = 8192  # 一次输出多类时的 max_tokens 下限
MAX_BACKOFF = 60  # 指数退避上限（秒）

LANGS = ("zh", "en")

# (key, 标题, 定义) —— 三个分析模块，互不干扰，支持中英两种分析语言。
# 对应报告页的「产品创意 / 用户痛点 / 潜在机会」三个文档，各自按分类（H3）组织。
CATEGORIES_BY_LANG: dict[str, list[tuple[str, str, str]]] = {
    "zh": [
        ("ideas", "产品创意", "帖子中提到或暗示的、有价值的想法、工具需求和产品方向"),
        ("pain", "用户痛点", "用户反复抱怨、求助、表达不满的问题"),
        ("indie", "潜在机会", "对独立开发者/小团队友好、低门槛、可快速验证的方向与机会"),
    ],
    "en": [
        (
            "ideas",
            "Product Ideas",
            "Valuable ideas, tool needs and product directions mentioned or implied in the posts",
        ),
        (
            "pain",
            "User Pain Points",
            "Problems users repeatedly complain about, seek help with or express dissatisfaction about",
        ),
        (
            "indie",
            "Opportunities",
            "Directions friendly to indie developers / small teams: low barrier, quick to validate",
        ),
    ],
}

# 兼容旧名：默认（zh）分类表，供测试与外部引用
CATEGORIES = CATEGORIES_BY_LANG["zh"]


def _categories(lang: str) -> list[tuple[str, str, str]]:
    """按语言取分类表；未知语言回落 zh。"""
    return CATEGORIES_BY_LANG.get(lang, CATEGORIES_BY_LANG["zh"])


# 来源链接锚点：最终输出时由代码还原为可点击链接（不经过 LLM）
LINK_RE = re.compile(r"\[#([^\]]+)\]")

# LLM 配置（main 里从 config/环境变量解析后填充），call_api 读取
_LLM: dict[str, str] = {"base_url": "", "model": "", "max_tokens": "4096"}

# 分析/界面语言（main 里从 --lang / ANALYZE_LANG 解析后填充），默认中文
_LANG: str = "zh"


def resolve_lang(lang: str | None) -> str:
    """解析分析语言：--lang 参数 > ANALYZE_LANG 环境变量 > zh。"""
    for candidate in (lang, os.environ.get("ANALYZE_LANG", "")):
        if candidate is not None and str(candidate).strip() in LANGS:
            return str(candidate).strip()
    return "zh"


# CLI / 界面文案（按分析语言输出，让任务日志随语言切换）
_UI: dict[str, dict[str, str]] = {
    "zh": {
        "no_api_key": (
            "未设置 OPENAI_API_KEY。\n"
            "拾贝使用 OpenAI 兼容 API，请自行提供 base_url、api_key 与模型名：\n"
            "  export OPENAI_API_KEY=sk-xxx   # 必填\n"
            "  export OPENAI_BASE_URL=https://api.deepseek.com/v1   # 必填（或用 config.json 的 llm.base_url）\n"
            "  export ANALYZE_MODEL=deepseek-v4-flash   # 必填（或用 config.json 的 llm.model）"
        ),
        "no_base_url": (
            "未设置 OPENAI_BASE_URL。\n"
            "拾贝需要用户自带的 OpenAI 兼容 API 地址：\n"
            "  export OPENAI_BASE_URL=https://api.deepseek.com/v1\n"
            "  或写入 config.json 的 llm.base_url"
        ),
        "no_model": (
            "未设置 ANALYZE_MODEL。\n"
            "拾贝需要指定模型名（不同厂商支持的模型各不相同）：\n"
            "  export ANALYZE_MODEL=deepseek-v4-flash\n"
            "  或写入 config.json 的 llm.model"
        ),
        "link_warn": "[!] 链接还原：未找到帖子 {pid} 的来源映射，保留原文",
        "report_written": "\n报告已写入：{path}",
        "interrupted": "\n[!] 已中断（Ctrl+C）。已爬取/分析的数据均已保存，下次运行自动继续。",
        "first_run_full": "首次运行或数据为空，自动全量爬取 ...",
        "posts_to_analyze": "共 {n} 个帖子待分析（来源: {summary}）...",
        "full_title": "{day} 全量总览",
        "no_new_latest": "没有新增帖子，无需分析。最近一次报告：{path}",
        "no_new_plain": "没有新增帖子，无需分析。",
        "no_posts": "没有可分析的帖子。自动爬取未获取到数据——",
        "no_posts_hint": "可能是来源 API 限流或暂时不可用（如 V2EX 403），请稍后重试或检查网络。",
    },
    "en": {
        "no_api_key": (
            "OPENAI_API_KEY is not set.\n"
            "Shibei uses an OpenAI-compatible API — provide base_url, api_key and model yourself:\n"
            "  export OPENAI_API_KEY=sk-xxx   # required\n"
            "  export OPENAI_BASE_URL=https://api.deepseek.com/v1   # required (or llm.base_url in config.json)\n"
            "  export ANALYZE_MODEL=deepseek-v4-flash   # required (or llm.model in config.json)"
        ),
        "no_base_url": (
            "OPENAI_BASE_URL is not set.\n"
            "Shibei needs your own OpenAI-compatible API endpoint:\n"
            "  export OPENAI_BASE_URL=https://api.deepseek.com/v1\n"
            "  or set llm.base_url in config.json"
        ),
        "no_model": (
            "ANALYZE_MODEL is not set.\n"
            "Shibei needs a model name (models vary by provider):\n"
            "  export ANALYZE_MODEL=deepseek-v4-flash\n"
            "  or set llm.model in config.json"
        ),
        "link_warn": "[!] Restore links: no source mapping for post {pid}, keeping original text",
        "report_written": "\nReport written to: {path}",
        "interrupted": "\n[!] Interrupted (Ctrl+C). Crawled/analyzed data is saved; the next run will continue.",
        "first_run_full": "First run or no data — running full crawl ...",
        "posts_to_analyze": "{n} posts to analyze (sources: {summary})...",
        "full_title": "{day} · Full Overview",
        "no_new_latest": "No new posts, nothing to analyze. Latest report: {path}",
        "no_new_plain": "No new posts, nothing to analyze.",
        "no_posts": "No posts to analyze — the auto crawl returned no data.",
        "no_posts_hint": (
            "The source API may be rate-limited or temporarily unavailable "
            "(e.g. V2EX 403). Retry later or check the network."
        ),
    },
}


def _t(lang: str, key: str, **kw: Any) -> str:
    """按语言取 CLI/界面文案；未知语言回落 zh。"""
    table = _UI.get(lang) or _UI["zh"]
    return table.get(key, "").format(**kw)


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


def resolve_llm_config(config: dict[str, Any], lang: str = "zh") -> dict[str, str]:
    """解析 LLM 配置。

    URL 与模型均必填（环境变量或 config.json 二选一），缺失即退出——
    避免误发到错误的端点或模型。max_tokens 可选，兜底 4096。
    """
    base_url = os.environ.get("OPENAI_BASE_URL") or config.get("llm", {}).get("base_url")
    if not base_url:
        raise SystemExit(_t(lang, "no_base_url"))
    model = os.environ.get("ANALYZE_MODEL") or config.get("llm", {}).get("model")
    if not model:
        raise SystemExit(_t(lang, "no_model"))
    max_tokens = str(os.environ.get("ANALYZE_MAX_TOKENS") or config.get("llm", {}).get("max_tokens") or "4096")
    return {"base_url": base_url.rstrip("/"), "model": model, "max_tokens": max_tokens}


def check_env() -> str:
    """检查 OPENAI_API_KEY，缺失则打印配置说明并退出。"""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print(_t(_LANG, "no_api_key"), file=sys.stderr)
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


def call_api(prompt: str, *, timeout: int = 120, retries: int = 3, max_tokens: int | None = None) -> str:
    """调用 OpenAI 协议 chat/completions，返回 assistant 文本。失败时 raise（附服务端原因）。

    max_tokens 缺省用配置值；一次输出多类的调用需要更大的上限时显式传入。
    """
    body = json.dumps(
        {
            "model": _LLM["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": max_tokens or int(_LLM.get("max_tokens", "4096")),
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


def build_batch_prompt(batch_text: str, idx: int, total: int, title: str, desc: str, lang: str = "zh") -> str:
    """单类批次 prompt；类别标题/说明由调用方按分析语言传入。"""
    if lang == "en":
        return f"""Analyze the community posts below; extract only "{title}" items.

Definition: {desc}

Rules:
- Output a plain item list, no overall heading
- Output only this category, nothing else
- If nothing matches the definition, output "None"
- Do not limit the count; extract as much valuable info as possible
- Mark each item's source post with ` — [#postID]` at the end; IDs must exactly match the post labels above
- Answer in English; even if the original text is in Chinese, output in English

---(batch {idx + 1}/{total})

{batch_text}"""
    return f"""分析以下社区帖子，只提炼「{title}」类信息。

定义：{desc}

规则：
- 直接输出条目列表，不加总标题
- 只输出这一类，不要输出其他类别
- 如果没有符合定义的信息，输出「无」
- 不要限制条数，尽可能多地提炼有价值的信息
- 每条在描述末尾用 ` — [#帖子ID]` 标注来源帖子，ID 必须与上文的帖子标注完全一致，不得改写
- 一律用中文回答；即使原文是英文，也要用中文输出

---（第 {idx + 1}/{total} 批）

{batch_text}"""


def build_multi_prompt(batch_text: str, idx: int, total: int, lang: str = "zh") -> str:
    """一次调用提炼全部类别：帖子正文只发一次，避免按类重复输入（省 token）。"""
    if lang == "en":
        sections = "\n".join(f"## {title}\n(Definition: {desc})" for _, title, desc in _categories(lang))
        return f"""Analyze the posts below; extract info per listed category (send the batch once, output in one go).

{sections}

Rules:
- In order above, start each category with `## Category name` (exact match), then its items; write "None" if empty
- No overall heading, no extra explanations, no unlisted categories
- Keep descriptions concise: one sentence per item, no more than 60 words
- Mark each item's source post with ` — [#postID]` at the end; IDs must exactly match the post labels above
- Answer in English; even if the original text is in Chinese, output in English

---(batch {idx + 1}/{total})

{batch_text}"""
    sections = "\n".join(f"## {title}\n（定义：{desc}）" for _, title, desc in _categories(lang))
    return f"""分析以下社区帖子，按下面每个类别分别提炼信息（同一批帖子只发一次，请一次全部输出）。

{sections}

规则：
- 按上面的顺序，每个类别先写 `## 类别名`（必须与上面完全一致），再列出该类条目；无匹配信息时写「无」
- 不要输出总标题、不要额外解释、不要输出未列出的类别
- 描述务必精简：每条一句话、不超过 60 字，去掉客套与重复限定
- 每条在描述末尾用 ` — [#帖子ID]` 标注来源帖子，ID 必须与上文的帖子标注完全一致，不得改写
- 一律用中文回答；即使原文是英文，也要用中文输出

---（第 {idx + 1}/{total} 批）

{batch_text}"""


_MULTI_HEAD_RE = re.compile(r"^##\s*(.+?)\s*$", re.M)


def parse_multi(raw: str, lang: str = "zh") -> dict[str, str]:
    """把一次调用的多类输出解析为 {key: 该类文本}；缺失的类别返回空串。"""
    cats = _categories(lang)
    out: dict[str, str] = {key: "" for key, _, _ in cats}
    if not raw:
        return out
    buckets: dict[str, list[str]] = {}
    current = ""
    for line in raw.split("\n"):
        m = _MULTI_HEAD_RE.match(line.strip())
        if m:
            current = m.group(1).strip()
            buckets.setdefault(current, [])
            continue
        if current:
            buckets[current].append(line)
    for key, title, _ in cats:
        text = "\n".join(buckets.get(title, [])).strip()
        out[key] = "" if is_empty_result(text, lang) else text
    return out


def build_merge_prompt(results: list[str], incremental: bool, lang: str = "zh") -> str:
    """合并去重 prompt：把多批结果合并成条目列表。"""
    if lang == "en":
        note = " (this is today's incremental analysis)" if incremental else ""
        body = "\n\n---\n\n".join(results)
        return f"""Below are analysis results from multiple batches; merge and dedupe them into an item list{note}.

Rules:
- Output a plain item list, no overall heading
- Drop duplicate items, keep the most representative description
- Do not limit the count; keep all valuable info
- Keep the trailing ` — [#postID]` source marker on every item; do not remove or alter it
- Sort by value from high to low
- Answer in English; even if the original text is in Chinese, output in English

{body}"""
    note = "（本次为今日新增分析）" if incremental else ""
    body = "\n\n---\n\n".join(results)
    return f"""以下是多批次的分析结果，请合并去重，输出条目列表{note}。

规则：
- 直接输出条目列表，不加总标题
- 去除重复条目，保留最有代表性的描述
- 不要限制条数，尽可能保留所有有价值的信息
- 每条保留描述末尾的 ` — [#帖子ID]` 来源标注，不得删除或改写
- 按价值从高到低排列
- 一律用中文回答；即使原文是英文，也要用中文输出

{body}"""


def build_organize_prompt(text: str, category_title: str, lang: str = "zh") -> str:
    """分组整理 prompt：只做「子主题分组」，不增删改条目。"""
    if lang == "en":
        return f"""Below is the item list for "{category_title}". Group it only; do not change any item.

Rules:
- Do not add, remove or change the meaning of any item; keep the trailing ` — [#postID]` marker on each item
- Group similar items: start each group with `### Subtopic` (<=10 words), then list its items
- At most 8 groups; if items are too scattered to group sensibly, output the whole list as-is (no ### lines)
- Sort groups (and items within groups) by value from high to low
- Answer in English; even if the original text is in Chinese, output in English

---Content to organize---

{text}"""
    return f"""以下是「{category_title}」类的分析条目列表。请只做整理分组，不要增删或改写任何条目。

规则：
- 不新增、不删除、不改写任何条目的含义；每条保留末尾的 ` — [#帖子ID]` 来源标注
- 把主题相近的条目归为一组：每组先用一行 `### 子主题名` 开头（子主题名不超过 10 字），随后列出该组全部条目
- 组数最多 8 组；条目过于零散、无法合理分组时，原样输出整个列表（不要添加任何 ### 行）
- 组间按价值从高到低排列
- 一律用中文回答；即使原文是英文，也要用中文输出

---待整理内容---

{text}"""


def organize_topics(text: str, category_title: str, lang: str = "zh") -> str:
    """把合并后的单个分类文本按子主题分组（输出 H3 小节），失败时原样回退。

    分组只是展示优化：任何异常（LLM 失败/空返回）都不影响报告内容本身。
    """
    if not text or not text.strip():
        return text
    try:
        grouped = call_api(build_organize_prompt(text, category_title, lang), timeout=180)
    except Exception:
        return text
    if not grouped or not grouped.strip():
        return text
    return grouped


def build_consolidate_prompt(results: list[str], category_title: str, incremental: bool, lang: str = "zh") -> str:
    """一次完成「合并去重 + 分类分组」，省掉「先全量合并、再全量分组」的第二轮调用。"""
    if lang == "en":
        note = " (this is today's incremental analysis)" if incremental else ""
        body = "\n\n---\n\n".join(results)
        return f"""Below are "{category_title}" items from multiple batches{note}. Merge, dedupe, group in one pass.

Rules:
- Do not add or rewrite items; merge duplicates, keep the most representative one
- Output structure: start each group with `### Group name` (<=10 words), then its items; at most 8 groups
- If items are too few or too scattered to group, output the plain item list (no ### lines)
- Sort groups and in-group items by value from high to low
- Keep the trailing ` — [#postID]` marker; do not remove or alter it
- Keep descriptions concise: one sentence per item, no more than 60 words
- Answer in English; even if the original text is in Chinese, output in English

---Content to organize---

{body}"""
    note = "（本次为今日新增分析）" if incremental else ""
    body = "\n\n---\n\n".join(results)
    return f"""以下是多批次分析得到的「{category_title}」条目{note}。请合并去重并分组整理，一次输出。

规则：
- 不新增、不改写条目含义；合并重复条目，保留最有代表性的一条
- 输出结构：每组先写一行 `### 分类名`（不超过 10 字），随后列出该组条目；组数最多 8 组
- 条目过少或无法合理分组时，直接输出条目列表（不要添加任何 ### 行）
- 每组与组内条目均按价值从高到低排列
- 每条保留描述末尾的 ` — [#帖子ID]` 来源标注，不得删除或改写
- 描述务必精简：每条一句话、不超过 60 字
- 一律用中文回答；即使原文是英文，也要用中文输出

---待整理内容---

{body}"""


def consolidate(results: list[str], category_title: str, incremental: bool, lang: str = "zh") -> str:
    """合并去重 + 分类分组。

    单批结果交给分组整理（organize_topics）；多批结果一次调用完成两步。
    调用失败或空返回时回退到「层级合并 + 分组」两步路径，保证不丢内容。
    """
    results = [r for r in results if not is_empty_result(r, lang)]
    if not results:
        return ""
    if len(results) == 1:
        return organize_topics(results[0], category_title, lang)
    try:
        merged = call_api(build_consolidate_prompt(results, category_title, incremental, lang), timeout=600)
        if merged and merged.strip():
            return merged
    except Exception:
        pass
    try:
        return organize_topics(merge_results(results, incremental, lang), category_title, lang)
    except Exception:
        # 两级都失败：原样拼接各批结果，保证不丢内容
        return "\n\n".join(results)


# ---------- 合并与链接还原 ----------


_EMPTY_RESULT: dict[str, set[str]] = {
    "zh": {"无", "没有"},
    "en": {"none", "nothing", "n/a", "nil", "no"},
}


def is_empty_result(text: str, lang: str = "zh") -> bool:
    """批次分析结果是否为空（LLM 按指令输出「无/None」或没输出内容）。"""
    t = text.strip().rstrip("。.!！")
    if not t:
        return True
    keywords = _EMPTY_RESULT.get(lang, _EMPTY_RESULT["zh"])
    return t.lower() in keywords


def merge_results(results: list[str], incremental: bool, lang: str = "zh") -> str:
    """层级合并：每 MERGE_SIZE 个一组，递归直到只剩 1 个结果。"""
    results = [r for r in results if not is_empty_result(r, lang)]
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
                nxt.append(call_api(build_merge_prompt(chunk, incremental, lang), timeout=300))
        current = nxt
    return current[0]


def restore_links(text: str, id2link: dict[str, tuple[str, str]], lang: str = "zh") -> str:
    """把 `[#帖子ID]` 还原为 `[来源](原帖URL)`（代码层，URL 不经过 LLM）。

    只保留可点击的来源链接，不显示帖子标题。
    """

    def _repl(m: re.Match[str]) -> str:
        pid = m.group(1)
        info = id2link.get(pid)
        if info is None:
            print(_t(lang, "link_warn", pid=pid), file=sys.stderr)
            return m.group(0)
        _title, url = info
        return f"[来源]({url})"

    return LINK_RE.sub(_repl, text)


def cleanup_cache(run_id: str) -> None:
    for f in CACHE_DIR.glob(f"{run_id}_*.json"):
        f.unlink(missing_ok=True)


# ---------- 分析主流程 ----------


def analyze(topics: list[Post], incremental: bool = False, language: str = "zh") -> dict[str, str]:
    """分析所有帖子，返回 {类别标题（按语言）: 分组整理后的文本}。

    token 优化：每批帖子只调用一次（一次输出全部类别，正文不再按类重复发送），
    每类再各调用一次完成「合并去重 + 分类分组」。
    """
    cats = _categories(language)
    run_id = hashlib.md5("".join(p.id for p in topics).encode("utf-8")).hexdigest()[:12]
    id2link = {p.id: (p.title, p.url) for p in topics}
    batches = [topics[i : i + BATCH_SIZE] for i in range(0, len(topics), BATCH_SIZE)]
    total_batches = len(batches)

    def analyze_batch(bi: int, batch_text: str) -> dict[str, str]:
        """单批一次调用输出全部类别，带 run_id 缓存；输出未按类别分节时回退为按类逐次调用。

        缓存文件名带语言后缀：同一批帖子多语言运行时互不误命中。
        """
        cache_file = CACHE_DIR / f"{run_id}_b{bi}_multi_{language}.json"
        cached = load_json(cache_file)
        if isinstance(cached, dict) and isinstance(cached.get("result"), dict):
            return cached["result"]
        parsed = parse_multi(
            call_api(build_multi_prompt(batch_text, bi, total_batches, language), max_tokens=MULTI_MAX_TOKENS),
            language,
        )
        if not any(parsed.values()):
            parsed = {
                key: call_api(build_batch_prompt(batch_text, bi, total_batches, title, desc, language))
                for key, title, desc in cats
            }
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"result": parsed}, f, ensure_ascii=False)
        return parsed

    per_key: dict[str, list[str]] = {key: [] for key, _, _ in cats}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        # 批次并行：每批一次调用输出全部类别
        batch_results = [
            fut.result() for fut in (ex.submit(analyze_batch, bi, format_batch(b)) for bi, b in enumerate(batches))
        ]
        for parsed in batch_results:
            for key, text in parsed.items():
                if text:
                    per_key[key].append(text)

        # 每类一次调用：合并去重 + 分类分组（失败自动回退，见 consolidate）
        grouped_raw = {
            key: fut.result()
            for fut, key in (
                (ex.submit(consolidate, per_key[key], title, incremental, language), key) for key, title, _ in cats
            )
        }

    result: dict[str, str] = {}
    for key, title, _ in cats:
        result[title] = restore_links(grouped_raw[key], id2link, language)

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


def build_report(merged: dict[str, str], total: int, summary: str, title: str, lang: str = "zh") -> str:
    """按语言拼装报告：标题 + 来源摘要 + 帖子数 + 各分类小节。"""
    if lang == "en":
        header = ["Sources: " + summary, "", f"Generated from {total} posts", ""]
        empty_text = "No insights found this round"
    else:
        header = [f"来源: {summary}", "", f"基于 {total} 个帖子自动生成", ""]
        empty_text = "本轮未发现相关信息"
    lines = [f"# {title}", ""] + header
    for title, text in merged.items():
        content = text.strip() or empty_text
        lines += [f"## {title}", "", content, ""]
    return "\n".join(lines)


def report_stem(incremental: bool, lang: str = "zh") -> str:
    """报告基名：zh 沿用原名（analysis / YYYY-MM-DD），en 加 .en 后缀。"""
    suffix = ".en" if lang == "en" else ""
    return (time.strftime("%Y-%m-%d") if incremental else "analysis") + suffix


def write_report(report: str, incremental: bool, lang: str = "zh") -> None:
    """报告落盘：增量写入当日归档 data/analysis/YYYY-MM-DD[.en].md（每天一份，
    同日多次运行刷新当天）；全量写入 analysis[.en].md 作为总览基线。"""
    target = REPORT_DIR / f"{report_stem(incremental, lang)}.md"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(_t(lang, "report_written", path=target.resolve()))


# ---------- CLI ----------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="analyzer.py",
        description=(
            "拾贝分析（单一入口）：自动爬取所需数据 → LLM 提炼 → 输出报告并打印绝对路径。\n"
            "Shibei analysis (single entry): auto crawl → LLM distill → report; prints the absolute path."
        ),
    )
    parser.add_argument("--full", action="store_true", help="强制全量分析（重跑全部帖子）/ force full re-analysis")
    parser.add_argument(
        "--lang",
        choices=LANGS,
        default=None,
        help="报告与日志语言（zh/en，默认 ANALYZE_LANG→zh）/ language of report & logs (default ANALYZE_LANG→zh)",
    )
    return parser


def _enabled_sources(config: dict[str, Any]) -> list[str]:
    return [name for name, conf in config.get("sources", {}).items() if conf.get("enabled", True)]


def _source_has_data(name: str) -> bool:
    """某来源目录下是否存在任何帖子 JSON。"""
    source_dir = DATA_DIR / name
    return source_dir.is_dir() and any(source_dir.rglob("*.json"))


def _has_data(config: dict[str, Any]) -> bool:
    """配置的 enabled 来源下是否存在任何帖子 JSON。"""
    return any(_source_has_data(name) for name in _enabled_sources(config))


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


def _prefer_lang(paths: list[Path], lang: str) -> list[Path]:
    """把同语言的报告文件排到列表末尾（"最新"优先语言一致）。"""
    suffix = f".{lang}"
    return [p for p in paths if not p.stem.endswith(suffix)] + [p for p in paths if p.stem.endswith(suffix)]


def _show_no_new(config: dict[str, Any], lang: str = "zh") -> None:
    # 提示最近一份报告：优先最新每日归档（YYYY-MM-DD[.en]，语言优先），其次全量总览
    stem_re = re.compile(rf"^\d{{4}}-\d{{2}}-\d{{2}}(\.{'|'.join(LANGS)})?$")
    dailies = sorted(
        (p for p in REPORT_DIR.glob("*.md") if stem_re.fullmatch(p.stem)),
        key=lambda p: p.stem,
    )
    dailies = _prefer_lang(dailies, lang)
    full = REPORT_DIR / f"analysis{'.en' if lang == 'en' else ''}.md"
    if not full.exists():
        full = REPORT_DIR / ("analysis.md" if lang == "en" else "analysis.en.md")
    target = dailies[-1] if dailies else (full if full.exists() else None)
    if target is not None:
        print(_t(lang, "no_new_latest", path=target.resolve()))
        return
    if _has_data(config):
        print(_t(lang, "no_new_plain"))
    else:
        print(_t(lang, "no_posts"))
        print(_t(lang, "no_posts_hint"))


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except KeyboardInterrupt:
        # 优雅退出：os._exit 绕过解释器对非守护工作线程的 join，立即结束；
        # 数据均原子写，已爬取/分析内容不丢，下次运行自动继续。
        print(_t(_LANG, "interrupted"), file=sys.stderr, flush=True)
        os._exit(130)


def _main(argv: list[str] | None = None) -> int:
    global _LANG
    args = build_parser().parse_args(argv)
    _LANG = resolve_lang(args.lang)
    check_env()  # 校验 OPENAI_API_KEY，缺失即退出（提示按 _LANG）
    config = load_config()
    _LLM.update(resolve_llm_config(config, _LANG))

    # 自动爬取：某来源数据为空时重置其状态，让增量爬取退化为全量；否则只抓新增。
    # 记录 freshly_full —— 该来源刚被全量爬取，last_crawl 已被更新为当前时刻，
    # 若仍以其为 since，刚爬下来的帖子（created 均早于此刻）会被全部过滤掉。
    state = load_state()
    freshly_full: set[str] = set()
    for name in _enabled_sources(config):
        if not _source_has_data(name):
            freshly_full.add(name)
            state.pop(name, None)
    if freshly_full:
        save_state(state)
        print(_t(_LANG, "first_run_full"))
    run_crawl(config, today=True, lang=_LANG)

    # 加载待分析帖子
    state = load_state()
    since_by_source: dict[str, int | None] = {}
    for name in _enabled_sources(config):
        if args.full or name in freshly_full:
            since_by_source[name] = None
        else:
            since_by_source[name] = state.get(name, {}).get("last_analysis") or state.get(name, {}).get("last_crawl")
    incremental = not args.full
    topics, source_nodes = _load_topics(config, since_by_source)

    if not topics:
        _show_no_new(config, _LANG)
        return 0

    summary = ", ".join(f"{name}({', '.join(sorted(nodes))})" for name, nodes in source_nodes.items())
    print(_t(_LANG, "posts_to_analyze", n=len(topics), summary=summary))
    merged = analyze(topics, incremental=incremental, language=_LANG)

    day = time.strftime("%Y-%m-%d")
    title = day if incremental else _t(_LANG, "full_title", day=day)
    report = build_report(merged, len(topics), summary, title, _LANG)
    write_report(report, incremental=incremental, lang=_LANG)

    now = int(time.time())
    for name in source_nodes:
        state.setdefault(name, {})["last_analysis"] = now
    save_state(state)

    print("\n" + report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
