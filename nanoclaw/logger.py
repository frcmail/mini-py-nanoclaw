from __future__ import annotations

import logging
import os


def _resolve_level() -> int:
    raw = os.getenv("LOG_LEVEL", "INFO").upper()
    return {
        "TRACE": logging.DEBUG,
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARN": logging.WARNING,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "FATAL": logging.CRITICAL,
        "CRITICAL": logging.CRITICAL,
    }.get(raw, logging.INFO)


def get_logger(name: str = "nanoclaw") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(_resolve_level())
    logger.propagate = False
    return logger


logger = get_logger()
