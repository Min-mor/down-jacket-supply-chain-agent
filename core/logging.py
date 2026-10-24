"""结构化日志。

默认输出 JSON Lines，便于采集（Loki / ELK / 云日志）。每个请求通过
contextvars 携带 request_id，贯穿整条调用链。
"""
from __future__ import annotations

import json
import logging
import sys
import time
from contextvars import ContextVar

from .config import settings

_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(rid: str) -> None:
    _request_id.set(rid)


def get_request_id() -> str:
    return _request_id.get()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "request_id": get_request_id(),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("agent")
    if logger.handlers:  # 避免重复添加
        return logger
    handler = logging.StreamHandler(sys.stdout)
    if settings.log_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s [%(request_id)s] %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(settings.log_level.upper())
    logger.propagate = False
    return logger


log = setup_logging()
