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
) -> Any:
    """GET 一个 JSON 端点，带指数退避重试。

    行为：
    - HTTP 404/403 直接返回 []（帖子被删或权限不足，不重试）。
    - 其他错误按 delay * 2^attempt 退避，上限 MAX_BACKOFF。
    - 全部失败返回 []，不抛异常，不中断流程。
    """
    headers = {"User-Agent": user_agent, "Accept": "application/json"}
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
