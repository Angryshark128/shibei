"""Webhook 通知：任务完成 / 手动测试时向用户配置的地址发送 JSON。"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from web import settings as st

logger = logging.getLogger("shibei.webhook")

TIMEOUT_S = 10


def _headers(cfg: dict[str, Any]) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    # Token 去掉首尾空白：粘贴时常带换行，http.client 会因非法请求头直接抛错
    token = str(cfg.get("token", "")).strip()
    if not token:
        return headers
    # Header 名称留空时按惯例用 Authorization，避免「填了 Token 却没带上」的静默失败
    key = str(cfg.get("header_key", "")).strip() or "Authorization"
    headers[key] = token
    return headers


def _post(cfg: dict[str, Any], payload: dict[str, Any]) -> tuple[bool, str]:
    """POST 一次，返回 (是否送达, 失败原因)；原因带上接收端的真实响应，便于界面提示与排障。"""
    url = str(cfg.get("url", "")).strip()
    if not url:
        return False, "未配置 Webhook 地址"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers=_headers(cfg))
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            resp.read()
        return True, ""
    except urllib.error.HTTPError as e:
        # 4xx/5xx：响应体通常是接收端的错误说明（如 {"error": "bad signature"}）
        try:
            text = e.read(300).decode("utf-8", errors="replace").strip()
        except Exception:
            text = ""
        detail = f"HTTP {e.code} {e.reason}".strip()
        if text:
            detail = f"{detail} · {text}"
        logger.warning("Webhook 发送失败：%s", detail)
        return False, detail
    except Exception as e:
        detail = f"{type(e).__name__}: {e}"
        logger.warning("Webhook 发送失败：%s", detail)
        return False, detail


def send_task_finished(task: dict[str, Any]) -> None:
    cfg = st.load_webhook()
    if not cfg.get("enabled") or not str(cfg.get("url", "")).strip():
        return
    payload = {
        "event": "task.finished",
        "timestamp": time.time(),
        "task": {
            "id": task.get("id"),
            "mode": task.get("mode"),
            "status": task.get("status"),
            "exit_code": task.get("exit_code"),
            "started_at": task.get("started_at"),
            "finished_at": task.get("finished_at"),
        },
    }
    ok, detail = _post(cfg, payload)
    logger.info("Webhook 通知任务完成：%s（%s）", task.get("status"), "成功" if ok else f"发送失败：{detail}")


def send_test() -> tuple[bool, str]:
    """发送测试事件，返回 (是否送达, 失败原因)；无 URL 时也返回 False。"""
    cfg = st.load_webhook()
    message = "拾贝 Webhook 测试" if st.load_report_lang() == "zh" else "Shibei webhook test"
    payload = {"event": "test", "timestamp": time.time(), "message": message}
    return _post(cfg, payload)
