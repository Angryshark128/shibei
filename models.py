"""统一帖子数据结构：来源无关的帖子/回复模型。

所有来源抓取的数据最终归一为 Post，作为爬虫输出与分析输入的契约（见 docs/design.md 4.1）。
仅用标准库 dataclass，零第三方依赖。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 每帖最多保存 / 分析的回复条数（控制文件大小与后续分析 token）
MAX_REPLIES = 10


@dataclass
class Reply:
    """一条回复。"""

    id: str
    author: str
    content: str
    created: int

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "author": self.author,
            "content": self.content,
            "created": self.created,
        }


@dataclass
class Post:
    """一篇帖子（来源无关）。"""

    id: str
    source: str
    node: str
    title: str
    content: str
    author: str
    created: int
    replies_count: int
    url: str
    reply_list: list[Reply] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "node": self.node,
            "title": self.title,
            "content": self.content,
            "author": self.author,
            "created": self.created,
            "replies_count": self.replies_count,
            "url": self.url,
            "reply_list": [r.to_dict() for r in self.reply_list],
        }


def post_from_dict(d: dict) -> Post:
    """从统一结构的 JSON dict 还原为 Post（加载缓存 / 分析输入）。"""
    return Post(
        id=str(d.get("id") or ""),
        source=str(d.get("source") or ""),
        node=str(d.get("node") or ""),
        title=str(d.get("title") or ""),
        content=str(d.get("content") or ""),
        author=str(d.get("author") or ""),
        created=int(d.get("created", 0) or 0),
        replies_count=int(d.get("replies_count", 0) or 0),
        url=str(d.get("url") or ""),
        reply_list=[
            Reply(
                id=str(r.get("id") or ""),
                author=str(r.get("author") or ""),
                content=str(r.get("content") or ""),
                created=int(r.get("created", 0) or 0),
            )
            for r in d.get("reply_list", [])
        ],
    )
