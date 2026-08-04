"""Dev.to (Forem) 来源实现。

读取端点无需 API Key，但需自定义 Accept header（见 DEVTO_HEADERS）：
- 文章列表 /api/articles?page={p}&per_page=30[&tag={tag}]
- 评论     /api/comments?a_id={article_id}（含嵌套 children）
- 标签     /api/tags

content 优先取 description（摘要）；评论 body_html 经 strip_html 去标签。
"""

from __future__ import annotations

from models import MAX_REPLIES, Post, Reply

from .base import Source, http_get_json, iso_to_unix, strip_html

API_BASE = "https://dev.to"
DEVTO_HEADERS = {"Accept": "application/vnd.forem.api-v1+json"}


class DevtoSource(Source):
    name = "devto"
    display_name = "Dev.to"

    def fetch_topics(self, node: str, page: int) -> list[Post]:
        params = f"page={page}&per_page=30"
        if node:
            params += f"&tag={node}"
        raw = http_get_json(
            f"{API_BASE}/api/articles?{params}",
            retries=self.max_retries,
            extra_headers=DEVTO_HEADERS,
        )
        if not isinstance(raw, list):
            return []
        return [self._normalize_topic(a, node) for a in raw if isinstance(a, dict)]

    def fetch_replies(self, topic_id: str) -> list[Reply]:
        raw = http_get_json(
            f"{API_BASE}/api/comments?a_id={topic_id}",
            retries=self.max_retries,
            extra_headers=DEVTO_HEADERS,
        )
        if not isinstance(raw, list):
            return []
        return self._flatten_comments(raw)[:MAX_REPLIES]

    def list_nodes(self) -> list[dict[str, str]]:
        raw = http_get_json(f"{API_BASE}/api/tags", retries=self.max_retries, extra_headers=DEVTO_HEADERS)
        if not isinstance(raw, list):
            return []
        return [
            {"name": str(t.get("name", "")), "title": str(t.get("name", "") or "")}
            for t in raw
            if isinstance(t, dict) and t.get("name")
        ]

    def _flatten_comments(self, comments: list[dict]) -> list[Reply]:
        """递归展平评论树（Dev.to 评论带 children），DFS 顺序取前 MAX_REPLIES 条。"""
        replies: list[Reply] = []
        for c in comments:
            if not isinstance(c, dict):
                continue
            user = c.get("user")
            replies.append(
                Reply(
                    id=str(c.get("id_code") or c.get("id") or ""),
                    author=(user.get("username", "") if isinstance(user, dict) else ""),
                    content=strip_html(str(c.get("body_html", "") or "")),
                    created=iso_to_unix(str(c.get("created_at", "") or "")),
                )
            )
            if len(replies) >= MAX_REPLIES:
                break
            replies.extend(self._flatten_comments(c.get("children") or []))
        return replies[:MAX_REPLIES]

    def _normalize_topic(self, a: dict, node: str) -> Post:
        user = a.get("user")
        tag_list = a.get("tag_list") or []
        return Post(
            id=str(a.get("id", "")),
            source=self.name,
            node=node or (tag_list[0] if tag_list else ""),
            title=str(a.get("title", "") or ""),
            content=str(a.get("description", "") or ""),
            author=(user.get("username", "") if isinstance(user, dict) else ""),
            created=iso_to_unix(str(a.get("created_at", "") or "")),
            replies_count=int(a.get("comments_count", 0) or 0),
            url=str(a.get("url", "") or ""),
        )
