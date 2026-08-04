from sources.lobsters import LobstersSource

STORY = {
    "short_id": "hfbqr3",
    "created_at": "2026-08-03T02:10:50.103-05:00",
    "title": "Don't be a meat proxy",
    "url": "https://gruhn.me/blog/2026-08-03/",
    "comment_count": 16,
    "description": "",
    "description_plain": "",
    "submitter_user": "antonmedv",
    "tags": ["practices", "vibecoding"],
}


def _mock(monkeypatch, result):
    monkeypatch.setattr("sources.lobsters.http_get_json", lambda url, **kw: result)


def test_normalize_topic_string_user_and_domain_fallback(monkeypatch):
    _mock(monkeypatch, [STORY])
    p = LobstersSource().fetch_topics("hottest", 1)[0]
    assert p.id == "hfbqr3"
    assert p.source == "lobsters"
    assert p.node == "hottest"  # 传入 node 优先
    assert p.author == "antonmedv"  # submitter_user 是字符串
    assert p.title == "Don't be a meat proxy"
    assert p.created == 1785741050  # 2026-08-03T02:10:50-05:00
    assert p.replies_count == 16
    assert p.content == "gruhn.me"  # description 为空 → url 域名摘要
    assert p.url == "https://gruhn.me/blog/2026-08-03/"


def test_normalize_topic_dict_user_defensive(monkeypatch):
    story = dict(STORY, submitter_user={"username": "dict_user"}, description_plain="描述")
    _mock(monkeypatch, [story])
    p = LobstersSource().fetch_topics("", 1)[0]
    assert p.author == "dict_user"
    assert p.content == "描述"  # description_plain 优先
    assert p.node == "practices"  # node 为空 → tags[0]


def test_fetch_topics_url_selection(monkeypatch):
    captured = {}

    def fake_get(url, **kw):
        captured["url"] = url
        return []

    monkeypatch.setattr("sources.lobsters.http_get_json", fake_get)

    LobstersSource().fetch_topics("programming", 1)
    assert captured["url"] == "https://lobste.rs/t/programming/page/1.json"

    LobstersSource().fetch_topics("hottest", 1)
    assert captured["url"] == "https://lobste.rs/hottest.json"

    LobstersSource().fetch_topics("", 1)
    assert captured["url"] == "https://lobste.rs/hottest.json"

    LobstersSource().fetch_topics("", 2)
    assert captured["url"] == "https://lobste.rs/page/2.json"


def test_fetch_topics_not_list(monkeypatch):
    _mock(monkeypatch, {"short_id": "x"})
    assert LobstersSource().fetch_topics("hottest", 1) == []


COMMENT = {
    "short_id": "2dsro8",
    "created_at": "2026-08-03T04:33:56.399-05:00",
    "comment": "<p>html only</p>",
    "comment_plain": "plain text",
    "commenting_user": "pepegar",
    "children": None,
}

DELETED = {
    "short_id": "dead1",
    "created_at": "2026-08-03T04:33:56.399-05:00",
    "comment": "gone",
    "comment_plain": "gone",
    "commenting_user": "u",
    "is_deleted": True,
    "children": None,
}


def test_fetch_replies_flat_comments(monkeypatch):
    _mock(monkeypatch, {"comments": [COMMENT, DELETED]})
    replies = LobstersSource().fetch_replies("hfbqr3")
    assert [r.id for r in replies] == ["2dsro8"]  # 已删除评论跳过
    r = replies[0]
    assert r.author == "pepegar"  # commenting_user 是字符串
    assert r.content == "plain text"  # comment_plain 优先
    assert r.created == 1785749636  # 2026-08-03T04:33:56-05:00


def test_fetch_replies_nested_children(monkeypatch):
    child = dict(COMMENT, short_id="child1", commenting_user="kid", comment_plain="child text", children=None)
    parent = dict(COMMENT, short_id="parent1", children=[child])
    _mock(monkeypatch, {"comments": [parent]})
    replies = LobstersSource().fetch_replies("x")
    assert [r.id for r in replies] == ["parent1", "child1"]


def test_fetch_replies_not_dict(monkeypatch):
    _mock(monkeypatch, [])
    assert LobstersSource().fetch_replies("x") == []


def test_list_nodes(monkeypatch):
    _mock(monkeypatch, [{"tag": "ruby", "description": "Ruby programming"}, "go"])
    assert LobstersSource().list_nodes() == [
        {"name": "ruby", "title": "Ruby programming"},
        {"name": "go", "title": "go"},
    ]


def test_retries_passed_to_http(monkeypatch):
    captured = {}

    def fake_get(url, **kw):
        captured.update(kw)
        return []

    monkeypatch.setattr("sources.lobsters.http_get_json", fake_get)
    LobstersSource(max_retries=5).fetch_topics("hottest", 1)
    assert captured["retries"] == 5
