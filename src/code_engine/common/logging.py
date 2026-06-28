"""Package logger factory without global logging reconfiguration."""

import logging


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"code_engine.{name}")

