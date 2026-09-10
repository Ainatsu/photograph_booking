from logging.config import fileConfig
import sys
from pathlib import Path

# Alembic is launched with ``backend`` as its working directory by the
# application, so the repository root is not necessarily importable yet.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# ---- 配置 Alembic ----
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 导入项目的所有模型和 Base，这样 autogenerate 才能检测到所有表
from backend.app.core.database import Base
from backend.app.core.config import settings

# 导入所有模型（必须导入，否则 alembic 不会检测到）
from backend.app.models.user import User
from backend.app.models.identity_verification import IdentityVerificationChallenge
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.order import Order
from backend.app.models.payment import Payment, Refund, Settlement
from backend.app.models.order_delivery import OrderDelivery, OrderDeliveryFile, OrderRevisionRequest
from backend.app.models.order_dispute import AdminAuditLog, OrderDispute, OrderDisputeEvidence
from backend.app.models.notification import OrderNotification, OutboxEvent
from backend.app.models.message import Message
from backend.app.models.like import Like
from backend.app.models.favorite import Favorite
from backend.app.models.comment import Comment
from backend.app.models.order_event import OrderEvent
from backend.app.models.order_reschedule import OrderRescheduleRequest
from backend.app.models.ai_conversation import AIConversation, AIMessage, AIConversationEvent, AIConversationCompression
from backend.app.models.agent_task import AgentTaskDraft, AgentTaskFormRevision
from backend.app.models.agent_task_session import AgentTaskEvent, AgentTaskResource, AgentTaskSession
from backend.app.models.agent_workflow import AgentWorkflowEvent, AgentWorkflowRun, AgentWorkflowStep
from backend.app.models.agent_memory import AgentMemoryEpisode, AgentUserMemory
from backend.app.models.ai_resource import AIResourceDocument
from backend.app.models.ai_production import AIIndexJob, AgentTrace
from backend.app.models.chat_read_state import ChatReadState
from backend.app.models.project import ProjectApplication, ProjectEvent, ShootProject
from backend.app.models.photographer_application import PhotographerApplication
from backend.app.models.follow import Follow
from backend.app.models.analytics import AnalyticsEvent
from backend.app.models.inspiration import Inspiration
from backend.app.models.inspiration_generation import InspirationGenerationBatch, InspirationGenerationJob
from backend.app.models.image_generation import ImageGenerationAsset, ImageGenerationJob

target_metadata = Base.metadata

# 从 settings 读取数据库 URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
