"""管理后台服务：用户与订单的管理操作。"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.user import User
from backend.app.models.order import Order
from backend.app.services.order_service import admin_cancel_order_transition


def get_dashboard_stats(db: Session) -> dict:
    """仪表盘统计数据"""
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_photographers = db.query(func.count(User.id)).filter(User.role == "photographer").scalar() or 0
    total_customers = db.query(func.count(User.id)).filter(User.role == "customer").scalar() or 0
    total_orders = db.query(func.count(Order.id)).scalar() or 0
    pending_orders = db.query(func.count(Order.id)).filter(Order.status == "pending").scalar() or 0
    today_orders = db.query(func.count(Order.id)).filter(
        func.date(Order.created_at) == func.date(func.now())
    ).scalar() or 0

    return {
        "total_users": total_users,
        "total_photographers": total_photographers,
        "total_customers": total_customers,
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "today_orders": today_orders,
    }


def get_all_users(db: Session, skip: int = 0, limit: int = 50) -> list[User]:
    """分页查询全部用户。"""
    return db.query(User).offset(skip).limit(limit).all()


def ban_user(db: Session, user_id: int) -> User | None:
    """封禁指定用户。"""
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.is_banned = True
        db.commit()
        db.refresh(user)
    return user


def unban_user(db: Session, user_id: int) -> User | None:
    """解除对指定用户的封禁。"""
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.is_banned = False
        db.commit()
        db.refresh(user)
    return user


def get_all_orders(db: Session, skip: int = 0, limit: int = 50) -> list[Order]:
    """按创建时间倒序分页查询全部订单。"""
    return db.query(Order).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()


def admin_cancel_order(db: Session, order_id: int, admin_id: int, reason: str) -> Order | None:
    """管理员取消指定订单并记录原因。"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if order:
        return admin_cancel_order_transition(db, order, admin_id, reason)
    return order
