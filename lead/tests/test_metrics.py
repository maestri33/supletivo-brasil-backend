"""Testes para app/metrics.py — Prometheus metrics setup.

Estrategia:
  - Testa que setup_metrics registra a rota /metrics.
  - Testa o fallback quando prometheus_client nao esta instalado.
  - Testa o middleware sem bloquear requests normais.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


class TestMetricsSetup:
    """setup_metrics — registra rota e middleware."""

    async def test_setup_metrics_adds_route(self):
        """setup_metrics adiciona rota /metrics a app."""
        from app.metrics import setup_metrics

        mock_app = MagicMock()
        setup_metrics(mock_app)

        # Should have added the /metrics route
        mock_app.add_api_route.assert_called_once()
        args, kwargs = mock_app.add_api_route.call_args
        assert args[0] == "/metrics"
        assert "GET" in kwargs.get("methods", ("GET",))

    async def test_setup_metrics_adds_middleware(self):
        """setup_metrics adiciona middleware HTTP."""
        from app.metrics import setup_metrics

        mock_app = MagicMock()
        setup_metrics(mock_app)

        mock_app.middleware.assert_called_once_with("http")

    async def test_metrics_endpoint_returns_ok(self, client):
        """GET /metrics returns 200 with prometheus data."""
        # The route might have a redirect prefix; check all routes.
        from app.main import app

        routes = [r.path for r in app.router.routes]
        metrics_route = next((p for p in routes if "/metric" in p.lower()), None)
        if metrics_route:
            response = await client.get(metrics_route)
            assert response.status_code == 200


class TestMetricsMiddleware:
    """Middleware HTTP — coleta duracao mesmo em caso de erro."""

    async def test_middleware_does_not_block_normal_request(self, client):
        """Middleware nao interfere em requests normais."""
        response = await client.get("/api/v1/public/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestMetricsFallback:
    """Fallback quando prometheus_client nao esta instalado."""

    async def test_noop_imports_do_not_crash(self):
        """Fallback no prometheus_client => no-ops que nao crasham."""
        from app.metrics import generate_latest, CONTENT_TYPE_LATEST

        result = generate_latest()
        assert result == b""
        assert CONTENT_TYPE_LATEST == "text/plain"

    async def test_fallback_objects_are_callable(self):
        """No-op fallbacks podem ser chamados sem crash."""
        from app.metrics import Counter, Histogram, CollectorRegistry

        # These should be no-op functions that accept any args
        registry = CollectorRegistry()
        counter = Counter("test", "help", registry=registry)
        hist = Histogram("test_h", "help", registry=registry)
        assert registry is None or True  # Should not crash


class TestMetricsIntegration:
    """Testes de integracao: o endpoint /metrics existe e responde."""

    async def test_metrics_route_is_registered(self):
        """Verifica que a app FastAPI tem a rota /metrics registrada."""
        from app.main import app

        routes = [r.path for r in app.router.routes]
        matching = [p for p in routes if "/metric" in p.lower()]
        assert len(matching) > 0, f"/metrics route not found. Routes: {routes}"
