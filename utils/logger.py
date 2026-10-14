# -*- coding: utf-8 -*-
"""
Logging Framework for SEC PAC Hydraulic Pitch HMI
Provides structured, rotating log file output and console logging,
with custom exception classes for OPC UA write and telemetry failures.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Any

from config import (
    LOG_DIR, LOG_FILE_PATH, LOG_MAX_BYTES, LOG_BACKUP_COUNT, LOG_LEVEL
)


class OpcUaWriteError(Exception):
    """
    Raised when an OPC UA write command fails (e.g. BadTypeMismatch, BadNodeIdUnknown).
    Carries command name, attempted value, and underlying asyncua error.
    """
    def __init__(self, cmd_name: str, value: Any, original_error: Exception):
        self.cmd_name = cmd_name
        self.value = value
        self.original_error = original_error
        super().__init__(f"OPC UA command '{cmd_name}' failed with value '{value}': {original_error}")


_initialized = False


def setup_logging():
    """Ensure log directory exists and root logging handlers are configured once."""
    global _initialized
    if _initialized:
        return

    os.makedirs(LOG_DIR, exist_ok=True)

    # Truncate existing log file so every application startup starts with a clean log
    try:
        with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
            pass
    except Exception:
        pass

    level_num = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)-7s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File Handler (UTF-8, rotating)
    file_handler = RotatingFileHandler(
        LOG_FILE_PATH,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level_num)

    # Console Stream Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level_num)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level_num)

    # Avoid duplicate handlers
    if not root_logger.handlers:
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

    # Suppress verbose asyncua internal protocol noise unless warning or error
    logging.getLogger("asyncua").setLevel(logging.WARNING)

    _initialized = True


def get_logger(name: str = "hmi") -> logging.Logger:
    """Return a configured logger with standard formatting and file output."""
    setup_logging()
    return logging.getLogger(name)
