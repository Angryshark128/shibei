from models import Post, Reply, post_from_dict


def _post() -> Post:
    return Post(
        id="1",
        source="v2ex",
        node="python",
        title="标题",
        content="正文",
        author="alice",
        created=100,
        replies_count=3,
        url="https://www.v2ex.com/t/1",
        reply_list=[Reply(id="r1", author="bob", content="回复", created=101)],
    )


def test_post_to_dict():
    d = _post().to_dict()
    assert d["id"] == "1"
    assert d["source"] == "v2ex"
    assert d["node"] == "python"
    assert d["author"] == "alice"
    assert d["reply_list"] == [{"id": "r1", "author": "bob", "content": "回复", "created": 101}]


def test_post_from_dict_roundtrip():
    d = _post().to_dict()
    p = post_from_dict(d)
    assert isinstance(p, Post)
    assert p.id == "1"
    assert p.url == "https://www.v2ex.com/t/1"
    assert p.reply_list[0].id == "r1"
    assert p.reply_list[0].created == 101


def test_post_from_dict_missing_reply_list():
    d = _post().to_dict()
    del d["reply_list"]
    p = post_from_dict(d)
    assert p.reply_list == []


def test_post_from_dict_null_fields():
    # 兼容 V2EX 字段可能为 null / 缺失
    d = {"id": "2", "title": None, "created": None}
    p = post_from_dict(d)
    assert p.id == "2"
    assert p.title == ""
    assert p.created == 0
    assert p.author == ""
    assert p.node == ""
