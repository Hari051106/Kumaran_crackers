"""Baseline schema: roles and users.

Creates the authentication foundation and seeds the three system roles. Role
rows are reference data the application depends on, so they are inserted here
rather than by an ad-hoc script that a deployment could forget to run.

Revision ID: ceff460d10dc
Revises:
Create Date: 2026-09-19 12:49:59.638157
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ceff460d10dc"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SYSTEM_ROLES: list[dict[str, str]] = [
    {"name": "ADMIN", "description": "Full access to the back-office and all data."},
    {"name": "STAFF", "description": "Day-to-day operations: orders, inventory, delivery."},
    {"name": "CUSTOMER", "description": "Shops on the Kumaran Crackers mobile app."},
]


def upgrade() -> None:
    roles_table = op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
    )
    op.create_index(op.f("ix_roles_name"), "roles", ["name"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("age_confirmed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_users_role_id_roles"),
            # RESTRICT: deleting a role that still has users must fail rather
            # than silently orphan or delete customer accounts.
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_phone"), "users", ["phone"], unique=True)
    op.create_index(op.f("ix_users_role_id"), "users", ["role_id"], unique=False)

    # ---- Seed reference data ------------------------------------------------
    op.bulk_insert(roles_table, SYSTEM_ROLES)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_role_id"), table_name="users")
    op.drop_index(op.f("ix_users_phone"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_roles_name"), table_name="roles")
    op.drop_table("roles")
