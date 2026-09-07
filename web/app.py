"""拾贝 · Web 界面后端（Flask）。

职责：
- 认证：登录 / 退出（flask signed session，凭据 scrypt 哈希持久化）
- 配置：LLM（base_url / model / max_tokens / api_key）与来源启用开关
- 任务：触发 analyzer 子进程（增量 / 全量）、查询状态与日志
- 报告：列出 / 读取 data/analysis 下的 Markdown 报告
- 静态：托管前端构建产物（frontend/dist → /app/static）

运行配置（环境变量）：
    SHIBEI_PORT        监听端口（默认 8000）
    SHIBEI_BASE_PATH   浏览器侧访问前缀，如 /shibei/（决定 cookie path）
    SHIBEI_USERNAME    初始管理员用户名（默认 admin）
    SHIBEI_PASSWORD    初始管理员密码；缺省时自动生成并打印到日志

运行时数据全部落在 data/ 下（已 gitignore）：
    data/web_config.json    运行时配置权威（含 sources 与 llm 节）
    data/web_secrets.json    登录凭据哈希与 LLM API Key（0600）
    data/.secret_key         Flask session 签名密钥
    data/tasks/              任务索引与日志
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from collections.abc import Callable
from datetime import timedelta
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar

from flask import Flask, jsonify, request, send_from_directory, session
from waitress import serve

from web.runner import TaskManager, TaskRunningError

logger = logging.getLogger("shibei.web")

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
REPORT_DIR = DATA_DIR / "analysis"
CONFIG_FILE = REPO_ROOT / "config.json"
WEB_CONFIG_FILE = DATA_DIR / "web_config.json"
SECRETS_FILE = DATA_DIR / "web_secrets.json"
SECRET_KEY_FILE = DATA_DIR / ".secret_key"
STATIC_DIR = REPO_ROOT / "static"

SESSION_TTL_DAYS = 7
F = TypeVar("F", bound=Callable[..., Any])


# ---------- 持久化小工具 ----------


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, obj: Any, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    if mode is not None:
        tmp.chmod(mode)
    tmp.replace(path)


def _atomic_write_text(path: Path, text: str, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    if mode is not None:
        tmp.chmod(mode)
    tmp.replace(path)


# ---------- 凭据与密钥 ----------


def _ensure_secret_key() -> str:
    if SECRET_KEY_FILE.exists():
        key = SECRET_KEY_FILE.read_text(encoding="utf-8").strip()
        if key:
            return key
    key = secrets.token_urlsafe(48)
    _atomic_write_text(SECRET_KEY_FILE, key, mode=0o600)
    return key


def _hash_password(password: str) -> str:
    """scrypt 哈希，格式: scrypt$<salt_b64>$<hash_b64>。"""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def _verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt_b64, hash_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return hmac.compare_digest(digest, expected)


class Secrets:
    """web_secrets.json：{username, password_hash, llm_api_key}。"""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        self._data = _read_json(SECRETS_FILE, {})
        if not self._data:
            self._bootstrap()

    def _bootstrap(self) -> None:
        username = os.environ.get("SHIBEI_USERNAME", "").strip() or "admin"
        password = os.environ.get("SHIBEI_PASSWORD", "").strip()
        generated = False
        if not password:
            password = secrets.token_urlsafe(12)
            generated = True
        self._data = {
            "username": username,
            "password_hash": _hash_password(password),
            "llm_api_key": "",
        }
        self.save()
        if generated:
            # 自动生成的初始密码打印到容器日志，仅供首次登录
            print(f"[shibei] 未设置 SHIBEI_PASSWORD，已生成初始管理员密码：{password}", flush=True)

    @property
    def username(self) -> str:
        return self._data.get("username", "")

    @property
    def has_llm_api_key(self) -> bool:
        return bool(self._data.get("llm_api_key"))

    @property
    def llm_api_key(self) -> str:
        return self._data.get("llm_api_key", "")

    def verify_login(self, username: str, password: str) -> bool:
        ok_user = username == self._data.get("username")
        return ok_user and _verify_password(password, self._data.get("password_hash", ""))

    def set_llm_api_key(self, api_key: str) -> None:
        self._data["llm_api_key"] = api_key
        self.save()

    def change_password(self, username: str, password: str) -> None:
        self._data["username"] = username
        self._data["password_hash"] = _hash_password(password)
        self.save()

    def save(self) -> None:
        _write_json(SECRETS_FILE, self._data, mode=0o600)


class WebConfig:
    """运行时配置权威（data/web_config.json），结构与仓库 config.json 一致。

    web 修改先落 web_config，再同步写仓库 config.json，保证 CLI 与容器内
    直接运行 analyzer.py 读到的是同一份最新配置。
    """

    def __init__(self) -> None:
        if not WEB_CONFIG_FILE.exists():
            default = _read_json(CONFIG_FILE, {"sources": {}, "llm": {}})
            _write_json(WEB_CONFIG_FILE, default, mode=0o600)
        self._data = _read_json(WEB_CONFIG_FILE, {"sources": {}, "llm": {}})
        self._sync_repo_config()

    def _sync_repo_config(self) -> None:
        # 只在内容确有差异时写，避免无谓触碰仓库文件
        if _read_json(CONFIG_FILE, None) != self._data:
            _write_json(CONFIG_FILE, self._data)

    def get(self) -> dict[str, Any]:
        return json.loads(json.dumps(self._data))

    def llm(self) -> dict[str, Any]:
        llm = self._data.setdefault("llm", {})
        return {
            "base_url": str(llm.get("base_url", "")),
            "model": str(llm.get("model", "")),
            "max_tokens": int(llm.get("max_tokens", 4096) or 4096),
        }

    def sources(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for name, conf in self._data.get("sources", {}).items():
            out.append(
                {
                    "name": name,
                    "enabled": bool(conf.get("enabled", True)),
                    "nodes": list(conf.get("nodes", [])),
                }
            )
        return out

    def set_llm(self, llm: dict[str, Any]) -> None:
        target = self._data.setdefault("llm", {})
        if "base_url" in llm:
            target["base_url"] = llm["base_url"].rstrip("/")
        if "model" in llm:
            target["model"] = llm["model"]
        if "max_tokens" in llm:
            target["max_tokens"] = int(llm["max_tokens"])
        self._save()

    def set_source_enabled(self, name: str, enabled: bool) -> None:
        conf = self._data.setdefault("sources", {}).setdefault(name, {})
        conf["enabled"] = bool(enabled)
        self._save()

    def _save(self) -> None:
        _write_json(WEB_CONFIG_FILE, self._data, mode=0o600)
        self._sync_repo_config()


# ---------- 报告 ----------


def _report_list() -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for path in sorted(REPORT_DIR.glob("*.md")):
        stat = path.stat()
        reports.append(
            {
                "name": path.stem,  # analysis / analysis_today
                "file": path.name,
                "updated_at": stat.st_mtime,
                "size": stat.st_size,
            }
        )
    return reports


def _summary(config: WebConfig, secrets_store: Secrets) -> dict[str, Any]:
    per_source: dict[str, int] = {}
    total = 0
    if DATA_DIR.is_dir():
        excluded = (".cache", ".tasks", "analysis", "tasks")
        for source_dir in sorted(p for p in DATA_DIR.iterdir() if p.is_dir() and p.name not in excluded):
            count = sum(1 for _ in source_dir.rglob("*.json") if not _.name.endswith(".tmp"))
            if count:
                per_source[source_dir.name] = count
            total += count
    reports = {r["name"]: r for r in _report_list()}
    return {
        "total_posts": total,
        "per_source": per_source,
        "llm_configured": bool(config.llm()["base_url"] and config.llm()["model"] and secrets_store.has_llm_api_key),
        "has_full_report": "analysis" in reports,
        "has_today_report": "analysis_today" in reports,
    }


# ---------- Flask 应用 ----------


def create_app() -> Flask:
    base_path = os.environ.get("SHIBEI_BASE_PATH", "/shibei/").strip()
    if not base_path.startswith("/"):
        base_path = "/" + base_path
    if not base_path.endswith("/"):
        base_path += "/"

    # dist 结构：index.html + assets/；/assets 映射到 static/assets 目录
    app = Flask(__name__, static_folder=str(STATIC_DIR / "assets"), static_url_path="/assets")
    app.config.update(
        SECRET_KEY=_ensure_secret_key(),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_PATH=base_path,
        PERMANENT_SESSION_LIFETIME=timedelta(days=SESSION_TTL_DAYS),
    )

    secrets_store = Secrets()
    config = WebConfig()
    tasks = TaskManager(REPO_ROOT)

    @app.after_request
    def _no_cache_api(response: Any) -> Any:
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    # ---------- 认证 ----------

    def require_login(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not session.get("user"):
                return jsonify({"error": "unauthorized", "message": "请先登录"}), 401
            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    def require_same_origin(fn: F) -> F:
        """JSON 写接口的 CSRF 防线：校验 Origin / Referer 与本机一致。"""

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            origin = request.headers.get("Origin") or request.headers.get("Referer")
            if origin:
                from urllib.parse import urlparse

                # 忽略端口（nginx 反代时 Host 不带端口）；hostname 不同即视为跨站
                origin_host = (urlparse(origin).hostname or "").lower()
                host = (request.host.split(":")[0]).lower()
                if origin_host != host:
                    return jsonify({"error": "bad_origin", "message": "请求来源不合法"}), 403
            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    def body_json() -> dict[str, Any]:
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}

    @app.post("/api/login")
    @require_same_origin
    def login() -> Any:
        data = body_json()
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        # 轻量防爆破：失败固定延迟，不区分“用户不存在/密码错”
        time.sleep(0.4)
        if not secrets_store.verify_login(username, password):
            return jsonify({"error": "bad_credentials", "message": "用户名或密码错误"}), 401
        session.permanent = True
        session["user"] = username
        return jsonify({"username": username})

    @app.post("/api/logout")
    @require_same_origin
    def logout() -> Any:
        session.clear()
        return jsonify({"ok": True})

    @app.get("/api/me")
    def me() -> Any:
        user = session.get("user")
        if not user:
            return jsonify({"error": "unauthorized", "message": "请先登录"}), 401
        return jsonify({"username": user})

    # ---------- 配置 ----------

    def _mask_key(key: str) -> str:
        if not key:
            return ""
        return "••••" + key[-4:]

    @app.get("/api/config")
    @require_login
    def get_config() -> Any:
        llm = config.llm()
        llm_view = {
            **llm,
            "has_api_key": secrets_store.has_llm_api_key,
            "api_key_hint": _mask_key(secrets_store.llm_api_key),
        }
        return jsonify({"llm": llm_view, "sources": config.sources()})

    @app.put("/api/config")
    @require_login
    @require_same_origin
    def put_config() -> Any:
        data = body_json()
        llm_in = data.get("llm")
        if isinstance(llm_in, dict):
            patch: dict[str, Any] = {}
            base_url = str(llm_in.get("base_url", "")).strip()
            model = str(llm_in.get("model", "")).strip()
            if "base_url" in llm_in:
                if not base_url.startswith(("http://", "https://")):
                    return jsonify({"error": "bad_url", "message": "API 地址需以 http:// 或 https:// 开头"}), 400
                patch["base_url"] = base_url
            if "model" in llm_in:
                if not model:
                    return jsonify({"error": "bad_model", "message": "模型名不能为空"}), 400
                patch["model"] = model
            if "max_tokens" in llm_in:
                try:
                    patch["max_tokens"] = max(256, int(llm_in["max_tokens"]))
                except (TypeError, ValueError):
                    return jsonify({"error": "bad_tokens", "message": "max_tokens 需为数字"}), 400
            if patch:
                config.set_llm(patch)

        api_key = data.get("api_key")
        if isinstance(api_key, str) and api_key.strip():
            secrets_store.set_llm_api_key(api_key.strip())
        elif data.get("clear_api_key") is True:
            secrets_store.set_llm_api_key("")

        return jsonify({"ok": True})

    @app.post("/api/password")
    @require_login
    @require_same_origin
    def change_password() -> Any:
        data = body_json()
        current = str(data.get("current_password", ""))
        new = str(data.get("new_password", ""))
        if not secrets_store.verify_login(session["user"], current):
            return jsonify({"error": "bad_credentials", "message": "当前密码不正确"}), 401
        if len(new) < 8:
            return jsonify({"error": "weak_password", "message": "新密码至少 8 位"}), 400
        secrets_store.change_password(secrets_store.username, new)
        return jsonify({"ok": True})

    @app.put("/api/sources/<name>")
    @require_login
    @require_same_origin
    def set_source(name: str) -> Any:
        data = body_json()
        config.set_source_enabled(name, bool(data.get("enabled", True)))
        return jsonify({"ok": True})

    # ---------- 任务 ----------

    def _run_env() -> dict[str, str]:
        env = dict(os.environ)
        llm = config.llm()
        if llm["base_url"]:
            env["OPENAI_BASE_URL"] = llm["base_url"]
        if llm["model"]:
            env["ANALYZE_MODEL"] = llm["model"]
        env["ANALYZE_MAX_TOKENS"] = str(llm["max_tokens"])
        if secrets_store.llm_api_key:
            env["OPENAI_API_KEY"] = secrets_store.llm_api_key
        return env

    @app.post("/api/run")
    @require_login
    @require_same_origin
    def run_task() -> Any:
        data = body_json()
        mode = data.get("mode", "today")
        if mode not in ("today", "full"):
            return jsonify({"error": "bad_mode", "message": "mode 需为 today 或 full"}), 400
        env = _run_env()
        if not env.get("OPENAI_API_KEY"):
            return jsonify({"error": "no_api_key", "message": "尚未配置 LLM API Key，请先到「设置」完成 AI 配置"}), 400
        try:
            task = tasks.start(mode, env)
        except TaskRunningError as e:
            running = tasks.running()
            return (
                jsonify({"error": "task_running", "message": str(e), "running": running}),
                409,
            )
        return jsonify({"task": task}), 202

    @app.get("/api/tasks")
    @require_login
    def list_tasks() -> Any:
        return jsonify({"tasks": tasks.list(limit=20)})

    @app.get("/api/tasks/<task_id>")
    @require_login
    def task_detail(task_id: str) -> Any:
        task = tasks.get(task_id)
        if not task:
            return jsonify({"error": "not_found", "message": "任务不存在"}), 404
        return jsonify({"task": {**task, "log_tail": tasks.log_tail(task_id, max_chars=4000)}})

    # ---------- 报告 ----------

    @app.get("/api/reports")
    @require_login
    def reports() -> Any:
        return jsonify({"reports": _report_list(), "summary": _summary(config, secrets_store)})

    @app.get("/api/reports/<name>")
    @require_login
    def report_detail(name: str) -> Any:
        # 仅允许已知报告名，拒绝路径穿越
        stem = Path(name).name
        if stem not in ("analysis", "analysis_today"):
            return jsonify({"error": "not_found", "message": "报告不存在"}), 404
        path = REPORT_DIR / f"{stem}.md"
        if not path.is_file():
            return jsonify({"error": "not_found", "message": "报告不存在，请先运行一次分析"}), 404
        return jsonify(
            {
                "name": path.stem,
                "updated_at": path.stat().st_mtime,
                "content": path.read_text(encoding="utf-8", errors="replace"),
            }
        )

    @app.get("/api/summary")
    @require_login
    def summary() -> Any:
        return jsonify({"summary": _summary(config, secrets_store)})

    # ---------- 静态页面 ----------

    @app.get("/")
    def index() -> Any:
        if not (STATIC_DIR / "index.html").exists():
            return "拾贝 Web：前端未构建，请先构建 frontend 或使用 Docker 镜像。", 503
        return send_from_directory(STATIC_DIR, "index.html")

    @app.errorhandler(404)
    def not_found(_e: Any) -> Any:
        if request.path.startswith("/api/"):
            return jsonify({"error": "not_found", "message": "接口不存在"}), 404
        return index()

    return app


def main() -> None:
    port = int(os.environ.get("SHIBEI_PORT", "8000"))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger.info("拾贝 Web 启动，监听 :%s", port)
    serve(create_app(), host="0.0.0.0", port=port, threads=8)


if __name__ == "__main__":
    main()
