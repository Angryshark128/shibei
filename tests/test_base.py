import urllib.error
from datetime import datetime, timedelta, timezone
from email.message import Message

from sources import SOURCES
from sources.base import (
    http_get_json,
    http_get_xml,
    iso_to_unix,
    parse_atom_feed,
    strip_html,
)


class FakeResp:
    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_urlopen(data: bytes = b"[]", exc: Exception | None = None, captured=None):
    def fake(req, timeout=30):
        if captured is not None:
            captured["req"] = req
        if exc is not None:
            raise exc
        return FakeResp(data)

    return fake


# ---------- strip_html ----------


def test_strip_html_basic():
    assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_strip_html_entities():
    assert strip_html("<p>A &amp; B &lt; C</p>") == "A & B < C"


def test_strip_html_plain():
    assert strip_html("plain text") == "plain text"


def test_strip_html_empty():
    assert strip_html("") == ""


# ---------- iso_to_unix ----------


def test_iso_to_unix_z_suffix():
    expected = int(datetime(2026, 7, 29, 19, 14, 47, tzinfo=timezone.utc).timestamp())
    assert iso_to_unix("2026-07-29T19:14:47Z") == expected


def test_iso_to_unix_offset_fractional():
    expected = int(datetime(2026, 8, 3, 2, 10, 50, 103000, tzinfo=timezone(timedelta(hours=-5))).timestamp())
    assert iso_to_unix("2026-08-03T02:10:50.103-05:00") == expected


def test_iso_to_unix_rfc2822():
    expected = int(datetime(2026, 8, 3, 18, 9, 0, tzinfo=timezone(timedelta(hours=8))).timestamp())
    assert iso_to_unix("Mon, 03 Aug 2026 18:09:00 +0800") == expected


def test_iso_to_unix_invalid():
    assert iso_to_unix("") == 0
    assert iso_to_unix("not-a-date") == 0
    assert iso_to_unix(None) == 0  # type: ignore[arg-type]


# ---------- parse_atom_feed ----------


ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Test</title>
  <entry>
    <title>Hello</title>
    <link href="https://example.com/posts/abc"/>
    <author><name>alice</name></author>
    <summary>Summary text</summary>
    <published>2026-07-29T19:14:47Z</published>
    <id>https://example.com/posts/abc</id>
  </entry>
</feed>
"""


def test_parse_atom_feed():
    items = parse_atom_feed(ATOM_XML)
    assert items == [
        {
            "title": "Hello",
            "url": "https://example.com/posts/abc",
            "author": "alice",
            "content": "Summary text",
            "published": "2026-07-29T19:14:47Z",
            "id": "https://example.com/posts/abc",
        }
    ]


RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Test</title>
    <item>
      <title>Post One</title>
      <link>https://example.com/post/1</link>
      <author>作者</author>
      <description>&lt;p&gt;正文内容&lt;/p&gt;</description>
      <pubDate>Mon, 03 Aug 2026 18:09:00 +0800</pubDate>
      <guid>https://example.com/post/1</guid>
    </item>
  </channel>
</rss>
"""


def test_parse_atom_feed_rss2():
    items = parse_atom_feed(RSS_XML)
    assert items == [
        {
            "title": "Post One",
            "url": "https://example.com/post/1",
            "author": "作者",
            "content": "<p>正文内容</p>",
            "published": "Mon, 03 Aug 2026 18:09:00 +0800",
            "id": "https://example.com/post/1",
        }
    ]


# ---------- http_get_json ----------


def test_http_get_json_extra_headers(monkeypatch):
    captured = {}
    monkeypatch.setattr("sources.base.urllib.request.urlopen", _fake_urlopen(b'{"ok": 1}', captured=captured))
    result = http_get_json("http://x", extra_headers={"Accept": "application/vnd.forem.api-v1+json"})
    assert result == {"ok": 1}
    req = captured["req"]
    lower = {k.lower(): v for k, v in req.headers.items()}
    assert lower["accept"] == "application/vnd.forem.api-v1+json"
    assert lower["user-agent"] == "ShiBei-Crawler/1.0"


def test_http_get_json_404_returns_empty(monkeypatch):
    exc = urllib.error.HTTPError("http://x", 404, "Not Found", Message(), None)
    monkeypatch.setattr("sources.base.urllib.request.urlopen", _fake_urlopen(exc=exc))
    assert http_get_json("http://x") == []


def test_http_get_json_retries_then_empty(monkeypatch):
    calls = {"n": 0}

    def always_fail(req, timeout=30):
        calls["n"] += 1
        raise OSError("boom")

    monkeypatch.setattr("sources.base.urllib.request.urlopen", always_fail)
    monkeypatch.setattr("sources.base.time.sleep", lambda _s: None)
    assert http_get_json("http://x", retries=3) == []
    assert calls["n"] == 4  # 初始 + 3 次重试


# ---------- http_get_xml ----------


def test_http_get_xml_success(monkeypatch):
    monkeypatch.setattr("sources.base.urllib.request.urlopen", _fake_urlopen(b"<rss/>"))
    assert http_get_xml("http://x") == "<rss/>"


def test_http_get_xml_retries_then_success(monkeypatch):
    calls = {"n": 0}

    def flaky(req, timeout=30):
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("boom")
        return FakeResp(b"<rss/>")

    monkeypatch.setattr("sources.base.urllib.request.urlopen", flaky)
    monkeypatch.setattr("sources.base.time.sleep", lambda _s: None)
    assert http_get_xml("http://x") == "<rss/>"
    assert calls["n"] == 3


def test_http_get_xml_all_fail_returns_none(monkeypatch):
    def always_fail(req, timeout=30):
        raise OSError("boom")

    monkeypatch.setattr("sources.base.urllib.request.urlopen", always_fail)
    monkeypatch.setattr("sources.base.time.sleep", lambda _s: None)
    assert http_get_xml("http://x", retries=2) is None


# ---------- 来源注册表 ----------


def test_source_registry():
    assert set(SOURCES) == {
        "v2ex",
        "hackernews",
        "lobsters",
        "devto",
        "sspai",
        "producthunt",
    }
