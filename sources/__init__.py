"""来源注册表。新增社区在此注册：实现类 + 一行登记。"""

from __future__ import annotations

from .base import Source, SourceError, http_get_json
from .devto import DevtoSource
from .hackernews import HNSource
from .lobsters import LobstersSource
from .producthunt import ProductHuntSource
from .sspai import SSPaiSource
from .v2ex import V2EXSource

__all__ = ["SOURCES", "Source", "SourceError", "http_get_json"]

SOURCES: dict[str, type[Source]] = {
    "v2ex": V2EXSource,
    "hackernews": HNSource,
    "lobsters": LobstersSource,
    "devto": DevtoSource,
    "sspai": SSPaiSource,
    "producthunt": ProductHuntSource,
}
