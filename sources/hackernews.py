"""Hacker News 来源实现。

HN Firebase API 无需认证；列表端点只返回 ID 数组，需二次请求详情：
- 列表   /v0/{showstories,askstories,topstories,newstories}.json
- 详情   /v0/item/{id}.json（story / comment 通用）

story 的 text 与 comment 的 text 含 HTML，统一经 strip_html 去标签后入库。
"""

from __future__ import annotations

from collections import deque

from models import MAX_REPLIES, Post, Reply

from .base import Source, http_get_json, strip_html

API_BASE = "https://hacker-news.firebaseio.com/v0"
PAGE_SIZE = 30

NODE_MAP = {
    "show": "showstories",
    "ask": "askstories",
    "top": "topstories",
    "new": "newstories",
}
NODE_TITLES = {"show": "Show HN", "ask": "Ask HN", "top": "Top", "new": "New"}


class HNSource(Source):
    name = "hackernews"
    display_name = "Hacker News"

    def fetch_topics(self, node: str, page: int) -> list[Post]:
        story_key = NODE_MAP.get(node, "topstories")
        ids = http_get_json(f"{API_BASE}/{story_key}.json", retries=self.max_retries)
        if not isinstance(ids, list):
            return []

        start = (page - 1) * PAGE_SIZE
        page_ids = ids[start : start + PAGE_SIZE]

        posts: list[Post] = []
        for item_id in page_ids:
            # 单帖详情价值低：失败快速跳过，不重试拖垮整页列表（黑洞防护）
            item = http_get_json(f"{API_BASE}/item/{item_id}.json", retries=1)
            if (
                isinstance(item, dict)
                and item.get("type") == "story"
                and not item.get("deleted")
                and not item.get("dead")
            ):
                posts.append(self._normalize_topic(item, node))
        return posts

    # 单帖最多拉取的评论 item 数：HN 热帖评论树可达上千，超过即放弃剩余，
    # 避免逐条串行重试把单帖拖成小时级黑洞（2026-09 故障记录）
    MAX_COMMENT_FETCH = 25

    def fetch_replies(self, topic_id: str) -> list[Reply]:
        item = http_get_json(f"{API_BASE}/item/{topic_id}.json", retries=1)
        if not isinstance(item, dict):
            return []
        return self._flatten_comments(item.get("kids") or [])[:MAX_REPLIES]

    def list_nodes(self) -> list[dict[str, str]]:
        return [{"name": n, "title": NODE_TITLES.get(n, n)} for n in NODE_MAP]

    def _flatten_comments(self, kids: list[int]) -> list[Reply]:
        """BFS 展平评论树，取前 MAX_REPLIES 条有效评论；deleted/dead 跳过。

        单条失败即跳过、至多请求 MAX_COMMENT_FETCH 个评论 item——HN 热帖评论树可达上千，
        逐条串行加重试会把单帖拖成小时级黑洞；分析只需前几条代表性评论。
        """
        replies: list[Reply] = []
        queue = deque(kids)
        fetched = 0
        while queue and len(replies) < MAX_REPLIES and fetched < self.MAX_COMMENT_FETCH:
            cid = queue.popleft()
            fetched += 1
            item = http_get_json(f"{API_BASE}/item/{cid}.json", retries=1)
            if not isinstance(item, dict) or item.get("type") != "comment" or item.get("deleted") or item.get("dead"):
                continue
            replies.append(
                Reply(
                    id=str(item.get("id", "")),
                    author=str(item.get("by", "") or ""),
                    content=strip_html(str(item.get("text", "") or "")),
                    created=int(item.get("time", 0) or 0),
                )
            )
            queue.extend(item.get("kids") or [])
        return replies

    def _normalize_topic(self, item: dict, node: str) -> Post:
        return Post(
            id=str(item.get("id", "")),
            source=self.name,
            node=node,
            title=str(item.get("title", "") or ""),
            content=strip_html(str(item.get("text", "") or "")),
            author=str(item.get("by", "") or ""),
            created=int(item.get("time", 0) or 0),
            replies_count=int(item.get("descendants", 0) or 0),
            url=f"https://news.ycombinator.com/item?id={item.get('id', '')}",
        )
