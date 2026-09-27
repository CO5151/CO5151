"""Structured logger configuration for LegalPilot-VN."""

import logging
import sys


def setup_logger(name: str = "legalpilot", level: str = "INFO") -> logging.Logger:
    """Configures and returns a structured logger instance."""
    logger = logging.getLogger(name)

    # Prevent duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


# Default application logger instance
logger = setup_logger()
get_logger = setup_logger
