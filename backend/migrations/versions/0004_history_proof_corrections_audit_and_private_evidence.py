"""Corrections, audit history, and private evidence metadata.

Revision ID: 0004_history_proof
Revises: 0003_ledger

No Storage bucket/provider configuration is changed. Downgrade refuses to erase
Level 2 history or orphan references once any have been recorded.
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_history_proof"
down_revision = "0003_ledger"
branch_labels = None
depends_on = None
S = "iou_app"


def upgrade() -> None:
    # Referenced composite keys MUST exist before creating evidence/audit foreign keys.
    op.create_unique_constraint("uq_loans_id_owner", "loans", ["id", "owner_id"], schema=S)
    op.add_column("loan_events", sa.Column("reversed_at", sa.DateTime(timezone=True)), schema=S)
    op.add_column("loan_events", sa.Column("replaces_event_id", sa.Uuid()), schema=S)
    op.create_unique_constraint(
        "uq_events_id_owner_loan", "loan_events", ["id", "owner_id", "loan_id"], schema=S
    )
    op.create_unique_constraint(
        "uq_event_replacement", "loan_events", ["replaces_event_id"], schema=S
    )
    op.create_foreign_key(
        "fk_replacement_original",
        "loan_events",
        "loan_events",
        ["replaces_event_id", "owner_id", "loan_id"],
        ["id", "owner_id", "loan_id"],
        source_schema=S,
        referent_schema=S,
    )
    # Alembic does not reliably detect a changed partial-index predicate.
    op.drop_index("uq_one_item_return", table_name="loan_events", schema=S)
    op.create_index(
        "uq_one_item_return",
        "loan_events",
        ["loan_id"],
        unique=True,
        schema=S,
        postgresql_where=sa.text("action = 'return' AND reversed_at IS NULL"),
    )
    op.create_table(
        "evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("loan_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid()),
        sa.Column("state", sa.String(12), server_default="pending", nullable=False),
        sa.Column("bucket", sa.String(63), nullable=False),
        sa.Column("storage_origin", sa.String(300), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("note", sa.String(2000)),
        sa.Column("content_type", sa.String(20), nullable=False),
        sa.Column("object_path", sa.String(300)),
        sa.Column("original_sha256", sa.String(64)),
        sa.Column("sha256", sa.String(64)),
        sa.Column("original_size_bytes", sa.BigInteger()),
        sa.Column("size_bytes", sa.BigInteger()),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True)),
        sa.Column("removed_at", sa.DateTime(timezone=True)),
        sa.Column("cleanup_attempted_at", sa.DateTime(timezone=True)),
        sa.Column("cleaned_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("content_type IN ('image/jpeg', 'image/png')", name="ck_evidence_type"),
        sa.CheckConstraint("state != 'ready' OR uploaded_at IS NOT NULL", name="ck_evidence_ready"),
        sa.CheckConstraint(
            "state != 'removed' OR removed_at IS NOT NULL", name="ck_evidence_removed"
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'removed') OR (object_path IS NOT NULL "
            "AND original_sha256 IS NOT NULL AND sha256 IS NOT NULL AND size_bytes IS NOT NULL "
            "AND original_size_bytes IS NOT NULL AND width IS NOT NULL AND height IS NOT NULL)",
            name="ck_evidence_upload_metadata",
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'uploading', 'ready', 'removed')", name="ck_evidence_state"
        ),
        sa.CheckConstraint(
            "original_size_bytes IS NULL OR original_size_bytes BETWEEN 1 AND 5242880",
            name="ck_evidence_original_size",
        ),
        sa.CheckConstraint(
            "size_bytes IS NULL OR size_bytes BETWEEN 1 AND 5242880", name="ck_evidence_size"
        ),
        sa.CheckConstraint(
            "width IS NULL OR (width BETWEEN 1 AND 8000 AND height BETWEEN 1 AND 8000 "
            "AND width * height <= 16000000)",
            name="ck_evidence_dimensions",
        ),
        sa.ForeignKeyConstraint(
            ["event_id", "owner_id", "loan_id"],
            [f"{S}.loan_events.id", f"{S}.loan_events.owner_id", f"{S}.loan_events.loan_id"],
            name="fk_evidence_event_owner_loan",
        ),
        sa.ForeignKeyConstraint(
            ["loan_id", "owner_id"],
            [f"{S}.loans.id", f"{S}.loans.owner_id"],
            name="fk_evidence_loan_owner",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "owner_id", "loan_id", name="uq_evidence_id_owner_loan"),
        sa.UniqueConstraint("object_path", name="uq_evidence_object_path"),
        schema=S,
    )
    op.create_index(
        "ix_evidence_cleanup", "evidence", ["state", "expires_at", "cleanup_attempted_at"], schema=S
    )
    op.create_index(
        "ix_evidence_owner_loan_created",
        "evidence",
        ["owner_id", "loan_id", "created_at", "id"],
        schema=S,
    )
    op.create_table(
        "ledger_audit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("loan_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("actor", sa.String(10), server_default="owner", nullable=False),
        sa.Column("reason", sa.String(1000)),
        sa.Column("event_id", sa.Uuid()),
        sa.Column("replacement_event_id", sa.Uuid()),
        sa.Column("evidence_id", sa.Uuid()),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("actor IN ('owner', 'system')", name="ck_audit_actor"),
        sa.CheckConstraint(
            "(action = 'reversal' AND event_id IS NOT NULL AND evidence_id IS NULL "
            "AND reason IS NOT NULL AND length(trim(reason)) > 0) OR "
            "(action = 'void' AND event_id IS NULL AND replacement_event_id IS NULL "
            "AND evidence_id IS NULL AND reason IS NOT NULL AND length(trim(reason)) > 0) OR "
            "(action IN ('evidence_added', 'evidence_removed') AND evidence_id IS NOT NULL "
            "AND replacement_event_id IS NULL AND (action = 'evidence_added' OR "
            "(reason IS NOT NULL AND length(trim(reason)) > 0)))",
            name="ck_audit_action",
        ),
        sa.ForeignKeyConstraint(
            ["loan_id", "owner_id"],
            [f"{S}.loans.id", f"{S}.loans.owner_id"],
            name="fk_audit_loan_owner",
        ),
        sa.ForeignKeyConstraint(
            ["event_id", "owner_id", "loan_id"],
            [f"{S}.loan_events.id", f"{S}.loan_events.owner_id", f"{S}.loan_events.loan_id"],
            name="fk_audit_event_owner_loan",
        ),
        sa.ForeignKeyConstraint(
            ["replacement_event_id", "owner_id", "loan_id"],
            [f"{S}.loan_events.id", f"{S}.loan_events.owner_id", f"{S}.loan_events.loan_id"],
            name="fk_audit_replacement_owner_loan",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id", "owner_id", "loan_id"],
            [f"{S}.evidence.id", f"{S}.evidence.owner_id", f"{S}.evidence.loan_id"],
            name="fk_audit_evidence_owner_loan",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=S,
    )
    op.create_index(
        "ix_audit_owner_loan_time",
        "ledger_audit",
        ["owner_id", "loan_id", "effective_at", "id"],
        schema=S,
    )
    op.create_index(
        "uq_event_reversal",
        "ledger_audit",
        ["event_id"],
        unique=True,
        schema=S,
        postgresql_where=sa.text("action = 'reversal'"),
    )
    op.create_index(
        "uq_loan_void",
        "ledger_audit",
        ["loan_id"],
        unique=True,
        schema=S,
        postgresql_where=sa.text("action = 'void'"),
    )
    op.create_index(
        "uq_evidence_audit_action",
        "ledger_audit",
        ["evidence_id", "action"],
        unique=True,
        schema=S,
        postgresql_where=sa.text("action IN ('evidence_added', 'evidence_removed')"),
    )
    for table in ("evidence", "ledger_audit"):
        op.execute(f"REVOKE ALL ON TABLE {S}.{table} FROM PUBLIC")
        op.execute(f"""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    REVOKE ALL ON TABLE {S}.{table} FROM anon;
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    REVOKE ALL ON TABLE {S}.{table} FROM authenticated;
                END IF;
            END $$
        """)


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM iou_app.ledger_audit)
                OR EXISTS (SELECT 1 FROM iou_app.evidence)
                OR EXISTS (SELECT 1 FROM iou_app.loan_events
                           WHERE reversed_at IS NOT NULL OR replaces_event_id IS NOT NULL)
            THEN RAISE EXCEPTION 'Cannot downgrade: Level 2 history/evidence must be preserved';
            END IF;
        END $$
    """)
    op.drop_table("ledger_audit", schema=S)
    op.drop_table("evidence", schema=S)
    op.drop_index("uq_one_item_return", table_name="loan_events", schema=S)
    op.create_index(
        "uq_one_item_return",
        "loan_events",
        ["loan_id"],
        unique=True,
        schema=S,
        postgresql_where=sa.text("action = 'return'"),
    )
    op.drop_constraint("fk_replacement_original", "loan_events", schema=S, type_="foreignkey")
    op.drop_constraint("uq_event_replacement", "loan_events", schema=S, type_="unique")
    op.drop_constraint("uq_events_id_owner_loan", "loan_events", schema=S, type_="unique")
    op.drop_column("loan_events", "replaces_event_id", schema=S)
    op.drop_column("loan_events", "reversed_at", schema=S)
    op.drop_constraint("uq_loans_id_owner", "loans", schema=S, type_="unique")
