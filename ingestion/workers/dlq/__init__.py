"""DLQ worker."""

from .tasks import record_failure

__all__ = ["record_failure"]
