"""Prometheus metrics for asaas-app — HMAC health gauge + /metrics endpoint.

Exposes:
    GET /metrics    — Prometheus text-format scrape endpoint
    asaas_webhook_hmac_configured — Gauge: 1 if HMAC configured, 0 otherwise

Usage:
    from app.metrics import setup_metrics, set_hmac_configured
    setup_metrics(app)
    set_hmac_configured(True)
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, generate_latest

_registry = CollectorRegistry()

_hmac_gauge = Gauge(
    "asaas_webhook_hmac_configured",
    "1 if Asaas webhook HMAC secret is configured, 0 otherwise",
    registry=_registry,
)


def set_hmac_configured(value: bool) -> None:
    """Set the asaas_webhook_hmac_configured gauge."""
    _hmac_gauge.set(1 if value else 0)


def _metrics_endpoint(request):
    """Prometheus /metrics scrape endpoint."""
    from starlette.responses import PlainTextResponse

    data = generate_latest(_registry)
    return PlainTextResponse(data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


def setup_metrics(app) -> None:
    """Register /metrics endpoint on the FastAPI app."""
    app.add_api_route(
        "/metrics",
        _metrics_endpoint,
        methods=["GET"],
        include_in_schema=False,
    )
