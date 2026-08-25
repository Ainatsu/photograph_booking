from backend.app.models.photographer import PhotographerProfile
from backend.app.schemas.photographer_application import PhotographerApplicationSubmit
from backend.app.services.photographer_application_service import (
    APPROVED,
    PENDING,
    approve_application,
    submit_application,
)


def _application_data() -> PhotographerApplicationSubmit:
    return PhotographerApplicationSubmit(
        profile_intro="I shoot portraits and events.",
        location="Hong Kong",
        equipment="Sony A7M4 + 24-70mm F2.8",
        styles=["portrait", "event"],
        portfolio_refs=[
            {
                "id": "work-1",
                "url": "/static/uploads/work-1.jpg",
                "thumbnail_url": "/static/uploads/work-1_thumb.jpg",
                "title": "Portrait sample",
            }
        ],
    )


def test_submit_application_keeps_user_as_customer(db, customer_user):
    application = submit_application(db, customer_user, _application_data())

    db.refresh(customer_user)

    assert application.status == PENDING
    assert customer_user.role == "customer"


def test_approve_application_promotes_user_and_creates_profile(db, customer_user, admin_user):
    application = submit_application(db, customer_user, _application_data())

    approved = approve_application(
        db,
        application.id,
        reviewer_id=admin_user.id,
        review_note="Looks good",
    )
    db.refresh(customer_user)
    profile = db.query(PhotographerProfile).filter(
        PhotographerProfile.user_id == customer_user.id
    ).first()

    assert approved.status == APPROVED
    assert approved.reviewed_by == admin_user.id
    assert customer_user.role == "photographer"
    assert customer_user.bio == "I shoot portraits and events."
    assert profile is not None
    assert profile.location == "Hong Kong"
    assert profile.equipment == "Sony A7M4 + 24-70mm F2.8"
    assert profile.styles == ["portrait", "event"]
    assert profile.portfolio[0]["id"] == "work-1"


def test_admin_api_lists_and_approves_application(client, db, customer_user, admin_user, admin_headers):
    application = submit_application(db, customer_user, _application_data())

    list_response = client.get(
        "/api/v1/admin/photographer-applications",
        headers=admin_headers,
    )
    approve_response = client.put(
        f"/api/v1/admin/photographer-applications/{application.id}/approve",
        json={"review_note": "Approved from admin API"},
        headers=admin_headers,
    )
    db.refresh(customer_user)

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == application.id
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == APPROVED
    assert approve_response.json()["reviewed_by"] == admin_user.id
    assert customer_user.role == "photographer"
