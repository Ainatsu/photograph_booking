"""测试 Booking Agent — 预约方案自动化"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from backend.app.services.ai_booking_service import (
    BookingState,
    get_available_slots,
    find_nearby_available_dates,
    _parse_time_range,
    _format_minutes,
    _weekday_name_cn,
    _day_name_en,
    _format_slot_summary,
    _booking_summary_text,
    _format_package_for_display,
    booking_agent_result,
    _latest_booking_task_state,
    _merge_booking_slots,
    _extract_booking_slots,
    _resolve_photographer,
    _resolve_package,
    _find_package_in_profile,
)
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.user import User
from backend.app.models.ai_conversation import AIConversation, AIMessage
from backend.app.models.order import Order, OrderStatus


# ─────────────────────────────
# 工具函数测试
# ─────────────────────────────

class TestUtilityFunctions:
    def test_parse_time_range(self):
        assert _parse_time_range("09:00-12:00") == (540, 720)
        assert _parse_time_range("14:00-18:00") == (840, 1080)
        assert _parse_time_range("09:00–12:00") == (540, 720)  # em dash
        assert _parse_time_range("invalid") is None
        assert _parse_time_range("") is None

    def test_format_minutes(self):
        assert _format_minutes(540) == "09:00"
        assert _format_minutes(720) == "12:00"
        assert _format_minutes(0) == "00:00"
        assert _format_minutes(1439) == "23:59"

    def test_weekday_name_cn(self):
        from datetime import date
        assert _weekday_name_cn(date(2026, 6, 29)) == "周一"
        assert _weekday_name_cn(date(2026, 6, 30)) == "周二"
        assert _weekday_name_cn(date(2026, 7, 5)) == "周日"

    def test_day_name_en(self):
        from datetime import date
        assert _day_name_en(date(2026, 6, 29)) == "Monday"
        assert _day_name_en(date(2026, 7, 5)) == "Sunday"

    def test_format_slot_summary(self):
        slots_data = {
            "date_label": "6月30日 (周二)",
            "slots": [
                {"start": "09:00", "end": "12:00", "duration_minutes": 180},
                {"start": "14:00", "end": "17:00", "duration_minutes": 180},
            ],
            "total_available": 2,
        }
        result = _format_slot_summary(slots_data)
        assert "6月30日" in result
        assert "09:00-12:00" in result
        assert "14:00-17:00" in result

    def test_format_slot_summary_empty(self):
        slots_data = {"date_label": "6月30日 (周二)", "slots": [], "total_available": 0}
        result = _format_slot_summary(slots_data)
        assert "暂无可用时段" in result

    def test_booking_summary_text(self):
        result = _booking_summary_text(
            photographer_name="测试摄影师",
            package_display="「个人写真」价格 699 元 时长 120 分钟",
            appointment_date="6月30日",
            appointment_time="14:00",
        )
        assert "测试摄影师" in result
        assert "个人写真" in result
        assert "6月30日" in result
        assert "14:00" in result

    def test_format_package_for_display(self):
        pkg = {"name": "个人写真", "price": 699, "duration": 120, "image_count": 30}
        result = _format_package_for_display(pkg, "测试摄影师")
        assert "测试摄影师" in result
        assert "个人写真" in result
        assert "699" in result
        assert "120" in result
        assert "30" in result

    def test_format_package_for_display_no_photographer(self):
        pkg = {"name": "个人写真", "price": 699, "duration": 120}
        result = _format_package_for_display(pkg)
        assert "个人写真" in result
        assert "测试摄影师" not in result

    def test_format_package_with_includes(self):
        pkg = {"name": "写真套餐", "price": 999, "duration": 180,
               "image_count": 50, "includes": ["精修50张", "底片全送", "妆造"]}
        result = _format_package_for_display(pkg, "摄影师小王")
        assert "精修" in result
        assert "底片全送" in result
        assert "妆造" in result


# ─────────────────────────────
# 预约参数提取测试
# ─────────────────────────────

class TestExtractBookingSlots:
    def test_extract_unicode_date_and_notes(self):
        result = _extract_booking_slots(
            "\u5e2e\u6211\u9884\u7ea6\u4e00\u4e0b\uff0c\u6211\u8981\u516b\u6708\u5341\u4e5d\u53f7\uff0c\u7136\u540e\u5907\u6ce8\u6444\u5f71\u5e08\u9700\u8981\u9ad8\u901f\u6444\u5f71\u673a"
        )
        assert result["date"] == "08-19"
        assert result["notes"] == "\u6444\u5f71\u5e08\u9700\u8981\u9ad8\u901f\u6444\u5f71\u673a"

    def test_extract_date(self):
        result = _extract_booking_slots("我想约6月15日拍摄")
        assert result.get("date") == "06-15"

    def test_extract_time(self):
        result = _extract_booking_slots("下午2点可以吗")
        assert result.get("time") == "14:00"

    def test_extract_time_with_minutes(self):
        result = _extract_booking_slots("14:30")
        assert result.get("time") == "14:30"

    def test_extract_photographer_name(self):
        result = _extract_booking_slots("测试摄影师1")
        assert result.get("photographer_name") == "测试摄影师1"

    def test_extract_date_and_time(self):
        result = _extract_booking_slots("7月3日 14:00")
        assert result.get("date") == "07-03"
        assert result.get("time") == "14:00"

    def test_empty_text(self):
        result = _extract_booking_slots("")
        assert result == {}

    def test_no_slots(self):
        result = _extract_booking_slots("你好，我想看看有什么套餐")
        assert result.get("date") is None
        assert result.get("time") is None


# ─────────────────────────────
# Slots 合并逻辑测试
# ─────────────────────────────

class TestMergeBookingSlots:
    def test_merge_from_task_state(self):
        task_state = {
            "slots": {
                "photographer_id": 1,
                "package_display": "个人写真",
                "duration_minutes": 120,
            }
        }
        result = _merge_booking_slots(task_state, None)
        assert result["photographer_id"] == 1
        assert result["package_display"] == "个人写真"

    def test_merge_with_content(self):
        task_state = {
            "slots": {
                "photographer_id": 1,
                "package_display": "个人写真",
                "duration_minutes": 120,
            }
        }
        result = _merge_booking_slots(task_state, "6月15日")
        assert result["photographer_id"] == 1
        assert result["date"] == "06-15"

    def test_merge_no_task_state(self):
        result = _merge_booking_slots(None, "预约")
        assert result == {}

    def test_content_overrides_empty_slots(self):
        task_state = {"slots": {"date": "06-15"}}
        result = _merge_booking_slots(task_state, "7月3日")
        assert result["date"] == "07-03"


# ─────────────────────────────
# 可用时间段查询测试
# ─────────────────────────────

class TestGetAvailableSlots:
    def test_photographer_not_found(self, db):
        result = get_available_slots(db, photographer_id=9999)
        assert result.get("error") == "photographer_not_found"
        assert result["total_available"] == 0

    def test_no_profile(self, db):
        user = User(
            email="photo@test.com", phone="13800000100",
            hashed_password="dummy", display_name="无资料摄影师",
            role="photographer",
        )
        db.add(user)
        db.commit()
        result = get_available_slots(db, photographer_id=user.id)
        assert result.get("error") == "profile_not_found"
        assert result["total_available"] == 0

    def test_no_busy_days_defaults_to_available(self, db, photographer_user, photographer_profile):
        """profile 有但没标忙碌时，默认可预约"""
        query_date = (datetime.now(timezone.utc).date() + timedelta(days=7)).isoformat()
        result = get_available_slots(db, photographer_id=photographer_user.id, date_str=query_date)
        assert result["total_available"] > 0

    def test_default_available_day_uses_platform_hours(self, db, photographer_user):
        profile = PhotographerProfile(
            user_id=photographer_user.id,
            styles=["日系"],
            packages=[{"name": "个人写真", "price": 699, "duration": 120}],
        )
        db.add(profile)
        db.commit()

        query_date = datetime.now(timezone.utc).date() + timedelta(days=7)
        result = get_available_slots(db, photographer_id=photographer_user.id, date_str=query_date.isoformat())
        assert result["total_available"] > 0
        assert result["date"] == query_date.strftime("%m-%d")
        all_start_times = {s["start"] for s in result["slots"]}
        for slot in result["slots"]:
            assert slot["duration_minutes"] == 120
        assert "09:00" in all_start_times
        assert "10:00" in all_start_times
        assert "14:00" in all_start_times
        assert "16:00" in all_start_times

    def test_slots_excludes_occupied(self, db, photographer_user, customer_user):
        """已有已确认订单的时间段不应出现在可用列表中"""
        profile = PhotographerProfile(
            user_id=photographer_user.id,
            styles=["日系"],
            packages=[{"name": "个人写真", "price": 699, "duration": 120}],
        )
        db.add(profile)
        db.commit()

        query_date = datetime.now(timezone.utc).date() + timedelta(days=7)
        # 创建一个已确认的订单占用 10:00-12:00
        order = Order(
            customer_id=customer_user.id,
            photographer_id=photographer_user.id,
            package_snapshot="个人写真 - ¥699/120分钟",
            appointment_time=datetime(query_date.year, query_date.month, query_date.day, 10, 0, 0),
            duration_minutes=120,
            status=OrderStatus.CONFIRMED,
        )
        db.add(order)
        db.commit()

        result = get_available_slots(db, photographer_id=photographer_user.id, date_str=query_date.isoformat())
        assert result["total_available"] > 0
        # 10:00-12:00 被占用 → 09:30-11:30 也冲突
        # 09:00-11:00 是唯一可用的上午时段
        for slot in result["slots"]:
            assert slot["start"] not in ("10:00", "10:30", "11:00", "11:30", "09:30")

    def test_busy_day_has_no_available_slots(self, db, photographer_user):
        query_date = datetime.now(timezone.utc).date() + timedelta(days=7)
        profile = PhotographerProfile(
            user_id=photographer_user.id,
            styles=["日系"],
            packages=[{"name": "个人写真", "price": 699, "duration": 120}],
            availability_exceptions=[
                {"date": query_date.isoformat(), "status": "busy", "location": "外部拍摄"},
            ],
        )
        db.add(profile)
        db.commit()

        result = get_available_slots(db, photographer_id=photographer_user.id, date_str=query_date.isoformat())
        assert result["total_available"] == 0
        assert result["info"] == "该日档期忙碌"
        assert result["location"] == "外部拍摄"

    def test_free_day_with_location_preserves_location(self, db, photographer_user):
        query_date = datetime.now(timezone.utc).date() + timedelta(days=7)
        profile = PhotographerProfile(
            user_id=photographer_user.id,
            styles=["日系"],
            packages=[{"name": "个人写真", "price": 699, "duration": 120}],
            availability_exceptions=[
                {"date": query_date.isoformat(), "status": "free", "location": "香港中环"},
            ],
        )
        db.add(profile)
        db.commit()

        result = get_available_slots(db, photographer_id=photographer_user.id, date_str=query_date.isoformat())
        assert result["total_available"] > 0
        assert result["location"] == "香港中环"

    def test_invalid_date_format(self, db, photographer_user):
        profile = PhotographerProfile(
            user_id=photographer_user.id,
            available_hours=[{"day": "Monday", "slots": ["09:00-12:00"]}],
        )
        db.add(profile)
        db.commit()
        result = get_available_slots(db, photographer_id=photographer_user.id, date_str="invalid")
        assert result.get("error") == "invalid_date_format"


class TestFindNearbyAvailableDates:
    def test_find_dates(self, db, photographer_user):
        """没有忙碌标记时，近期日期默认可预约"""
        profile = PhotographerProfile(
            user_id=photographer_user.id,
            styles=["日系"],
            packages=[{"name": "写真", "price": 699, "duration": 120}],
        )
        db.add(profile)
        db.commit()

        results = find_nearby_available_dates(db, photographer_id=photographer_user.id, max_days=7)
        assert len(results) > 0
        for r in results:
            assert r["total_available"] > 0
            assert "date" in r
            assert "date_label" in r


# ─────────────────────────────
# 套餐查找测试
# ─────────────────────────────

class TestFindPackageInProfile:
    def test_find_first_package(self, db, photographer_user, photographer_profile):
        pkg = _find_package_in_profile(db, photographer_user.id)
        assert pkg is not None
        assert pkg["name"] == "个人写真"

    def test_find_by_name_hint(self, db, photographer_user, photographer_profile):
        pkg = _find_package_in_profile(db, photographer_user.id, package_hint="个人写真")
        assert pkg is not None
        assert pkg["name"] == "个人写真"

    def test_find_no_profile(self, db):
        pkg = _find_package_in_profile(db, 9999)
        assert pkg is None

    def test_find_no_packages(self, db, photographer_user):
        profile = PhotographerProfile(
            user_id=photographer_user.id,
            styles=["日系"],
            packages=[],
        )
        db.add(profile)
        db.commit()
        pkg = _find_package_in_profile(db, photographer_user.id)
        assert pkg is None


# ─────────────────────────────
# booking_agent_result 集成测试
# ─────────────────────────────

class TestBookingAgentResult:
    """测试 booking_agent_result 主入口"""

    def test_missing_photographer(self, db):
        """没有摄影师信息时返回 awaiting_package"""
        conv = AIConversation(user_id=1)
        db.add(conv)
        db.commit()

        result = booking_agent_result(
            db,
            user_id=1,
            conversation_id=conv.id,
            message_id=None,
            content="我想预约",
            confirm_requested=False,
        )
        assert result["metadata"]["task_state"]["status"] == "awaiting_package"

    def test_missing_date(self, db, photographer_user):
        """有摄影师和套餐但没有日期时，返回 awaiting_date"""
        conv = AIConversation(user_id=1)
        db.add(conv)
        db.commit()

        # 添加一条带 references 的 assistant 消息
        msg = AIMessage(
            conversation_id=conv.id,
            role="assistant",
            content="推荐结果",
            message_metadata={
                "references": {
                    "packages": [
                        {"package_name": "个人写真", "price": 699, "duration": 120,
                         "image_count": 30, "includes": ["精修30张"],
                         "photographer_id": photographer_user.id,
                         "photographer_name": photographer_user.display_name}
                    ]
                }
            },
        )
        db.add(msg)
        db.commit()

        result = booking_agent_result(
            db,
            user_id=1,
            conversation_id=conv.id,
            message_id=msg.id,
            content="就这个套餐",
            confirm_requested=False,
        )
        task_state = result["metadata"]["task_state"]
        assert task_state["task_type"] == "create_booking"
        assert task_state["status"] in ("awaiting_date", "awaiting_package")

    def test_with_photographer_and_package_via_direct_slots(self, db, photographer_user):
        """通过 slots 直接传入摄影师和套餐信息，缺少具体时间时默认 12:00"""
        conv = AIConversation(user_id=1)
        db.add(conv)
        db.commit()

        # 给摄影师创建资料（含套餐）
        profile = PhotographerProfile(
            user_id=photographer_user.id,
            location="北京",
            styles=["日系"],
            packages=[{"name": "个人写真", "price": 699, "duration": 120,
                       "image_count": 30, "includes": ["精修30张"]}],
        )
        db.add(profile)
        db.commit()

        # 预设 booking task_state
        msg = AIMessage(
            conversation_id=conv.id,
            role="assistant",
            content="预约信息",
            message_metadata={
                "task_state": {
                    "task_type": "create_booking",
                    "status": "awaiting_date",
                    "slots": {
                        "photographer_id": photographer_user.id,
                        "photographer_name": photographer_user.display_name,
                        "package_display": "「个人写真」价格 699 元 时长 120 分钟",
                        "duration_minutes": 120,
                    },
                }
            },
        )
        db.add(msg)
        db.commit()

        result = booking_agent_result(
            db,
            user_id=1,
            conversation_id=conv.id,
            message_id=msg.id,
            content="6月30日",
            confirm_requested=False,
        )
        task_state = result["metadata"]["task_state"]
        assert task_state["task_type"] == "create_booking"
        assert task_state["status"] == "awaiting_confirmation"
        assert task_state["slots"]["time"] == "12:00"
        assert "时间：12:00" in result["content"]

    def test_date_prompt_lists_dates_without_specific_time_ranges(self, db, photographer_profile):
        """询问日期时只展示日期，不列出具体可用时段"""
        conv = AIConversation(user_id=1)
        db.add(conv)
        db.commit()

        msg = AIMessage(
            conversation_id=conv.id,
            role="assistant",
            content="推荐结果",
            message_metadata={
                "references": {
                    "packages": [
                        {
                            "package_name": "个人写真",
                            "price": 699,
                            "duration": 120,
                            "image_count": 30,
                            "includes": ["精修30张"],
                            "photographer_id": photographer_profile.user_id,
                            "photographer_name": photographer_profile.user.display_name,
                        }
                    ]
                }
            },
        )
        db.add(msg)
        db.commit()

        result = booking_agent_result(
            db,
            user_id=1,
            conversation_id=conv.id,
            message_id=msg.id,
            content="就这个套餐",
            confirm_requested=False,
        )

        assert result["metadata"]["task_state"]["status"] == "awaiting_date"
        assert "默认约 12:00" in result["content"]
        assert "09:00-" not in result["content"]

    @pytest.mark.skip(reason="需要完整的上下文 references + slots 设置")
    def test_full_booking_flow_confirmation(self, db, photographer_user):
        """完整流程：有摄影师、套餐、日期、时间 → 生成确认"""
        pass

    @pytest.mark.skip(reason="需要真实的 create_booking 工具调用")
    def test_execute_booking(self, db, photographer_user):
        """确认后执行创建预约"""
        pass
