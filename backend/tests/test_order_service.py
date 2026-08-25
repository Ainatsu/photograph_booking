"""
test_order_service.py — 订单服务层单元测试
测试：创建订单、时间冲突检测、状态流转、订单查询
"""
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified

from backend.app.models.order import Order, OrderStatus
from backend.app.models.order_reschedule import OrderRescheduleRequest, OrderRescheduleStatus
from backend.app.models.photographer import PhotographerProfile
from backend.app.schemas.order import OrderCreateRequest
from backend.app.services.order_service import (
    cancel_order,
    counter_order_reschedule,
    confirm_order_reschedule,
    create_order,
    get_order_by_id,
    get_order_detail,
    get_order_history,
    request_order_reschedule,
    respond_order_reschedule,
    transition_order,
    withdraw_order_reschedule,
    OrderAction,
    update_order_status,
    get_my_orders_as_customer,
    get_my_orders_as_photographer,
    get_photographer_stats,
)


class TestCreateOrder:
    """订单创建测试"""

    def test_create_order_success(self, db, customer_user, photographer_user):
        """正常场景：创建订单成功"""
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="个人写真 - ¥699/120分钟",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=120,
            notes="外景拍摄",
        )
        order = create_order(db, customer_user.id, data)
        assert order.id is not None
        assert order.status == OrderStatus.PENDING
        assert order.customer_id == customer_user.id
        assert order.photographer_id == photographer_user.id
        assert order.source_type == "legacy"
        assert order.currency == "CNY"
        assert order.final_price is None
        assert order.contract_snapshot["source"]["type"] == "legacy"

    def test_create_order_photographer_not_found(self, db, customer_user):
        """异常场景：摄影师不存在"""
        data = OrderCreateRequest(
            photographer_id=99999,
            package_description="测试",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        with pytest.raises(HTTPException) as exc:
            create_order(db, customer_user.id, data)
        assert exc.value.status_code == 404

    def test_create_order_photographer_not_role(self, db, customer_user):
        """异常场景：用户不是摄影师角色"""
        data = OrderCreateRequest(
            photographer_id=customer_user.id,
            package_description="测试",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        with pytest.raises(HTTPException) as exc:
            create_order(db, customer_user.id, data)
        assert exc.value.status_code == 400
        assert "自己" in exc.value.detail

    def test_create_order_with_notes(self, db, customer_user, photographer_user):
        """正常场景：含备注信息的订单"""
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="婚纱摄影 - ¥2999/360分钟",
            appointment_time=datetime(2026, 8, 15, 10, 0, 0),
            duration_minutes=360,
            notes="需要去海边拍摄",
        )
        order = create_order(db, customer_user.id, data)
        assert order.notes == "需要去海边拍摄"

    def test_package_order_uses_server_contract_and_cny(
        self,
        db,
        customer_user,
        photographer_user,
        photographer_profile,
    ):
        data = OrderCreateRequest(
            package_id="package-test-1",
            photographer_id=photographer_user.id,
            package_description="篡改价格 - ¥1/1分钟",
            appointment_time=datetime(2026, 8, 1, 10, 0, 0),
            duration_minutes=1,
            notes="希望安排自然光拍摄",
        )

        order = create_order(db, customer_user.id, data)

        assert order.source_type == "package"
        assert order.source_id == "package-test-1"
        assert order.package_id == "package-test-1"
        assert order.package_name == "个人写真"
        assert order.package_price == Decimal("699.00")
        assert order.final_price == Decimal("699.00")
        assert order.currency == "CNY"
        assert order.duration_minutes == 120
        assert order.service_location == "北京市内"
        assert order.delivery_due_at == datetime(2026, 8, 8, 10, 0, 0)
        assert order.original_image_count == 120
        assert order.retouched_image_count == 30
        assert order.delivery_formats == ["JPG", "PNG"]
        assert order.included_revision_count == 1
        assert order.contract_snapshot["pricing"] == {
            "package_price": 699.0,
            "final_price": 699.0,
            "currency": "CNY",
        }
        assert order.contract_snapshot["customer_notes"] == "希望安排自然光拍摄"

    def test_package_contract_snapshot_is_not_changed_by_later_package_edits(
        self,
        db,
        customer_user,
        photographer_user,
        photographer_profile,
    ):
        order = create_order(
            db,
            customer_user.id,
            OrderCreateRequest(
                package_id="package-test-1",
                photographer_id=photographer_user.id,
                appointment_time=datetime(2026, 8, 2, 10, 0, 0),
            ),
        )
        original_snapshot = order.contract_snapshot

        packages = [dict(item) for item in photographer_profile.packages]
        packages[0]["price"] = 9999
        packages[0]["duration"] = 30
        packages[0]["description"] = "新方案内容"
        photographer_profile.packages = packages
        flag_modified(photographer_profile, "packages")
        db.commit()
        db.expire(order)

        assert order.final_price == Decimal("699.00")
        assert order.duration_minutes == 120
        assert order.contract_snapshot == original_snapshot

    def test_package_must_belong_to_submitted_photographer(
        self,
        db,
        customer_user,
        photographer_profile,
    ):
        from backend.app.models.user import User

        other = User(
            email="package-owner-mismatch@test.com",
            hashed_password="hash",
            display_name="另一位摄影师",
            role="photographer",
        )
        db.add(other)
        db.commit()
        db.refresh(other)

        with pytest.raises(HTTPException) as exc:
            create_order(
                db,
                customer_user.id,
                OrderCreateRequest(
                    package_id="package-test-1",
                    photographer_id=other.id,
                    appointment_time=datetime(2026, 8, 3, 10, 0, 0),
                ),
            )

        assert exc.value.status_code == 400
        assert "不属于" in exc.value.detail

    def test_inactive_package_cannot_be_booked(
        self,
        db,
        customer_user,
        photographer_user,
        photographer_profile,
    ):
        packages = [dict(item) for item in photographer_profile.packages]
        packages[0]["is_active"] = False
        photographer_profile.packages = packages
        flag_modified(photographer_profile, "packages")
        db.commit()

        with pytest.raises(HTTPException) as exc:
            create_order(
                db,
                customer_user.id,
                OrderCreateRequest(
                    package_id="package-test-1",
                    photographer_id=photographer_user.id,
                    appointment_time=datetime(2026, 8, 4, 10, 0, 0),
                ),
            )

        assert exc.value.status_code == 404
        assert "停止预约" in exc.value.detail

    def test_database_rejects_non_cny_order_currency(
        self,
        db,
        customer_user,
        photographer_user,
    ):
        order = Order(
            customer_id=customer_user.id,
            photographer_id=photographer_user.id,
            package_snapshot="非法币种测试",
            appointment_time=datetime(2026, 8, 5, 10, 0, 0),
            duration_minutes=60,
            currency="USD",
            status=OrderStatus.PENDING,
        )
        db.add(order)

        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_create_order_zero_duration_raises_error(self):
        """边界条件：服务时长为0的请求在 Pydantic 验证拦截"""
        with pytest.raises(Exception):
            OrderCreateRequest(
                photographer_id=1,
                package_description="测试",
                appointment_time=datetime(2026, 7, 1, 14, 0, 0),
                duration_minutes=0,
            )

    def test_create_order_negative_duration_raises_error(self):
        """边界条件：负服务时长的请求在 Pydantic 验证拦截"""
        with pytest.raises(Exception):
            OrderCreateRequest(
                photographer_id=1,
                package_description="测试",
                appointment_time=datetime(2026, 7, 1, 14, 0, 0),
                duration_minutes=-60,
            )

    def test_time_conflict_detected(self, db, customer_user, photographer_user):
        """异常场景：时间冲突（完全重叠）"""
        # 先创建第一个订单
        data1 = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="预约 A",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=120,
        )
        order1 = create_order(db, customer_user.id, data1)
        # 手动确认为已确认（使其参与冲突检测）
        order1.status = OrderStatus.CONFIRMED
        db.commit()

        # 尝试创建完全重叠的订单
        data2 = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="预约 B",
            appointment_time=datetime(2026, 7, 1, 15, 0, 0),
            duration_minutes=60,
        )
        with pytest.raises(HTTPException) as exc:
            create_order(db, customer_user.id, data2)
        assert exc.value.status_code == 409
        assert "冲突" in exc.value.detail or "预约" in exc.value.detail

    def test_no_conflict_on_different_times(self, db, customer_user, photographer_user):
        """正常场景：不同时段不冲突"""
        data1 = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="预约 A",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order1 = create_order(db, customer_user.id, data1)
        order1.status = OrderStatus.CONFIRMED
        db.commit()

        # 不重叠的预约（14:00-15:00 之后）
        data2 = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="预约 B",
            appointment_time=datetime(2026, 7, 1, 15, 0, 0),
            duration_minutes=60,
        )
        order2 = create_order(db, customer_user.id, data2)
        assert order2.id is not None

    def test_create_order_defaults_to_available_when_not_busy(self, db, customer_user, photographer_user):
        profile = PhotographerProfile(
            user_id=photographer_user.id,
        )
        db.add(profile)
        db.commit()

        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="预约 B",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)
        assert order.id is not None

    def test_create_order_manual_busy_exception_rejected(self, db, customer_user, photographer_user):
        profile = PhotographerProfile(
            user_id=photographer_user.id,
            availability_exceptions=[
                {"date": "2026-07-01", "status": "busy", "location": "外部拍摄"},
            ],
        )
        db.add(profile)
        db.commit()

        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="预约 B",
            appointment_time=datetime(2026, 7, 1, 15, 0, 0),
            duration_minutes=60,
        )
        with pytest.raises(HTTPException) as exc:
            create_order(db, customer_user.id, data)
        assert exc.value.status_code == 409
        assert "档期" in exc.value.detail


class TestUpdateOrderStatus:
    """订单状态更新测试"""

    def test_confirm_pending_order(self, db, photographer_user, customer_user):
        """正常场景：确认待处理订单"""
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="测试方案",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)

        updated = update_order_status(db, order, OrderStatus.CONFIRMED, photographer_user.id)
        assert updated.status == OrderStatus.CONFIRMED

    def test_cancel_pending_order(self, db, photographer_user, customer_user):
        """正常场景：取消待处理订单"""
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="测试方案",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)

        updated = update_order_status(
            db,
            order,
            OrderStatus.CANCELLED,
            photographer_user.id,
            rejection_reason="该时间段已有拍摄安排",
        )
        assert updated.status == OrderStatus.CANCELLED
        assert updated.rejection_reason == "该时间段已有拍摄安排"

    def test_cancel_pending_order_requires_reason(self, db, photographer_user, customer_user):
        """异常场景：拒绝待处理订单必须填写原因"""
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="测试方案",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)

        with pytest.raises(HTTPException) as exc:
            update_order_status(db, order, OrderStatus.CANCELLED, photographer_user.id)
        assert exc.value.status_code == 400
        assert "原因" in exc.value.detail

    def test_wrong_photographer_forbidden(self, db, photographer_user, customer_user):
        """异常场景：非订单所属摄影师无权更新"""
        # 创建第二个摄影师
        from backend.app.models.user import User
        other_photographer = User(
            email="other_photographer@test.com",
            hashed_password="hash",
            display_name="其他摄影师",
            role="photographer",
        )
        db.add(other_photographer)
        db.commit()
        db.refresh(other_photographer)

        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="测试方案",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)

        with pytest.raises(HTTPException) as exc:
            update_order_status(db, order, OrderStatus.CONFIRMED, other_photographer.id)
        assert exc.value.status_code == 403

    def test_invalid_status_transition(self, db, photographer_user, customer_user):
        """异常场景：无效的状态流转（PENDING -> DELIVERED）"""
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="测试方案",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)

        with pytest.raises(HTTPException) as exc:
            update_order_status(db, order, OrderStatus.DELIVERED, photographer_user.id)
        assert exc.value.status_code == 400

    def test_full_lifecycle(self, db, photographer_user, customer_user):
        """正常场景：完整订单生命周期 PENDING->CONFIRMED->IN_PROGRESS->DELIVERED"""
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="测试方案",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)

        order = update_order_status(db, order, OrderStatus.CONFIRMED, photographer_user.id)
        assert order.status == OrderStatus.CONFIRMED

        order = update_order_status(db, order, OrderStatus.IN_PROGRESS, photographer_user.id)
        assert order.status == OrderStatus.IN_PROGRESS

        order = update_order_status(db, order, OrderStatus.DELIVERED, photographer_user.id)
        assert order.status == OrderStatus.DELIVERED


class TestOrderHistory:
    def test_create_order_records_history_event(self, db, customer_user, photographer_user):
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)

        history = get_order_history(db, order)
        assert len(history) == 1
        assert history[0]["event_type"] == "created"
        assert history[0]["status"] == OrderStatus.PENDING.value
        assert history[0]["actor_id"] == customer_user.id

    def test_status_changes_record_history_events(self, db, customer_user, photographer_user):
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)

        order = update_order_status(db, order, OrderStatus.CONFIRMED, photographer_user.id)
        order = update_order_status(db, order, OrderStatus.IN_PROGRESS, photographer_user.id)

        history = get_order_history(db, order)
        assert [item["event_type"] for item in history] == ["created", "confirmed", "in_progress"]
        assert history[-1]["status"] == OrderStatus.IN_PROGRESS.value
        assert history[-1]["actor_id"] == photographer_user.id

    def test_synthetic_history_for_existing_order_without_events(self, db, pending_order):
        history = get_order_history(db, pending_order)

        assert history[0]["event_type"] == "created"
        assert history[0]["status"] == OrderStatus.PENDING.value
        assert history[0]["actor_id"] == pending_order.customer_id


class TestRescheduleAndCancellation:
    def test_customer_requests_reschedule(self, db, customer_user, photographer_user):
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)
        update_order_status(db, order, OrderStatus.CONFIRMED, photographer_user.id)

        requested_time = datetime(2026, 7, 2, 15, 0, 0)
        updated = request_order_reschedule(
            db,
            order,
            customer_user.id,
            requested_time,
            "临时有事，需要调整时间",
        )

        assert updated.status == OrderStatus.CONFIRMED
        assert updated.reschedule_requested_time == requested_time
        assert updated.reschedule_reason == "临时有事，需要调整时间"
        request = db.query(OrderRescheduleRequest).filter_by(order_id=updated.id).one()
        assert request.status == OrderRescheduleStatus.PENDING
        assert request.original_appointment_time == datetime(2026, 7, 1, 14, 0, 0)
        history = get_order_history(db, updated)
        assert history[-1]["event_type"] == "reschedule_requested"

    def test_photographer_confirms_reschedule(self, db, customer_user, photographer_user):
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)
        update_order_status(db, order, OrderStatus.CONFIRMED, photographer_user.id)
        requested_time = datetime(2026, 7, 2, 15, 0, 0)
        order = request_order_reschedule(
            db,
            order,
            customer_user.id,
            requested_time,
            "临时有事，需要调整时间",
        )

        updated = confirm_order_reschedule(db, order, photographer_user.id)

        assert updated.status == OrderStatus.CONFIRMED
        assert updated.appointment_time == requested_time
        assert updated.reschedule_requested_time is None
        assert updated.reschedule_reason is None
        history = get_order_history(db, updated)
        assert history[-1]["event_type"] == "reschedule_accepted"

    def test_customer_cancel_order_records_reason(self, db, customer_user, photographer_user):
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)
        update_order_status(db, order, OrderStatus.CONFIRMED, photographer_user.id)

        updated = cancel_order(db, order, customer_user.id, "customer", "行程变化，取消拍摄")

        assert updated.status == OrderStatus.CANCELLED
        assert updated.cancellation_reason == "行程变化，取消拍摄"
        assert updated.cancelled_by == "customer"
        history = get_order_history(db, updated)
        assert history[-1]["event_type"] == "cancelled"
        assert history[-1]["note"] == "行程变化，取消拍摄"

    def test_reject_reschedule_keeps_original_appointment(self, db, customer_user, photographer_user):
        order = create_order(db, customer_user.id, OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        ))
        update_order_status(db, order, OrderStatus.CONFIRMED, photographer_user.id)
        request_order_reschedule(
            db, order, customer_user.id, datetime(2026, 7, 2, 15, 0, 0), "临时有事"
        )

        updated = respond_order_reschedule(
            db, order, photographer_user.id, "reject", response_note="新时间无法安排"
        )

        assert updated.appointment_time == datetime(2026, 7, 1, 14, 0, 0)
        request = db.query(OrderRescheduleRequest).filter_by(order_id=order.id).one()
        assert request.status == OrderRescheduleStatus.REJECTED

    def test_requester_can_withdraw_reschedule(self, db, customer_user, photographer_user):
        order = create_order(db, customer_user.id, OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        ))
        update_order_status(db, order, OrderStatus.CONFIRMED, photographer_user.id)
        request_order_reschedule(
            db, order, customer_user.id, datetime(2026, 7, 2, 15, 0, 0), "临时有事"
        )

        withdraw_order_reschedule(db, order, customer_user.id)

        request = db.query(OrderRescheduleRequest).filter_by(order_id=order.id).one()
        assert request.status == OrderRescheduleStatus.WITHDRAWN
        assert order.appointment_time == datetime(2026, 7, 1, 14, 0, 0)

    def test_counter_reschedule_creates_new_request(self, db, customer_user, photographer_user):
        order = create_order(db, customer_user.id, OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        ))
        update_order_status(db, order, OrderStatus.CONFIRMED, photographer_user.id)
        request_order_reschedule(
            db, order, customer_user.id, datetime(2026, 7, 2, 15, 0, 0), "客户候选"
        )

        counter_order_reschedule(
            db, order, photographer_user.id, datetime(2026, 7, 3, 16, 0, 0), "摄影师反提"
        )

        requests = db.query(OrderRescheduleRequest).filter_by(order_id=order.id).order_by(OrderRescheduleRequest.id).all()
        assert [request.status for request in requests] == [
            OrderRescheduleStatus.REJECTED,
            OrderRescheduleStatus.PENDING,
        ]
        assert requests[-1].requested_by == photographer_user.id

    def test_requested_slot_is_temporarily_locked(self, db, customer_user, photographer_user):
        from backend.app.models.user import User
        other_customer = User(
            email="other-customer@test.com",
            hashed_password="hash",
            display_name="其他客户",
            role="customer",
        )
        db.add(other_customer)
        db.commit()
        db.refresh(other_customer)

        order = create_order(db, customer_user.id, OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        ))
        update_order_status(db, order, OrderStatus.CONFIRMED, photographer_user.id)
        requested_time = datetime(2026, 7, 2, 15, 0, 0)
        request_order_reschedule(db, order, customer_user.id, requested_time, "临时有事")

        with pytest.raises(HTTPException) as exc:
            create_order(db, other_customer.id, OrderCreateRequest(
                photographer_id=photographer_user.id,
                package_description="conflicting package",
                appointment_time=requested_time,
                duration_minutes=60,
            ))
        assert exc.value.status_code == 409

    def test_expired_request_releases_candidate_slot(self, db, customer_user, photographer_user):
        order = create_order(db, customer_user.id, OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        ))
        update_order_status(db, order, OrderStatus.CONFIRMED, photographer_user.id)
        request_order_reschedule(
            db, order, customer_user.id, datetime(2026, 7, 2, 15, 0, 0), "临时有事"
        )
        request = db.query(OrderRescheduleRequest).filter_by(order_id=order.id).one()
        request.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
        db.commit()

        detail = get_order_detail(db, order)

        db.refresh(request)
        assert request.status == OrderRescheduleStatus.EXPIRED
        assert detail["order"]["active_reschedule_request"] is None


class TestRelationshipBasedOrderPermissions:
    def test_photographer_can_be_customer_for_another_photographer(self, db, photographer_user):
        from backend.app.models.user import User
        provider = User(
            email="provider-two@test.com",
            hashed_password="hash",
            display_name="第二位摄影师",
            role="photographer",
        )
        db.add(provider)
        db.commit()
        db.refresh(provider)

        order = create_order(db, photographer_user.id, OrderCreateRequest(
            photographer_id=provider.id,
            package_description="摄影师互约",
            appointment_time=datetime(2026, 8, 1, 10, 0, 0),
            duration_minutes=60,
        ))
        transition_order(
            db, order=order, action=OrderAction.ACCEPT_BOOKING, actor_id=provider.id
        )
        request_order_reschedule(
            db, order, photographer_user.id, datetime(2026, 8, 2, 10, 0, 0), "作为客户申请改期"
        )
        respond_order_reschedule(db, order, provider.id, "accept")
        transition_order(db, order=order, action=OrderAction.START_SERVICE, actor_id=provider.id)
        transition_order(
            db,
            order=order,
            action=OrderAction.SUBMIT_DELIVERY,
            actor_id=provider.id,
            payload={"delivery": {"images": ["/test.jpg"], "description": "交付"}},
        )
        transition_order(db, order=order, action=OrderAction.ACCEPT_DELIVERY, actor_id=photographer_user.id)
        transition_order(
            db,
            order=order,
            action=OrderAction.SUBMIT_REVIEW,
            actor_id=photographer_user.id,
            payload={"rating": 10, "review_text": "很好"},
        )

        assert order.status == OrderStatus.COMPLETED
        assert order.customer_id == photographer_user.id

    def test_unrelated_user_cannot_transition_order(self, db, pending_order):
        from backend.app.models.user import User
        stranger = User(
            email="stranger@test.com",
            hashed_password="hash",
            display_name="无关用户",
            role="customer",
        )
        db.add(stranger)
        db.commit()
        db.refresh(stranger)

        with pytest.raises(HTTPException) as exc:
            transition_order(
                db,
                order=pending_order,
                action=OrderAction.ACCEPT_BOOKING,
                actor_id=stranger.id,
            )
        assert exc.value.status_code == 403

    def test_repeated_transition_does_not_duplicate_event(self, db, customer_user, photographer_user):
        order = create_order(db, customer_user.id, OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 9, 1, 10, 0, 0),
            duration_minutes=60,
        ))
        transition_order(db, order=order, action=OrderAction.ACCEPT_BOOKING, actor_id=photographer_user.id)
        before = len(get_order_history(db, order))

        transition_order(db, order=order, action=OrderAction.ACCEPT_BOOKING, actor_id=photographer_user.id)

        assert len(get_order_history(db, order)) == before


class TestOrderAPI:
    def test_place_order_requires_stable_package_id(self, client, customer_headers, photographer_user):
        res = client.post(
            "/api/v1/orders/",
            json={
                "photographer_id": photographer_user.id,
                "package_description": "客户端拼接方案",
                "appointment_time": "2026-08-05T10:00:00",
                "duration_minutes": 60,
            },
            headers=customer_headers,
        )

        assert res.status_code == 400
        assert "package_id" in res.json()["detail"]

    def test_place_order_rejects_client_currency_override(
        self,
        client,
        customer_headers,
        photographer_user,
        photographer_profile,
    ):
        res = client.post(
            "/api/v1/orders/",
            json={
                "package_id": "package-test-1",
                "photographer_id": photographer_user.id,
                "appointment_time": "2026-08-05T11:00:00",
                "currency": "USD",
            },
            headers=customer_headers,
        )

        assert res.status_code == 422

    def test_place_order_returns_structured_cny_contract(
        self,
        client,
        customer_headers,
        photographer_user,
        photographer_profile,
    ):
        res = client.post(
            "/api/v1/orders/",
            json={
                "package_id": "package-test-1",
                "photographer_id": photographer_user.id,
                "package_description": "篡改为 ¥1",
                "appointment_time": "2026-08-06T10:00:00",
                "duration_minutes": 1,
                "notes": "API 合同快照测试",
            },
            headers=customer_headers,
        )

        assert res.status_code == 201
        body = res.json()
        assert body["package_id"] == "package-test-1"
        assert body["final_price"] == "699.00"
        assert body["currency"] == "CNY"
        assert body["duration_minutes"] == 120
        assert body["contract_snapshot"]["currency"] == "CNY"

        detail_res = client.get(
            f"/api/v1/orders/{body['id']}/detail",
            headers=customer_headers,
        )
        assert detail_res.status_code == 200
        detail = detail_res.json()["order"]
        assert detail["final_price"] == "699.00"
        assert detail["delivery_formats"] == ["JPG", "PNG"]
        assert detail["included_revision_count"] == 1
        assert detail["contract_snapshot"]["source"]["type"] == "package"

    def test_order_detail_returns_history(self, client, db, customer_user, photographer_user, customer_headers):
        customer_user.avatar_url = "/static/avatars/customer.jpg"
        db.commit()
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)

        res = client.get(f"/api/v1/orders/{order.id}/detail", headers=customer_headers)

        assert res.status_code == 200
        body = res.json()
        assert body["order"]["id"] == order.id
        assert body["order"]["customer_name"] == customer_user.display_name
        assert body["order"]["customer_avatar_url"] == customer_user.avatar_url
        assert body["history"][0]["event_type"] == "created"

    def test_start_order_route_moves_to_in_progress(self, client, db, customer_user, photographer_user, photographer_headers):
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)
        update_order_status(db, order, OrderStatus.CONFIRMED, photographer_user.id)

        res = client.put(f"/api/v1/orders/{order.id}/start", headers=photographer_headers)

        assert res.status_code == 200
        assert res.json()["status"] == OrderStatus.IN_PROGRESS.value

    def test_delivery_route_requires_start_service(self, client, db, customer_user, photographer_user, photographer_headers):
        order = create_order(db, customer_user.id, OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        ))
        update_order_status(db, order, OrderStatus.CONFIRMED, photographer_user.id)

        res = client.post(
            f"/api/v1/orders/{order.id}/deliver",
            data={"description": "不应直接交付"},
            files={"files": ("test.jpg", b"fake-image", "image/jpeg")},
            headers=photographer_headers,
        )

        assert res.status_code == 400
        assert "先开始服务" in res.json()["detail"]

    def test_reject_order_route_requires_reason(self, client, db, customer_user, photographer_user, photographer_headers):
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)

        res = client.put(
            f"/api/v1/orders/{order.id}/reject",
            json={"rejection_reason": "   "},
            headers=photographer_headers,
        )

        assert res.status_code == 400

    def test_reject_order_route_returns_reason_in_detail(self, client, db, customer_user, photographer_user, photographer_headers, customer_headers):
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)
        reason = "档期已满，建议重新选择下周工作日下午。"

        reject_res = client.put(
            f"/api/v1/orders/{order.id}/reject",
            json={"rejection_reason": reason},
            headers=photographer_headers,
        )
        detail_res = client.get(f"/api/v1/orders/{order.id}/detail", headers=customer_headers)

        assert reject_res.status_code == 200
        assert reject_res.json()["rejection_reason"] == reason
        assert detail_res.status_code == 200
        body = detail_res.json()
        assert body["order"]["rejection_reason"] == reason
        assert body["history"][-1]["event_type"] == "cancelled"
        assert body["history"][-1]["note"] == reason

    def test_reschedule_routes(self, client, db, customer_user, photographer_user, photographer_headers, customer_headers):
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)
        update_order_status(db, order, OrderStatus.CONFIRMED, photographer_user.id)
        requested_time = datetime(2026, 7, 2, 15, 0, 0)

        request_res = client.put(
            f"/api/v1/orders/{order.id}/reschedule/request",
            json={
                "appointment_time": requested_time.isoformat(),
                "reason": "临时有事，需要调整时间",
            },
            headers=customer_headers,
        )
        confirm_res = client.put(
            f"/api/v1/orders/{order.id}/reschedule/confirm",
            headers=photographer_headers,
        )

        assert request_res.status_code == 200
        assert request_res.json()["status"] == OrderStatus.CONFIRMED.value
        assert request_res.json()["reschedule_reason"] == "临时有事，需要调整时间"
        assert request_res.json()["active_reschedule_request"]["status"] == "pending"
        assert confirm_res.status_code == 200
        assert confirm_res.json()["status"] == OrderStatus.CONFIRMED.value
        assert confirm_res.json()["reschedule_requested_time"] is None

    def test_cancel_route_records_reason(self, client, db, customer_user, photographer_user, customer_headers):
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="test package",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        order = create_order(db, customer_user.id, data)

        res = client.put(
            f"/api/v1/orders/{order.id}/cancel",
            json={"cancel_reason": "行程变化，取消拍摄"},
            headers=customer_headers,
        )

        assert res.status_code == 200
        assert res.json()["status"] == OrderStatus.CANCELLED.value
        assert res.json()["cancellation_reason"] == "行程变化，取消拍摄"
        assert res.json()["cancelled_by"] == "customer"


class TestGetOrderById:
    """订单查询测试"""

    def test_get_existing_order(self, db, pending_order):
        """正常场景：查询已存在的订单"""
        result = get_order_by_id(db, pending_order.id)
        assert result is not None
        assert result.id == pending_order.id

    def test_get_nonexistent_order(self, db):
        """异常场景：查询不存在订单"""
        result = get_order_by_id(db, 99999)
        assert result is None


class TestGetMyOrders:
    """客户/摄影师查看订单测试"""

    def test_customer_my_orders(self, db, customer_user, pending_order):
        """正常场景：客户查看自己的订单"""
        orders = get_my_orders_as_customer(db, customer_user.id)
        assert len(orders) >= 1
        assert all(o.customer_id == customer_user.id for o in orders)

    def test_photographer_my_orders(self, db, photographer_user, pending_order):
        """正常场景：摄影师查看分配给自己的订单"""
        orders = get_my_orders_as_photographer(db, photographer_user.id)
        assert len(orders) >= 1
        assert all(o.photographer_id == photographer_user.id for o in orders)

    def test_customer_status_filter(self, db, customer_user, pending_order):
        """边界条件：按状态筛选"""
        orders = get_my_orders_as_customer(db, customer_user.id, status=OrderStatus.PENDING)
        assert all(o.status == OrderStatus.PENDING for o in orders)

    def test_skip_limit_pagination(self, db, customer_user, pending_order):
        """边界条件：分页参数"""
        orders = get_my_orders_as_customer(db, customer_user.id, skip=0, limit=1)
        assert len(orders) <= 1


class TestGetPhotographerStats:
    """摄影师统计数据测试"""

    def test_stats_no_orders(self, db, photographer_user):
        """边界条件：没有订单时的统计"""
        stats = get_photographer_stats(db, photographer_user.id)
        assert stats["monthly_orders"] == 0
        assert stats["weekly_orders"] == 0
        assert stats["completion_rate"] == 0.0
        assert stats["avg_rating"] == 0.0

    def test_stats_with_orders(self, db, photographer_user, customer_user):
        """正常场景：有订单时的统计数据"""
        data = OrderCreateRequest(
            photographer_id=photographer_user.id,
            package_description="测试方案",
            appointment_time=datetime(2026, 7, 1, 14, 0, 0),
            duration_minutes=60,
        )
        create_order(db, customer_user.id, data)
        stats = get_photographer_stats(db, photographer_user.id)
        assert stats["monthly_orders"] >= 0
        assert "completion_rate" in stats
        assert "avg_rating" in stats
