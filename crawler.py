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
import sys
import time
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


def get_sources(source_name: str | None, config: dict[str, Any]) -> list[Source]:
    """按 config 的 enabled 过滤来源；指定 source_name 时只保留该来源。"""
    sources: list[Source] = []
    for name, cls in SOURCES.items():
        if source_name and name != source_name:
            continue
        conf = config.get("sources", {}).get(name, {})
        if not conf.get("enabled", True):
            continue
        sources.append(
            cls(
                request_delay=float(conf.get("request_delay", 1.2)),
                max_retries=int(conf.get("max_retries", 3)),
            )
        )
    if not sources:
        raise SystemExit("没有可用来源，请检查 config.json 的 sources 节（enabled）。")
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
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump([p.to_dict() for p in result], f, ensure_ascii=False)
    return result


def save_topic(target: Path, post: Post) -> None:
    """按 4.1 统一结构写帖子 JSON。"""
    with open(target, "w", encoding="utf-8") as f:
        json.dump(post.to_dict(), f, ensure_ascii=False, indent=2)


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
            print(f"[{i}/{len(posts)}] {post.id} - {post.title}")
    return new_count


# ---------- CLI ----------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crawler.py",
        description="拾贝爬虫：抓取社区帖子存为本地 JSON（多来源）。",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="crawl",
        choices=["crawl", "list"],
        help="crawl=爬取（默认），list=列出节点",
    )
    parser.add_argument("--source", default=None, help="只处理指定来源（如 v2ex）")
    parser.add_argument("--today", action="store_true", help="增量爬取（只爬上次之后的帖子）")
    parser.add_argument("keyword", nargs="?", default=None, help="list 模式的节点关键词过滤")
    return parser


def cmd_list(args: argparse.Namespace, config: dict[str, Any]) -> int:
    for source in get_sources(args.source, config):
        print(f"\n== {source.display_name} ==")
        nodes = source.list_nodes()
        if not nodes:
            print("  (无节点数据)")
            continue
        for n in nodes:
            name, title = n.get("name", ""), n.get("title", "")
            if args.keyword and args.keyword.lower() not in f"{name} {title}".lower():
                continue
            print(f"  {name:<28} {title}")
    return 0


def run_crawl(config: dict[str, Any], source_name: str | None = None, today: bool = False) -> int:
    """爬取全部 enabled 来源（或指定来源），返回新增帖数。供 CLI 与 analyzer 复用。

    today=True 时按 state 的 last_crawl 增量爬取，并更新 last_crawl；
    today=False 时全量爬取、不更新时间戳。
    """
    state = load_state()
    total_new = 0
    for source in get_sources(source_name, config):
        conf = config.get("sources", {}).get(source.name, {})
        nodes = list(conf.get("nodes", []))
        pages = int(conf.get("pages_per_node", 3))
        since = state.get(source.name, {}).get("last_crawl") if today else None

        try:
            new = crawl(source, nodes, pages, since=since)
        except Exception as e:  # 单来源失败不影响其他来源
            print(f"[!] 来源 {source.display_name} 爬取失败: {e}", file=sys.stderr)
            continue

        if today:
            state.setdefault(source.name, {})["last_crawl"] = int(time.time())
            save_state(state)
        total_new += new
        print(f"[{source.display_name}] 新增 {new} 帖")
    return total_new


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config()

    if args.command == "list":
        return cmd_list(args, config)

    total_new = run_crawl(config, source_name=args.source, today=args.today)
    print(f"完成，共新增 {total_new} 帖")
    return 0


if __name__ == "__main__":
    sys.exit(main())
