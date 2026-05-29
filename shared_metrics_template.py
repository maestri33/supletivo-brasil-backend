"""Prometheus metrics setup for Supletivo microservices.

Usage in main.py:
    from app.metrics import setup_metrics
    setup_metrics(app, "service_name")
"""

from __future__ import annotations

import time
from typing import Callable

try:
    import prometheus_client
    from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest
except ImportError:
    prometheus_client = None

    def _stub(*args, **kwargs):
        return 0.0

    CollectorRegistry = _stub
    Counter = _stub
    Gauge = _stub
    Histogram = _stub
    CONTENT_TYPE_LATEST = "text/plain"
    generate_latest = _stub


_registry: CollectorRegistry | None = None


def _get_registry() -> CollectorRegistry:
    global _registry
    if _registry is None:
        if prometheus_client is not None:
            _registry = CollectorRegistry()
    return _registry


def _make_counter(name: str, doc: str, labels: tuple[str, ...]) -> Counter | Callable:
    if prometheus_client is None:
        return _stub
    return Counter(name, doc, labels, registry=_get_registry())


def _make_histogram(name: str, doc: str, labels: tuple[str, ...]) -> Histogram | Callable:
    if prometheus_client is None:
        return _stub
    return Histogram(name, doc, labels, registry=_get_registry())


# ── Generic per-service metrics ──

_http_requests_total: Counter | Callable | None = None
_http_request_duration_seconds: Histogram | Callable | None = None
_health_checks_total: Counter | Callable | None = None


def setup_metrics(app, service: str) -> None:
    """Wire /metrics endpoint and HTTP middleware into a FastAPI app.

    Args:
        app: FastAPI application instance
        service: Service name (e.g., "auth", "hub", "candidate")
    """
    global _http_requests_total, _http_request_duration_seconds, _health_checks_total

    # Metrics are shared globally — only create once
    if _http_requests_total is None:
        _http_requests_total = _make_counter(
            f"{service}_http_requests_total",
            f"Total HTTP requests for {service}",
            ("method", "path", "status"),
        )
        _http_request_duration_seconds = _make_histogram(
            f"{service}_http_request_duration_seconds",
            f"HTTP request duration for {service}",
            ("method", "path"),
        )
        _health_checks_total = _make_counter(
            f"{service}_health_checks_total",
            f"Total health checks for {service}",
            ("status",),
        )

    # ── /metrics endpoint ──
    def _metrics(request):
        from starlette.responses import Response

        if prometheus_client is None:
            return Response("prometheus_client not installed\n", status_code=503, media_type="text/plain")
        try:
            data = generate_latest(_get_registry())
            return Response(content=data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
        except Exception:
            return Response("error generating metrics\n", status_code=500, media_type="text/plain")

    app.add_api_route("/metrics", _metrics, methods=["GET"], include_in_schema=False)

    # ── HTTP duration middleware ──
    @app.middleware("http")
    async def _metrics_middleware(request, call_next):
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = time.monotonic() - start
            if _http_request_duration_seconds is not None:
                try:
                    _http_request_duration_seconds.labels(method=request.method, path=request.url.path).observe(elapsed)
                except Exception:
                    pass
            raise
        elapsed = time.monotonic() - start
        if _http_request_duration_seconds is not None and _http_requests_total is not None:
            try:
                _http_request_duration_seconds.labels(method=request.method, path=request.url.path).observe(elapsed)
                _http_requests_total.labels(method=request.method, path=request.url.path, status=str(response.status_code)).inc()
            except Exception:
                pass
        return response
