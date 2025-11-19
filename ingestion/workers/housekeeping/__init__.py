"""Housekeeping worker placeholder."""

__all__ = ["finalize_job"]


def __getattr__(name):
    if name == "finalize_job":
        from .tasks import finalize_job as _finalize

        return _finalize
    raise AttributeError(name)
