"""Prometheus metrics middleware + /metrics endpoint for money-path services.

Usage (Asaas / InfinitePay):
    from shared_metrics import setup_metrics
    app = FastAPI(...)
    setup_metrics(app, service="asaas")

Exposes:
    GET /metrics           — Prometheus text format scrape endpoint
    asaas_payments_total   — Counter: payments by kind + status
    asaas_webhook_events_total — Counter: webhook events by event type
    asaas_http_request_duration_seconds — Histogram: HTTP request latency
    asaas_webhook_hmac_configured — Gauge: 1 if HMAC configured, 0 otherwise
    infinitepay_checkouts_total — Counter: checkouts by status
    infinitepay_webhook_security_configured — Gauge: 1 if secure, 0 otherwise

Counters are incremented via module-level functions; the metrics module
re-exports the same Prometheus objects so callers don't need to import
prometheus_client directly.
"""

from __future__ import annotations

import time
from typing import Callable

try:
    import prometheus_client  # type: ignore[import-untyped]
    from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
    from prometheus_client import Counter as PromCounter
    from prometheus_client import Gauge as PromGauge
    from prometheus_client import Histogram as PromHistogram
except ImportError:
    prometheus_client = None  # type: ignore[assignment]


def _allow_any_callable() -> Callable[..., object]:
    """Stub for type-checking when prometheus_client is not installed."""

    def stub(*args: object, **kwargs: object) -> object:
        return 0.0

    return stub


# ── Registry (one per service per process) ──────────────────────────────────


_registry: CollectorRegistry | None = None
_service_name: str = "asaas"


def _get_registry() -> CollectorRegistry:
    global _registry  # noqa: PLW0603
    if _registry is None:
        _registry = CollectorRegistry()
    return _registry


# ── Counters ────────────────────────────────────────────────────────────────


def _make_counter(name: str, doc: str, labels: tuple[str, ...]) -> PromCounter:
    if prometheus_client is None:
        return _allow_any_callable()  # type: ignore[return-value]
    return PromCounter(name, doc, labels, registry=_get_registry())


def _make_gauge(name: str, doc: str) -> PromGauge:
    if prometheus_client is None:
        return _allow_any_callable()  # type: ignore[return-value]
    return PromGauge(name, doc, registry=_get_registry())


def _make_histogram(name: str, doc: str, labels: tuple[str, ...]) -> PromHistogram:
    if prometheus_client is None:
        return _allow_any_callable()  # type: ignore[return-value]
    return PromHistogram(name, doc, labels, registry=_get_registry())


# ── metric objects ──────────────────────────────────────────────────────────


asaas_payments = _make_counter(
    "asaas_payments_total",
    "Payment transactions by kind and status",
    ("kind", "status"),
)

asaas_webhook_events = _make_counter(
    "asaas_webhook_events_total",
    "Webhook events received from Asaas",
    ("event",),
)

asaas_http_duration = _make_histogram(
    "asaas_http_request_duration_seconds",
    "HTTP request latency for Asaas app",
    ("method", "path"),
)

asaas_hmac_gauge = _make_gauge(
    "asaas_webhook_hmac_configured",
    "1 if Asaas webhook HMAC secret is configured, 0 otherwise",
)

infinitepay_checkouts = _make_counter(
    "infinitepay_checkouts_total",
    "Checkout transactions by status",
    ("status",),
)

infinitepay_webhook_events = _make_counter(
    "infinitepay_webhook_events_total",
    "Webhook events received from InfinitePay",
    ("event",),
)

infinitepay_http_duration = _make_histogram(
    "infinitepay_http_request_duration_seconds",
    "HTTP request latency for InfinitePay app",
    ("method", "path"),
)

infinitepay_security_gauge = _make_gauge(
    "infinitepay_webhook_security_configured",
    "1 if InfinitePay webhook security (HMAC + CIDRs) is fully configured, 0 otherwise",
)


# ── update helpers (call from service code) ─────────────────────────────────


def inc_payment(kind: str, status: str) -> None:
    """Increment asaas_payments_total for a given kind and status."""
    try:
        asaas_payments.labels(kind=kind, status=status).inc()
    except Exception:
        pass


def inc_webhook_event(event: str) -> None:
    """Increment asaas_webhook_events_total for a given event type."""
    try:
        asaas_webhook_events.labels(event=event).inc()
    except Exception:
        pass


def observe_http(method: str, path: str, duration: float) -> None:
    """Record HTTP request duration for Asaas endpoints."""
    try:
        asaas_http_duration.labels(method=method, path=path).observe(duration)
    except Exception:
        pass


def set_hmac_configured(value: bool) -> None:
    """Set asaas_webhook_hmac_configured gauge."""
    try:
        asaas_hmac_gauge.set(1 if value else 0)
    except Exception:
        pass


def inc_infinitepay_checkout(status: str) -> None:
    """Increment infinitepay_checkouts_total for a given status."""
    try:
        infinitepay_checkouts.labels(status=status).inc()
    except Exception:
        pass


def inc_infinitepay_webhook_event(event: str) -> None:
    """Increment infinitepay_webhook_events_total for a given event type."""
    try:
        infinitepay_webhook_events.labels(event=event).inc()
    except Exception:
        pass


def observe_infinitepay_http(method: str, path: str, duration: float) -> None:
    """Record HTTP request duration for InfinitePay endpoints."""
    try:
        infinitepay_http_duration.labels(method=method, path=path).observe(duration)
    except Exception:
        pass


def set_infinitepay_security_configured(value: bool) -> None:
    """Set infinitepay_webhook_security_configured gauge."""
    try:
        infinitepay_security_gauge.set(1 if value else 0)
    except Exception:
        pass


# ── Metrics endpoint ────────────────────────────────────────────────────────


def metrics_response() -> tuple[str, int, dict[str, str]]:
    """Generate Prometheus scrape response."""
    if prometheus_client is None:
        return ("prometheus_client not installed\n", 503, {"content-type": "text/plain"})
    try:
        data = generate_latest(_get_registry())
        return data.decode("utf-8"), 200, {"content-type": CONTENT_TYPE_LATEST}
    except Exception:
        return ("error generating metrics\n", 500, {"content-type": "text/plain"})


# ── FastAPI middleware + endpoint ───────────────────────────────────────────


def setup_metrics(app, service: str | None = None) -> None:
    """Wire /metrics endpoint and HTTP duration middleware into a FastAPI app.

    Args:
        app: FastAPI application instance
        service: Optional service name override. When None, uses _service_name.
    """
    global _service_name  # noqa: PLW0603
    svc = service or _service_name

    # ── /metrics endpoint ──
    def _metrics(request):
        from starlette.responses import Response

        body, status, headers = metrics_response()
        return Response(content=body, status_code=status, media_type=headers["content-type"])

    # Register at module level — callers wire it to their router
    app.add_api_route("/metrics", _metrics, methods=["GET"], include_in_schema=False)

    # ── HTTP duration middleware ──
    @app.middleware("http")
    async def _metrics_middleware(request, call_next):
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = time.monotonic() - start
            if svc == "asaas":
                observe_http(request.method, request.url.path, elapsed)
            elif svc == "infinitepay":
                observe_infinitepay_http(request.method, request.url.path, elapsed)
            raise
        elapsed = time.monotonic() - start
        if svc == "asaas":
            observe_http(request.method, request.url.path, elapsed)
        elif svc == "infinitepay":
            observe_infinitepay_http(request.method, request.url.path, elapsed)
        return response
