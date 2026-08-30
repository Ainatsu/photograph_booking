"""Private inspiration repository model."""

import enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, JSON, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.app.core.database import Base


class InspirationStatus(str, enum.Enum):
    DRAFT = "draft"
    SAVED = "saved"
    ARCHIVED = "archived"


class Inspiration(Base):
    __tablename__ = "inspirations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(120), nullable=False)
    summary = Column(String(300), nullable=True)
    content = Column(JSON, nullable=False, default=list)
    cover_url = Column(String(500), nullable=True)
    tags = Column(JSON, nullable=False, default=list)
    location_name = Column(String(120), nullable=True)
    location_address = Column(String(255), nullable=True)
    latitude = Column(Numeric(10, 7), nullable=True)
    longitude = Column(Numeric(10, 7), nullable=True)
    place_id = Column(String(160), nullable=True)
    provider = Column(String(30), nullable=True)
    coordinate_system = Column(String(20), nullable=True)
    location_precision = Column(String(20), nullable=True)
    status = Column(SAEnum(InspirationStatus), nullable=False, default=InspirationStatus.DRAFT, index=True)
    visibility = Column(String(20), nullable=False, default="private")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    owner = relationship("User")

    __table_args__ = (
        Index("ix_inspirations_owner_status", "owner_id", "status"),
        Index("ix_inspirations_owner_updated", "owner_id", "updated_at"),
    )
