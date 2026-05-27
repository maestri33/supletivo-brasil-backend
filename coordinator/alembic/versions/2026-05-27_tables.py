"""Create all coordinator tables.

Revision ID: 2026-05-27_tables
Revises: 2026-05-27_initial_schema
Create Date: 2026-05-27

Creates all 6 coordinator domain tables:
  - coordinators
  - training_approvals
  - enrollment_fees
  - exams
  - student_documents
  - diplomas
"""

from typing import Sequence, Union

import sqlalchemy as sa  # noqa: F401
from alembic import op

revision: str = "2026-05-27_tables"
down_revision: Union[str, None] = "2026-05-27_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── coordinators ───────────────────────────────────────────
    op.create_table(
        "coordinators",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("external_id", sa.String(36), nullable=False, unique=True),
        sa.Column("hub_external_id", sa.String(36), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "inactive", "suspended", name="coordinator_status"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="coordinator",
    )

    # ── training_approvals ─────────────────────────────────────
    op.create_table(
        "training_approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("coordinator_id", sa.String(36), nullable=False),
        sa.Column("candidate_external_id", sa.String(36), nullable=False),
        sa.Column("training_external_id", sa.String(36), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", name="approval_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="coordinator",
    )

    # ── enrollment_fees ────────────────────────────────────────
    op.create_table(
        "enrollment_fees",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("coordinator_id", sa.String(36), nullable=False),
        sa.Column("student_external_id", sa.String(36), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "paid", "cancelled", name="fee_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("payment_external_id", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="coordinator",
    )

    # ── exams ──────────────────────────────────────────────────
    op.create_table(
        "exams",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("coordinator_id", sa.String(36), nullable=False),
        sa.Column("student_external_id", sa.String(36), nullable=False),
        sa.Column("training_external_id", sa.String(36), nullable=False),
        sa.Column(
            "status",
            sa.Enum("created", "in_progress", "submitted", "graded", name="exam_status"),
            nullable=False,
            server_default="created",
        ),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("max_score", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("result_notes", sa.Text(), nullable=True),
        sa.Column("ai_correction", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="coordinator",
    )

    # ── student_documents ──────────────────────────────────────
    op.create_table(
        "student_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_external_id", sa.String(36), nullable=False, index=True),
        sa.Column("coordinator_external_id", sa.String(36), nullable=False, index=True),
        sa.Column("document_type", sa.String(50), nullable=False, index=True),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("submitted_to_institution", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="coordinator",
    )

    # ── diplomas ───────────────────────────────────────────────
    op.create_table(
        "diplomas",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_external_id", sa.String(36), nullable=False, index=True),
        sa.Column("coordinator_external_id", sa.String(36), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, index=True, server_default="pending"),
        sa.Column("history_path", sa.String(500), nullable=True),
        sa.Column("diploma_photo_path", sa.String(500), nullable=True),
        sa.Column("commission_triggered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("graduated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="coordinator",
    )


def downgrade() -> None:
    op.drop_table("diplomas", schema="coordinator")
    op.drop_table("student_documents", schema="coordinator")
    op.drop_table("exams", schema="coordinator")
    op.drop_table("enrollment_fees", schema="coordinator")
    op.drop_table("training_approvals", schema="coordinator")
    op.drop_table("coordinators", schema="coordinator")

    # Drop ENUM types created in upgrade
    op.execute("DROP TYPE IF EXISTS coordinator.coordinator_status")
    op.execute("DROP TYPE IF EXISTS coordinator.approval_status")
    op.execute("DROP TYPE IF EXISTS coordinator.fee_status")
    op.execute("DROP TYPE IF EXISTS coordinator.exam_status")
