"""Seed do polo default.

Fonte única dos valores do polo default, usada pela migração `0001` e pelos
testes. UUID **fixo/determinístico**: torna o seed idempotente e permite outros
serviços referenciarem o polo default no bootstrap.

Refs (address/coordinator) ficam nulas até esses serviços existirem; ajuste os
valores aqui quando definir o polo real.
"""

DEFAULT_HUB_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_HUB_NAME = "Polo Default"
DEFAULT_HUB_BRAND = "estacio"


def default_hub_insert_sql(schema: str) -> str:
    """INSERT idempotente do polo default (created_at/updated_at via server_default)."""
    return (
        f"INSERT INTO {schema}.hub (id, name, brand) "
        f"VALUES ('{DEFAULT_HUB_ID}', '{DEFAULT_HUB_NAME}', '{DEFAULT_HUB_BRAND}') "
        f"ON CONFLICT (id) DO NOTHING"
    )
