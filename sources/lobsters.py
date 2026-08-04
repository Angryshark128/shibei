"""Lobste.rs 来源实现。

JSON API 无需认证（需 Accept: application/json，http_get_json 已自带）：
- 热门      /hottest.json
- 通用分页  /page/{page}.json
- 按标签    /t/{tag}/page/{page}.json
- 帖子详情  /s/{short_id}.json（含评论列表）
- 标签列表  /tags.json

注意（与直觉不同）：submitter_user / commenting_user 是字符串用户名而非对象；
评论为扁平列表（children 多为 null），按 depth/parent_comment 表达层级。
"""

from __future__ import annotations

from models import MAX_REPLIES, Post, Reply

from .base import Source, http_get_json, iso_to_unix, strip_html

API_BASE = "https://lobste.rs"


class LobstersSource(Source):
    name = "lobsters"
    display_name = "Lobste.rs"

    def fetch_topics(self, node: str, page: int) -> list[Post]:
        # node="hottest" 或空时走通用热门/分页；否则按标签
        if node and node != "hottest":
            url = f"{API_BASE}/t/{node}/page/{page}.json"
        elif page == 1:
            url = f"{API_BASE}/hottest.json"
        else:
            url = f"{API_BASE}/page/{page}.json"
        raw = http_get_json(url, retries=self.max_retries)
        if not isinstance(raw, list):
            return []
        return [self._normalize_topic(s, node) for s in raw if isinstance(s, dict)]

    def fetch_replies(self, topic_id: str) -> list[Reply]:
        raw = http_get_json(f"{API_BASE}/s/{topic_id}.json", retries=self.max_retries)
        if not isinstance(raw, dict):
            return []
        return self._flatten_comments(raw.get("comments") or [])[:MAX_REPLIES]

    def list_nodes(self) -> list[dict[str, str]]:
        raw = http_get_json(f"{API_BASE}/tags.json", retries=self.max_retries)
        if not isinstance(raw, list):
            return []
        nodes = []
        for t in raw:
            if isinstance(t, dict):
                tag = str(t.get("tag", ""))
                nodes.append({"name": tag, "title": str(t.get("description", "") or tag)})
            elif isinstance(t, str):
                nodes.append({"name": t, "title": t})
        return nodes

    def _flatten_comments(self, comments: list[dict]) -> list[Reply]:
        """递归展平评论列表（兼容扁平与 children 嵌套两种形态）。"""
        replies: list[Reply] = []
        for c in comments:
            if not isinstance(c, dict):
                continue
            children = c.get("children") or []
            if c.get("is_deleted") or c.get("is_moderated"):
                replies.extend(self._flatten_comments(children))
                continue
            user = c.get("commenting_user", "")
            replies.append(
                Reply(
                    id=str(c.get("short_id", "")),
                    author=user
                    if isinstance(user, str)
                    else (user.get("username", "") if isinstance(user, dict) else ""),
                    content=str(c.get("comment_plain", "") or "") or strip_html(str(c.get("comment", "") or "")),
                    created=iso_to_unix(str(c.get("created_at", "") or "")),
                )
            )
            replies.extend(self._flatten_comments(children))
        return replies

    def _normalize_topic(self, s: dict, node: str) -> Post:
        submitter = s.get("submitter_user", "")
        author = (
            submitter
            if isinstance(submitter, str)
            else (submitter.get("username", "") if isinstance(submitter, dict) else "")
        )
        tags = s.get("tags") or []
        content = str(s.get("description_plain", "") or "") or strip_html(str(s.get("description", "") or ""))
        if not content:
            content = self._domain_of(str(s.get("url", "") or ""))
        return Post(
            id=str(s.get("short_id", "")),
            source=self.name,
            node=node or (tags[0] if tags else ""),
            title=str(s.get("title", "") or ""),
            content=content,
            author=author,
            created=iso_to_unix(str(s.get("created_at", "") or "")),
            replies_count=int(s.get("comment_count", 0) or 0),
            url=str(s.get("url", "") or ""),
        )

    @staticmethod
    def _domain_of(url: str) -> str:
        """描述为空时用 url 域名作摘要。"""
        if "://" not in url:
            return ""
        parts = url.split("/")
        return parts[2] if len(parts) > 2 else ""
