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


def _today_name() -> str:
    """增量报告按日归档名 YYYY-MM-DD.md（与 analyzer.write_report 一致）。"""
    return analyzer.time.strftime("%Y-%m-%d") + ".md"


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
    prompt = analyzer.build_batch_prompt("批次文本", idx=0, total=2, title="痛点机会", desc="定义")
    assert "只提炼「痛点机会」类信息" in prompt
    assert "[#帖子ID]" in prompt
    assert "（第 1/2 批）" in prompt
    assert "批次文本" in prompt


def test_build_batch_prompt_forces_chinese_even_for_english():
    # 数据源有英文（HN / Lobste.rs / Dev.to / Product Hunt），结论必须仍是中文
    prompt = analyzer.build_batch_prompt("Hello world", idx=0, total=1, title="Trend", desc="def")
    assert "一律用中文回答" in prompt
    assert "原文是英文" in prompt


def test_build_merge_prompt_forces_chinese_even_for_english():
    prompt = analyzer.build_merge_prompt(["English result"], incremental=False)
    assert "一律用中文回答" in prompt
    assert "原文是英文" in prompt


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
    assert out == "洞察 [来源](https://v2ex.com/t/1) 与 [#2]"  # 未知 ID 保留原文


def test_restore_links_unknown_warns(capsys):
    analyzer.restore_links("[#999]", {})
    assert "未找到帖子 999" in capsys.readouterr().err


# ---------- analyze ----------


def test_analyze_end_to_end(env, monkeypatch):
    # 20 帖 → 1 批（BATCH_SIZE=20）：1 次「一次输出多类」调用 + 3 次「合并+分组」调用
    topics = [_post(i) for i in range(20)]
    calls = {"count": 0}

    def fake_call(prompt, **kw):
        calls["count"] += 1
        if "整理" in prompt:  # 「合并去重并分组整理」或「只做整理分组」
            return "### 分类A\n- [#1] 洞察"
        return "## 产品创意\n- [#1] 洞察\n## 用户痛点\n- [#1] 洞察\n## 潜在机会\n- [#1] 洞察"

    monkeypatch.setattr(analyzer, "call_api", fake_call)

    merged = analyzer.analyze(topics, incremental=False)
    assert set(merged) == {"产品创意", "用户痛点", "潜在机会"}
    for text in merged.values():
        assert "### 分类A" in text  # 分组结构保留
        assert "[来源](https://www.v2ex.com/t/1)" in text  # [#1] 已还原为来源链接
    assert calls["count"] == 1 + 3  # 1 批多类 + 3 类合并分组
    # 缓存已清理
    assert not list(analyzer.CACHE_DIR.glob("*.json"))


def test_analyze_cache_hit(env, monkeypatch):
    # 预写该 run_id 的批次缓存（一次调用输出多类）→ 批次全命中，只跑每类合并分组
    topics = [_post(i) for i in range(20)]  # 1 批 = 1 个缓存文件
    run_id = hashlib.md5("".join(p.id for p in topics).encode("utf-8")).hexdigest()[:12]
    analyzer.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (analyzer.CACHE_DIR / f"{run_id}_b0_multi_zh.json").write_text(
        json.dumps({"result": {key: "[#1] 洞察" for key, _, _ in analyzer.CATEGORIES}}),
        encoding="utf-8",
    )

    calls = {"count": 0}
    monkeypatch.setattr(
        analyzer,
        "call_api",
        lambda prompt, **kw: (
            calls.__setitem__("count", calls["count"] + 1),
            "### 分类A\n- [#1] 洞察",
        )[1],
    )
    analyzer.analyze(topics)
    assert calls["count"] == 3  # 仅 3 类合并分组（批次分析全命中缓存）


def test_analyze_falls_back_to_per_category_when_unparsed(env, monkeypatch):
    # 多类输出未按 `## 类别` 分节（无法解析）→ 回退为按类逐次调用（保底路径）
    topics = [_post(i) for i in range(5)]
    calls = {"count": 0}
    monkeypatch.setattr(
        analyzer,
        "call_api",
        lambda prompt, **kw: (calls.__setitem__("count", calls["count"] + 1), "[#1] 洞察")[1],
    )
    analyzer.analyze(topics)
    assert calls["count"] == 1 + 3 + 3  # 1 次多类调用（解析失败）+ 回退按类 3 次 + 3 类合并分组


def test_build_multi_prompt_lists_all_categories():
    prompt = analyzer.build_multi_prompt("批次文本", idx=0, total=2)
    for _, title, _ in analyzer.CATEGORIES:
        assert f"## {title}" in prompt
    assert "[#帖子ID]" in prompt
    assert "（第 1/2 批）" in prompt
    assert "批次文本" in prompt


def test_parse_multi_splits_sections_and_drops_empty():
    raw = "## 产品创意\n- [#1] 洞察\n## 用户痛点\n无\n## 潜在机会\n\n- [#2] 机会"
    out = analyzer.parse_multi(raw)
    assert out["ideas"] == "- [#1] 洞察"
    assert out["pain"] == ""  # 「无」视为空
    assert out["indie"] == "- [#2] 机会"


def test_parse_multi_ignores_unknown_sections():
    out = analyzer.parse_multi("## 别的标题\n- x\n正文")
    assert set(out.values()) == {""}


def test_consolidate_single_result_organizes(monkeypatch):
    # 单批结果交给分组整理（organize_topics）
    monkeypatch.setattr(analyzer, "call_api", lambda prompt, **kw: "### 分类A\n- [#1] x")
    out = analyzer.consolidate(["- [#1] x"], "产品创意", incremental=True)
    assert out.startswith("### 分类A")


def test_consolidate_keeps_content_when_all_calls_fail(monkeypatch):
    # 合并分组与回退路径都失败 → 原样拼接各批结果，不丢内容
    def boom(prompt, **kw):
        raise RuntimeError("llm down")

    monkeypatch.setattr(analyzer, "call_api", boom)
    out = analyzer.consolidate(["- [#1] x", "- [#2] y"], "产品创意", incremental=False)
    assert "[#1] x" in out and "[#2] y" in out


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

    rc = analyzer.main([])  # 默认：增量 → 当日归档 YYYY-MM-DD.md
    assert rc == 0

    report = (analyzer.REPORT_DIR / _today_name()).read_text(encoding="utf-8")
    assert f"# {_today_name().removesuffix('.md')}" in report
    assert "来源: v2ex(python)" in report
    assert "## 产品创意" in report
    assert "[来源](https://www.v2ex.com/t/1)" in report  # 链接还原生效

    # 打印报告的绝对路径
    abs_path = str((analyzer.REPORT_DIR / _today_name()).resolve())
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


def test_main_empty_data_full_crawl_still_analyzes(env, monkeypatch, capsys):
    # 数据为空 → 全量爬取后 last_crawl 被更新为当前时刻，
    # 刚爬下来的帖子（created 早于此刻）不应被 since 过滤掉，必须照常分析并出报告。
    monkeypatch.setattr(
        analyzer,
        "load_config",
        lambda: {"sources": {"v2ex": {"enabled": True, "nodes": ["python"]}}, "llm": {}},
    )
    monkeypatch.setattr(analyzer, "call_api", lambda prompt, **kw: "[#1] 洞察")

    def fake_run_crawl(config, source_name=None, today=False, lang="zh"):
        # 模拟真实爬虫：写入帖子文件，并把 last_crawl 置为当前时刻
        _make_post_file(analyzer.DATA_DIR / "v2ex" / "python", _post(1))
        state = analyzer.load_state()
        state.setdefault("v2ex", {})["last_crawl"] = int(analyzer.time.time())
        analyzer.save_state(state)
        return 1

    monkeypatch.setattr(analyzer, "run_crawl", fake_run_crawl)
    rc = analyzer.main([])
    assert rc == 0
    report = (analyzer.REPORT_DIR / _today_name()).read_text(encoding="utf-8")
    assert "基于 1 个帖子自动生成" in report
    assert "没有新增帖子" not in capsys.readouterr().out


def test_main_mixed_empty_source_still_analyzes(env, monkeypatch, capsys):
    # 来源 a 已有数据与 last_analysis，来源 b 为空：b 被全量爬取后 last_crawl=当前时刻，
    # b 刚爬下来的帖子（created 早于此刻）不应被 since 过滤掉；a 仍按增量处理。
    monkeypatch.setattr(
        analyzer,
        "load_config",
        lambda: {
            "sources": {
                "a": {"enabled": True, "nodes": ["x"]},
                "b": {"enabled": True, "nodes": ["y"]},
            },
            "llm": {},
        },
    )
    monkeypatch.setattr(analyzer, "call_api", lambda prompt, **kw: "[#1] 洞察")
    _make_post_file(analyzer.DATA_DIR / "a" / "x", _post(1))  # a 已有数据
    analyzer.save_state({"a": {"last_crawl": 100, "last_analysis": 200}})  # a 增量点

    def fake_run_crawl(config, source_name=None, today=False, lang="zh"):
        # 只给空的来源 b 写帖子，并把 last_crawl 置为当前时刻；a 不新增
        _make_post_file(analyzer.DATA_DIR / "b" / "y", _post(2))
        st = analyzer.load_state()
        st.setdefault("b", {})["last_crawl"] = int(analyzer.time.time())
        analyzer.save_state(st)
        return 1

    monkeypatch.setattr(analyzer, "run_crawl", fake_run_crawl)
    rc = analyzer.main([])
    assert rc == 0
    report = (analyzer.REPORT_DIR / _today_name()).read_text(encoding="utf-8")
    assert "基于 1 个帖子自动生成" in report  # 只有 b 的新帖被分析，a 无新增
    assert "没有新增帖子" not in capsys.readouterr().out


def test_main_no_topics(env, monkeypatch, capsys):
    monkeypatch.setattr(analyzer, "load_config", lambda: {"sources": {"v2ex": {"enabled": True}}, "llm": {}})
    monkeypatch.setattr(analyzer, "run_crawl", lambda *a, **kw: 0)
    rc = analyzer.main([])
    assert rc == 0
    assert "没有可分析的帖子" in capsys.readouterr().out


def test_main_interrupt_exits_130(env, monkeypatch, capsys):
    def boom(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(analyzer, "run_crawl", boom)
    monkeypatch.setattr(analyzer.os, "_exit", lambda code: (_ for _ in ()).throw(SystemExit(code)))
    with pytest.raises(SystemExit) as e:
        analyzer.main([])
    assert e.value.code == 130
    assert "已中断" in capsys.readouterr().err


def test_main_missing_key_exits(env, monkeypatch, capsys):
    monkeypatch.setattr(analyzer, "load_config", lambda: {"sources": {}, "llm": {}})
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        analyzer.main([])


# ---------- 报告子主题分组（organize_topics） ----------


def test_organize_topics_groups_into_h3(monkeypatch):
    # LLM 正常返回带 ### 的分组文本 → 原样保留（报告按 H3 子主题分节）
    monkeypatch.setattr(
        analyzer,
        "call_api",
        lambda prompt, **kw: "### 效率工具\n- [#1] 洞察A\n### 生态\n- [#2] 洞察B",
    )
    out = analyzer.organize_topics("some merged text", "产品创意")
    assert "### 效率工具" in out
    assert "### 生态" in out
    assert "[#2] 洞察B" in out


def test_organize_topics_empty_input_returns_as_is(monkeypatch):
    def boom(*a, **kw):
        raise AssertionError("空输入不应触发 LLM 调用")

    monkeypatch.setattr(analyzer, "call_api", boom)
    assert analyzer.organize_topics("", "产品创意") == ""
    assert analyzer.organize_topics("   \n", "产品创意") == "   \n"


def test_organize_topics_fallback_on_error(monkeypatch):
    # LLM 异常 → 回退原样文本，不影响报告
    def boom(*a, **kw):
        raise RuntimeError("llm down")

    monkeypatch.setattr(analyzer, "call_api", boom)
    src = "- [#1] 洞察A"
    assert analyzer.organize_topics(src, "产品创意") == src


def test_organize_topics_fallback_on_empty_reply(monkeypatch):
    monkeypatch.setattr(analyzer, "call_api", lambda prompt, **kw: "  ")
    src = "- [#1] 洞察A"
    assert analyzer.organize_topics(src, "产品创意") == src


def test_build_organize_prompt_keeps_marker_rule():
    prompt = analyzer.build_organize_prompt("内容", "痛点机会")
    assert "只做整理分组" in prompt
    assert "[#帖子ID]" in prompt
    assert "### 子主题名" in prompt


# ---------- 英文报告（--lang en / ANALYZE_LANG=en） ----------


def test_resolve_lang_priority(monkeypatch):
    monkeypatch.delenv("ANALYZE_LANG", raising=False)
    assert analyzer.resolve_lang(None) == "zh"  # 无参默认中文
    assert analyzer.resolve_lang("en") == "en"
    assert analyzer.resolve_lang("fr") == "zh"  # 非法值回落默认
    monkeypatch.setenv("ANALYZE_LANG", "en")
    assert analyzer.resolve_lang(None) == "en"
    assert analyzer.resolve_lang("zh") == "zh"  # --lang 优先于环境变量


def test_english_categories_and_prompt():
    assert [t for _, t, _ in analyzer._categories("en")] == ["Product Ideas", "User Pain Points", "Opportunities"]
    prompt = analyzer.build_multi_prompt("batch text", idx=0, total=1, lang="en")
    for _, title, _ in analyzer._categories("en"):
        assert f"## {title}" in prompt
    assert "Answer in English" in prompt
    assert "产品创意" not in prompt


def test_is_empty_result_by_language():
    assert analyzer.is_empty_result("无", "zh")
    assert analyzer.is_empty_result("None", "en")
    assert analyzer.is_empty_result("  nothing. ", "en")
    assert not analyzer.is_empty_result("- item", "en")


def test_parse_multi_english_sections():
    raw = "## Product Ideas\n- [#1] insight\n## User Pain Points\nNone\n## Opportunities\n\n- [#2] chance"
    out = analyzer.parse_multi(raw, "en")
    assert out["ideas"].startswith("- [#1]")
    assert out["pain"] == ""  # 「None」视为空
    assert out["indie"].startswith("- [#2]")


def test_build_report_english():
    report = analyzer.build_report(
        {"Product Ideas": "- thing — [来源](https://x)", "User Pain Points": ""},
        3,
        "v2ex(python)",
        "2026-09-10",
        "en",
    )
    assert report.startswith("# 2026-09-10")
    assert "Sources: v2ex(python)" in report
    assert "Generated from 3 posts" in report
    assert "No insights found this round" in report  # 空类别占位


def test_report_stem_by_language(env):
    today = analyzer.time.strftime("%Y-%m-%d")
    assert analyzer.report_stem(incremental=True, lang="zh") == today
    assert analyzer.report_stem(incremental=True, lang="en") == today + ".en"
    assert analyzer.report_stem(incremental=False, lang="zh") == "analysis"
    assert analyzer.report_stem(incremental=False, lang="en") == "analysis.en"


def test_write_report_english_files(env):
    analyzer.write_report("# English daily", incremental=True, lang="en")
    analyzer.write_report("# English full", incremental=False, lang="en")
    daily = analyzer.REPORT_DIR / (analyzer.time.strftime("%Y-%m-%d") + ".en.md")
    assert daily.read_text(encoding="utf-8").startswith("# English daily")
    assert (analyzer.REPORT_DIR / "analysis.en.md").exists()
    assert not (analyzer.REPORT_DIR / _today_name()).exists()  # 不写中文文件


def test_analyze_english_end_to_end(env, monkeypatch):
    topics = [_post(1), _post(2)]
    monkeypatch.setattr(
        analyzer,
        "call_api",
        lambda prompt, **kw: (
            "## Product Ideas\n- [#1] 洞察\n## User Pain Points\n- [#1] 痛点\n## Opportunities\n- [#2] 机会"
        ),
    )
    merged = analyzer.analyze(topics, incremental=False, language="en")
    assert set(merged) == {"Product Ideas", "User Pain Points", "Opportunities"}
    assert "[来源]" in merged["Product Ideas"]  # 链接还原仍生效
    assert not list(analyzer.CACHE_DIR.glob("*.json"))  # 分析完清理缓存
