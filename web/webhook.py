"""Webhook 通知：任务完成 / 手动测试时向用户配置的地址发送 JSON。"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from typing import Any

from web import settings as st

logger = logging.getLogger("shibei.webhook")

TIMEOUT_S = 10


def _headers(cfg: dict[str, Any]) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    key = str(cfg.get("header_key", "")).strip()
    token = str(cfg.get("token", ""))
    if key and token:
        headers[key] = token
    return headers


def _post(cfg: dict[str, Any], payload: dict[str, Any]) -> bool:
    url = str(cfg.get("url", "")).strip()
    if not url:
        return False
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers=_headers(cfg))
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            resp.read()
        return True
    except Exception as e:
        logger.warning("Webhook 发送失败：%s", e)
        return False


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
    ok = _post(cfg, payload)
    logger.info("Webhook 通知任务完成：%s（%s）", task.get("status"), "成功" if ok else "发送失败")


def send_test() -> bool:
    """发送测试事件，返回是否送达（无 URL 也返回 False）。"""
    cfg = st.load_webhook()
    payload = {"event": "test", "timestamp": time.time(), "message": "拾贝 Webhook 测试"}
    return _post(cfg, payload)
