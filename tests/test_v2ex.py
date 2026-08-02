from sources.v2ex import V2EXSource

TOPIC_RAW = {
    "id": 1229217,
    "title": "Hello",
    "url": "https://www.v2ex.com/t/1229217",
    "content": "正文",
    "replies": 5,
    "created": 1784774167,
    "member": {"id": 1, "username": "alice"},
    "node": {"id": 90, "name": "python", "title": "Python"},
}

REPLY_RAW = {
    "id": 123456,
    "content": "回复内容",
    "created": 1784775000,
    "member": {"id": 2, "username": "bob"},
}


def _mock(monkeypatch, result):
    monkeypatch.setattr("sources.v2ex.http_get_json", lambda url, **kw: result)


def test_normalize_topic(monkeypatch):
    _mock(monkeypatch, [TOPIC_RAW])
    posts = V2EXSource().fetch_topics("python", 1)
    assert len(posts) == 1
    p = posts[0]
    assert p.id == "1229217"
    assert p.source == "v2ex"
    assert p.node == "python"
    assert p.author == "alice"
    assert p.replies_count == 5
    assert p.created == 1784774167
    assert p.url == "https://www.v2ex.com/t/1229217"
    assert p.title == "Hello"


def test_normalize_topic_missing_fields(monkeypatch):
    _mock(monkeypatch, [{"id": 1}])
    p = V2EXSource().fetch_topics("python", 1)[0]
    assert p.id == "1"
    assert p.author == ""
    assert p.node == ""
    assert p.title == ""
    assert p.created == 0
    assert p.replies_count == 0


def test_fetch_topics_not_list(monkeypatch):
    _mock(monkeypatch, {"id": 1})
    assert V2EXSource().fetch_topics("python", 1) == []


def test_fetch_topics_empty(monkeypatch):
    _mock(monkeypatch, [])
    assert V2EXSource().fetch_topics("python", 1) == []


def test_normalize_reply(monkeypatch):
    _mock(monkeypatch, [REPLY_RAW])
    replies = V2EXSource().fetch_replies("1229217")
    assert len(replies) == 1
    r = replies[0]
    assert r.id == "123456"
    assert r.author == "bob"
    assert r.content == "回复内容"
    assert r.created == 1784775000


def test_list_nodes(monkeypatch):
    _mock(monkeypatch, [{"name": "python", "title": "Python"}, {"name": "go", "title": "Go"}])
    assert V2EXSource().list_nodes() == [
        {"name": "python", "title": "Python"},
        {"name": "go", "title": "Go"},
    ]


def test_retries_passed_to_http(monkeypatch):
    captured = {}

    def fake_get(url, **kw):
        captured.update(kw)
        return []

    monkeypatch.setattr("sources.v2ex.http_get_json", fake_get)
    s = V2EXSource(request_delay=0.5, max_retries=7)
    s.fetch_topics("python", 1)
    assert captured["retries"] == 7
