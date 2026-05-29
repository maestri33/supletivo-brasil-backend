"""Drop tabelas que migraram para o servico `student`.

As tabelas `exams`, `student_documents` e `diplomas` viviam em `coordinator`,
mas pertencem ao dominio do aluno (CONVENTION §6). Movidas para o schema
`student` em uma migration paralela do servico student.

Revision ID: 2026-05-27_drop_student_owned
Revises: 2026-05-27_tables
Create Date: 2026-05-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "2026-05-27_drop_student_owned"
down_revision: str | None = "2026-05-27_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = "coordinator"


def upgrade() -> None:
    # IF EXISTS: tolera ambientes onde tabelas nunca foram criadas (e.g. dev fresh).
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.diplomas")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.student_documents")
    op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.exams")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.exam_status")


def downgrade() -> None:
    # Sem restauracao: dados ja vivem no servico `student`. Re-create deixaria
    # tabelas vazias e re-introduziria a violacao de fronteira (§6).
    raise NotImplementedError(
        "Downgrade nao suportado: dominio do aluno migrou para o servico student"
    )
