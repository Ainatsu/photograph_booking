"""AI 助手会话相关 Schema 定义"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

class AIConversationCreate(BaseModel):
    """创建 AI 会话请求"""

    title: str | None = Field(default=None, max_length=255)
    approval_policy: Literal["auto", "confirm_write", "confirm_all"] = "confirm_write"
    tool_permission_profile: Literal["read_only", "normal", "publisher", "booking"] = "normal"
    confirmation_mode: Literal["inline", "modal", "explicit_text"] = "inline"


class AIConversationResponse(BaseModel):
    """AI 会话响应"""

    id: int
    user_id: int
    title: str | None
    status: str = "active"
    last_message_preview: str | None = None
    last_message_at: datetime | None = None
    summary: str | None = None
    source: str | None = None
    approval_policy: Literal["auto", "confirm_write", "confirm_all"] = "confirm_write"
    tool_permission_profile: Literal["read_only", "normal", "publisher", "booking"] = "normal"
    confirmation_mode: Literal["inline", "modal", "explicit_text"] = "inline"
    active_task_id: str | None = None
    root_conversation_id: int | None = None
    forked_from_conversation_id: int | None = None
    fork_boundary: str | None = None
    folder_id: int | None = None
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AIConversationUpdate(BaseModel):
    """Update mutable conversation metadata without touching its container data."""

    title: str | None = Field(default=None, max_length=255)
    archived: bool | None = None
    status: Literal["active", "archived"] | None = None
    summary: str | None = Field(default=None, max_length=10000)
    source: str | None = Field(default=None, max_length=64)
    approval_policy: Literal["auto", "confirm_write", "confirm_all"] | None = None
    tool_permission_profile: Literal["read_only", "normal", "publisher", "booking"] | None = None
    confirmation_mode: Literal["inline", "modal", "explicit_text"] | None = None

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError("at least one conversation field is required")
        if "title" in self.model_fields_set and self.title is not None:
            self.title = " ".join(self.title.split()) or None
        return self


class AIConversationForkRequest(BaseModel):
    task_id: str | None = None
    turn_id: int | None = Field(default=None, gt=0)


class AIConversationFolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    sort_order: int = 0


class AIConversationFolderResponse(BaseModel):
    id: int
    user_id: int
    name: str
    sort_order: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AIMessageAttachment(BaseModel):
    """AI 消息附件"""

    type: Literal["image"]
    url: str
    mime_type: str | None = None
    thumb_url: str | None = None
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    size_bytes: int | None = Field(default=None, ge=0)
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    original_width: int | None = Field(default=None, gt=0)
    original_height: int | None = Field(default=None, gt=0)
    original_size_bytes: int | None = Field(default=None, ge=0)
    normalized: bool | None = None


class AITaskSubmission(BaseModel):
    """Agent 表单卡片提交协议。

    ``slots`` 保留为兼容窗口，新的客户端必须使用 ``form_data``。
    """

    task_id: UUID | None = None
    task_type: Literal[
        "create_project",
        "publish_package",
        "publish_work",
        "project_application",
        "create_booking",
        "create_inspiration",
    ]
    action: Literal["publish", "save_draft", "cancel"]
    revision: int = Field(default=1, ge=1)
    form_data: dict[str, Any] | None = None
    media_refs: list[str] = Field(default_factory=list)
    idempotency_key: UUID = Field(default_factory=uuid4)
    slots: dict[str, Any] | None = None
    skip_reference_images: bool = False

    @model_validator(mode="after")
    def validate_form_data(self):
        if self.form_data is None and self.slots is None and self.action != "cancel":
            raise ValueError("form_data is required")
        if self.form_data is not None and not isinstance(self.form_data, dict):
            raise ValueError("form_data must be an object")
        return self


class AIShootContextSelection(BaseModel):
    """A validated choice from a previous ambiguous shoot-context response."""

    source_message_id: int = Field(gt=0)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class AIImageGenerationRequest(BaseModel):
    """Structured request used by explicit image generation controls."""

    mode: Literal["text_to_image", "image_to_image"]
    aspect_ratio: Literal["1:1", "3:4", "4:3", "9:16", "16:9"] = "1:1"
    count: int = Field(default=1, ge=1, le=2)
    quality: Literal["standard", "high"] = "standard"
    strength: float | None = Field(default=None, ge=0.1, le=1.0)
    idempotency_key: UUID = Field(default_factory=uuid4)


class AIMessageCreate(BaseModel):
    """发送 AI 消息请求"""

    content: str | None = Field(default=None, max_length=8000)
    attachments: list[AIMessageAttachment] = Field(default_factory=list)
    page_context: dict[str, Any] | None = None
    task_submission: AITaskSubmission | None = None
    shoot_context_selection: AIShootContextSelection | None = None
    generation_request: AIImageGenerationRequest | None = None


class AIMessageResponse(BaseModel):
    """AI 消息响应"""

    id: int
    conversation_id: int
    role: Literal["user", "assistant", "system"]
    content: str
    metadata: dict | None = Field(
        default=None,
        validation_alias=AliasChoices("message_metadata", "metadata"),
        serialization_alias="metadata",
    )
    attachments: list[dict] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @model_validator(mode="after")
    def _populate_attachments(self):
        """从 metadata 中还原附件列表"""
        if self.metadata:
            stored = self.metadata.get("attachments")
            if isinstance(stored, list):
                self.attachments = stored
        return self


class AgentTaskOperation(BaseModel):
    """One allow-listed field patch from a handoff page or chat turn."""

    field: str = Field(min_length=1, max_length=80)
    op: Literal["set", "clear"]
    value: Any = None
    confidence: float = Field(default=1.0, ge=0, le=1)
    evidence: str | None = Field(default=None, max_length=500)


class AgentTaskPatch(BaseModel):
    revision: int = Field(ge=0)
    operations: list[AgentTaskOperation] = Field(default_factory=list, max_length=50)
    idempotency_key: UUID | None = None
    source: Literal["page", "chat", "system"] = "page"


class AgentTaskFormRevisionResponse(BaseModel):
    id: int
    task_id: str
    conversation_id: int
    user_id: int
    revision: int
    operations: list[dict[str, Any]]
    resulting_form: dict[str, Any]
    source: str
    source_message_id: int | None = None
    idempotency_key: str | None = None
    created_by: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentTaskComplete(BaseModel):
    result: dict[str, Any] | None = None


class AgentTaskCommit(BaseModel):
    revision: int = Field(ge=0)
    idempotency_key: UUID = Field(default_factory=uuid4)


class PublishPolishRequest(BaseModel):
    """Text-only publishing form payload sent to the agent for polishing."""

    content_type: Literal["project", "package", "work"]
    fields: dict[str, Any] = Field(min_length=1, max_length=20)


class PublishPolishResponse(BaseModel):
    """Sanitized fields returned by the publishing polish agent."""

    fields: dict[str, Any]
    polished_field_count: int = Field(ge=0)


class AIChatResponse(BaseModel):
    """AI 对话回合响应"""

    user_message: AIMessageResponse
    assistant_message: AIMessageResponse
    active_task: dict[str, Any] | None = None
