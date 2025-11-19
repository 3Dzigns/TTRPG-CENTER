#!/usr/bin/env python3
"""
path_utils.py - Shared helpers for resolving Transfer Station paths.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

DEFAULT_TRANSFER_ROOT = Path("/Transfer_Station")
ENV_TRANSFER_ROOT = "INGESTION_TRANSFER_ROOT"


def _normalize_root(raw_path: str) -> Path:
    """Return expanded path without resolving symlinks (safe for missing dirs)."""
    return Path(raw_path).expanduser()


def get_transfer_root() -> Path:
    """
    Return the Transfer Station root directory.

    Order of precedence:
      1. Environment variable INGESTION_TRANSFER_ROOT
      2. Default /Transfer_Station
    """
    env_value = os.getenv(ENV_TRANSFER_ROOT)
    if env_value:
        return _normalize_root(env_value)
    return DEFAULT_TRANSFER_ROOT


def resolve_transfer_path(*parts: str) -> Path:
    """
    Join the transfer root with additional path parts.

    Args:
        *parts: Path segments relative to the transfer root.

    Returns:
        Path object pointing to the composed location.
    """
    # Allow resolve_transfer_path("Pass_A_Out") or ("Pass_A_Out", "subdir")
    filtered_parts = [segment for segment in parts if segment]
    return get_transfer_root().joinpath(*filtered_parts)


def with_transfer_root(value: Path | None, *default_segments: str) -> Path:
    """
    Ensure a path is anchored under the transfer root when not provided.

    Args:
        value: Explicit path from CLI/config; may be None.
        *default_segments: Default segments relative to the root.

    Returns:
        Path anchored under the transfer root.
    """
    if value:
        return Path(value)
    return resolve_transfer_path(*default_segments)
