"""摄影师仪表盘聚合测试。"""

from datetime import datetime, timedelta, timezone

from backend.app.models.analytics import AnalyticsEvent
from backend.app.models.favorite import Favorite
from backend.app.models.follow import Follow
from backend.app.models.like import Like
from backend.app.models.message import Message
from backend.app.models.order import Order, OrderStatus
from backend.app.models.photographer import PhotographerProfile
from backend.app.models.project import (
    ProjectApplication,
    ProjectApplicationStatus,
    ProjectStatus,
    ShootProject,
)
from backend.app.models.user import User
from backend.app.services.photographer_dashboard_service import (
    get_photographer_dashboard,
    get_public_photographer_dashboard,
)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _add_order(
    db,
    customer_user,
    photographer_user,
    status,
    appointment_time,
    package_snapshot="测试方案",
    created_at=None,
    rating=None,
):
    order = Order(
        customer_id=customer_user.id,
        photographer_id=photographer_user.id,
        package_snapshot=package_snapshot,
        appointment_time=appointment_time,
        duration_minutes=90,
        status=status,
        rating=rating,
    )
    db.add(order)
    db.commit()
    if created_at is not None:
        order.created_at = created_at
        db.commit()
    db.refresh(order)
    return order


def test_photographer_dashboard_counts_todos_and_schedule(db, customer_user, photographer_user):
    now = _utc_now_naive()
    today_slot = now.replace(hour=0, minute=0, second=0, microsecond=0)
    next_slot = now + timedelta(days=1)

    _add_order(db, customer_user, photographer_user, OrderStatus.PENDING, now + timedelta(days=2))
    _add_order(db, customer_user, photographer_user, OrderStatus.RESCHEDULE_REQUESTED, now + timedelta(days=3))
    _add_order(db, customer_user, photographer_user, OrderStatus.CONFIRMED, today_slot)
    next_order = _add_order(db, customer_user, photographer_user, OrderStatus.CONFIRMED, next_slot)
    _add_order(db, customer_user, photographer_user, OrderStatus.IN_PROGRESS, now + timedelta(days=4))
    _add_order(db, customer_user, photographer_user, OrderStatus.RECEIVED, now - timedelta(days=1))
    _add_order(db, customer_user, photographer_user, OrderStatus.CANCELLED, now + timedelta(days=5))

    dashboard = get_photographer_dashboard(db, photographer_user.id)

    assert dashboard["summary"]["monthly_orders"] >= 6
    assert dashboard["summary"]["period_orders"] >= 6
    assert dashboard["period"]["range_key"] == "month"
    assert dashboard["revenue"]["available"] is False
    assert dashboard["todo"] == {
        "pending_orders": 1,
        "reschedule_requests": 1,
        "orders_to_deliver": 3,
        "orders_waiting_review": 1,
    }
    assert dashboard["schedule"]["today_orders"] == 1
    assert dashboard["schedule"]["week_confirmed_orders"] >= 1
    assert dashboard["schedule"]["next_order"]["id"] == next_order.id
    assert len(dashboard["schedule"]["upcoming_orders"]) == 3
    assert all(item["status"] != OrderStatus.CANCELLED.value for item in dashboard["schedule"]["upcoming_orders"])


def test_photographer_dashboard_range_trends(db, customer_user, photographer_user):
    now = _utc_now_naive()
    current_created = now - timedelta(days=1)
    previous_created = now - timedelta(days=8)

    _add_order(
        db,
        customer_user,
        photographer_user,
        OrderStatus.REVIEWED,
        now - timedelta(hours=3),
        created_at=current_created,
        rating=10,
    )
    _add_order(
        db,
        customer_user,
        photographer_user,
        OrderStatus.PENDING,
        now - timedelta(hours=2),
        created_at=current_created,
    )
    _add_order(
        db,
        customer_user,
        photographer_user,
        OrderStatus.CONFIRMED,
        now - timedelta(hours=1),
        created_at=current_created,
    )
    _add_order(
        db,
        customer_user,
        photographer_user,
        OrderStatus.REVIEWED,
        now - timedelta(days=8),
        created_at=previous_created,
        rating=8,
    )
    _add_order(
        db,
        customer_user,
        photographer_user,
        OrderStatus.CONFIRMED,
        now - timedelta(days=8, hours=1),
        created_at=previous_created,
    )

    dashboard = get_photographer_dashboard(db, photographer_user.id, "7d")

    assert dashboard["period"]["range_key"] == "7d"
    assert dashboard["period"]["has_comparison"] is True
    assert dashboard["summary"]["period_orders"] == 3
    assert dashboard["summary"]["confirmed_shoots"] == 1
    assert dashboard["summary"]["completion_rate"] == 33.3
    assert dashboard["summary"]["avg_rating"] == 5.0
    assert dashboard["trends"]["period_orders_delta"] == 1
    assert dashboard["trends"]["confirmed_shoots_delta"] == 0
    assert dashboard["trends"]["completion_rate_delta"] == -16.7
    assert dashboard["trends"]["avg_rating_delta"] == 1.0


def test_photographer_dashboard_all_range_has_no_comparison(db, photographer_user):
    dashboard = get_photographer_dashboard(db, photographer_user.id, "all")

    assert dashboard["period"]["range_key"] == "all"
    assert dashboard["period"]["has_comparison"] is False
    assert dashboard["trends"]["has_comparison"] is False
    assert dashboard["trends"]["period_orders_delta"] is None


def test_photographer_dashboard_content_insights(db, customer_user, photographer_user):
    now = _utc_now_naive()
    other_customer = User(
        email="other-content-customer@test.com",
        hashed_password="hash",
        display_name="内容测试客户",
        role="customer",
    )
    db.add(other_customer)
    db.commit()
    db.refresh(other_customer)

    profile = PhotographerProfile(
        user_id=photographer_user.id,
        portfolio=[
            {
                "id": "work-1",
                "url": "/static/portfolios/work-1.jpg",
                "thumbnail_url": "/static/portfolios/work-1-thumb.jpg",
                "title": "春日写真",
                "tags": ["日系", "校园"],
                "created_at": (now - timedelta(days=3)).isoformat(),
            },
            {
                "id": "work-2",
                "url": "/static/portfolios/work-2.jpg",
                "title": "夜景人像",
                "tag": "夜景",
                "created_at": (now - timedelta(days=45)).isoformat(),
            },
        ],
        packages=[
            {
                "id": "pkg-1",
                "name": "个人写真",
                "price": 699,
                "duration": 90,
                "samples": ["/static/package_samples/pkg-1.jpg"],
            },
            {
                "id": "pkg-2",
                "name": "情侣写真",
                "price": 1299,
                "duration": 120,
                "samples": [],
            },
        ],
    )
    db.add(profile)
    db.add_all([
        Like(user_id=customer_user.id, target_type="portfolio", target_id="work-1"),
        Like(user_id=other_customer.id, target_type="portfolio", target_id="work-1"),
        Like(user_id=customer_user.id, target_type="portfolio", target_id="work-2"),
        Favorite(
            user_id=customer_user.id,
            favorite_type="work",
            work_id="work-1",
            photographer_id=photographer_user.id,
            work_data={"title": "春日写真"},
        ),
        Favorite(
            user_id=customer_user.id,
            favorite_type="package",
            package_id="pkg-1",
            photographer_id=photographer_user.id,
            package_data={"package_name": "个人写真"},
        ),
        Favorite(
            user_id=other_customer.id,
            favorite_type="package",
            package_id="pkg-1",
            photographer_id=photographer_user.id,
            package_data={"package_name": "个人写真"},
        ),
        Favorite(
            user_id=other_customer.id,
            favorite_type="package",
            package_id="pkg-2",
            photographer_id=photographer_user.id,
            package_data={"package_name": "情侣写真"},
        ),
    ])
    db.commit()

    dashboard = get_photographer_dashboard(db, photographer_user.id)

    assert dashboard["content"] == {
        "portfolio_count": 2,
        "package_count": 2,
        "packages_with_samples": 1,
        "recent_upload_count": 1,
    }
    assert dashboard["top_works"][0]["id"] == "work-1"
    assert dashboard["top_works"][0]["like_count"] == 2
    assert dashboard["top_works"][0]["favorite_count"] == 1
    assert dashboard["top_packages"][0]["id"] == "pkg-1"
    assert dashboard["top_packages"][0]["favorite_count"] == 2
    assert dashboard["top_packages"][0]["booking_count"] is None
    assert dashboard["top_packages"][0]["booking_count_available"] is False


def test_photographer_dashboard_interactions_and_funnel(db, customer_user, photographer_user):
    now = _utc_now_naive()
    profile = PhotographerProfile(
        user_id=photographer_user.id,
        portfolio=[{"id": "work-1", "url": "/static/work-1.jpg", "title": "互动作品"}],
        packages=[{"id": "pkg-1", "name": "互动套餐", "samples": ["/static/pkg-1.jpg"]}],
    )
    db.add(profile)
    _add_order(
        db,
        customer_user,
        photographer_user,
        OrderStatus.REVIEWED,
        now + timedelta(days=2),
        created_at=now - timedelta(hours=1),
    )
    db.add_all([
        AnalyticsEvent(
            user_id=photographer_user.id,
            actor_id=customer_user.id,
            event_type="profile_view",
            target_type="photographer",
            target_id=str(photographer_user.id),
            event_metadata={"source": "test"},
        ),
        AnalyticsEvent(
            user_id=photographer_user.id,
            actor_id=customer_user.id,
            event_type="profile_view",
            target_type="photographer",
            target_id=str(photographer_user.id),
        ),
        AnalyticsEvent(
            user_id=photographer_user.id,
            actor_id=customer_user.id,
            event_type="portfolio_view",
            target_type="portfolio",
            target_id="work-1",
        ),
        AnalyticsEvent(
            user_id=photographer_user.id,
            actor_id=customer_user.id,
            event_type="package_view",
            target_type="package",
            target_id="pkg-1",
        ),
        Follow(follower_id=customer_user.id, following_id=photographer_user.id),
        Like(user_id=customer_user.id, target_type="portfolio", target_id="work-1"),
        Favorite(
            user_id=customer_user.id,
            favorite_type="work",
            work_id="work-1",
            photographer_id=photographer_user.id,
            work_data={"title": "互动作品"},
        ),
        Favorite(
            user_id=customer_user.id,
            favorite_type="package",
            package_id="pkg-1",
            photographer_id=photographer_user.id,
            package_data={"package_name": "互动套餐"},
        ),
        Message(
            sender_id=customer_user.id,
            receiver_id=photographer_user.id,
            content="想咨询一下拍摄",
        ),
    ])
    db.commit()

    dashboard = get_photographer_dashboard(db, photographer_user.id)
    nodes = {node["key"]: node for node in dashboard["funnel"]["nodes"]}

    assert dashboard["interactions"]["new_followers"] == 1
    assert dashboard["interactions"]["message_conversations"] == 1
    assert dashboard["interactions"]["work_likes"] == 1
    assert dashboard["interactions"]["work_favorites"] == 1
    assert dashboard["interactions"]["package_favorites"] == 1
    assert dashboard["interactions"]["profile_views"] == 2
    assert dashboard["interactions"]["portfolio_views"] == 1
    assert dashboard["interactions"]["package_views"] == 1
    assert dashboard["funnel"]["tracked_event_count"] == 4
    assert nodes["profile_views"]["count"] == 2
    assert nodes["work_interactions"]["count"] == 2
    assert nodes["package_favorites"]["conversion_rate"] == 50.0
    assert nodes["created_orders"]["count"] == 1
    assert nodes["completed_orders"]["count"] == 1


def test_photographer_dashboard_project_performance(db, customer_user, photographer_user):
    now = _utc_now_naive()
    converted_order = _add_order(
        db,
        customer_user,
        photographer_user,
        OrderStatus.PENDING,
        now + timedelta(days=5),
    )
    selected_project = ShootProject(
        customer_id=customer_user.id,
        title="品牌写真",
        description="需要一组品牌写真",
        category="portrait",
        city="上海",
        budget_min=500,
        budget_max=900,
        status=ProjectStatus.CONVERTED,
    )
    submitted_project = ShootProject(
        customer_id=customer_user.id,
        title="活动跟拍",
        description="需要活动跟拍",
        category="event",
        city="上海",
        budget_min=500,
        budget_max=900,
        status=ProjectStatus.OPEN,
    )
    db.add_all([selected_project, submitted_project])
    db.flush()

    selected_application = ProjectApplication(
        project_id=selected_project.id,
        photographer_id=photographer_user.id,
        status=ProjectApplicationStatus.SELECTED,
        proposal_text="可提供 2 小时拍摄",
        price_quote=800,
    )
    submitted_application = ProjectApplication(
        project_id=submitted_project.id,
        photographer_id=photographer_user.id,
        status=ProjectApplicationStatus.SUBMITTED,
        proposal_text="可提供全天拍摄",
        price_quote=1400,
    )
    db.add_all([selected_application, submitted_application])
    db.flush()
    selected_project.selected_application_id = selected_application.id
    selected_project.converted_order_id = converted_order.id
    db.commit()

    dashboard = get_photographer_dashboard(db, photographer_user.id)

    assert dashboard["project_performance"]["submitted_applications"] == 2
    assert dashboard["project_performance"]["selected_applications"] == 1
    assert dashboard["project_performance"]["converted_orders"] == 1
    assert dashboard["project_performance"]["application_conversion_rate"] == 50.0
    assert dashboard["project_performance"]["average_quote"] == 1100.0
    assert dashboard["project_performance"]["budget_match_rate"] == 50.0
    assert dashboard["project_performance"]["budget_match_sample_count"] == 2


def test_public_photographer_dashboard_exposes_safe_trust_and_content(db, customer_user, photographer_user):
    now = _utc_now_naive()
    profile = PhotographerProfile(
        user_id=photographer_user.id,
        portfolio=[
            {
                "id": "public-work-1",
                "url": "/static/public-work-1.jpg",
                "thumbnail_url": "/static/public-work-1-thumb.jpg",
                "title": "公开热门作品",
                "created_at": (now - timedelta(days=2)).isoformat(),
            },
        ],
        packages=[
            {
                "id": "public-pkg-1",
                "name": "公开热门套餐",
                "price": 899,
                "duration": 120,
                "samples": ["/static/public-pkg-1.jpg"],
            },
        ],
    )
    db.add(profile)
    for index in range(4):
        _add_order(
            db,
            customer_user,
            photographer_user,
            OrderStatus.REVIEWED,
            now + timedelta(days=index + 1),
            created_at=now - timedelta(days=index),
            rating=8 + (index % 2),
        )
    _add_order(
        db,
        customer_user,
        photographer_user,
        OrderStatus.PENDING,
        now + timedelta(days=7),
        created_at=now - timedelta(days=1),
    )
    db.add_all([
        Like(user_id=customer_user.id, target_type="portfolio", target_id="public-work-1"),
        Favorite(
            user_id=customer_user.id,
            favorite_type="work",
            work_id="public-work-1",
            photographer_id=photographer_user.id,
            work_data={"title": "公开热门作品"},
        ),
        Favorite(
            user_id=customer_user.id,
            favorite_type="package",
            package_id="public-pkg-1",
            photographer_id=photographer_user.id,
            package_data={"package_name": "公开热门套餐"},
        ),
    ])
    db.commit()

    dashboard = get_public_photographer_dashboard(db, photographer_user.id)

    assert set(dashboard.keys()) == {"trust", "content", "top_works", "top_packages"}
    assert dashboard["trust"]["completed_orders"] == 4
    assert dashboard["trust"]["rating_count"] == 4
    assert dashboard["trust"]["rating_visible"] is True
    assert dashboard["trust"]["avg_rating"] == 4.2
    assert dashboard["trust"]["completion_rate_visible"] is True
    assert dashboard["trust"]["completion_rate"] == 80.0
    assert dashboard["trust"]["completion_sample_count"] == 5
    assert dashboard["trust"]["recent_order_activity"] is True
    assert dashboard["content"]["portfolio_count"] == 1
    assert dashboard["content"]["package_count"] == 1
    assert dashboard["content"]["recent_upload_count"] == 1
    assert dashboard["top_works"][0]["id"] == "public-work-1"
    assert dashboard["top_packages"][0]["id"] == "public-pkg-1"


def test_analytics_event_route_records_actor(client, db, customer_user, photographer_user, customer_headers):
    response = client.post(
        "/api/v1/analytics/events",
        headers=customer_headers,
        json={
            "user_id": photographer_user.id,
            "event_type": "profile_view",
            "target_type": "photographer",
            "target_id": str(photographer_user.id),
            "metadata": {"source": "test"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["actor_id"] == customer_user.id
    assert body["metadata"] == {"source": "test"}
    event = db.query(AnalyticsEvent).filter_by(id=body["id"]).one()
    assert event.user_id == photographer_user.id
    assert event.actor_id == customer_user.id


def test_photographer_dashboard_route_requires_photographer(client, customer_headers):
    response = client.get("/api/v1/orders/dashboard", headers=customer_headers)

    assert response.status_code == 403


def test_photographer_dashboard_route_returns_dashboard(client, db, customer_user, photographer_user, photographer_headers):
    now = _utc_now_naive()
    order = _add_order(
        db,
        customer_user,
        photographer_user,
        OrderStatus.PENDING,
        now + timedelta(days=1),
        package_snapshot="新人写真 - ¥899/90分钟",
    )

    response = client.get("/api/v1/orders/dashboard", headers=photographer_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["todo"]["pending_orders"] == 1
    assert body["period"]["range_key"] == "month"
    assert body["schedule"]["upcoming_orders"][0]["id"] == order.id
    assert body["schedule"]["upcoming_orders"][0]["customer_name"] == customer_user.display_name


def test_photographer_dashboard_route_accepts_range(client, photographer_headers):
    response = client.get("/api/v1/orders/dashboard?range=90d", headers=photographer_headers)

    assert response.status_code == 200
    assert response.json()["period"]["range_key"] == "90d"


def test_public_photographer_dashboard_route_returns_safe_payload(client, db, customer_user, photographer_user):
    now = _utc_now_naive()
    _add_order(
        db,
        customer_user,
        photographer_user,
        OrderStatus.REVIEWED,
        now + timedelta(days=1),
        created_at=now - timedelta(days=1),
        rating=10,
    )

    response = client.get(f"/api/v1/orders/dashboard/public/{photographer_user.id}")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"trust", "content", "top_works", "top_packages"}
    assert "todo" not in body
    assert "schedule" not in body
    assert "interactions" not in body
    assert body["trust"]["completed_orders"] == 1
    assert body["trust"]["completion_rate_visible"] is False
    assert body["trust"]["completion_rate"] is None
    assert body["trust"]["rating_visible"] is True


def test_public_photographer_dashboard_route_requires_photographer(client, customer_user):
    response = client.get(f"/api/v1/orders/dashboard/public/{customer_user.id}")

    assert response.status_code == 404
