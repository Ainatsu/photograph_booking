"""add recommendation tables
Revision ID: c2d3e4f5a6b7
Revises: bb4d8e2f1a6c
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "bb4d8e2f1a6c"
branch_labels = depends_on = None

def upgrade():
    op.create_table("recommendation_user_profiles", sa.Column("user_id",sa.Integer(),primary_key=True),sa.Column("tag_preferences",sa.JSON(),nullable=False),sa.Column("author_preferences",sa.JSON(),nullable=False),sa.Column("city_preferences",sa.JSON(),nullable=False),sa.Column("event_count",sa.Integer(),nullable=False),sa.Column("version",sa.String(30),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.ForeignKeyConstraint(["user_id"],["users.id"]))
    op.create_table("recommendation_item_stats",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("target_type",sa.String(30),nullable=False),sa.Column("target_id",sa.String(80),nullable=False),sa.Column("owner_user_id",sa.Integer(),nullable=False),sa.Column("impression_count",sa.Integer(),nullable=False),sa.Column("click_count",sa.Integer(),nullable=False),sa.Column("like_count",sa.Integer(),nullable=False),sa.Column("favorite_count",sa.Integer(),nullable=False),sa.Column("comment_count",sa.Integer(),nullable=False),sa.Column("booking_intent_count",sa.Integer(),nullable=False),sa.Column("smoothed_ctr",sa.Float(),nullable=False),sa.Column("quality_score",sa.Float(),nullable=False),sa.Column("trend_score",sa.Float(),nullable=False),sa.Column("last_event_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.ForeignKeyConstraint(["owner_user_id"],["users.id"]),sa.UniqueConstraint("target_type","target_id",name="uq_recommendation_item_target"))
    op.create_index("ix_recommendation_item_stats_trend","recommendation_item_stats",["target_type","trend_score"])
    op.create_table("recommendation_exposures",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("recommendation_id",sa.String(50),nullable=False),sa.Column("request_id",sa.String(50)),sa.Column("viewer_user_id",sa.Integer()),sa.Column("session_id",sa.String(100)),sa.Column("target_type",sa.String(30),nullable=False),sa.Column("target_id",sa.String(80),nullable=False),sa.Column("position",sa.Integer(),nullable=False),sa.Column("scene",sa.String(40),nullable=False),sa.Column("candidate_source",sa.String(40),nullable=False),sa.Column("algorithm_version",sa.String(40),nullable=False),sa.Column("exposed_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.ForeignKeyConstraint(["viewer_user_id"],["users.id"]))

def downgrade():
    op.drop_table("recommendation_exposures"); op.drop_table("recommendation_item_stats"); op.drop_table("recommendation_user_profiles")
