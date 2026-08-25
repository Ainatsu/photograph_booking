"""add shoot projects

Revision ID: b9c7d8e9f0a1
Revises: e3f4a5b6c7d8
Create Date: 2026-06-17 14:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9c7d8e9f0a1"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

project_status = sa.Enum("DRAFT", "OPEN", "CONVERTED", "CLOSED", "CANCELLED", name="projectstatus")
application_status = sa.Enum(
    "SUBMITTED",
    "SELECTED",
    "REJECTED",
    "WITHDRAWN",
    name="projectapplicationstatus",
)


def upgrade() -> None:
    op.create_table(
        "shoot_projects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("style_tags", sa.JSON(), nullable=True),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("location_text", sa.String(length=255), nullable=True),
        sa.Column("shoot_date_start", sa.DateTime(), nullable=True),
        sa.Column("shoot_date_end", sa.DateTime(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("budget_min", sa.Integer(), nullable=True),
        sa.Column("budget_max", sa.Integer(), nullable=True),
        sa.Column("deliverables", sa.JSON(), nullable=True),
        sa.Column("reference_images", sa.JSON(), nullable=True),
        sa.Column("visibility", sa.String(length=20), nullable=False),
        sa.Column("status", project_status, nullable=False),
        sa.Column("selected_application_id", sa.Integer(), nullable=True),
        sa.Column("converted_order_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["converted_order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["selected_application_id"], ["project_applications.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_shoot_projects_id"), "shoot_projects", ["id"], unique=False)
    op.create_index(op.f("ix_shoot_projects_customer_id"), "shoot_projects", ["customer_id"], unique=False)
    op.create_index(op.f("ix_shoot_projects_status"), "shoot_projects", ["status"], unique=False)
    op.create_index(op.f("ix_shoot_projects_expires_at"), "shoot_projects", ["expires_at"], unique=False)
    op.create_index("ix_shoot_projects_status_created_at", "shoot_projects", ["status", "created_at"], unique=False)
    op.create_index("ix_shoot_projects_city_status", "shoot_projects", ["city", "status"], unique=False)

    op.create_table(
        "project_applications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("photographer_id", sa.Integer(), nullable=False),
        sa.Column("status", application_status, nullable=False),
        sa.Column("proposal_text", sa.Text(), nullable=False),
        sa.Column("price_quote", sa.Integer(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("available_time", sa.DateTime(), nullable=True),
        sa.Column("package_snapshot", sa.String(length=500), nullable=True),
        sa.Column("portfolio_refs", sa.JSON(), nullable=True),
        sa.Column("included_items", sa.JSON(), nullable=True),
        sa.Column("revision_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["photographer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["shoot_projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "photographer_id", name="uq_project_application_photographer"),
    )
    op.create_index(op.f("ix_project_applications_id"), "project_applications", ["id"], unique=False)
    op.create_index(op.f("ix_project_applications_project_id"), "project_applications", ["project_id"], unique=False)
    op.create_index(op.f("ix_project_applications_photographer_id"), "project_applications", ["photographer_id"], unique=False)
    op.create_index(op.f("ix_project_applications_status"), "project_applications", ["status"], unique=False)

    op.create_table(
        "project_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_role", sa.String(length=20), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["application_id"], ["project_applications.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["shoot_projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_project_events_id"), "project_events", ["id"], unique=False)
    op.create_index(op.f("ix_project_events_project_id"), "project_events", ["project_id"], unique=False)
    op.create_index(op.f("ix_project_events_application_id"), "project_events", ["application_id"], unique=False)
    op.create_index(op.f("ix_project_events_actor_id"), "project_events", ["actor_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_project_events_actor_id"), table_name="project_events")
    op.drop_index(op.f("ix_project_events_application_id"), table_name="project_events")
    op.drop_index(op.f("ix_project_events_project_id"), table_name="project_events")
    op.drop_index(op.f("ix_project_events_id"), table_name="project_events")
    op.drop_table("project_events")

    op.drop_index(op.f("ix_project_applications_status"), table_name="project_applications")
    op.drop_index(op.f("ix_project_applications_photographer_id"), table_name="project_applications")
    op.drop_index(op.f("ix_project_applications_project_id"), table_name="project_applications")
    op.drop_index(op.f("ix_project_applications_id"), table_name="project_applications")
    op.drop_table("project_applications")

    op.drop_index("ix_shoot_projects_city_status", table_name="shoot_projects")
    op.drop_index("ix_shoot_projects_status_created_at", table_name="shoot_projects")
    op.drop_index(op.f("ix_shoot_projects_expires_at"), table_name="shoot_projects")
    op.drop_index(op.f("ix_shoot_projects_status"), table_name="shoot_projects")
    op.drop_index(op.f("ix_shoot_projects_customer_id"), table_name="shoot_projects")
    op.drop_index(op.f("ix_shoot_projects_id"), table_name="shoot_projects")
    op.drop_table("shoot_projects")
