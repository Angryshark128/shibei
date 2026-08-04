from sources.producthunt import ProductHuntSource

ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Product Hunt Daily</title>
  <entry>
    <title>Product One</title>
    <link href="https://www.producthunt.com/posts/one"/>
    <summary>&lt;p&gt;Product summary&lt;/p&gt;</summary>
    <published>2026-08-03T00:00:00Z</published>
    <id>https://www.producthunt.com/posts/one</id>
  </entry>
</feed>
"""


def _mock_xml(monkeypatch, xml):
    monkeypatch.setattr("sources.producthunt.http_get_xml", lambda url, **kw: xml)


def test_fetch_topics_parses_atom(monkeypatch):
    _mock_xml(monkeypatch, ATOM_XML)
    posts = ProductHuntSource().fetch_topics("today", 1)
    assert len(posts) == 1
    p = posts[0]
    assert p.id == "one"  # URL 末段
    assert p.source == "producthunt"
    assert p.node == "today"
    assert p.title == "Product One"
    assert p.content == "Product summary"  # HTML 去标签
    assert p.created == 1785715200  # 2026-08-03T00:00:00Z
    assert p.replies_count == 0
    assert p.url == "https://www.producthunt.com/posts/one"


def test_fetch_topics_page_gt_1_empty(monkeypatch):
    _mock_xml(monkeypatch, ATOM_XML)
    assert ProductHuntSource().fetch_topics("today", 2) == []


def test_fetch_topics_xml_none(monkeypatch):
    _mock_xml(monkeypatch, None)
    assert ProductHuntSource().fetch_topics("today", 1) == []


def test_fetch_topics_malformed_xml(monkeypatch):
    _mock_xml(monkeypatch, "<feed><entry>")
    assert ProductHuntSource().fetch_topics("today", 1) == []


def test_fetch_replies_empty():
    assert ProductHuntSource().fetch_replies("one") == []
