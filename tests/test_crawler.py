import datetime as dt
import json

import pytest

import crawler
from models import Post, Reply
from sources import Source


class FakeSource(Source):
    name = "fake"
    display_name = "Fake"

    def __init__(self, topics=None, replies=None, **kw):
        super().__init__(**kw)
        self.topics: dict[tuple[str, int], list[Post]] = topics or {}
        self.replies: dict[str, list[Reply]] = replies or {}
        self.topics_calls: list[tuple[str, int]] = []
        self.replies_calls: list[str] = []

    def fetch_topics(self, node: str, page: int) -> list[Post]:
        self.topics_calls.append((node, page))
        return self.topics.get((node, page), [])

    def fetch_replies(self, topic_id: str) -> list[Reply]:
        self.replies_calls.append(topic_id)
        return self.replies.get(topic_id, [])


def _post(id: int, created: int = 100) -> Post:
    return Post(
        id=str(id),
        source="fake",
        node="python",
        title=f"帖{id}",
        content="",
        author="u",
        created=created,
        replies_count=0,
        url=f"https://example.com/t/{id}",
    )


@pytest.fixture
def env(monkeypatch, tmp_path):
    """隔离 data/ 与缓存目录，禁用 sleep。"""
    monkeypatch.setattr(crawler, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(crawler, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(crawler, "STATE_FILE", tmp_path / "data" / "state.json")
    monkeypatch.setattr(crawler.time, "sleep", lambda _s: None)
    return tmp_path


# ---------- collect_topics ----------


def test_collect_topics_dedup(env):
    src = FakeSource(
        topics={
            ("python", 1): [_post(1), _post(2)],
            ("python", 2): [_post(2), _post(3)],  # 与第 1 页重复的 id=2
        }
    )
    posts = crawler.collect_topics(src, "python", pages=2)
    assert {p.id for p in posts} == {"1", "2", "3"}
    assert src.topics_calls == [("python", 1), ("python", 2)]


def _today_cache_file(node: str = "python"):
    today = dt.date.today().isoformat()
    return crawler.CACHE_DIR / f"fake_{node}_{today}.json"


def test_collect_topics_cache_hit(env):
    # 预写足够条目的今日缓存，应命中且不再请求
    cache_file = _today_cache_file()
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps([_post(i).to_dict() for i in range(12)]), encoding="utf-8")
    src = FakeSource()
    posts = crawler.collect_topics(src, "python", pages=2)  # 需要 >= 2*5=10 条
    assert len(posts) == 12
    assert src.topics_calls == []


def test_collect_topics_cache_refetch_if_too_few(env):
    cache_file = _today_cache_file()
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps([_post(i).to_dict() for i in range(3)]), encoding="utf-8")
    src = FakeSource(topics={("python", 1): [_post(9)]})
    posts = crawler.collect_topics(src, "python", pages=1)  # 需要 >= 5 条
    assert [p.id for p in posts] == ["9"]
    assert src.topics_calls == [("python", 1)]


# ---------- crawl ----------


def test_crawl_saves_posts_with_reply_limit(env):
    replies = [Reply(id=f"r{i}", author="u", content="c", created=i) for i in range(15)]
    src = FakeSource(
        topics={("python", 1): [_post(1), _post(2)]},
        replies={"1": replies, "2": replies},
    )
    new = crawler.crawl(src, ["python"], pages=1)
    assert new == 2

    target = crawler.DATA_DIR / "fake" / "python" / "1.json"
    assert target.exists()
    d = json.loads(target.read_text(encoding="utf-8"))
    assert d["id"] == "1"
    assert d["source"] == "fake"
    assert d["node"] == "python"
    assert len(d["reply_list"]) == 10  # 只存前 10 条回复


def test_crawl_skip_existing(env):
    out = crawler.DATA_DIR / "fake" / "python"
    out.mkdir(parents=True, exist_ok=True)
    (out / "1.json").write_text(json.dumps(_post(1).to_dict()), encoding="utf-8")
    src = FakeSource(topics={("python", 1): [_post(1), _post(2)]})
    new = crawler.crawl(src, ["python"], pages=1)
    assert new == 1  # 只有 id=2 新增
    assert src.replies_calls == ["2"]


def test_crawl_since_filter(env):
    src = FakeSource(topics={("python", 1): [_post(1, created=100), _post(2, created=200)]})
    new = crawler.crawl(src, ["python"], pages=1, since=150)
    assert new == 1
    target = crawler.DATA_DIR / "fake" / "python" / "2.json"
    assert target.exists()
    assert not (crawler.DATA_DIR / "fake" / "python" / "1.json").exists()


# ---------- 状态 ----------


def test_state_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    crawler.save_state({"v2ex": {"last_crawl": 123}}, path)
    assert crawler.load_state(path) == {"v2ex": {"last_crawl": 123}}


def test_load_state_missing(env):
    assert crawler.load_state() == {}


# ---------- 来源选择 ----------


def test_get_sources_filter_and_config():
    config = {"sources": {"v2ex": {"enabled": True, "request_delay": 0.5, "max_retries": 5}}}
    sources = crawler.get_sources(None, config)
    assert [s.name for s in sources] == ["v2ex"]
    assert sources[0].request_delay == 0.5
    assert sources[0].max_retries == 5


def test_get_sources_disabled(monkeypatch):
    config = {"sources": {"v2ex": {"enabled": False}}}
    with pytest.raises(SystemExit):
        crawler.get_sources(None, config)


def test_get_sources_unknown_source(monkeypatch):
    config = {"sources": {"v2ex": {"enabled": True}}}
    with pytest.raises(SystemExit):
        crawler.get_sources("nonexistent", config)


# ---------- run_crawl ----------


def test_run_crawl_today_updates_state(env, monkeypatch):
    monkeypatch.setattr(crawler, "get_sources", lambda *a, **k: [FakeSource()])
    monkeypatch.setattr(crawler, "crawl", lambda *a, **k: 5)
    config = {"sources": {"fake": {"enabled": True, "nodes": ["python"], "pages_per_node": 1}}}
    total = crawler.run_crawl(config, today=True)
    assert total == 5
    assert crawler.load_state()["fake"]["last_crawl"] > 0


def test_run_crawl_full_no_timestamp(env, monkeypatch):
    monkeypatch.setattr(crawler, "get_sources", lambda *a, **k: [FakeSource()])
    monkeypatch.setattr(crawler, "crawl", lambda *a, **k: 3)
    config = {"sources": {"fake": {"enabled": True}}}
    crawler.run_crawl(config, today=False)
    assert crawler.load_state() == {}


def test_run_crawl_source_failure_continues(env, monkeypatch):
    # 单来源失败不影响其他来源
    def fake_crawl(source, nodes, pages, since=None):
        if source.name == "bad":
            raise RuntimeError("boom")
        return 2

    class FakeBad(FakeSource):
        name = "bad"
        display_name = "Bad"

    monkeypatch.setattr(crawler, "get_sources", lambda *a, **k: [FakeBad(), FakeSource()])
    monkeypatch.setattr(crawler, "crawl", fake_crawl)
    config = {"sources": {"bad": {"enabled": True}, "fake": {"enabled": True}}}
    assert crawler.run_crawl(config, today=False) == 2


def test_run_crawl_parallel_sources_all_update_state(env, monkeypatch):
    # 来源并行爬取，每个来源的 last_crawl 都写入且不互相覆盖
    def make(name):
        return type(name, (FakeSource,), {"name": name, "display_name": name})()

    s1, s2 = make("s1"), make("s2")
    monkeypatch.setattr(crawler, "get_sources", lambda *a, **k: [s1, s2])
    monkeypatch.setattr(crawler, "crawl", lambda *a, **k: 1)
    config = {"sources": {"s1": {"enabled": True}, "s2": {"enabled": True}}}
    assert crawler.run_crawl(config, today=True) == 2
    st = crawler.load_state()
    assert st["s1"]["last_crawl"] > 0
    assert st["s2"]["last_crawl"] > 0


def test_run_crawl_parallel_sources_fail_one(env, monkeypatch):
    # 并行时单来源抛异常不影响其他来源的新增统计
    def fake_crawl(source, nodes, pages, since=None):
        if source.name == "bad":
            raise RuntimeError("boom")
        return 3

    class FakeBad(FakeSource):
        name = "bad"
        display_name = "Bad"

    monkeypatch.setattr(crawler, "get_sources", lambda *a, **k: [FakeBad(), FakeSource()])
    monkeypatch.setattr(crawler, "crawl", fake_crawl)
    config = {"sources": {"bad": {"enabled": True}, "fake": {"enabled": True}}}
    assert crawler.run_crawl(config, today=True) == 3
    st = crawler.load_state()
    assert "bad" not in st  # 失败来源不写 last_crawl
    assert st["fake"]["last_crawl"] > 0


# ---------- 日志与优雅退出 ----------


def test_crawl_log_includes_source(env, capsys):
    # 并行爬取后日志需带来源标识，便于区分
    src = FakeSource(topics={("python", 1): [_post(1)]}, replies={"1": []})
    crawler.crawl(src, ["python"], pages=1)
    assert "[fake 1/1] 1 - 帖1" in capsys.readouterr().out


def test_main_interrupt_exits_130(monkeypatch, capsys):
    def boom(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(crawler, "run_crawl", boom)
    monkeypatch.setattr(crawler.os, "_exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
    with pytest.raises(SystemExit) as e:
        crawler.main([])
    assert e.value.code == 130
    assert "已中断" in capsys.readouterr().err
