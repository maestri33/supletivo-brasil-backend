"""Tabelas do funil do aluno — documents, exams, diplomas.

Sem FK cross-schema (§4): student_id referencia students.id (intra-schema),
external_ids opacos do auth/documents ficam como UUID puro sem FK.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SCHEMA = "student"


def upgrade() -> None:
    op.create_table(
        "student_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(length=40), nullable=False),
        sa.Column("document_external_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "validation_status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("validation_result", postgresql.JSONB(), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="student_documents_pkey"),
        sa.ForeignKeyConstraint(
            ["student_id"],
            [f"{SCHEMA}.students.id"],
            ondelete="CASCADE",
            name="student_documents_student_id_fkey",
        ),
        sa.UniqueConstraint(
            "student_id", "document_type", name="student_documents_student_type_key"
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "student_documents_student_id_idx",
        "student_documents",
        ["student_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "student_documents_document_type_idx",
        "student_documents",
        ["document_type"],
        schema=SCHEMA,
    )
    op.create_index(
        "student_documents_document_external_id_idx",
        "student_documents",
        ["document_external_id"],
        schema=SCHEMA,
    )

    op.create_table(
        "student_exams",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject", sa.String(length=80), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "attempt_number",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("result", sa.String(length=20), nullable=True),
        sa.Column(
            "corrected_by_external_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="student_exams_pkey"),
        sa.ForeignKeyConstraint(
            ["student_id"],
            [f"{SCHEMA}.students.id"],
            ondelete="CASCADE",
            name="student_exams_student_id_fkey",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "student_exams_student_id_idx",
        "student_exams",
        ["student_id"],
        schema=SCHEMA,
    )

    op.create_table(
        "student_diplomas",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "issued_by_external_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("picked_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "pickup_photo_external_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "commission_triggered_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="student_diplomas_pkey"),
        sa.ForeignKeyConstraint(
            ["student_id"],
            [f"{SCHEMA}.students.id"],
            ondelete="CASCADE",
            name="student_diplomas_student_id_fkey",
        ),
        sa.UniqueConstraint("student_id", name="student_diplomas_student_id_key"),
        schema=SCHEMA,
    )
    op.create_index(
        "student_diplomas_student_id_idx",
        "student_diplomas",
        ["student_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "student_diplomas_student_id_idx", table_name="student_diplomas", schema=SCHEMA
    )
    op.drop_table("student_diplomas", schema=SCHEMA)

    op.drop_index(
        "student_exams_student_id_idx", table_name="student_exams", schema=SCHEMA
    )
    op.drop_table("student_exams", schema=SCHEMA)

    op.drop_index(
        "student_documents_document_external_id_idx",
        table_name="student_documents",
        schema=SCHEMA,
    )
    op.drop_index(
        "student_documents_document_type_idx",
        table_name="student_documents",
        schema=SCHEMA,
    )
    op.drop_index(
        "student_documents_student_id_idx",
        table_name="student_documents",
        schema=SCHEMA,
    )
    op.drop_table("student_documents", schema=SCHEMA)
