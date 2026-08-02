import hashlib
import http.client
import io
import json
import urllib.error

import pytest

import analyzer
from models import MAX_REPLIES, Post, Reply


def _post(id: int, replies: int = 0) -> Post:
    return Post(
        id=str(id),
        source="v2ex",
        node="python",
        title=f"标题{id}",
        content="正文" * 300,  # 600 字符，测试截断到 500
        author="u",
        created=100 + id,
        replies_count=replies,
        url=f"https://www.v2ex.com/t/{id}",
        reply_list=[
            Reply(id=f"r{i}", author="a", content="回复" * 150, created=i)
            for i in range(replies)  # 300 字符 → 截断到 200
        ],
    )


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(analyzer, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(analyzer, "CACHE_DIR", tmp_path / "data" / ".cache")
    monkeypatch.setattr(analyzer, "STATE_FILE", tmp_path / "data" / "state.json")
    monkeypatch.setattr(analyzer, "REPORT_DIR", tmp_path / "data" / "analysis")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://fake/v1")  # URL 必填
    monkeypatch.setenv("ANALYZE_MODEL", "test-model")  # 模型必填
    return tmp_path


# ---------- format ----------


def test_format_post_truncates_content_and_replies():
    p = _post(1, replies=15)  # 回复 > MAX_REPLIES，应只保留前 10 条
    text = analyzer.format_post(p)
    assert "## [#1] 标题1" in text
    content_full = "正文" * 300  # 600 字符
    assert content_full[:500] in text
    assert content_full not in text  # 已截断到 500 字符
    assert text.count("  - a:") == MAX_REPLIES
    assert "回复" * 100 in text  # 截断后的 200 字符
    assert "回复" * 150 not in text  # 每条回复截断 200 字符


def test_build_batch_prompt_contains_marker_rule():
    prompt = analyzer.build_batch_prompt("批次文本", idx=0, total=2, title="用户痛点", desc="定义")
    assert "只提炼「用户痛点」类信息" in prompt
    assert "[#帖子ID]" in prompt
    assert "（第 1/2 批）" in prompt
    assert "批次文本" in prompt


# ---------- merge ----------


def test_merge_results_hierarchical(monkeypatch):
    # 7 个结果 → [abc][def][g] → 首轮 2 次合并，余 1 个直通 → 再 1 次合并 = 3 次调用
    calls = []
    monkeypatch.setattr(analyzer, "call_api", lambda prompt, **kw: calls.append(prompt) or "merged")
    result = analyzer.merge_results([f"r{i}" for i in range(7)], incremental=False)
    assert result == "merged"
    assert len(calls) == 3


def test_merge_results_single_no_call(monkeypatch):
    monkeypatch.setattr(analyzer, "call_api", lambda *a, **kw: pytest.fail("不应调用 LLM"))
    assert analyzer.merge_results(["only"], incremental=False) == "only"
    assert analyzer.merge_results([], incremental=False) == ""


# ---------- 链接还原 ----------


def test_restore_links():
    id2link = {"1": ("标题1", "https://v2ex.com/t/1")}
    text = "洞察 [#1] 与 [#2]"
    out = analyzer.restore_links(text, id2link)
    assert out == "洞察 [标题1](https://v2ex.com/t/1) 与 [#2]"  # 未知 ID 保留原文


def test_restore_links_unknown_warns(capsys):
    analyzer.restore_links("[#999]", {})
    assert "未找到帖子 999" in capsys.readouterr().err


# ---------- analyze ----------


def test_analyze_end_to_end(env, monkeypatch):
    # 20 帖 → 2 批 × 4 类 = 8 次分析调用 + 4 次合并调用
    topics = [_post(i) for i in range(20)]
    calls = {"count": 0}
    monkeypatch.setattr(
        analyzer,
        "call_api",
        lambda prompt, **kw: (calls.__setitem__("count", calls["count"] + 1), "[#1] 洞察")[1],
    )

    merged = analyzer.analyze(topics, incremental=False)
    assert set(merged) == {"好的创意/产品点子", "用户痛点", "个人开发者机会", "趋势洞察"}
    for text in merged.values():
        assert "[标题1](https://www.v2ex.com/t/1)" in text  # [#1] 已还原
    assert calls["count"] == 8 + 4
    # 缓存已清理
    assert not list(analyzer.CACHE_DIR.glob("*.json"))


def test_analyze_cache_hit(env, monkeypatch):
    # 预写该 run_id 的批次缓存 → 批次分析全命中，只跑合并
    topics = [_post(i) for i in range(20)]  # 2 批 × 4 类 = 8 个缓存文件
    run_id = hashlib.md5("".join(p.id for p in topics).encode("utf-8")).hexdigest()[:12]
    analyzer.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for bi in (0, 1):
        for key, _, _ in analyzer.CATEGORIES:
            (analyzer.CACHE_DIR / f"{run_id}_b{bi}_{key}.json").write_text(
                json.dumps({"key": key, "result": "[#1] 洞察"}), encoding="utf-8"
            )

    calls = {"count": 0}
    monkeypatch.setattr(
        analyzer,
        "call_api",
        lambda prompt, **kw: (calls.__setitem__("count", calls["count"] + 1), "[#1] 洞察")[1],
    )
    analyzer.analyze(topics)
    assert calls["count"] == 4  # 只有合并调用，8 次批次分析全命中缓存


def test_analyze_single_batch_no_merge(env, monkeypatch):
    topics = [_post(i) for i in range(5)]
    calls = {"count": 0}
    monkeypatch.setattr(
        analyzer,
        "call_api",
        lambda prompt, **kw: (calls.__setitem__("count", calls["count"] + 1), "[#1] 洞察")[1],
    )
    analyzer.analyze(topics)
    assert calls["count"] == 4  # 1 批 × 4 类，无合并


# ---------- load_topics ----------


def test_load_topics_since_and_bad_file(env):
    node = analyzer.DATA_DIR / "v2ex" / "python"
    node.mkdir(parents=True)
    (node / "1.json").write_text(json.dumps(_post(1).to_dict()), encoding="utf-8")
    (node / "2.json").write_text(json.dumps(_post(2).to_dict()), encoding="utf-8")
    (node / "bad.json").write_text("{not json", encoding="utf-8")  # 应跳过

    # post1.created=101, post2.created=102 → since=102 只留 post2
    posts = analyzer.load_topics(node, since=102)
    assert [p.id for p in posts] == ["2"]  # 文件名排序 + since 过滤 + 坏文件跳过


# ---------- LLM 配置 ----------


def test_resolve_llm_config_url_required(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("ANALYZE_MODEL", raising=False)
    # URL 未提供 → 必须显式配置，缺失即退出
    with pytest.raises(SystemExit):
        analyzer.resolve_llm_config({})
    # URL 有了但模型缺失 → 也要退出
    with pytest.raises(SystemExit):
        analyzer.resolve_llm_config({"llm": {"base_url": "https://cfg.example/v1"}})


def test_resolve_llm_config_model_required(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("ANALYZE_MODEL", raising=False)
    with pytest.raises(SystemExit):
        analyzer.resolve_llm_config({"llm": {"base_url": "https://cfg.example/v1"}})
    # 模型缺省不再兜底 gpt-4o-mini


def test_resolve_llm_config_priority(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("ANALYZE_MODEL", raising=False)
    monkeypatch.delenv("ANALYZE_MAX_TOKENS", raising=False)

    # config.json 提供 URL / model / max_tokens
    cfg = {"llm": {"base_url": "https://cfg.example/v1/", "model": "cfg-model", "max_tokens": 2048}}
    assert analyzer.resolve_llm_config(cfg) == {
        "base_url": "https://cfg.example/v1",
        "model": "cfg-model",
        "max_tokens": "2048",
    }

    # max_tokens 可选，兜底默认
    assert analyzer.resolve_llm_config({"llm": {"base_url": "https://cfg.example/v1", "model": "m"}}) == {
        "base_url": "https://cfg.example/v1",
        "model": "m",
        "max_tokens": "4096",
    }

    # 环境变量覆盖 config.json
    monkeypatch.setenv("OPENAI_BASE_URL", "https://env.example/v1")
    monkeypatch.setenv("ANALYZE_MODEL", "env-model")
    monkeypatch.setenv("ANALYZE_MAX_TOKENS", "8192")
    assert analyzer.resolve_llm_config(cfg) == {
        "base_url": "https://env.example/v1",
        "model": "env-model",
        "max_tokens": "8192",
    }


# ---------- call_api ----------


def _fake_http_error(code: int, message: str):
    body = json.dumps({"error": {"message": message}}).encode()
    hdrs = http.client.HTTPMessage()
    return urllib.error.HTTPError("http://fake/v1/chat/completions", code, "Error", hdrs, io.BytesIO(body))


def test_call_api_400_raises_with_detail_no_retry(monkeypatch):
    calls = []

    def fake_urlopen(req, **kw):
        calls.append(req)
        raise _fake_http_error(400, "model not found")

    monkeypatch.setattr(analyzer.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(analyzer, "_LLM", {"base_url": "http://fake/v1", "model": "m", "max_tokens": "4096"})
    with pytest.raises(RuntimeError, match="model not found"):
        analyzer.call_api("hi", retries=3)
    assert len(calls) == 1  # 4xx 不重试


def test_call_api_429_retries_then_raises(monkeypatch):
    calls = []

    def fake_urlopen(req, **kw):
        calls.append(req)
        raise _fake_http_error(429, "rate limited")

    monkeypatch.setattr(analyzer.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(analyzer, "_LLM", {"base_url": "http://fake/v1", "model": "m", "max_tokens": "4096"})
    monkeypatch.setattr(analyzer.time, "sleep", lambda _s: None)
    with pytest.raises(RuntimeError, match="429"):
        analyzer.call_api("hi", retries=2)
    assert len(calls) == 3  # 429 可重试


def test_check_env_missing(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        analyzer.check_env()
    assert "OPENAI_API_KEY" in capsys.readouterr().err


# ---------- main ----------


def _make_post_file(dir_path, post: Post):
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / f"{post.id}.json").write_text(json.dumps(post.to_dict()), encoding="utf-8")


def test_main_writes_report_and_state(env, monkeypatch, capsys):
    monkeypatch.setattr(
        analyzer,
        "load_config",
        lambda: {"sources": {"v2ex": {"enabled": True, "nodes": ["python"]}}, "llm": {}},
    )
    monkeypatch.setattr(analyzer, "call_api", lambda prompt, **kw: "[#1] 洞察")
    monkeypatch.setattr(analyzer, "run_crawl", lambda *a, **kw: 0)  # 自动爬取：测试中不真实联网
    _make_post_file(analyzer.DATA_DIR / "v2ex" / "python", _post(1))

    rc = analyzer.main([])  # 默认：增量 → analysis_today.md
    assert rc == 0

    report = (analyzer.REPORT_DIR / "analysis_today.md").read_text(encoding="utf-8")
    assert "# 拾贝 · 多来源分析" in report
    assert "来源: v2ex(python)" in report
    assert "## 好的创意/产品点子" in report
    assert "[标题1](https://www.v2ex.com/t/1)" in report  # 链接还原生效

    # 打印报告的绝对路径
    abs_path = str((analyzer.REPORT_DIR / "analysis_today.md").resolve())
    assert abs_path in capsys.readouterr().out

    state = json.loads(analyzer.STATE_FILE.read_text(encoding="utf-8"))
    assert "last_analysis" in state["v2ex"]


def test_main_full_writes_full_report(env, monkeypatch):
    monkeypatch.setattr(
        analyzer,
        "load_config",
        lambda: {"sources": {"v2ex": {"enabled": True, "nodes": ["python"]}}, "llm": {}},
    )
    monkeypatch.setattr(analyzer, "call_api", lambda prompt, **kw: "[#1] 洞察")
    monkeypatch.setattr(analyzer, "run_crawl", lambda *a, **kw: 0)
    _make_post_file(analyzer.DATA_DIR / "v2ex" / "python", _post(1))

    rc = analyzer.main(["--full"])  # 全量 → analysis.md
    assert rc == 0
    assert (analyzer.REPORT_DIR / "analysis.md").exists()
    state = json.loads(analyzer.STATE_FILE.read_text(encoding="utf-8"))
    assert "last_analysis" in state["v2ex"]


def test_main_empty_data_auto_full_crawl(env, monkeypatch, capsys):
    # 数据为空 → 应重置状态并走全量（run_crawl 被调用且 today=True）
    calls = {}
    monkeypatch.setattr(
        analyzer,
        "load_config",
        lambda: {"sources": {"v2ex": {"enabled": True, "nodes": ["python"]}}, "llm": {}},
    )
    monkeypatch.setattr(analyzer, "call_api", lambda prompt, **kw: "[#1] 洞察")
    monkeypatch.setattr(
        analyzer,
        "run_crawl",
        lambda *a, **kw: calls.update(kw) or 0,
    )
    rc = analyzer.main([])
    assert rc == 0
    assert calls["today"] is True
    assert "自动全量爬取" in capsys.readouterr().out


def test_main_no_topics(env, monkeypatch, capsys):
    monkeypatch.setattr(analyzer, "load_config", lambda: {"sources": {"v2ex": {"enabled": True}}, "llm": {}})
    monkeypatch.setattr(analyzer, "run_crawl", lambda *a, **kw: 0)
    rc = analyzer.main([])
    assert rc == 0
    assert "没有可分析的帖子" in capsys.readouterr().out


def test_main_missing_key_exits(env, monkeypatch, capsys):
    monkeypatch.setattr(analyzer, "load_config", lambda: {"sources": {}, "llm": {}})
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        analyzer.main([])
