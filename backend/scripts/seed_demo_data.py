"""Create the repeatable local/demo dataset.

The command is deliberately additive: it only owns records identified by the
three demo email addresses and the ``demo-*`` resource keys.  It never clears
the database or modifies unrelated user content.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.core.database import Base, SessionLocal, engine
from backend.app.core.security import hash_password
from backend.app.models.ai_conversation import AIConversation, AIMessage
from backend.app.models.ai_resource import AIResourceDocument
from backend.app.models.message import Message
from backend.app.models.order import Order, OrderStatus
from backend.app.models.order_delivery import OrderDelivery, OrderDeliveryFile, OrderRevisionRequest  # noqa: F401
from backend.app.models.order_dispute import AdminAuditLog, OrderDispute, OrderDisputeEvidence  # noqa: F401
from backend.app.models.order_event import OrderEvent  # noqa: F401
from backend.app.models.order_reschedule import OrderRescheduleRequest  # noqa: F401
from backend.app.models.notification import OrderNotification, OutboxEvent  # noqa: F401
from backend.app.models.payment import Payment, PaymentStatus
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.photographer_application import PhotographerApplication  # noqa: F401
from backend.app.models.project import ProjectApplication, ProjectApplicationStatus, ProjectStatus, ShootProject
from backend.app.models.user import User


ROOT = Path(__file__).resolve().parents[2]
ASSET_SOURCE = ROOT / "docs" / "example-pictures"
DEMO_ASSET_DIR = ROOT / "uploads" / "demo"
PASSWORD = "Demo123456!"
DEMO_USERS = {
    "customer": ("customer.demo@example.com", "Demo Customer", "customer"),
    "photographer": ("photographer.demo@example.com", "Demo Photographer", "photographer"),
    "admin": ("admin.demo@example.com", "Demo Admin", "admin"),
}


def _asset_urls() -> list[str]:
    """准备演示图片并返回对应的静态访问 URL 列表。"""
    files = sorted(p for p in ASSET_SOURCE.iterdir() if p.is_file())[:12]
    if not files:
        raise RuntimeError(f"No demo assets found in {ASSET_SOURCE}")
    DEMO_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    urls = []
    for source in files:
        target = DEMO_ASSET_DIR / source.name
        if not target.exists() or target.stat().st_size != source.stat().st_size:
            shutil.copy2(source, target)
        urls.append(f"/static/demo/{source.name}")
    return urls


def _user(db: Session, key: str) -> User:
    """按 key 获取或创建对应的演示用户并返回。"""
    email, name, role = DEMO_USERS[key]
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is None:
        user = User(
            username=f"demo_{key}", email=email, display_name=name,
            hashed_password=hash_password(PASSWORD), role=role,
            is_admin=key == "admin", is_active=True,
        )
        db.add(user)
        db.flush()
    return user


def _profile(db: Session, user: User, urls: list[str], index: int) -> PhotographerProfile:
    """获取或创建摄影师资料，并用演示套餐与作品集填充。"""
    profile = db.query(PhotographerProfile).filter_by(user_id=user.id).one_or_none()
    if profile is None:
        profile = PhotographerProfile(user_id=user.id)
        db.add(profile)
    profile.location = ["Hong Kong", "Shenzhen", "Shanghai"][index]
    profile.styles = [["portrait", "film"], ["wedding", "documentary"], ["fashion", "editorial"]][index]
    profile.equipment = "Sony A7 IV / natural light"
    profile.packages = [
        {"id": f"demo-package-{index}-1", "name": "城市人像", "price": 1299 + index * 300, "duration": 120, "includes": ["精修 30 张", "底片全送"], "image_count": 30},
        {"id": f"demo-package-{index}-2", "name": "半日创作", "price": 2399 + index * 400, "duration": 240, "includes": ["精修 60 张", "短视频花絮"], "image_count": 60},
    ]
    profile.portfolio = [{"url": url, "title": f"Demo work {n + 1}", "city": profile.location, "styles": profile.styles} for n, url in enumerate(urls[index * 4:index * 4 + 4])]
    return profile


def seed_demo_data(db: Session) -> dict[str, int]:
    """写入整套演示数据（用户、项目、订单、AI 资源等），返回各项数量统计。"""
    urls = _asset_urls()
    customer = _user(db, "customer")
    photographer = _user(db, "photographer")
    admin = _user(db, "admin")
    primary_profile = _profile(db, photographer, urls, 0)
    # Two additional approved/pending photographer accounts make admin review demos meaningful.
    for index, key in enumerate(("photographer-2", "photographer-3"), start=1):
        email = f"{key}.demo@example.com"
        user = db.query(User).filter_by(email=email).one_or_none()
        if user is None:
            user = User(username=key.replace("-", "_"), email=email, display_name=f"Demo Photographer {index + 1}", hashed_password=hash_password(PASSWORD), role="photographer")
            db.add(user); db.flush()
        _profile(db, user, urls, index)

    now = datetime.now()
    projects = []
    specs = [("夏日城市人像企划", "Hong Kong", ProjectStatus.OPEN), ("复古婚礼纪实", "Shenzhen", ProjectStatus.DRAFT), ("棚拍风格招募", "Shanghai", ProjectStatus.CLOSED)]
    for title, city, status in specs:
        project = db.query(ShootProject).filter_by(title=title, customer_id=customer.id).one_or_none()
        if project is None:
            project = ShootProject(customer_id=customer.id, title=title, description=f"Demo project: {title}", category="portrait", style_tags=["film", "editorial"], city=city, location_text=f"{city} central", shoot_date_start=now + timedelta(days=14), shoot_date_end=now + timedelta(days=14, hours=4), duration_minutes=120, budget_min=1200, budget_max=2600, deliverables=["精修照片", "网络交付"], reference_images=urls[:2], visibility="public", status=status, expires_at=now + timedelta(days=7))
            db.add(project); db.flush()
        projects.append(project)

    application = db.query(ProjectApplication).filter_by(project_id=projects[0].id, photographer_id=photographer.id).one_or_none()
    if application is None:
        application = ProjectApplication(project_id=projects[0].id, photographer_id=photographer.id, status=ProjectApplicationStatus.SUBMITTED, proposal_text="我可以用自然光完成这组城市人像。", price_quote=1800, duration_minutes=120, available_time=now + timedelta(days=14), package_snapshot="城市人像", portfolio_refs=primary_profile.portfolio[:2], included_items=["精修 30 张"])
        db.add(application); db.flush()

    order = db.query(Order).filter_by(source_id="demo-order-1").one_or_none()
    if order is None:
        order = Order(customer_id=customer.id, photographer_id=photographer.id, package_snapshot="城市人像 - CNY 1800", source_type="demo", source_id="demo-order-1", package_id="demo-package-0-1", package_name="城市人像", package_price=Decimal("1800"), final_price=Decimal("1800"), currency="CNY", service_location="Central, Hong Kong", appointment_time=now + timedelta(days=14), duration_minutes=120, status=OrderStatus.AWAITING_PAYMENT, payment_status="unpaid", payment_mode="full", fulfillment_mode="single_delivery", delivery_formats=["JPG"], notes="Demo order for the customer/photographer walkthrough")
        db.add(order); db.flush()
        db.add(Payment(payment_no="PAY-DEMO-0001", order_id=order.id, customer_id=customer.id, purpose="full", amount=Decimal("1800"), currency="CNY", status=PaymentStatus.PENDING.value, provider="mock", idempotency_key="demo-payment-1", expires_at=now + timedelta(days=1)))

    if not db.query(Message).filter_by(order_id=order.id).first():
        db.add_all([Message(sender_id=customer.id, receiver_id=photographer.id, order_id=order.id, content="你好，我想确认一下拍摄地点。"), Message(sender_id=photographer.id, receiver_id=customer.id, order_id=order.id, content="可以在中环或上环取景，稍后确认具体时间。")])

    resource_rows = [("photographer", photographer, primary_profile.portfolio), ("shoot_project", customer, [projects[0].reference_images[0]]), ("package", photographer, [primary_profile.packages[0]])]
    for resource_type, owner, payload in resource_rows:
        resource_id = f"demo-{resource_type}-1"
        existing = db.query(AIResourceDocument).filter_by(resource_type=resource_type, resource_id=resource_id).one_or_none()
        data = {"type": resource_type, "owner_user_id": owner.id, "title": f"Demo {resource_type}", "payload": payload}
        encoded = repr(data).encode()
        if existing is None:
            db.add(AIResourceDocument(resource_type=resource_type, resource_id=resource_id, owner_user_id=owner.id, title=data["title"], summary="Stable demo resource", search_text=f"demo {resource_type} Hong Kong portrait film", tags=["demo", "film"], city="Hong Kong", price_min=1200, price_max=2600, payload=data, content_hash=hashlib.sha256(encoded).hexdigest()))

    conversation = db.query(AIConversation).filter_by(user_id=customer.id, title="Demo AI 助手").one_or_none()
    if conversation is None:
        conversation = AIConversation(user_id=customer.id, title="Demo AI 助手"); db.add(conversation); db.flush()
        db.add_all([AIMessage(conversation_id=conversation.id, role="user", content="我想在香港拍一组胶片人像", message_metadata={"demo": True}), AIMessage(conversation_id=conversation.id, role="assistant", content="我找到了一位适合的摄影师，可以先查看城市人像套餐。", message_metadata={"demo": True, "references": [{"type": "photographer", "id": "demo-photographer-1"}]})])

    db.commit()
    return {"users": 5, "projects": len(projects), "orders": 1, "assets": len(urls)}


def main() -> int:
    """命令行入口：初始化表结构并执行演示数据填充。"""
    parser = argparse.ArgumentParser(description="Seed repeatable local demo data")
    parser.parse_args()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        summary = seed_demo_data(db)
    print("Demo seed complete: " + ", ".join(f"{key}={value}" for key, value in summary.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
