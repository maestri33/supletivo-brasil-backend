"""Testes do provisionamento em background do /api/v1/register.

Nao depende de DB nem de servicos externos reais — substitui os clients de
integracao por fakes e chama `_provision` diretamente. Verifica a ordem dos
passos e o comportamento best-effort (CONVENTION §12): a falha de uma
integracao nao impede as demais nem levanta excecao.
"""

from __future__ import annotations

import pytest

from app.api import register as register_module

EID = "11111111-1111-1111-1111-111111111111"
ROLE = "candidate"
CPF = "39053344705"
PHONE = "11999999999"


def _install(monkeypatch, calls: list[str], fail: str | None = None) -> None:
    """Substitui todos os clients e o dispatch_otp por fakes que registram em `calls`.

    Se `fail` casar com o label de um client, esse passo levanta — para testar
    que os passos seguintes ainda rodam.
    """

    def client(label: str):
        class _Fake:
            def __init__(self, *args, **kwargs) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args) -> None:
                return None

            def _hit(self) -> dict:
                calls.append(label)
                if fail == label:
                    raise RuntimeError(f"{label} boom")
                return {}

            async def assign(self, *args, **kwargs) -> dict:
                return self._hit()

            async def create(self, *args, **kwargs) -> dict:
                return self._hit()

            async def create_contact(self, *args, **kwargs) -> dict:
                return self._hit()

            async def ensure(self, *args, **kwargs) -> dict:
                return self._hit()

        return _Fake

    monkeypatch.setattr(register_module, "RolesClient", client("roles"))
    monkeypatch.setattr(register_module, "ProfilesClient", client("profile"))
    monkeypatch.setattr(register_module, "NotifyClient", client("contato"))
    monkeypatch.setattr(register_module, "DocumentsClient", client("documentos"))
    monkeypatch.setattr(register_module, "AddressClient", client("endereco"))

    async def fake_dispatch_otp(external_id: str) -> None:
        calls.append("otp")

    monkeypatch.setattr(register_module, "dispatch_otp", fake_dispatch_otp)


@pytest.mark.asyncio
async def test_provision_calls_all_services_in_order(monkeypatch):
    calls: list[str] = []
    _install(monkeypatch, calls)

    await register_module._provision(EID, ROLE, CPF, PHONE)

    assert calls == ["roles", "profile", "contato", "documentos", "endereco", "otp"]


@pytest.mark.asyncio
async def test_provision_is_best_effort_when_documents_fails(monkeypatch):
    calls: list[str] = []
    _install(monkeypatch, calls, fail="documentos")

    # Nao deve levantar mesmo com documentos falhando.
    await register_module._provision(EID, ROLE, CPF, PHONE)

    assert "documentos" in calls  # tentou
    assert "endereco" in calls  # passo seguinte ainda rodou
    assert "otp" in calls  # fluxo seguiu ate o fim


@pytest.mark.asyncio
async def test_provision_is_best_effort_when_roles_fails(monkeypatch):
    calls: list[str] = []
    _install(monkeypatch, calls, fail="roles")

    await register_module._provision(EID, ROLE, CPF, PHONE)

    # Falha no primeiro passo nao impede nenhum dos seguintes.
    assert calls == ["roles", "profile", "contato", "documentos", "endereco", "otp"]
