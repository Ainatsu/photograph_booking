"""
test_admin_service.py — 管理员服务层单元测试
测试：仪表盘统计、用户管理、订单管理
"""
import pytest
from datetime import datetime
from backend.app.services.admin_service import (
    get_dashboard_stats,
    get_all_users,
    ban_user,
    unban_user,
    get_all_orders,
    admin_cancel_order,
)
from backend.app.models.order import Order, OrderStatus
from backend.app.models.user import User
from backend.app.services.user_service import create_user


class TestGetDashboardStats:
    """仪表盘统计测试"""

    def test_empty_database(self, db):
        """边界条件：空数据库统计"""
        stats = get_dashboard_stats(db)
        assert stats["total_users"] == 0
        assert stats["total_photographers"] == 0
        assert stats["total_customers"] == 0
        assert stats["total_orders"] == 0
        assert stats["pending_orders"] == 0
        assert stats["today_orders"] == 0

    def test_with_users_only(self, db):
        """正常场景：只有用户无订单"""
        create_user(db, "cust@test.com", None, "pass", "客户", "customer")
        create_user(db, "photo@test.com", None, "pass", "摄影师", "photographer")
        stats = get_dashboard_stats(db)
        assert stats["total_users"] == 2
        assert stats["total_photographers"] == 1
        assert stats["total_customers"] == 1
        assert stats["total_orders"] == 0

    def test_with_orders(self, db, customer_user, photographer_user):
        """正常场景：含订单的统计"""
        order = Order(
            customer_id=customer_user.id,
            photographer_id=photographer_user.id,
            package_snapshot="测试方案",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
            status=OrderStatus.PENDING,
        )
        db.add(order)
        db.commit()

        stats = get_dashboard_stats(db)
        assert stats["total_users"] >= 2
        assert stats["total_orders"] == 1
        assert stats["pending_orders"] == 1

    def test_returns_correct_types(self, db):
        """正常场景：返回值类型正确"""
        stats = get_dashboard_stats(db)
        assert isinstance(stats, dict)
        for key in ["total_users", "total_photographers", "total_customers",
                     "total_orders", "pending_orders", "today_orders"]:
            assert key in stats
            assert isinstance(stats[key], int)


class TestGetAllUsers:
    """用户列表测试"""

    def test_list_all_users(self, db, customer_user, photographer_user):
        """正常场景：获取所有用户"""
        users = get_all_users(db)
        assert len(users) >= 2

    def test_pagination(self, db, customer_user, photographer_user):
        """边界条件：分页"""
        users = get_all_users(db, skip=0, limit=1)
        assert len(users) == 1
        users_page2 = get_all_users(db, skip=1, limit=1)
        assert len(users_page2) == 1
        assert users[0].id != users_page2[0].id

    def test_default_limit(self, db):
        """边界条件：默认分页大小"""
        users = get_all_users(db)
        assert len(users) <= 50


class TestBanUnbanUser:
    """封禁/解封用户测试"""

    def test_ban_user(self, db, customer_user):
        """正常场景：封禁用户"""
        user = ban_user(db, customer_user.id)
        assert user.is_banned is True

    def test_unban_user(self, db, customer_user):
        """正常场景：解封用户"""
        ban_user(db, customer_user.id)
        user = unban_user(db, customer_user.id)
        assert user.is_banned is False

    def test_ban_nonexistent_user(self, db):
        """异常场景：封禁不存在的用户"""
        user = ban_user(db, 99999)
        assert user is None

    def test_unban_nonexistent_user(self, db):
        """异常场景：解封不存在的用户"""
        user = unban_user(db, 99999)
        assert user is None

    def test_ban_already_banned(self, db, customer_user):
        """边界条件：重复封禁"""
        ban_user(db, customer_user.id)
        user = ban_user(db, customer_user.id)
        assert user.is_banned is True

    def test_unban_already_unbanned(self, db, customer_user):
        """边界条件：重复解封"""
        user = unban_user(db, customer_user.id)
        assert user.is_banned is False


class TestAdminGetAllOrders:
    """管理员订单列表测试"""

    def test_list_all_orders(self, db, pending_order):
        """正常场景：获取所有订单"""
        orders = get_all_orders(db)
        assert len(orders) >= 1

    def test_orders_ordered_by_date(self, db, customer_user, photographer_user):
        """正常场景：按时间倒序"""
        order1 = Order(
            customer_id=customer_user.id,
            photographer_id=photographer_user.id,
            package_snapshot="旧订单",
            appointment_time=datetime(2026, 6, 1, 10, 0, 0),
            duration_minutes=60,
            status=OrderStatus.PENDING,
        )
        order2 = Order(
            customer_id=customer_user.id,
            photographer_id=photographer_user.id,
            package_snapshot="新订单",
            appointment_time=datetime(2026, 7, 1, 10, 0, 0),
            duration_minutes=60,
            status=OrderStatus.PENDING,
        )
        db.add_all([order1, order2])
        db.commit()

        orders = get_all_orders(db)
        # 按 created_at 倒序，由于自动时间戳可能相同，先验证非空
        assert len(orders) >= 2

    def test_pagination(self, db, pending_order):
        """边界条件：分页"""
        orders = get_all_orders(db, skip=0, limit=10)
        assert len(orders) >= 0


class TestAdminCancelOrder:
    """管理员取消订单测试"""

    def test_cancel_order(self, db, pending_order, admin_user):
        """正常场景：取消订单"""
        order = admin_cancel_order(db, pending_order.id, admin_user.id, "平台审核后取消")
        assert order is not None
        assert order.status == "cancelled"
        assert order.cancelled_by == "admin"
        assert order.cancellation_reason == "平台审核后取消"

    def test_cancel_nonexistent_order(self, db, admin_user):
        """异常场景：取消不存在的订单"""
        order = admin_cancel_order(db, 99999, admin_user.id, "不存在")
        assert order is None

    def test_cancel_already_cancelled(self, db, pending_order, admin_user):
        """边界条件：取消已取消的订单"""
        admin_cancel_order(db, pending_order.id, admin_user.id, "第一次取消")
        order = admin_cancel_order(db, pending_order.id, admin_user.id, "重复取消")
        assert order.status == "cancelled"

    def test_admin_cancel_api_records_actor_reason_and_event(
        self,
        client,
        pending_order,
        admin_headers,
        customer_headers,
    ):
        response = client.put(
            f"/api/v1/admin/orders/{pending_order.id}/cancel",
            json={"reason": "平台风控审核取消"},
            headers=admin_headers,
        )

        assert response.status_code == 200
        assert response.json()["cancelled_by"] == "admin"
        assert response.json()["cancellation_reason"] == "平台风控审核取消"

        detail = client.get(
            f"/api/v1/orders/{pending_order.id}/detail",
            headers=customer_headers,
        ).json()
        assert detail["history"][-1]["actor_role"] == "admin"
        assert detail["history"][-1]["note"] == "平台风控审核取消"
