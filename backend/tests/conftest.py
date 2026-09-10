"""
测试通用 Fixtures
提供：数据库会话、HTTP 客户端、认证用户等
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import Base, get_db
from backend.app.core.security import create_access_token
from backend.app.core.cache import get_redis
from backend.app.models.user import User
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.order import Order, OrderStatus
from backend.app.models.payment import Payment, Refund, Settlement
from backend.app.models.order_dispute import AdminAuditLog, OrderDispute, OrderDisputeEvidence
from backend.app.models.notification import OrderNotification, OutboxEvent
from backend.app.models.message import Message
from backend.app.models.comment import Comment
from backend.app.models.order_event import OrderEvent
from backend.app.models.ai_conversation import AIConversation, AIMessage
from backend.app.models.ai_resource import AIResourceDocument
from backend.app.models.agent_workflow import AgentWorkflowEvent, AgentWorkflowRun, AgentWorkflowStep
from backend.app.models.chat_read_state import ChatReadState
from backend.app.models.project import ProjectApplication, ProjectEvent, ShootProject
from backend.app.models.photographer_application import PhotographerApplication
from backend.app.core.config import settings

# ---- 内存 SQLite 测试数据库 ----
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


# ---- Fixtures ----

@pytest.fixture(autouse=True)
def setup_db():
    """每个测试前创建所有表，测试后清理"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def mock_text_embeddings(monkeypatch):
    """单元测试使用确定性 mock，真实本地模型由专门集成验证覆盖。"""
    monkeypatch.setattr(settings, "AI_EMBEDDING_PROVIDER", "mock")
    monkeypatch.setattr(settings, "AI_TEXT_EMBEDDING_PROVIDER", "mock")


@pytest.fixture(autouse=True)
def clean_redis():
    """每个测试前清空 Redis 缓存，避免跨测试数据污染"""
    try:
        get_redis().flushall()
    except Exception:
        pass
    yield


@pytest.fixture
def db():
    """提供数据库会话"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    """提供 FastAPI TestClient"""
    with TestClient(app) as c:
        yield c


# ---- 用户 Fixtures ----

@pytest.fixture
def customer_user(db) -> User:
    """创建一个普通客户用户"""
    user = User(
        email="customer@test.com",
        phone="13800000001",
        hashed_password="$2b$12$dummyhash",  # 不实际验证的占位哈希
        display_name="测试客户",
        role="customer",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def photographer_user(db) -> User:
    """创建一个摄影师用户"""
    user = User(
        email="photographer@test.com",
        phone="13800000002",
        hashed_password="$2b$12$dummyhash",
        display_name="测试摄影师",
        bio="擅长自然光日系人像，也喜欢用胶片质感记录校园写真。",
        role="photographer",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_user(db) -> User:
    """创建一个管理员用户"""
    user = User(
        email="admin@test.com",
        phone="13800000003",
        hashed_password="$2b$12$dummyhash",
        display_name="管理员",
        role="customer",
        is_admin=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---- 认证 Headers Fixtures ----

@pytest.fixture
def customer_headers(customer_user) -> dict:
    """客户认证头"""
    token = create_access_token({"sub": str(customer_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def photographer_headers(photographer_user) -> dict:
    """摄影师认证头"""
    token = create_access_token({"sub": str(photographer_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(admin_user) -> dict:
    """管理员认证头"""
    token = create_access_token({"sub": str(admin_user.id), "is_admin": True})
    return {"Authorization": f"Bearer {token}"}


# ---- Order Fixture ----

@pytest.fixture
def pending_order(db, customer_user, photographer_user) -> Order:
    """创建一个待确认的订单"""
    from datetime import datetime
    order = Order(
        customer_id=customer_user.id,
        photographer_id=photographer_user.id,
        package_snapshot="个人写真 - ¥699/120分钟",
        appointment_time=datetime(2026, 7, 1, 14, 0, 0),
        duration_minutes=120,
        notes="拍摄需求描述",
        status=OrderStatus.PENDING,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


# ---- Photographer Profile Fixture ----

@pytest.fixture
def photographer_profile(db, photographer_user) -> PhotographerProfile:
    """创建摄影师资料"""
    profile = PhotographerProfile(
        user_id=photographer_user.id,
        location="北京",
        styles=["日系", "复古", "人像", "婚纱"],
        equipment="Canon R5 + 85mm f/1.2",
        packages=[
            {
                "id": "package-test-1",
                "name": "个人写真",
                "price": 699,
                "duration": 120,
                "description": "2小时外景拍摄",
                "includes": ["精修30张", "底片全送"],
                "styles": ["日系", "自然光"],
                "image_count": 30,
                "service_location": "北京市内",
                "original_image_count": 120,
                "retouched_image_count": 30,
                "delivery_formats": ["JPG", "PNG"],
                "included_revision_count": 1,
                "delivery_days": 7,
                "commercial_license": False,
                "copyright_terms": "著作权归摄影师，客户享有个人用途使用权。",
                "cancellation_policy": {"version": 1, "description": "确认前可取消"},
                "reschedule_policy": {"version": 1, "response_hours": 24},
                "payment_mode": "full",
                "fulfillment_mode": "single_delivery",
                "is_active": True,
                "samples": ["/static/sample.jpg"],
            }
        ],
        portfolio=[
            {
                "url": "/static/1.jpg",
                "thumbnail_url": "/static/1_thumb.jpg",
                "media_type": "image",
                "tag": "人像",
                "tags": ["日系", "校园"],
                "title": "春日写真",
                "description": "自然光、清新、校园氛围的日系写真。",
            },
            {"url": "/static/2.jpg", "tag": "婚纱", "title": "浪漫婚礼"},
        ],
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile
