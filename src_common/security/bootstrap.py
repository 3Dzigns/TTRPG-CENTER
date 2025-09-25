"""Security, observability, and audit bootstrap utilities for services."""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src_common.auth_middleware import AuthMiddleware
from src_common.auth_models import UserContext
from src_common.config import get_environment_config
from src_common.logging import get_logger

logger = get_logger(__name__)

_auth_middleware_singleton: Optional[AuthMiddleware] = None
_token_extractor = HTTPBearer(auto_error=False)


DEFAULT_RATE_LIMIT = {
    "window_seconds": 60,
    "max_requests": 120,
}

SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer-when-downgrade",
    "X-XSS-Protection": "1; mode=block",
}


def _get_auth_middleware() -> AuthMiddleware:
    global _auth_middleware_singleton
    if _auth_middleware_singleton is None:
        _auth_middleware_singleton = AuthMiddleware()
    return _auth_middleware_singleton


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach environment-specific security headers to responses."""

    def __init__(self, app: ASGIApp, *, hsts_enabled: bool) -> None:
        super().__init__(app)
        self._hsts_enabled = hsts_enabled

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        response: Response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        if self._hsts_enabled:
            response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
        return response


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Simple in-memory, per-identity rate limiting middleware."""

    def __init__(self, app: ASGIApp, *, window_seconds: int, max_requests: int) -> None:
        super().__init__(app)
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self._buckets: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        identity = self._resolve_identity(request)
        if identity:
            async with self._lock:
                now = time.monotonic()
                bucket = self._buckets[identity]
                while bucket and now - bucket[0] > self.window_seconds:
                    bucket.popleft()
                if len(bucket) >= self.max_requests:
                    return Response(
                        status_code=429,
                        content=json.dumps({"detail": "Rate limit exceeded"}),
                        media_type="application/json",
                        headers={
                            "Retry-After": str(int(self.window_seconds / max(1, self.max_requests))),
                            "X-RateLimit-Limit": str(self.max_requests),
                            "X-RateLimit-Reset": str(int(self.window_seconds)),
                        },
                    )
                bucket.append(now)
        response: Response = await call_next(request)
        if identity:
            response.headers.setdefault("X-RateLimit-Limit", str(self.max_requests))
            response.headers.setdefault("X-RateLimit-Window", str(self.window_seconds))
        return response

    def _resolve_identity(self, request: Request) -> str:
        user: Optional[UserContext] = request.state.__dict__.get("user_context")  # type: ignore[attr-defined]
        if user and user.user_id:
            return f"user:{user.user_id}"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        client = request.client
        if client:
            return f"ip:{client.host}"
        return ""


class AuditLogger:
    """Append structured audit events under env/<env>/logs/audit."""

    def __init__(self, environment: str) -> None:
        base_dir = Path(f"env/{environment}/logs/audit")
        base_dir.mkdir(parents=True, exist_ok=True)
        self._path = base_dir / f"audit-{time.strftime('%Y%m%d')}.log"
        self._lock = asyncio.Lock()

    async def write(self, event: Dict[str, Any]) -> None:
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **event,
        }
        async with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload) + "\n")


def _configure_cors(app: FastAPI, environment: str, config: Dict[str, Any]) -> None:
    cors_overrides = config or {}
    allow_origins: Iterable[str] = cors_overrides.get("allow_origins") or (
        ["http://localhost:3000", "http://localhost:5173"] if environment == "dev" else ["https://admin.ttrpg-center.com"]
    )
    allow_methods: Iterable[str] = cors_overrides.get("allow_methods") or ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers: Iterable[str] = cors_overrides.get("allow_headers") or ["Authorization", "Content-Type", "X-Requested-With"]
    allow_credentials: bool = bool(cors_overrides.get("allow_credentials", environment != "prod"))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allow_origins),
        allow_methods=list(allow_methods),
        allow_headers=list(allow_headers),
        allow_credentials=allow_credentials,
    )


def bootstrap_app_security(app: FastAPI, *, service_name: str) -> AuditLogger:
    """Attach security, observability, and audit middleware to a FastAPI app."""

    env_config = get_environment_config()
    environment = env_config.get("environment", "dev")
    security_config = env_config.get("security", {})
    rate_limit_cfg = security_config.get("rate_limit", DEFAULT_RATE_LIMIT)

    _configure_cors(app, environment, security_config.get("cors", {}))

    auth_middleware = _get_auth_middleware()

    @app.middleware("http")
    async def inject_user_context(request: Request, call_next: Callable[[Request], Any]) -> Response:  # type: ignore[override]
        credentials = await _token_extractor(request)
        request.state.user_context = await auth_middleware.get_current_user(credentials)  # type: ignore[attr-defined]
        response = await call_next(request)
        return response

    app.dependency_overrides.setdefault(auth_middleware.require_auth, auth_middleware.require_auth)

    app.add_middleware(
        SecurityHeadersMiddleware,
        hsts_enabled=environment in {"test", "prod"},
    )
    app.add_middleware(
        RateLimiterMiddleware,
        window_seconds=int(rate_limit_cfg.get("window_seconds", DEFAULT_RATE_LIMIT["window_seconds"])),
        max_requests=int(rate_limit_cfg.get("max_requests", DEFAULT_RATE_LIMIT["max_requests"])),
    )

    enable_tracing(app, environment, service_name)

    audit_logger = AuditLogger(environment)
    app.state.audit_logger = audit_logger  # type: ignore[attr-defined]
    return audit_logger


def enable_tracing(app: FastAPI, environment: str, service_name: str) -> None:
    """Enable OpenTelemetry FastAPI instrumentation if configured."""

    env_config = get_environment_config()
    flags = env_config.get("flags", {})
    otel_enabled = bool(flags.get("opentelemetry", False))
    if not otel_enabled:
        logger.info("OpenTelemetry disabled via flags")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:  # pragma: no cover - optional dependency
        logger.warning("OpenTelemetry packages not available; skipping instrumentation")
        return

    endpoint = env_config.get("observability", {}).get("otlp_endpoint")
    if not endpoint:
        endpoint = env_config.get("OTLP_ENDPOINT") or env_config.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    exporter = OTLPSpanExporter(endpoint=endpoint) if endpoint else OTLPSpanExporter()
    resource = Resource.create({"service.name": service_name, "deployment.environment": environment})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    logger.info("OpenTelemetry instrumentation enabled", extra={"service": service_name, "env": environment})


async def record_audit_event(request: Request, event: Dict[str, Any]) -> None:
    """Helper to record audit events from within request handlers."""

    audit_logger = getattr(request.app.state, "audit_logger", None)  # type: ignore[attr-defined]
    if not audit_logger:
        return

    user: Optional[UserContext] = getattr(request.state, "user_context", None)
    payload = {
        "event": event.get("event", "unknown"),
        "user": user.username if user else None,
        "user_id": user.user_id if user else None,
        "path": request.url.path,
        "method": request.method,
        **event,
    }
    await audit_logger.write(payload)


def require_roles(*roles: str):
    """FastAPI dependency enforcing that the current user carries one of the specified roles."""

    async def _dependency(
        request: Request,
        _: UserContext = Depends(_get_auth_middleware().require_auth),
    ) -> UserContext:
        user: Optional[UserContext] = getattr(request.state, "user_context", None)
        if not user:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        if roles:
            allowed = {role.lower() for role in roles}
            user_role = getattr(user.role, "value", user.role).lower() if user.role else ""
            if user_role not in allowed:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return _dependency


__all__ = [
    "bootstrap_app_security",
    "enable_tracing",
    "record_audit_event",
    "require_roles",
]
