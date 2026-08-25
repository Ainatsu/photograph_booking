from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from backend.app.models.order import Order, OrderStatus
from backend.app.models.project import ProjectApplicationStatus, ProjectStatus
from backend.app.models.user import User
from backend.app.schemas.project import ProjectApplicationCreate, ProjectCreate, ProjectUpdate
from backend.app.services.project_service import (
    apply_project,
    create_project,
    list_open_projects,
    list_my_projects,
    list_project_applications,
    publish_project,
    select_application,
    update_project,
)


FUTURE_SHOOT_START = datetime.now() + timedelta(days=30)


def _project_data(publish: bool = True) -> ProjectCreate:
    return ProjectCreate(
        title="Outdoor portrait shoot",
        description="Need a relaxed portrait session with natural light.",
        category="portrait",
        style_tags=["natural", "film"],
        city="Hong Kong",
        location_text="Central or Sheung Wan",
        location_name="Central Market",
        location_address="93 Queen's Road Central, Hong Kong",
        location_latitude=Decimal("22.2841370"),
        location_longitude=Decimal("114.1546270"),
        location_provider="openstreetmap",
        coordinate_system="WGS84",
        location_precision="exact",
        shoot_date_start=FUTURE_SHOOT_START,
        shoot_date_end=FUTURE_SHOOT_START + timedelta(hours=8),
        duration_minutes=120,
        budget_min=800,
        budget_max=1600,
        deliverables="精修 20 张，交付底片",
        visibility="public",
        publish=publish,
    )


def _application_data(
    available_time: datetime | None = None,
    price_quote: int = 1200,
) -> ProjectApplicationCreate:
    return ProjectApplicationCreate(
        proposal_text="I can shoot this with a clean editorial approach.",
        price_quote=price_quote,
        duration_minutes=120,
        available_time=available_time or datetime(2026, 7, 20, 11, 0, 0),
        package_snapshot="Portrait plan",
        portfolio_refs=[{"url": "/static/portfolio/sample.jpg"}],
        included_items=["2 hours", "20 retouched photos"],
    )


def _create_other_photographer(db) -> User:
    user = User(
        email="other-project-photographer@test.com",
        hashed_password="hash",
        display_name="Other Photographer",
        role="photographer",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestProjectService:
    def test_project_coordinates_must_be_provided_together(self):
        payload = _project_data(publish=True).model_dump()
        payload["location_longitude"] = None

        with pytest.raises(ValueError, match="must be provided together"):
            ProjectCreate(**payload)

    def test_project_coordinate_ranges_are_validated(self):
        payload = _project_data(publish=True).model_dump()
        payload["location_latitude"] = Decimal("91")

        with pytest.raises(ValueError):
            ProjectCreate(**payload)

    def test_customer_can_create_open_project(self, db, customer_user):
        project = create_project(db, customer_user.id, _project_data(publish=True))

        assert project.id is not None
        assert project.status == ProjectStatus.OPEN
        assert project.location_name == "Central Market"
        assert project.location_latitude == Decimal("22.2841370")

        projects = list_open_projects(db, city="Hong Kong")
        assert [item.id for item in projects] == [project.id]

    def test_publishing_an_open_project_is_idempotent(self, db, customer_user):
        project = create_project(db, customer_user.id, _project_data(publish=True))

        published = publish_project(db, project, customer_user.id)

        assert published.id == project.id
        assert published.status == ProjectStatus.OPEN

    def test_expired_project_is_hidden_from_public_list_but_kept_for_owner(self, db, customer_user):
        project = create_project(db, customer_user.id, _project_data(publish=True))
        project.expires_at = datetime(2026, 7, 1, 0, 0, 0)
        db.commit()

        assert list_open_projects(db, city="Hong Kong") == []

        db.refresh(project)
        assert project.status == ProjectStatus.EXPIRED

        my_projects = list_my_projects(db, customer_user.id)
        assert [item.id for item in my_projects] == [project.id]
        assert my_projects[0].status == ProjectStatus.EXPIRED

    def test_project_expires_when_shoot_start_passes_without_expiry(self, db, customer_user):
        project = create_project(db, customer_user.id, _project_data(publish=True))
        project.expires_at = None
        project.shoot_date_start = datetime(2026, 7, 1, 0, 0, 0)
        db.commit()

        assert list_open_projects(db, city="Hong Kong") == []

        db.refresh(project)
        assert project.status == ProjectStatus.EXPIRED

    def test_expiry_must_be_before_shoot_start(self, db, customer_user):
        data = _project_data(publish=True)
        data.expires_at = data.shoot_date_start

        with pytest.raises(HTTPException) as exc:
            create_project(db, customer_user.id, data)

        assert exc.value.status_code == 400
        assert exc.value.detail == "expires_at must be before shoot_date_start"

    def test_expired_project_can_be_edited_and_republished(self, db, customer_user):
        project = create_project(db, customer_user.id, _project_data(publish=True))
        project.expires_at = datetime(2026, 7, 1, 0, 0, 0)
        db.commit()

        assert list_open_projects(db, city="Hong Kong") == []
        db.refresh(project)
        assert project.status == ProjectStatus.EXPIRED

        future_shoot_start = datetime.now() + timedelta(days=10)
        project = update_project(
            db,
            project,
            customer_user.id,
            ProjectUpdate(
                title="Updated portrait shoot",
                shoot_date_start=future_shoot_start,
                shoot_date_end=future_shoot_start + timedelta(hours=8),
                expires_at=datetime.now() + timedelta(days=5),
            ),
        )
        assert project.title == "Updated portrait shoot"
        assert project.status == ProjectStatus.EXPIRED

        project = publish_project(db, project, customer_user.id)
        assert project.status == ProjectStatus.OPEN
        assert [item.id for item in list_open_projects(db, city="Hong Kong")] == [project.id]

    def test_expired_project_cannot_be_republished_with_past_expiry(self, db, customer_user):
        project = create_project(db, customer_user.id, _project_data(publish=True))
        project.expires_at = datetime.now() - timedelta(days=1)
        db.commit()

        assert list_open_projects(db, city="Hong Kong") == []
        db.refresh(project)
        assert project.status == ProjectStatus.EXPIRED

        with pytest.raises(HTTPException) as exc:
            publish_project(db, project, customer_user.id)

        assert exc.value.status_code == 400
        assert exc.value.detail == "expires_at cannot be in the past"

    def test_photographer_can_apply_once(self, db, customer_user, photographer_user):
        project = create_project(db, customer_user.id, _project_data(publish=True))

        application = apply_project(db, project, photographer_user.id, _application_data())

        assert application.id is not None
        assert application.status == ProjectApplicationStatus.SUBMITTED
        assert application.photographer_id == photographer_user.id

        with pytest.raises(HTTPException) as exc:
            apply_project(db, project, photographer_user.id, _application_data())
        assert exc.value.status_code == 409

    def test_only_project_owner_can_list_applications(self, db, customer_user, photographer_user):
        project = create_project(db, customer_user.id, _project_data(publish=True))
        apply_project(db, project, photographer_user.id, _application_data())

        with pytest.raises(HTTPException) as exc:
            list_project_applications(db, project, customer_id=99999)
        assert exc.value.status_code == 403

        applications = list_project_applications(db, project, customer_user.id)
        assert len(applications) == 1

    def test_select_application_converts_to_pending_order_and_rejects_others(
        self,
        db,
        customer_user,
        photographer_user,
    ):
        other_photographer = _create_other_photographer(db)
        project = create_project(db, customer_user.id, _project_data(publish=True))
        selected = apply_project(db, project, photographer_user.id, _application_data(price_quote=1200))
        rejected = apply_project(db, project, other_photographer.id, _application_data(price_quote=1000))

        project, selected, order = select_application(db, project, selected, customer_user.id)
        db.refresh(rejected)

        assert project.status == ProjectStatus.CONVERTED
        assert project.selected_application_id == selected.id
        assert project.converted_order_id == order.id
        assert selected.status == ProjectApplicationStatus.SELECTED
        assert rejected.status == ProjectApplicationStatus.REJECTED
        assert order.status == OrderStatus.PENDING
        assert order.customer_id == customer_user.id
        assert order.photographer_id == photographer_user.id
        assert order.source_type == "project"
        assert order.source_id == str(project.id)
        assert order.source_application_id == selected.id
        assert order.final_price == Decimal("1200.00")
        assert order.currency == "CNY"
        assert order.service_location == "Central or Sheung Wan"
        assert order.contract_snapshot["source"] == {
            "type": "project",
            "id": str(project.id),
            "application_id": selected.id,
        }
        assert order.contract_snapshot["pricing"]["final_price"] == 1200.0
        assert order.contract_snapshot["project"]["customer_requirements"]["description"] == (
            "Need a relaxed portrait session with natural light."
        )
        assert order.contract_snapshot["application"]["proposal_text"] == (
            "I can shoot this with a clean editorial approach."
        )
        assert "【用户的需求】" in order.notes
        assert "【自己的提供】" in order.notes

    def test_select_application_checks_photographer_schedule(
        self,
        db,
        customer_user,
        photographer_user,
    ):
        project = create_project(db, customer_user.id, _project_data(publish=True))
        application = apply_project(
            db,
            project,
            photographer_user.id,
            _application_data(available_time=FUTURE_SHOOT_START + timedelta(hours=1)),
        )
        conflicting_order = Order(
            customer_id=customer_user.id,
            photographer_id=photographer_user.id,
            package_snapshot="Existing booking",
            appointment_time=FUTURE_SHOOT_START + timedelta(minutes=30),
            duration_minutes=120,
            status=OrderStatus.CONFIRMED,
        )
        db.add(conflicting_order)
        db.commit()

        with pytest.raises(HTTPException) as exc:
            select_application(db, project, application, customer_user.id)
        assert exc.value.status_code == 409


class TestProjectAPI:
    def test_photographer_can_manage_own_project(
        self,
        client,
        photographer_headers,
    ):
        draft_data = _project_data(publish=False).model_dump(mode="json")
        create_res = client.post(
            "/api/v1/projects/",
            json=draft_data,
            headers=photographer_headers,
        )
        assert create_res.status_code == 201
        project = create_res.json()
        assert project["status"] == "draft"

        update_res = client.put(
            f"/api/v1/projects/{project['id']}",
            json={"title": "Photographer-owned updated project"},
            headers=photographer_headers,
        )
        assert update_res.status_code == 200
        assert update_res.json()["title"] == "Photographer-owned updated project"

        publish_res = client.put(
            f"/api/v1/projects/{project['id']}/publish",
            headers=photographer_headers,
        )
        assert publish_res.status_code == 200
        assert publish_res.json()["status"] == "open"

        applications_res = client.get(
            f"/api/v1/projects/{project['id']}/applications",
            headers=photographer_headers,
        )
        assert applications_res.status_code == 200
        assert applications_res.json() == []

        close_res = client.put(
            f"/api/v1/projects/{project['id']}/close",
            json={"reason": "Test completed"},
            headers=photographer_headers,
        )
        assert close_res.status_code == 200
        assert close_res.json()["status"] == "closed"

    def test_photographer_cannot_edit_another_users_project(
        self,
        client,
        customer_headers,
        photographer_headers,
    ):
        create_res = client.post(
            "/api/v1/projects/",
            json=_project_data(publish=False).model_dump(mode="json"),
            headers=customer_headers,
        )
        project = create_res.json()

        update_res = client.put(
            f"/api/v1/projects/{project['id']}",
            json={"title": "Unauthorized edit"},
            headers=photographer_headers,
        )
        assert update_res.status_code == 403
        assert update_res.json()["detail"] == "Only the project owner can perform this action"

    def test_project_api_main_flow(
        self,
        client,
        customer_headers,
        photographer_headers,
        photographer_user,
    ):
        create_res = client.post(
            "/api/v1/projects/",
            json=_project_data(publish=True).model_dump(mode="json"),
            headers=customer_headers,
        )
        assert create_res.status_code == 201
        project = create_res.json()
        assert project["status"] == "open"
        assert project["location_name"] == "Central Market"
        assert project["location_latitude"] == "22.2841370"

        list_res = client.get("/api/v1/projects/")
        assert list_res.status_code == 200
        assert list_res.json()[0]["id"] == project["id"]

        apply_res = client.post(
            f"/api/v1/projects/{project['id']}/applications",
            json=_application_data().model_dump(mode="json"),
            headers=photographer_headers,
        )
        assert apply_res.status_code == 201
        application = apply_res.json()
        assert application["photographer_id"] == photographer_user.id

        applications_res = client.get(
            f"/api/v1/projects/{project['id']}/applications",
            headers=customer_headers,
        )
        assert applications_res.status_code == 200
        assert len(applications_res.json()) == 1

        select_res = client.post(
            f"/api/v1/projects/{project['id']}/applications/{application['id']}/select",
            headers=customer_headers,
        )
        assert select_res.status_code == 200
        body = select_res.json()
        assert body["project"]["status"] == "converted"
        assert body["application"]["status"] == "selected"
        assert body["order"]["status"] == "pending"
