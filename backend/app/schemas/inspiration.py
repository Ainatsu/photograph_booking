"""Schemas for the private inspiration repository."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError


class InspirationBlock(BaseModel):
    type: Literal["paragraph", "heading", "quote", "list", "image"]
    text: str | None = Field(None, max_length=5000)
    url: str | None = Field(None, max_length=500)
    thumb_url: str | None = Field(None, max_length=500)
    alt: str | None = Field(None, max_length=200)

    @model_validator(mode="after")
    def validate_payload(self):
        if self.type == "image" and not self.url:
            raise PydanticCustomError("image_url_required", "image blocks require url")
        if self.type != "image" and not (self.text or "").strip():
            raise PydanticCustomError("block_text_required", "text blocks require text")
        return self


class InspirationFields(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    summary: str | None = Field(None, max_length=300)
    content: list[InspirationBlock] = Field(default_factory=list, max_length=100)
    cover_url: str | None = Field(None, max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=10)
    location_name: str | None = Field(None, max_length=120)
    location_address: str | None = Field(None, max_length=255)
    latitude: Decimal | None = Field(None, ge=-90, le=90)
    longitude: Decimal | None = Field(None, ge=-180, le=180)
    place_id: str | None = Field(None, max_length=160)
    provider: str | None = Field(None, max_length=30)
    coordinate_system: str | None = Field(None, pattern="^(WGS84|GCJ02)$")
    location_precision: str | None = Field(None, pattern="^(exact|approximate)$")
    status: Literal["draft", "saved"] = "draft"

    @model_validator(mode="after")
    def validate_location(self):
        if (self.latitude is None) != (self.longitude is None):
            raise PydanticCustomError("coordinate_pair_required", "latitude and longitude must be provided together")
        self.tags = list(dict.fromkeys(tag.strip() for tag in self.tags if tag.strip()))
        return self


class InspirationCreate(InspirationFields):
    pass


class InspirationUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=120)
    summary: str | None = Field(None, max_length=300)
    content: list[InspirationBlock] | None = Field(None, max_length=100)
    cover_url: str | None = Field(None, max_length=500)
    tags: list[str] | None = Field(None, max_length=10)
    location_name: str | None = Field(None, max_length=120)
    location_address: str | None = Field(None, max_length=255)
    latitude: Decimal | None = Field(None, ge=-90, le=90)
    longitude: Decimal | None = Field(None, ge=-180, le=180)
    place_id: str | None = Field(None, max_length=160)
    provider: str | None = Field(None, max_length=30)
    coordinate_system: str | None = Field(None, pattern="^(WGS84|GCJ02)$")
    location_precision: str | None = Field(None, pattern="^(exact|approximate)$")
    status: Literal["draft", "saved"] | None = None

    @model_validator(mode="after")
    def validate_location_update(self):
        latitude_set = "latitude" in self.model_fields_set
        longitude_set = "longitude" in self.model_fields_set
        if latitude_set != longitude_set:
            raise PydanticCustomError("coordinate_pair_required", "latitude and longitude must be updated together")
        if latitude_set and ((self.latitude is None) != (self.longitude is None)):
            raise PydanticCustomError("coordinate_pair_required", "latitude and longitude must be provided together")
        if self.tags is not None:
            self.tags = list(dict.fromkeys(tag.strip() for tag in self.tags if tag.strip()))
        return self


class InspirationGenerationStatus(BaseModel):
    status: Literal["queued", "generating", "partial", "completed", "failed", "cancelled"]
    total_images: int = Field(ge=0)
    completed_images: int = Field(ge=0)
    failed_images: int = Field(ge=0)
    can_retry: bool = False
    updated_at: datetime | None = None


class InspirationResponse(BaseModel):
    id: int
    owner_id: int
    title: str
    summary: str | None = None
    content: list[dict[str, Any]] = []
    cover_url: str | None = None
    tags: list[str] = []
    location_name: str | None = None
    location_address: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    place_id: str | None = None
    provider: str | None = None
    coordinate_system: str | None = None
    location_precision: str | None = None
    status: str
    visibility: str
    created_at: datetime
    updated_at: datetime
    generation: "InspirationGenerationStatus | None" = None

    class Config:
        from_attributes = True


class InspirationMapPreview(BaseModel):
    id: int
    title: str
    cover_url: str | None = None
    updated_at: datetime


class InspirationMapPoint(BaseModel):
    key: str
    name: str
    latitude: float
    longitude: float
    count: int
    preview: list[InspirationMapPreview]


class InspirationMapResponse(BaseModel):
    points: list[InspirationMapPoint]


class InspirationUploadResponse(BaseModel):
    url: str
    thumb_url: str | None = None


class InspirationImageAdvice(BaseModel):
    """One image's generated inspiration note. Business identifiers are forbidden."""

    model_config = ConfigDict(extra="forbid")

    attachment_index: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=400)
    extension: str = Field(min_length=1, max_length=300)


class InspirationGenerationResult(BaseModel):
    """Strict output contract returned by the internal Inspiration Agent."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=300)
    tags: list[str] = Field(min_length=1, max_length=10)
    items: list[InspirationImageAdvice] = Field(min_length=1)

    @model_validator(mode="after")
    def normalize_tags(self):
        self.tags = list(dict.fromkeys(tag.strip() for tag in self.tags if tag.strip()))[:10]
        if not self.tags:
            raise PydanticCustomError("inspiration_tags_required", "at least one non-empty tag is required")
        return self


class InspirationBatchImageAdvice(BaseModel):
    """Validated inspiration note for one image in a small generation batch."""

    model_config = ConfigDict(extra="forbid")

    attachment_index: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=24)
    description: str = Field(min_length=1, max_length=160)
    extension: str = Field(min_length=1, max_length=120)


class InspirationBatchResult(BaseModel):
    """Strict JSON contract returned for one or two reference images."""

    model_config = ConfigDict(extra="forbid")

    batch_theme: str = Field(min_length=1, max_length=24)
    tags: list[str] = Field(min_length=1, max_length=4)
    items: list[InspirationBatchImageAdvice] = Field(min_length=1, max_length=2)

    @model_validator(mode="after")
    def normalize_tags(self):
        self.tags = list(dict.fromkeys(tag.strip() for tag in self.tags if tag.strip()))[:4]
        if not self.tags:
            raise PydanticCustomError("inspiration_tags_required", "at least one non-empty tag is required")
        if any(len(tag) > 8 for tag in self.tags):
            raise PydanticCustomError("inspiration_tag_too_long", "batch tags must be at most 8 characters")
        return self


class InspirationSummaryResult(BaseModel):
    """Title, summary and tags synthesized from batch text only."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=300)
    tags: list[str] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def normalize_tags(self):
        self.tags = list(dict.fromkeys(tag.strip() for tag in self.tags if tag.strip()))[:10]
        if not self.tags:
            raise PydanticCustomError("inspiration_tags_required", "at least one non-empty tag is required")
        if any(len(tag) > 8 for tag in self.tags):
            raise PydanticCustomError("inspiration_tag_too_long", "summary tags must be at most 8 characters")
        return self


# Short aliases keep the contract discoverable for service and test callers.
InspirationBatchAdvice = InspirationBatchImageAdvice
