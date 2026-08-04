"""Product Hunt 来源实现。

官方 GraphQL API 需 OAuth，改用 RSS feed（每日新发布产品列表），零认证：
- feed  https://www.producthunt.com/feed

无评论接口，fetch_replies 返回空；RSS 无分页，page>1 返回空。
"""

from __future__ import annotations

from models import Post, Reply

from .base import Source, http_get_xml, iso_to_unix, parse_atom_feed, strip_html

API_BASE = "https://www.producthunt.com"


class ProductHuntSource(Source):
    name = "producthunt"
    display_name = "Product Hunt"

    def fetch_topics(self, node: str, page: int) -> list[Post]:
        if page > 1:
            return []
        xml = http_get_xml(f"{API_BASE}/feed", retries=self.max_retries)
        if not xml:
            return []
        return [self._normalize_entry(e, node) for e in self._parse(xml)]

    def fetch_replies(self, topic_id: str) -> list[Reply]:
        return []

    def _parse(self, xml: str) -> list[dict]:
        try:
            return parse_atom_feed(xml)
        except Exception:
            return []

    def _normalize_entry(self, e: dict, node: str) -> Post:
        url = str(e.get("url", "") or "")
        return Post(
            id=self._extract_id(url),
            source=self.name,
            node=node or "today",
            title=str(e.get("title", "") or ""),
            content=strip_html(str(e.get("content", "") or "")),
            author=str(e.get("author", "") or ""),
            created=iso_to_unix(str(e.get("published", "") or "")),
            replies_count=0,
            url=url,
        )

    @staticmethod
    def _extract_id(url: str) -> str:
        """从 URL 路径末段提取短标识（如 https://www.producthunt.com/posts/slug → slug）。"""
        return url.rstrip("/").rsplit("/", 1)[-1] if url else ""
