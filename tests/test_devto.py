from sources.devto import DEVTO_HEADERS, DevtoSource

ARTICLE = {
    "id": 4265440,
    "title": "Amazon Bedrock Agents",
    "description": "Summary desc",
    "url": "https://dev.to/gde/amazon-1",
    "comments_count": 5,
    "created_at": "2026-07-29T19:14:47Z",
    "tag_list": ["webdev", "js"],
    "user": {"username": "xbill"},
}


def _mock(monkeypatch, result):
    monkeypatch.setattr("sources.devto.http_get_json", lambda url, **kw: result)


def test_normalize_topic(monkeypatch):
    _mock(monkeypatch, [ARTICLE])
    p = DevtoSource().fetch_topics("webdev", 1)[0]
    assert p.id == "4265440"
    assert p.source == "devto"
    assert p.node == "webdev"  # 传入 node 优先
    assert p.author == "xbill"
    assert p.title == "Amazon Bedrock Agents"
    assert p.content == "Summary desc"  # description 优先
    assert p.replies_count == 5
    assert p.created == 1785352487  # 2026-07-29T19:14:47Z
    assert p.url == "https://dev.to/gde/amazon-1"


def test_normalize_topic_node_from_tag_list(monkeypatch):
    _mock(monkeypatch, [ARTICLE])
    p = DevtoSource().fetch_topics("", 1)[0]
    assert p.node == "webdev"  # node 为空 → tag_list[0]


def test_fetch_topics_passes_forem_header(monkeypatch):
    captured = {}

    def fake_get(url, **kw):
        captured["url"] = url
        captured.update(kw)
        return []

    monkeypatch.setattr("sources.devto.http_get_json", fake_get)
    DevtoSource().fetch_topics("webdev", 2)
    assert captured["extra_headers"] == DEVTO_HEADERS
    assert captured["url"] == "https://dev.to/api/articles?page=2&per_page=30&tag=webdev"
    assert captured["retries"] == 3


def test_fetch_topics_not_list(monkeypatch):
    _mock(monkeypatch, {"id": 1})
    assert DevtoSource().fetch_topics("webdev", 1) == []


COMMENT = {
    "id_code": "c1",
    "created_at": "2026-08-03T06:42:00Z",
    "body_html": "<p><em>Great</em> post</p>",
    "user": {"username": "dmsmenula"},
    "children": None,
}

NESTED = {
    "id_code": "c0",
    "created_at": "2026-08-03T06:42:00Z",
    "body_html": "<p>parent</p>",
    "user": {"username": "parent"},
    "children": [
        {
            "id_code": "c1",
            "created_at": "2026-08-03T06:43:00Z",
            "body_html": "<p>child</p>",
            "user": {"username": "child"},
            "children": [],
        }
    ],
}


def test_fetch_replies_strips_html(monkeypatch):
    _mock(monkeypatch, [COMMENT])
    replies = DevtoSource().fetch_replies("4265440")
    assert len(replies) == 1
    r = replies[0]
    assert r.id == "c1"  # id_code
    assert r.author == "dmsmenula"
    assert r.content == "Great post"  # body_html 去标签
    assert r.created == 1785739320  # 2026-08-03T06:42:00Z


def test_fetch_replies_flatten_nested(monkeypatch):
    _mock(monkeypatch, [NESTED])
    replies = DevtoSource().fetch_replies("x")
    assert [r.id for r in replies] == ["c0", "c1"]


def test_fetch_replies_not_list(monkeypatch):
    _mock(monkeypatch, {"a": 1})
    assert DevtoSource().fetch_replies("x") == []


def test_list_nodes(monkeypatch):
    _mock(monkeypatch, [{"name": "webdev"}, {"name": "ruby"}])
    assert DevtoSource().list_nodes() == [
        {"name": "webdev", "title": "webdev"},
        {"name": "ruby", "title": "ruby"},
    ]
