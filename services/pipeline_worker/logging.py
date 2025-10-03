"""
Logging configuration for pipeline-worker service.
"""

import logging
import sys
from .config import config


def get_logger(name: str) -> logging.Logger:
    """
    Get configured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)

    # Set level from config
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Only add handler if logger doesn't have one
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)

        # Format
        if config.structured_logging:
            formatter = logging.Formatter(
                '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                '"service": "pipeline-worker", "module": "%(name)s", '
                '"message": "%(message)s"}'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger