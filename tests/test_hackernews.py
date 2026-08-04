from sources.hackernews import HNSource

STORY = {
    "id": 1,
    "type": "story",
    "by": "pg",
    "title": "Y Combinator",
    "text": None,
    "time": 1160418111,
    "descendants": 3,
    "kids": [100, 200],
}

ASK = {
    "id": 2,
    "type": "story",
    "by": "alice",
    "title": "Ask HN: X",
    "text": "<p>Ask <b>anything</b></p>",
    "time": 1160418112,
    "descendants": 1,
}

JOB = {"id": 3, "type": "job", "by": "bob", "title": "Job", "time": 1}
DELETED_STORY = {"id": 4, "type": "story", "by": "u", "title": "Gone", "time": 2, "deleted": True}
DEAD_STORY = {"id": 5, "type": "story", "by": "u", "title": "Dead", "time": 3, "dead": True}


def _mock(monkeypatch, ids, items):
    def fake_get(url, **kw):
        if url.endswith("/topstories.json"):
            return ids
        if "/item/" in url:
            tail = url.rsplit("/", 1)[-1].split(".json")[0]
            if not tail.isdigit():
                return {}
            return items.get(int(tail), {})
        return []

    monkeypatch.setattr("sources.hackernews.http_get_json", fake_get)


def test_fetch_topics_returns_stories_and_strips_html(monkeypatch):
    _mock(monkeypatch, [1, 2, 3, 4, 5], {1: STORY, 2: ASK, 3: JOB, 4: DELETED_STORY, 5: DEAD_STORY})
    posts = HNSource().fetch_topics("top", 1)
    assert [p.id for p in posts] == ["1", "2"]  # job / deleted / dead 跳过
    ask = posts[1]
    assert ask.content == "Ask anything"
    assert ask.node == "top"
    assert ask.author == "alice"
    assert ask.replies_count == 1
    assert ask.url == "https://news.ycombinator.com/item?id=2"


def test_fetch_topics_pagination(monkeypatch):
    ids = list(range(1, 61))  # 60 条，每页 30
    _mock(monkeypatch, ids, {i: dict(STORY, id=i, title=f"t{i}") for i in ids})
    page1 = HNSource().fetch_topics("top", 1)
    page2 = HNSource().fetch_topics("top", 2)
    assert [p.id for p in page1] == [str(i) for i in range(1, 31)]
    assert [p.id for p in page2] == [str(i) for i in range(31, 61)]


def test_fetch_topics_not_list(monkeypatch):
    _mock(monkeypatch, {"a": 1}, {})
    assert HNSource().fetch_topics("top", 1) == []


def test_fetch_topics_empty(monkeypatch):
    _mock(monkeypatch, [], {})
    assert HNSource().fetch_topics("top", 1) == []


def _comment(cid, kids=None, deleted=False, dead=False):
    return {
        "id": cid,
        "type": "comment",
        "by": "u",
        "text": f"<p>c{cid}</p>",
        "time": cid,
        "kids": kids or [],
        "deleted": deleted,
        "dead": dead,
    }


def test_fetch_replies_bfs_order_and_strip(monkeypatch):
    items = {
        1: STORY,
        100: _comment(100, kids=[300]),
        200: _comment(200, deleted=True, kids=[400]),
        300: _comment(300),
        400: _comment(400),
    }
    _mock(monkeypatch, [], items)
    replies = HNSource().fetch_replies("1")
    assert [r.id for r in replies] == ["100", "300"]  # BFS；deleted 的 200 被跳过，其子级不深入
    assert replies[0].content == "c100"  # HTML 已去标签


def test_fetch_replies_capped_at_10(monkeypatch):
    items = {1: STORY}
    items.update({100 + i: _comment(100 + i) for i in range(12)})
    items[1]["kids"] = [100 + i for i in range(12)]
    _mock(monkeypatch, [], items)
    assert len(HNSource().fetch_replies("1")) == 10


def test_fetch_replies_not_dict(monkeypatch):
    _mock(monkeypatch, [], {})
    assert HNSource().fetch_replies("nope") == []


def test_list_nodes():
    nodes = HNSource().list_nodes()
    assert nodes == [
        {"name": "show", "title": "Show HN"},
        {"name": "ask", "title": "Ask HN"},
        {"name": "top", "title": "Top"},
        {"name": "new", "title": "New"},
    ]


def test_retries_passed_to_http(monkeypatch):
    captured = {}

    def fake_get(url, **kw):
        captured.update(kw)
        return []

    monkeypatch.setattr("sources.hackernews.http_get_json", fake_get)
    HNSource(max_retries=7).fetch_topics("top", 1)
    assert captured["retries"] == 7
