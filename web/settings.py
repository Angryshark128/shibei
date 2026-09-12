"""拾贝 Web 扩展配置存储（调度 / Webhook）。

与 config.json（sources + llm）分离，避免把 UI 扩展配置同步进仓库 config.json。
文件全部落在 data/ 下（0600）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
SCHEDULE_FILE = DATA_DIR / "web_schedule.json"
WEBHOOK_FILE = DATA_DIR / "webhook.json"

DEFAULT_SCHEDULE: dict[str, Any] = {"enabled": True, "time": "00:00"}
DEFAULT_WEBHOOK: dict[str, Any] = {"enabled": False, "url": "", "header_key": "", "token": ""}


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(path)


# ---------- 每日定时调度 ----------


def load_schedule() -> dict[str, Any]:
    data = dict(DEFAULT_SCHEDULE)
    data.update(_read_json(SCHEDULE_FILE, {}))
    return data


def save_schedule(enabled: bool | None = None, time: str | None = None) -> dict[str, Any]:
    data = load_schedule()
    if enabled is not None:
        data["enabled"] = bool(enabled)
    if time is not None:
        data["time"] = time
    _write_json(SCHEDULE_FILE, data)
    return data


def mark_schedule_fired(today: str) -> None:
    data = load_schedule()
    data["last_fired"] = today
    _write_json(SCHEDULE_FILE, data)


# ---------- Webhook ----------


def load_webhook() -> dict[str, Any]:
    data = dict(DEFAULT_WEBHOOK)
    data.update(_read_json(WEBHOOK_FILE, {}))
    return data


def save_webhook(
    enabled: bool | None = None,
    url: str | None = None,
    header_key: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    data = load_webhook()
    if enabled is not None:
        data["enabled"] = bool(enabled)
    if url is not None:
        data["url"] = url
    if header_key is not None:
        data["header_key"] = header_key
    if token is not None:
        data["token"] = token
    _write_json(WEBHOOK_FILE, data)
    return data


# ---------- 报告语言 ----------


REPORT_LANGS = ("zh", "en")
REPORT_LANG_FILE = DATA_DIR / "web_report_lang.json"


def load_report_lang() -> str:
    """Web 报告生成语言（zh/en），供手动/定时任务触发时传给 analyzer。默认 zh。"""
    data = _read_json(REPORT_LANG_FILE, {})
    lang = str(data.get("lang", "zh"))
    return lang if lang in REPORT_LANGS else "zh"


def save_report_lang(lang: str) -> None:
    if lang not in REPORT_LANGS:
        raise ValueError(f"未知报告语言: {lang}")
    _write_json(REPORT_LANG_FILE, {"lang": lang})
