"""Prometheus metrics for promoter."""

from __future__ import annotations

import time

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Histogram,
        generate_latest,
    )
except ImportError:
    prometheus_client = None  # type: ignore[assignment]
    CONTENT_TYPE_LATEST = "text/plain"

    def generate_latest(*args, **kwargs):
        return b""

    def _noop(*args, **kwargs):
        pass

    CollectorRegistry = _noop
    Counter = _noop
    Histogram = _noop


_registry: CollectorRegistry | None = None


def _get_registry() -> CollectorRegistry:
    global _registry
    if _registry is None:
        try:
            _registry = CollectorRegistry()
        except Exception:
            pass
    return _registry


_http_requests_total = None
_http_request_duration_seconds = None


def setup_metrics(app) -> None:
    """Register /metrics endpoint and HTTP duration middleware."""

    # Create metrics lazily
    global _http_requests_total, _http_request_duration_seconds
    if _http_requests_total is None:
        try:
            _http_requests_total = Counter(
                "promoter_http_requests_total",
                "Total HTTP requests",
                ("method", "path", "status"),
                registry=_get_registry(),
            )
            _http_request_duration_seconds = Histogram(
                "promoter_http_request_duration_seconds",
                "HTTP request duration",
                ("method", "path"),
                registry=_get_registry(),
            )
        except Exception:
            pass

    # /metrics endpoint
    def _metrics_endpoint(request):
        from starlette.responses import Response

        try:
            data = generate_latest(_get_registry())
            return Response(content=data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
        except Exception:
            return Response("# error\n", status_code=500, media_type="text/plain")

    app.add_api_route("/metrics", _metrics_endpoint, methods=["GET"], include_in_schema=False)

    # HTTP duration middleware
    @app.middleware("http")
    async def _middleware(request, call_next):
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = time.monotonic() - start
            if _http_request_duration_seconds is not None:
                try:
                    _http_request_duration_seconds.labels(
                        method=request.method, path=request.url.path
                    ).observe(elapsed)
                except Exception:
                    pass
            raise
        elapsed = time.monotonic() - start
        if _http_request_duration_seconds is not None and _http_requests_total is not None:
            try:
                _http_request_duration_seconds.labels(
                    method=request.method, path=request.url.path
                ).observe(elapsed)
                _http_requests_total.labels(
                    method=request.method, path=request.url.path, status=str(response.status_code)
                ).inc()
            except Exception:
                pass
        return response
