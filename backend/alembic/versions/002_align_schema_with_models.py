"""Align the initial schema with the current SQLAlchemy models.

Revision ID: 002_align_schema_with_models
Revises: 001_initial_schema
"""

from alembic import op
import sqlalchemy as sa


revision = "002_align_schema_with_models"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def _assert_existing_data_is_migratable() -> None:
    connection = op.get_bind()
    null_cities = connection.execute(
        sa.text("SELECT COUNT(*) FROM donor_profiles WHERE city IS NULL")
    ).scalar_one()
    if null_cities:
        raise RuntimeError(
            "Cannot make donor_profiles.city required while existing profiles have no city."
        )

    broken_assignments = connection.execute(sa.text(
        "SELECT COUNT(*) FROM volunteer_assignments va "
        "LEFT JOIN blood_requests br ON br.id = va.request_id "
        "LEFT JOIN users volunteer ON volunteer.id = va.volunteer_id "
        "LEFT JOIN users coordinator ON coordinator.id = va.assigned_by "
        "WHERE br.id IS NULL OR volunteer.id IS NULL OR coordinator.id IS NULL"
    )).scalar_one()
    if broken_assignments:
        raise RuntimeError(
            "Cannot add volunteer-assignment foreign keys while orphaned rows exist."
        )

    broken_audit_actors = connection.execute(sa.text(
        "SELECT COUNT(*) FROM audit_logs al "
        "LEFT JOIN users u ON u.id = al.actor_user_id "
        "WHERE al.actor_user_id IS NOT NULL AND u.id IS NULL"
    )).scalar_one()
    if broken_audit_actors:
        raise RuntimeError(
            "Cannot add audit actor foreign keys while orphaned rows exist."
        )


def upgrade() -> None:
    _assert_existing_data_is_migratable()

    profiles = sa.table(
        "donor_profiles",
        sa.column("user_id", sa.Integer()),
        sa.column("blood_group", sa.String()),
        sa.column("city", sa.String()),
        sa.column("area", sa.String()),
        sa.column("latitude", sa.Float()),
        sa.column("longitude", sa.Float()),
        sa.column("available", sa.Boolean()),
        sa.column("verified", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    profiles_new = sa.table(
        "donor_profiles_new",
        sa.column("user_id", sa.Integer()),
        sa.column("blood_group", sa.String()),
        sa.column("city", sa.String()),
        sa.column("area", sa.String()),
        sa.column("latitude", sa.Float()),
        sa.column("longitude", sa.Float()),
        sa.column("available", sa.Boolean()),
        sa.column("last_donation_date", sa.Date()),
        sa.column("verified", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "donor_profiles_new",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("blood_group", sa.String(), nullable=False),
        sa.Column("city", sa.String(), nullable=False),
        sa.Column("area", sa.String(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("available", sa.Boolean(), nullable=True),
        sa.Column("last_donation_date", sa.Date(), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.get_bind().execute(
        profiles_new.insert().from_select(
            [
                "user_id",
                "blood_group",
                "city",
                "area",
                "latitude",
                "longitude",
                "available",
                "last_donation_date",
                "verified",
                "created_at",
                "updated_at",
            ],
            sa.select(
                profiles.c.user_id,
                profiles.c.blood_group,
                profiles.c.city,
                profiles.c.area,
                profiles.c.latitude,
                profiles.c.longitude,
                profiles.c.available,
                sa.cast(sa.null(), sa.Date()),
                profiles.c.verified,
                profiles.c.created_at,
                profiles.c.updated_at,
            ),
        )
    )
    op.drop_table("donor_profiles")
    op.rename_table("donor_profiles_new", "donor_profiles")
    op.create_index("ix_donor_profiles_id", "donor_profiles", ["id"])
    op.create_index("ix_donor_profiles_user_id", "donor_profiles", ["user_id"], unique=True)

    op.add_column(
        "donor_matches",
        sa.Column("compatibility_type", sa.String(), nullable=True),
    )
    op.execute(sa.text(
        "UPDATE donor_matches SET compatibility_type = 'legacy_unknown' "
        "WHERE compatibility_type IS NULL"
    ))
    with op.batch_alter_table("donor_matches") as batch_op:
        batch_op.alter_column(
            "compatibility_type",
            existing_type=sa.String(),
            nullable=False,
        )
    op.create_index("ix_donor_matches_id", "donor_matches", ["id"])
    op.create_index("ix_donor_matches_request_id", "donor_matches", ["request_id"])
    op.create_index("ix_donor_matches_donor_id", "donor_matches", ["donor_id"])

    op.add_column("donor_responses", sa.Column("notes", sa.Text(), nullable=True))
    op.create_index("ix_donor_responses_id", "donor_responses", ["id"])
    op.create_index("ix_donor_responses_request_id", "donor_responses", ["request_id"])
    op.create_index("ix_donor_responses_donor_id", "donor_responses", ["donor_id"])
    op.create_index("ix_campaigns_id", "campaigns", ["id"])

    with op.batch_alter_table("volunteer_assignments") as batch_op:
        batch_op.create_foreign_key(
            "fk_volunteer_assignments_request_id_blood_requests",
            "blood_requests",
            ["request_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_volunteer_assignments_volunteer_id_users",
            "users",
            ["volunteer_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_volunteer_assignments_assigned_by_users",
            "users",
            ["assigned_by"],
            ["id"],
        )

    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.create_foreign_key(
            "fk_audit_logs_actor_user_id_users",
            "users",
            ["actor_user_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.drop_constraint("fk_audit_logs_actor_user_id_users", type_="foreignkey")

    with op.batch_alter_table("volunteer_assignments") as batch_op:
        batch_op.drop_constraint(
            "fk_volunteer_assignments_assigned_by_users",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_volunteer_assignments_volunteer_id_users",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_volunteer_assignments_request_id_blood_requests",
            type_="foreignkey",
        )

    op.drop_index("ix_campaigns_id", table_name="campaigns")
    op.drop_index("ix_donor_responses_donor_id", table_name="donor_responses")
    op.drop_index("ix_donor_responses_request_id", table_name="donor_responses")
    op.drop_index("ix_donor_responses_id", table_name="donor_responses")
    op.drop_column("donor_responses", "notes")

    op.drop_index("ix_donor_matches_donor_id", table_name="donor_matches")
    op.drop_index("ix_donor_matches_request_id", table_name="donor_matches")
    op.drop_index("ix_donor_matches_id", table_name="donor_matches")
    with op.batch_alter_table("donor_matches") as batch_op:
        batch_op.drop_column("compatibility_type")

    op.drop_index("ix_donor_profiles_user_id", table_name="donor_profiles")
    op.drop_index("ix_donor_profiles_id", table_name="donor_profiles")
    profiles = sa.table(
        "donor_profiles",
        sa.column("user_id", sa.Integer()),
        sa.column("blood_group", sa.String()),
        sa.column("city", sa.String()),
        sa.column("area", sa.String()),
        sa.column("latitude", sa.Float()),
        sa.column("longitude", sa.Float()),
        sa.column("available", sa.Boolean()),
        sa.column("verified", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    profiles_legacy = sa.table(
        "donor_profiles_legacy",
        sa.column("user_id", sa.Integer()),
        sa.column("blood_group", sa.String()),
        sa.column("city", sa.String()),
        sa.column("area", sa.String()),
        sa.column("latitude", sa.Float()),
        sa.column("longitude", sa.Float()),
        sa.column("available", sa.Boolean()),
        sa.column("verified", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "donor_profiles_legacy",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("blood_group", sa.String(), nullable=False),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("area", sa.String(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("available", sa.Boolean(), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.get_bind().execute(
        profiles_legacy.insert().from_select(
            [
                "user_id",
                "blood_group",
                "city",
                "area",
                "latitude",
                "longitude",
                "available",
                "verified",
                "created_at",
                "updated_at",
            ],
            sa.select(
                profiles.c.user_id,
                profiles.c.blood_group,
                profiles.c.city,
                profiles.c.area,
                profiles.c.latitude,
                profiles.c.longitude,
                profiles.c.available,
                profiles.c.verified,
                profiles.c.created_at,
                profiles.c.updated_at,
            ),
        )
    )
    op.drop_table("donor_profiles")
    op.rename_table("donor_profiles_legacy", "donor_profiles")
