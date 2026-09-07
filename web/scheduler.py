"""每日定时调度：每天 HH:MM（服务器本地时区）触发一次增量分析。"""

from __future__ import annotations

import datetime as dt
import logging
import threading
from collections.abc import Callable
from typing import Any

from web import settings as st

logger = logging.getLogger("shibei.schedule")

CHECK_INTERVAL_S = 20


class DailyScheduler:
    """单实例守护线程；同一天同一时刻只触发一次（last_fired 落盘防重启重复）。"""

    def __init__(self, trigger: Callable[[], Any]) -> None:
        self._trigger = trigger
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="shibei-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        logger.info("定时调度已启动（默认每天 00:00 增量分析，可在设置中调整）")
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:  # 循环永不死
                logger.exception("调度循环异常")
            self._stop.wait(CHECK_INTERVAL_S)

    def _tick(self) -> None:
        cfg = st.load_schedule()
        if not cfg.get("enabled"):
            return
        target = str(cfg.get("time") or "00:00")
        now = dt.datetime.now()
        today = now.date().isoformat()
        if now.strftime("%H:%M") != target:
            return
        if cfg.get("last_fired") == today:
            return  # 今天已触发过（含重启后）
        logger.info("定时任务触发：每天 %s 增量分析", target)
        try:
            self._trigger()
        except Exception as e:  # 触发失败（无 key / 已有任务等）也防重复，次日再试
            logger.warning("定时任务触发失败：%s", e)
        finally:
            st.mark_schedule_fired(today)
