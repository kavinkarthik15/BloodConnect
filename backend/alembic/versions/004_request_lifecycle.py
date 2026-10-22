"""Add request lifecycle accounting and donation confirmations.

Revision ID: 004_request_lifecycle
Revises: 003_auth_security
"""

from alembic import op
import sqlalchemy as sa


revision = "004_request_lifecycle"
down_revision = "003_auth_security"
branch_labels = None
depends_on = None


def _assert_response_and_match_pairs_are_unique() -> None:
    connection = op.get_bind()
    duplicate_responses = connection.execute(sa.text(
        "SELECT COUNT(*) FROM ("
        "SELECT request_id, donor_id FROM donor_responses "
        "GROUP BY request_id, donor_id HAVING COUNT(*) > 1"
        ") AS duplicates"
    )).scalar_one()
    if duplicate_responses:
        raise RuntimeError(
            "Cannot enforce one donor response per request while duplicate rows exist; review and resolve them before migration."
        )

    duplicate_matches = connection.execute(sa.text(
        "SELECT COUNT(*) FROM ("
        "SELECT request_id, donor_id FROM donor_matches "
        "GROUP BY request_id, donor_id HAVING COUNT(*) > 1"
        ") AS duplicates"
    )).scalar_one()
    if duplicate_matches:
        raise RuntimeError(
            "Cannot enforce one donor match per request while duplicate rows exist; review and resolve them before migration."
        )

    for table_name in ("donor_responses", "donor_matches"):
        orphan_requests = connection.execute(sa.text(
            f"SELECT COUNT(*) FROM {table_name} child "
            "LEFT JOIN blood_requests parent ON parent.id = child.request_id "
            "WHERE parent.id IS NULL"
        )).scalar_one()
        orphan_donors = connection.execute(sa.text(
            f"SELECT COUNT(*) FROM {table_name} child "
            "LEFT JOIN users parent ON parent.id = child.donor_id "
            "WHERE parent.id IS NULL"
        )).scalar_one()
        if orphan_requests or orphan_donors:
            raise RuntimeError(
                f"Cannot add foreign keys to {table_name}; orphan references exist and must be reviewed before migration."
            )


def upgrade() -> None:
    _assert_response_and_match_pairs_are_unique()

    op.add_column("notifications", sa.Column("dedupe_key", sa.String(), nullable=True))
    op.create_index("ix_notifications_dedupe_key", "notifications", ["dedupe_key"], unique=True)

    op.add_column(
        "blood_requests",
        sa.Column("units_confirmed", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "blood_requests",
        sa.Column("legacy_fulfillment_unverified", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "blood_requests",
        sa.Column("escalation_status", sa.String(), server_default="normal", nullable=False),
    )
    op.execute(sa.text(
        "UPDATE blood_requests SET legacy_fulfillment_unverified = "
        "CASE WHEN status = 'fulfilled' THEN TRUE ELSE FALSE END"
    ))
    op.execute(sa.text(
        "UPDATE blood_requests SET status = 'coordinating' "
        "WHERE status IN ('donor_accepted', 'coordination')"
    ))
    op.execute(sa.text(
        "UPDATE blood_requests SET escalation_status = "
        "CASE WHEN urgency = 'Emergency' AND status = 'expired' THEN 'emergency_overdue' "
        "WHEN urgency = 'Emergency' THEN 'emergency' "
        "WHEN status = 'expired' THEN 'overdue' ELSE 'normal' END"
    ))
    with op.batch_alter_table("blood_requests") as batch_op:
        batch_op.create_check_constraint(
            "ck_blood_requests_units_confirmed_nonnegative",
            "units_confirmed >= 0",
        )
        batch_op.create_check_constraint(
            "ck_blood_requests_units_confirmed_not_over_required",
            "units_confirmed <= units_required",
        )

    op.create_table(
        "donation_confirmations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("donor_id", sa.Integer(), nullable=False),
        sa.Column("confirmed_by", sa.Integer(), nullable=False),
        sa.Column("units_confirmed", sa.Integer(), nullable=False),
        sa.Column("verification_source", sa.String(), nullable=False),
        sa.Column("reference", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("units_confirmed > 0", name="ck_donation_confirmations_units_positive"),
        sa.ForeignKeyConstraint(["request_id"], ["blood_requests.id"]),
        sa.ForeignKeyConstraint(["donor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", "donor_id", name="uq_donation_confirmations_request_donor"),
    )
    op.create_index("ix_donation_confirmations_request_id", "donation_confirmations", ["request_id"])
    op.create_index("ix_donation_confirmations_donor_id", "donation_confirmations", ["donor_id"])
    op.create_index("ix_donation_confirmations_confirmed_by", "donation_confirmations", ["confirmed_by"])

    with op.batch_alter_table("donor_responses") as batch_op:
        batch_op.create_unique_constraint(
            "uq_donor_responses_request_donor",
            ["request_id", "donor_id"],
        )
        batch_op.create_foreign_key(
            "fk_donor_responses_request_id_blood_requests",
            "blood_requests",
            ["request_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_donor_responses_donor_id_users",
            "users",
            ["donor_id"],
            ["id"],
        )

    with op.batch_alter_table("donor_matches") as batch_op:
        batch_op.create_unique_constraint(
            "uq_donor_matches_request_donor",
            ["request_id", "donor_id"],
        )
        batch_op.create_foreign_key(
            "fk_donor_matches_request_id_blood_requests",
            "blood_requests",
            ["request_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_donor_matches_donor_id_users",
            "users",
            ["donor_id"],
            ["id"],
        )


def downgrade() -> None:
    raise RuntimeError("Migration 004 is forward-only because downgrade would discard donation confirmation records.")
