"""Persistent image generation jobs and media assets."""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from backend.app.core.database import Base


class ImageGenerationJob(Base):
    __tablename__ = "image_generation_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id"), nullable=False, index=True)
    source_message_id = Column(Integer, ForeignKey("ai_messages.id"), nullable=False, index=True)
    agent_task_id = Column(String(36), nullable=False, index=True)
    mode = Column(String(24), nullable=False)
    status = Column(String(20), nullable=False, default="queued", index=True)
    stage = Column(String(32), nullable=False, default="queued")
    prompt = Column(Text, nullable=False)
    normalized_prompt = Column(Text, nullable=True)
    parameters = Column(JSON, nullable=False, default=dict)
    provider = Column(String(50), nullable=True)
    model = Column(String(120), nullable=True)
    provider_request_id = Column(String(160), nullable=True)
    idempotency_key = Column(String(36), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    available_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    last_error_code = Column(String(80), nullable=True)
    last_error = Column(String(500), nullable=True)
    usage_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_image_generation_owner_idempotency"),
        Index("ix_image_generation_jobs_status_available", "status", "available_at"),
    )


class ImageGenerationAsset(Base):
    __tablename__ = "image_generation_assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("image_generation_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(16), nullable=False)
    position = Column(Integer, nullable=False, default=0)
    storage_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    mime_type = Column(String(80), nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    sha256 = Column(String(64), nullable=True)
    provider_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("job_id", "role", "position", name="uq_image_generation_asset_position"),
    )
