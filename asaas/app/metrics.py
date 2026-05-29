"""Prometheus metrics for asaas-app — HMAC health gauge + /metrics endpoint.

Exposes:
    GET /metrics                       — Prometheus text-format scrape endpoint
    asaas_webhook_hmac_configured      — Gauge: 1 if HMAC configured, 0 otherwise
    asaas_payments_total               — Counter: payment transactions by kind + status
    asaas_webhook_events_total         — Counter: webhook events received
    asaas_http_request_duration_seconds — Histogram: HTTP request latency

Usage:
    from app.metrics import setup_metrics, set_hmac_configured, inc_payment, inc_webhook_event
    setup_metrics(app)
    set_hmac_configured(True)
    inc_payment(kind="pixkey", status="PAID")
"""

from __future__ import annotations

import time

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Gauge, Histogram, generate_latest

_registry = CollectorRegistry()

# ── Gauges ──────────────────────────────────────────────────────────────────

_hmac_gauge = Gauge(
    "asaas_webhook_hmac_configured",
    "1 if Asaas webhook HMAC secret is configured, 0 otherwise",
    registry=_registry,
)


def set_hmac_configured(value: bool) -> None:
    """Set the asaas_webhook_hmac_configured gauge."""
    _hmac_gauge.set(1 if value else 0)


# ── Counters ────────────────────────────────────────────────────────────────

_payments_total = Counter(
    "asaas_payments_total",
    "Payment transactions by kind and status",
    ("kind", "status"),
    registry=_registry,
)

_webhook_events_total = Counter(
    "asaas_webhook_events_total",
    "Webhook events received from Asaas",
    ("event",),
    registry=_registry,
)

_http_duration = Histogram(
    "asaas_http_request_duration_seconds",
    "HTTP request latency for Asaas app",
    ("method", "path"),
    registry=_registry,
)


def inc_payment(kind: str, status: str) -> None:
    """Increment asaas_payments_total for a given kind and status."""
    try:
        _payments_total.labels(kind=kind, status=status).inc()
    except Exception:
        pass


def inc_webhook_event(event: str) -> None:
    """Increment asaas_webhook_events_total for a given event type."""
    try:
        _webhook_events_total.labels(event=event).inc()
    except Exception:
        pass


def observe_http(method: str, path: str, duration: float) -> None:
    """Record HTTP request duration."""
    try:
        _http_duration.labels(method=method, path=path).observe(duration)
    except Exception:
        pass


def _metrics_endpoint(request):
    """Prometheus /metrics scrape endpoint."""
    from starlette.responses import PlainTextResponse

    data = generate_latest(_registry)
    return PlainTextResponse(data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


def setup_metrics(app) -> None:
    """Register /metrics + HTTP duration middleware on the FastAPI app."""
    # /metrics endpoint
    app.add_api_route(
        "/metrics",
        _metrics_endpoint,
        methods=["GET"],
        include_in_schema=False,
    )

    # HTTP duration middleware
    @app.middleware("http")
    async def _metrics_middleware(request, call_next):
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = time.monotonic() - start
            observe_http(request.method, request.url.path, elapsed)
            raise
        elapsed = time.monotonic() - start
        observe_http(request.method, request.url.path, elapsed)
        return response
