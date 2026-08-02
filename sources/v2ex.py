"""V2EX 来源实现。

V2EX v1 API 无需认证：
- 帖子列表 topics/show.json?node_name={node}&p={page}
- 回复     replies/show.json?topic_id={topic_id}
- 节点     nodes/all.json
"""

from __future__ import annotations

from models import Post, Reply

from .base import Source, http_get_json

API_BASE = "https://www.v2ex.com/api"


class V2EXSource(Source):
    name = "v2ex"
    display_name = "V2EX"

    def fetch_topics(self, node: str, page: int) -> list[Post]:
        url = f"{API_BASE}/topics/show.json?node_name={node}&p={page}"
        raw = http_get_json(url, retries=self.max_retries)
        if not isinstance(raw, list):
            return []
        return [self._normalize_topic(t) for t in raw if isinstance(t, dict)]

    def fetch_replies(self, topic_id: str) -> list[Reply]:
        url = f"{API_BASE}/replies/show.json?topic_id={topic_id}"
        raw = http_get_json(url, retries=self.max_retries)
        if not isinstance(raw, list):
            return []
        return [self._normalize_reply(r) for r in raw if isinstance(r, dict)]

    def list_nodes(self) -> list[dict[str, str]]:
        raw = http_get_json(f"{API_BASE}/nodes/all.json", retries=self.max_retries)
        if not isinstance(raw, list):
            return []
        return [{"name": str(n.get("name", "")), "title": str(n.get("title", ""))} for n in raw if isinstance(n, dict)]

    def _normalize_topic(self, t: dict) -> Post:
        member = t.get("member")
        node = t.get("node")
        return Post(
            id=str(t.get("id", "")),
            source=self.name,
            node=node.get("name", "") if isinstance(node, dict) else "",
            title=str(t.get("title", "") or ""),
            content=str(t.get("content", "") or ""),
            author=(member.get("username") or "") if isinstance(member, dict) else "",
            created=int(t.get("created", 0) or 0),
            replies_count=int(t.get("replies", 0) or 0),
            url=str(t.get("url", "") or ""),
        )

    def _normalize_reply(self, r: dict) -> Reply:
        member = r.get("member")
        return Reply(
            id=str(r.get("id", "")),
            author=(member.get("username") or "") if isinstance(member, dict) else "",
            content=str(r.get("content", "") or ""),
            created=int(r.get("created", 0) or 0),
        )
