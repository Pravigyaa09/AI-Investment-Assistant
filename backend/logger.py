"""
logger.py - Centralized logging configuration for Python backend project

Usage:
    from logger import get_logger
    logger = get_logger(__name__)
    logger.info("This is an info message")
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'
    }

    def format(self, record):
        if hasattr(record, '_console_output'):
            level_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            reset_color = self.COLORS['RESET']
            record.levelname = f"{level_color}{record.levelname}{reset_color}"
        return super().format(record)


def setup_logging():
    logs_dir = Path(__file__).resolve().parent / 'logs'
    logs_dir.mkdir(exist_ok=True)

    today = datetime.now().strftime('%Y-%m-%d')
    log_file = logs_dir / f'backend_{today}.log'

    log_format = '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColoredFormatter(log_format, date_format))

    def add_console_marker(record):
        record._console_output = True
        return True

    console_handler.addFilter(add_console_marker)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    root_logger.info(f"Logging initialized. Log file: {log_file}")
    return root_logger


def get_logger(name=None):
    if name is None:
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')

    logger = logging.getLogger(name)

    if not logging.getLogger().handlers:
        setup_logging()

    return logger


def log_exception(logger, message="An exception occurred"):
    logger.exception(message)


# Quick logging functions
def info(message, logger_name='quick'):
    get_logger(logger_name).info(message)

def warning(message, logger_name='quick'):
    get_logger(logger_name).warning(message)

def error(message, logger_name='quick'):
    get_logger(logger_name).error(message)

def debug(message, logger_name='quick'):
    get_logger(logger_name).debug(message)


if not logging.getLogger().handlers:
    setup_logging()


if __name__ == "__main__":
    logger = get_logger(__name__)
    logger.info("Logger test started")
    logger.debug("Debug message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical message")

    try:
        1 / 0
    except Exception:
        log_exception(logger, "Division error")

    print(f"\nLog file created in: logs/backend_{datetime.now().strftime('%Y-%m-%d')}.log")
