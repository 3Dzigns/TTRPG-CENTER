"""Timezone-aware datetime helpers."""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_now_isoformat(with_z: bool = False) -> str:
    """
    Return ISO 8601 representation of utc_now.

    Args:
        with_z: If True, replace +00:00 with Z for compatibility.
    """
    iso = utc_now().isoformat()
    if with_z:
        return iso.replace("+00:00", "Z")
    return iso
