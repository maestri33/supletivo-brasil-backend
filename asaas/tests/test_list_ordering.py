"""Regressao do desempate por id em order_by (commit 93bde73).

Com PK UUID (nao-sequencial), ordenar so por created_at deixa empates de
timestamp sem ordem definida (drift de paginacao, FIFO nao-deterministico). O
fix adicionou id como criterio secundario. Este teste cria varias linhas com o
MESMO created_at e afirma que a ordem volta totalmente determinada por id desc.
"""

from datetime import UTC, datetime

from app.models import Customer
from app.services import customer as customer_service


async def test_list_all_desempata_por_id_quando_created_at_empata(db):
    ts = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)  # mesmo timestamp p/ todos
    for i in range(6):
        db.add(
            Customer(
                external_id=f"ext-{i}",
                asaas_id=f"cus_{i}",
                name=f"Cliente {i}",
                cpf_cnpj=f"0000000000{i}",
                created_at=ts,
                updated_at=ts,
            )
        )
    await db.commit()

    rows = await customer_service.list_all(db)
    ids = [r.id for r in rows]

    assert len(ids) == 6
    # empate total em created_at => ordem definida exclusivamente por id desc
    assert ids == sorted(ids, reverse=True)
