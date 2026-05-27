"""Prometheus metrics for infinitepay — webhook security gauge + business counters.

Exposes:
    GET /metrics                              — Prometheus text-format scrape endpoint
    infinitepay_checkouts_total               — Counter: checkout transactions by status
    infinitepay_webhook_events_total          — Counter: webhook events received
    infinitepay_http_request_duration_seconds — Histogram: HTTP request latency
    infinitepay_webhook_security_configured   — Gauge: 1 if fully secure, 0 otherwise

Usage:
    from app.metrics import setup_metrics, inc_checkout, inc_webhook_event
    setup_metrics(app)
    inc_checkout(status="paid")
"""
from __future__ import annotations

import time

try:
    from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest
except ImportError:
    prometheus_client = None  # type: ignore[assignment]
    CONTENT_TYPE_LATEST = "text/plain"

    def generate_latest(*args, **kwargs):
        return b""

    def _noop(*args, **kwargs):
        pass

    CollectorRegistry = _noop
    Counter = _noop
    Gauge = _noop
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


_checkouts_total = None
_webhook_events_total = None
_http_duration = None
_security_gauge = None


def setup_metrics(app) -> None:
    """Register /metrics endpoint and HTTP duration middleware."""
    global _checkouts_total, _webhook_events_total, _http_duration, _security_gauge

    if _checkouts_total is None:
        try:
            _checkouts_total = Counter(
                "infinitepay_checkouts_total",
                "Checkout transactions by status",
                ("status",),
                registry=_get_registry(),
            )
            _webhook_events_total = Counter(
                "infinitepay_webhook_events_total",
                "Webhook events received from InfinitePay",
                ("event",),
                registry=_get_registry(),
            )
            _http_duration = Histogram(
                "infinitepay_http_request_duration_seconds",
                "HTTP request latency for InfinitePay app",
                ("method", "path"),
                registry=_get_registry(),
            )
            _security_gauge = Gauge(
                "infinitepay_webhook_security_configured",
                "1 if InfinitePay webhook security (HMAC + CIDRs) is fully configured, 0 otherwise",
                registry=_get_registry(),
            )
        except Exception:
            pass

    def _metrics_endpoint(request):
        from starlette.responses import Response

        try:
            data = generate_latest(_get_registry())
            return Response(content=data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
        except Exception:
            return Response("# error\n", status_code=500, media_type="text/plain")

    app.add_api_route("/metrics", _metrics_endpoint, methods=["GET"], include_in_schema=False)

    @app.middleware("http")
    async def _middleware(request, call_next):
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = time.monotonic() - start
            if _http_duration is not None:
                try:
                    _http_duration.labels(method=request.method, path=request.url.path).observe(elapsed)
                except Exception:
                    pass
            raise
        elapsed = time.monotonic() - start
        if _http_duration is not None:
            try:
                _http_duration.labels(method=request.method, path=request.url.path).observe(elapsed)
            except Exception:
                pass
        return response


def inc_checkout(status: str) -> None:
    """Increment infinitepay_checkouts_total for a given status."""
    global _checkouts_total
    if _checkouts_total is not None:
        try:
            _checkouts_total.labels(status=status).inc()
        except Exception:
            pass


def inc_webhook_event(event: str) -> None:
    """Increment infinitepay_webhook_events_total for a given event type."""
    global _webhook_events_total
    if _webhook_events_total is not None:
        try:
            _webhook_events_total.labels(event=event).inc()
        except Exception:
            pass


def set_security_configured(value: bool) -> None:
    """Set infinitepay_webhook_security_configured gauge."""
    global _security_gauge
    if _security_gauge is not None:
        try:
            _security_gauge.set(1 if value else 0)
        except Exception:
            pass
