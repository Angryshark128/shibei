"""来源抽象层：Source 抽象基类 + 通用 HTTP 助手。

新增社区来源 = 继承 Source 实现三个方法 + 在 sources/__init__.py 注册 + 加配置节。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from models import Post, Reply

DEFAULT_USER_AGENT = "ShiBei-Crawler/1.0"
DEFAULT_TIMEOUT = 30  # 秒
MAX_BACKOFF = 60  # 指数退避上限（秒）


class SourceError(Exception):
    """来源相关错误。"""


def http_get_json(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = 3,
    delay: float = 1.2,
    user_agent: str = DEFAULT_USER_AGENT,
    extra_headers: dict[str, str] | None = None,
) -> Any:
    """GET 一个 JSON 端点，带指数退避重试。

    行为：
    - HTTP 404/403 直接返回 []（帖子被删或权限不足，不重试）。
    - 其他错误按 delay * 2^attempt 退避，上限 MAX_BACKOFF。
    - 全部失败返回 []，不抛异常，不中断流程。
    - extra_headers 合并进请求头（可覆盖默认 Accept，如 Forem 的 v1 header）。
    """
    headers = {"User-Agent": user_agent, "Accept": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (404, 403):
                return []
        except (OSError, ValueError):
            pass
        if attempt < retries:
            time.sleep(min(delay * (2**attempt), MAX_BACKOFF))
    return []


def http_get_xml(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = 3,
    delay: float = 1.2,
    user_agent: str = DEFAULT_USER_AGENT,
) -> str | None:
    """GET 一个 XML/RSS 端点，返回原始文本；失败返回 None。

    与 http_get_json 同款退避重试，但不解析 JSON。
    """
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
    }
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            pass
        if attempt < retries:
            time.sleep(min(delay * (2**attempt), MAX_BACKOFF))
    return None


def _elem_text(el: Any) -> str:
    """取元素全部文本（含子元素与 CDATA），无则空串。"""
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


def parse_atom_feed(xml_text: str) -> list[dict]:
    """解析 Atom 或 RSS 2.0 feed，返回统一结构 [{title,url,author,content,published,id}, ...]。

    少数派 / Product Hunt 的「Atom」feed 实际是 RSS 2.0（带 atom 命名空间声明），
    故同时兼容两种格式，按根标签自动识别。
    """
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_text)
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    root_tag = root.tag.rsplit("}", 1)[-1]
    items: list[dict] = []

    if root_tag == "feed":  # Atom
        for entry in root.findall("atom:entry", ns):
            link = entry.find("atom:link", ns)
            items.append(
                {
                    "title": _elem_text(entry.find("atom:title", ns)),
                    "url": (link.get("href", "") if link is not None else "").strip(),
                    "author": _elem_text(entry.find("atom:author/atom:name", ns)),
                    "content": _elem_text(entry.find("atom:summary", ns)) or _elem_text(entry.find("atom:content", ns)),
                    "published": _elem_text(entry.find("atom:published", ns))
                    or _elem_text(entry.find("atom:updated", ns)),
                    "id": _elem_text(entry.find("atom:id", ns)),
                }
            )
    else:  # RSS 2.0
        for item in root.iter("item"):
            guid = item.find("guid")
            link = item.find("link")
            items.append(
                {
                    "title": _elem_text(item.find("title")),
                    "url": _elem_text(link) if link is not None else "",
                    "author": _elem_text(item.find("author")) or _elem_text(item.find("dc:creator", ns)),
                    "content": _elem_text(item.find("description")),
                    "published": _elem_text(item.find("pubDate")),
                    "id": (_elem_text(guid) if guid is not None else _elem_text(link) if link is not None else ""),
                }
            )
    return items


def strip_html(text: str) -> str:
    """用标准库去除 HTML 标签，返回纯文本（实体已解码）。"""
    from html.parser import HTMLParser

    class _Stripper(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self._parts: list[str] = []

        def handle_data(self, d: str) -> None:
            self._parts.append(d)

        def get_text(self) -> str:
            return "".join(self._parts)

    s = _Stripper()
    s.feed(text)
    return s.get_text()


def iso_to_unix(iso_str: str) -> int:
    """ISO 8601 / RFC 2822 时间字符串转 unix 秒级时间戳；解析失败返回 0。

    - ISO 8601（HN 外的社区 JSON API）：如 2026-07-29T19:14:47Z、2026-08-03T02:10:50.103-05:00
    - RFC 2822（RSS pubDate）：如 Mon, 03 Aug 2026 18:09:00 +0800
    """
    from datetime import datetime, timezone

    if not iso_str:
        return 0
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return int(dt.astimezone(timezone.utc).timestamp())
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(iso_str)
        if dt is None:
            return 0
        return int(dt.astimezone(timezone.utc).timestamp())
    except (TypeError, ValueError, OverflowError):
        return 0


class Source(ABC):
    """社区来源抽象基类。"""

    name: str = ""
    display_name: str = ""

    def __init__(self, *, request_delay: float = 1.2, max_retries: int = 3) -> None:
        self.request_delay = request_delay
        self.max_retries = max_retries

    @abstractmethod
    def fetch_topics(self, node: str, page: int) -> list[Post]:
        """抓取某节点第 page 页的帖子元数据（统一结构，不含 reply_list）。"""

    @abstractmethod
    def fetch_replies(self, topic_id: str) -> list[Reply]:
        """抓取某帖子的回复列表（统一结构）。"""

    def list_nodes(self) -> list[dict[str, str]]:
        """列出该来源全部可用节点，返回 [{"name": ..., "title": ...}]。"""
        return []
