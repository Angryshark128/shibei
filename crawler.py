#!/usr/bin/env python3
"""拾贝 · 爬虫主循环（来源无关）。

用法：
    python3 crawler.py                   # 全量爬取所有 enabled 来源
    python3 crawler.py --source v2ex     # 只爬指定来源
    python3 crawler.py --today           # 增量爬取（只爬上次之后的帖子）
    python3 crawler.py list [关键词]      # 列出节点
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from models import MAX_REPLIES, Post, Reply, post_from_dict
from sources import SOURCES, Source

DATA_DIR = Path("data")
CACHE_DIR = DATA_DIR / ".cache" / "topic_lists"
STATE_FILE = DATA_DIR / "state.json"
CONFIG_FILE = "config.json"

# 每页帖子数的保守估计，用于校验今日缓存是否覆盖足够
TOPICS_PER_PAGE = 5


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


# CLI 文案（按语言输出，让爬取日志随分析语言切换；默认中文）
_CRAWL_UI: dict[str, dict[str, str]] = {
    "zh": {
        "no_sources": "没有可用来源，请检查 config.json 的 sources 节（enabled）。",
        "crawl_failed": "[!] 来源 {name} 爬取失败: {err}",
        "new_posts": "[{name}] 新增 {n} 帖",
        "no_nodes": "  (无节点数据)",
        "interrupted": "\n[!] 已中断（Ctrl+C）。已爬取的数据均已保存，下次运行自动续传。",
        "done": "完成，共新增 {n} 帖",
    },
    "en": {
        "no_sources": "No available sources. Check the sources section (enabled) in config.json.",
        "crawl_failed": "[!] Source {name} crawl failed: {err}",
        "new_posts": "[{name}] {n} new posts",
        "no_nodes": "  (no node data)",
        "interrupted": "\n[!] Interrupted (Ctrl+C). Scraped data is saved; the next run resumes.",
        "done": "Done — {n} new posts in total",
    },
}


def _t(lang: str, key: str, **kw: Any) -> str:
    """按语言取 CLI 文案；未知语言回落 zh。"""
    table = _CRAWL_UI.get(lang) or _CRAWL_UI["zh"]
    return table.get(key, "").format(**kw)


def get_sources(source_name: str | None, config: dict[str, Any], lang: str = "zh") -> list[Source]:
    """按 config 的 enabled 过滤来源；指定 source_name 时只保留该来源。

    来源必须出现在 config 的 sources 节且 enabled 为真才启用（新来源需先加配置节，
    避免仅注册实现类就静默爬取）。source_name 指定了但不在已启用列表时返回空。
    """
    sources: list[Source] = []
    for name, cls in SOURCES.items():
        if source_name and name != source_name:
            continue
        conf = config.get("sources", {}).get(name)
        if not conf or not conf.get("enabled", True):
            continue
        sources.append(
            cls(
                request_delay=float(conf.get("request_delay", 1.2)),
                max_retries=int(conf.get("max_retries", 3)),
            )
        )
    if not sources:
        raise SystemExit(_t(lang, "no_sources"))
    return sources


# ---------- 抓取 ----------


def collect_topics(source: Source, node: str, pages: int) -> list[Post]:
    """按页抓取某节点帖子列表：今日缓存 + set 去重，返回统一 Post 列表（无 reply_list）。"""
    today = dt.date.today().isoformat()
    cache_file = CACHE_DIR / f"{source.name}_{node}_{today}.json"

    cached = load_json(cache_file)
    if isinstance(cached, list) and len(cached) >= pages * TOPICS_PER_PAGE:
        return [post_from_dict(d) for d in cached]

    seen: dict[str, Post] = {}
    for page in range(1, pages + 1):
        for p in source.fetch_topics(node, page):
            seen.setdefault(p.id, p)
        if page < pages:
            time.sleep(source.request_delay)

    result = list(seen.values())
    result.sort(key=lambda p: p.created, reverse=True)  # 新帖在前
    _write_json_atomic(cache_file, [p.to_dict() for p in result])
    return result


def _write_json_atomic(path: Path, obj: Any, indent: int | None = None) -> None:
    """原子写 JSON：先写临时文件再 os.replace，中断/崩溃不留半截文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)
    tmp.replace(path)


def save_topic(target: Path, post: Post) -> None:
    """按 4.1 统一结构写帖子 JSON（原子写，Ctrl+C 中断不产生损坏文件）。"""
    _write_json_atomic(target, post.to_dict(), indent=2)


def crawl(source: Source, nodes: list[str], pages: int, since: int | None = None) -> int:
    """抓取一个来源的指定节点，返回新增帖子数。

    since 传入时过滤 created >= since 的帖子；本地已存在的 JSON 直接跳过。
    """
    new_count = 0
    for node in nodes:
        out_dir = DATA_DIR / source.name / node
        out_dir.mkdir(parents=True, exist_ok=True)

        posts = collect_topics(source, node, pages)
        if since is not None:
            posts = [p for p in posts if p.created >= since]

        for i, post in enumerate(posts, 1):
            target = out_dir / f"{post.id}.json"
            if target.exists():
                continue
            replies: list[Reply] = source.fetch_replies(post.id)
            time.sleep(source.request_delay)
            post.reply_list = replies[:MAX_REPLIES]
            save_topic(target, post)
            new_count += 1
            print(f"[{source.name} {i}/{len(posts)}] {post.id} - {post.title}")
    return new_count


# ---------- CLI ----------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crawler.py",
        description=(
            "拾贝爬虫：抓取社区帖子存为本地 JSON（多来源）。\n"
            "Shibei crawler: scrape community posts to local JSON (multi-source)."
        ),
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="crawl",
        choices=["crawl", "list"],
        help="crawl=爬取（默认），list=列出节点 / crawl (default), list=list nodes",
    )
    parser.add_argument("--source", default=None, help="只处理指定来源（如 v2ex）/ only process one source")
    parser.add_argument("--today", action="store_true", help="增量爬取（只爬上次之后的帖子）/ incremental crawl")
    parser.add_argument(
        "--lang",
        choices=("zh", "en"),
        default="zh",
        help="日志语言（zh/en），默认 zh / log language, default zh",
    )
    parser.add_argument(
        "keyword", nargs="?", default=None, help="list 模式的节点关键词过滤 / filter node list by keyword"
    )
    return parser


def cmd_list(args: argparse.Namespace, config: dict[str, Any]) -> int:
    for source in get_sources(args.source, config, args.lang):
        print(f"\n== {source.display_name} ==")
        nodes = source.list_nodes()
        if not nodes:
            print(_t(args.lang, "no_nodes"))
            continue
        for n in nodes:
            name, title = n.get("name", ""), n.get("title", "")
            if args.keyword and args.keyword.lower() not in f"{name} {title}".lower():
                continue
            print(f"  {name:<28} {title}")
    return 0


def run_crawl(config: dict[str, Any], source_name: str | None = None, today: bool = False, lang: str = "zh") -> int:
    """爬取全部 enabled 来源（或指定来源），返回新增帖数。供 CLI 与 analyzer 复用。

    today=True 时按 state 的 last_crawl 增量爬取，并更新 last_crawl；
    today=False 时全量爬取、不更新时间戳。

    来源之间并行（ThreadPoolExecutor）：不同来源是独立端点、限流互不影响，
    request_delay 各自保护自己，串行纯属浪费。state 写入用锁保护防丢键。
    """
    sources = get_sources(source_name, config, lang)
    state = load_state()
    state_lock = threading.Lock()
    total_new = 0

    def _crawl_one(source: Source) -> int:
        conf = config.get("sources", {}).get(source.name, {})
        nodes = list(conf.get("nodes", []))
        pages = int(conf.get("pages_per_node", 3))
        since = state.get(source.name, {}).get("last_crawl") if today else None

        try:
            new = crawl(source, nodes, pages, since=since)
        except Exception as e:  # 单来源失败不影响其他来源
            print(_t(lang, "crawl_failed", name=source.display_name, err=e), file=sys.stderr)
            return 0

        if today:
            with state_lock:  # 共享 state 读写加锁，避免并行丢键
                state.setdefault(source.name, {})["last_crawl"] = int(time.time())
                save_state(state)
        print(_t(lang, "new_posts", name=source.display_name, n=new))
        return new

    pool = ThreadPoolExecutor(max_workers=len(sources))
    try:
        for n in pool.map(_crawl_one, sources):
            total_new += n
    except KeyboardInterrupt:
        # 中断：取消未开始任务，不等待进行中线程（进程退出即终止），已保存数据幂等
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown(wait=True)
    return total_new


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config()
    lang = args.lang

    try:
        if args.command == "list":
            return cmd_list(args, config)
        total_new = run_crawl(config, source_name=args.source, today=args.today, lang=lang)
    except KeyboardInterrupt:
        # 优雅退出：os._exit 绕过解释器对非守护工作线程的 join，立即结束；
        # 数据均原子写，已保存内容不丢，下次运行自动断点续传。
        print(_t(lang, "interrupted"), file=sys.stderr, flush=True)
        os._exit(130)
    print(_t(lang, "done", n=total_new))
    return 0


if __name__ == "__main__":
    sys.exit(main())
