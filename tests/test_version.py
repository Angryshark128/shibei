"""部署验证接口测试：/api/version。

镜像构建时由 Dockerfile 的 ARG VERSION 写入 /app/VERSION，部署后由
.github/workflows/deploy.yml 末步 curl 此接口与 git tag 比对。
"""

from web import app as web_app


def test_api_version_reads_version_file(monkeypatch, tmp_path):
    fake_version = tmp_path / "VERSION"
    fake_version.write_text("v9.9.9-test", encoding="utf-8")
    # 避免 _ensure_secret_key 落盘到仓库 data/.secret_key
    monkeypatch.setattr(web_app, "_ensure_secret_key", lambda: "test-secret-key")
    monkeypatch.setattr(web_app, "VERSION_FILE", fake_version)

    app = web_app.create_app()
    client = app.test_client()
    resp = client.get("/api/version")

    assert resp.status_code == 200
    assert resp.get_json() == {"version": "v9.9.9-test"}


def test_api_version_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(web_app, "_ensure_secret_key", lambda: "test-secret-key")
    monkeypatch.setattr(web_app, "VERSION_FILE", tmp_path / "does-not-exist")

    app = web_app.create_app()
    client = app.test_client()
    resp = client.get("/api/version")

    assert resp.status_code == 200
    assert resp.get_json() == {"version": ""}
