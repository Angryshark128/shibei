from sources.sspai import SSPaiSource

# 实际 feed 为 RSS 2.0（尽管声明 atom 命名空间）
RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>少数派</title>
  <item>
    <title>派评 | 近期值得关注的 App</title>
    <link>https://sspai.com/post/113040</link>
    <description>&gt;实用、好用的正版软件，少数派为你呈现</description>
    <author>少数派编辑部</author>
    <pubDate>Mon, 03 Aug 2026 18:09:00 +0800</pubDate>
  </item>
</channel>
</rss>
"""

MALFORMED_XML = "<rss><channel><item>"


def _mock_xml(monkeypatch, xml):
    monkeypatch.setattr("sources.sspai.http_get_xml", lambda url, **kw: xml)


def test_fetch_topics_parses_rss2(monkeypatch):
    _mock_xml(monkeypatch, RSS_XML)
    posts = SSPaiSource().fetch_topics("all", 1)
    assert len(posts) == 1
    p = posts[0]
    assert p.id == "113040"  # URL 末段
    assert p.source == "sspai"
    assert p.node == "all"
    assert p.title == "派评 | 近期值得关注的 App"
    assert p.content == ">实用、好用的正版软件，少数派为你呈现"
    assert p.author == "少数派编辑部"
    assert p.created == 1785751740  # Mon, 03 Aug 2026 18:09:00 +0800 (RFC 2822)
    assert p.replies_count == 0
    assert p.url == "https://sspai.com/post/113040"


def test_fetch_topics_page_gt_1_empty(monkeypatch):
    _mock_xml(monkeypatch, RSS_XML)
    assert SSPaiSource().fetch_topics("all", 2) == []


def test_fetch_topics_xml_none(monkeypatch):
    _mock_xml(monkeypatch, None)
    assert SSPaiSource().fetch_topics("all", 1) == []


def test_fetch_topics_malformed_xml(monkeypatch):
    _mock_xml(monkeypatch, MALFORMED_XML)
    assert SSPaiSource().fetch_topics("all", 1) == []


def test_fetch_replies_empty(monkeypatch):
    assert SSPaiSource().fetch_replies("113040") == []
