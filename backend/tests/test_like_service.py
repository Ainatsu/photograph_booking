import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.models.like import Like
from backend.app.services.like_service import (
    batch_like_count,
    batch_like_status,
    batch_like_summary,
    get_like_count,
    get_popular_like_targets,
    get_like_targets_for_user,
    get_liked_works_for_user,
    is_liked,
    set_like_state,
    sync_cache_from_db,
    toggle_like,
    warmup_like_cache,
)


class TestToggleLikeBasic:
    def test_first_like_creates_record(self, db, customer_user):
        result = toggle_like(db, customer_user.id, "portfolio", "p1")
        assert result == {"liked": True, "count": 1}

        record = db.query(Like).filter_by(
            user_id=customer_user.id,
            target_type="portfolio",
            target_id="p1",
        ).first()
        assert record is not None

    def test_second_toggle_unlikes(self, db, customer_user):
        toggle_like(db, customer_user.id, "portfolio", "p1")
        result = toggle_like(db, customer_user.id, "portfolio", "p1")

        assert result == {"liked": False, "count": 0}
        assert (
            db.query(Like)
            .filter_by(user_id=customer_user.id, target_type="portfolio", target_id="p1")
            .first()
            is None
        )

    def test_different_targets_are_independent(self, db, customer_user):
        toggle_like(db, customer_user.id, "portfolio", "p1")
        toggle_like(db, customer_user.id, "portfolio", "p2")
        toggle_like(db, customer_user.id, "package", "pkg1")

        assert is_liked(db, customer_user.id, "portfolio", "p1") is True
        assert is_liked(db, customer_user.id, "portfolio", "p2") is True
        assert is_liked(db, customer_user.id, "package", "pkg1") is True

        toggle_like(db, customer_user.id, "portfolio", "p1")
        assert is_liked(db, customer_user.id, "portfolio", "p1") is False
        assert is_liked(db, customer_user.id, "portfolio", "p2") is True
        assert is_liked(db, customer_user.id, "package", "pkg1") is True

    def test_multiple_users_like_same_target(self, db, customer_user, photographer_user):
        toggle_like(db, customer_user.id, "portfolio", "p1")
        toggle_like(db, photographer_user.id, "portfolio", "p1")

        assert get_like_count(db, "portfolio", "p1") == 2


class TestBatchQueries:
    def test_batch_status(self, db, customer_user):
        toggle_like(db, customer_user.id, "portfolio", "p1")
        toggle_like(db, customer_user.id, "portfolio", "p3")

        status = batch_like_status(db, customer_user.id, "portfolio", ["p1", "p2", "p3"])
        assert status == {"p1": True, "p2": False, "p3": True}

    def test_batch_count(self, db, customer_user, photographer_user):
        toggle_like(db, customer_user.id, "portfolio", "p1")
        toggle_like(db, photographer_user.id, "portfolio", "p1")
        toggle_like(db, customer_user.id, "portfolio", "p2")

        counts = batch_like_count(db, "portfolio", ["p1", "p2", "p3"])
        assert counts == {"p1": 2, "p2": 1, "p3": 0}

    def test_batch_summary_with_user(self, db, customer_user, photographer_user):
        toggle_like(db, customer_user.id, "portfolio", "p1")
        toggle_like(db, photographer_user.id, "portfolio", "p1")

        summary = batch_like_summary(
            db,
            "portfolio",
            ["p1", "p2"],
            user_id=customer_user.id,
        )
        assert summary == {
            "p1": {"count": 2, "liked": True},
            "p2": {"count": 0, "liked": False},
        }

    def test_batch_summary_without_user(self, db, customer_user):
        toggle_like(db, customer_user.id, "portfolio", "p1")
        summary = batch_like_summary(db, "portfolio", ["p1", "p2"])
        assert summary == {
            "p1": {"count": 1, "liked": False},
            "p2": {"count": 0, "liked": False},
        }

    def test_batch_queries_empty_list(self, db, customer_user):
        assert batch_like_status(db, customer_user.id, "portfolio", []) == {}
        assert batch_like_count(db, "portfolio", []) == {}
        assert batch_like_summary(db, "portfolio", []) == {}

    def test_batch_queries_deduplicate_ids(self, db, customer_user):
        toggle_like(db, customer_user.id, "portfolio", "p1")
        counts = batch_like_count(db, "portfolio", ["p1", "p1", "p2"])
        assert counts == {"p1": 1, "p2": 0}


class TestSourceOfTruth:
    def test_status_reads_from_database(self, db, customer_user):
        toggle_like(db, customer_user.id, "portfolio", "p1")
        assert batch_like_status(db, customer_user.id, "portfolio", ["p1"]) == {"p1": True}

    def test_count_reads_from_database(self, db, customer_user, photographer_user):
        toggle_like(db, customer_user.id, "portfolio", "p1")
        toggle_like(db, photographer_user.id, "portfolio", "p1")
        assert batch_like_count(db, "portfolio", ["p1"]) == {"p1": 2}

    def test_toggle_after_external_state_change_still_works(self, db, customer_user):
        set_like_state(db, customer_user.id, "package", "pkg1", True)
        result = toggle_like(db, customer_user.id, "package", "pkg1")
        assert result == {"liked": False, "count": 0}

    def test_new_toggle_creates_record(self, db, customer_user):
        result = toggle_like(db, customer_user.id, "portfolio", "fresh")
        assert result == {"liked": True, "count": 1}


class TestWarmupAndSync:
    def test_warmup_returns_distinct_target_count(self, db, customer_user, photographer_user):
        toggle_like(db, customer_user.id, "portfolio", "p1")
        toggle_like(db, photographer_user.id, "portfolio", "p1")
        toggle_like(db, customer_user.id, "portfolio", "p2")
        toggle_like(db, customer_user.id, "package", "pkg1")

        assert warmup_like_cache(db) == 3

    def test_warmup_empty_db(self, db):
        assert warmup_like_cache(db) == 0

    def test_sync_cache_from_db_matches_warmup_contract(self, db, customer_user):
        toggle_like(db, customer_user.id, "portfolio", "p1")
        toggle_like(db, customer_user.id, "package", "pkg1")
        assert sync_cache_from_db(db) == 2


class TestIdempotency:
    def test_toggle_same_target_multiple_times_gives_consistent_result(self, db, customer_user):
        results = [toggle_like(db, customer_user.id, "portfolio", "p1") for _ in range(5)]
        assert results == [
            {"liked": True, "count": 1},
            {"liked": False, "count": 0},
            {"liked": True, "count": 1},
            {"liked": False, "count": 0},
            {"liked": True, "count": 1},
        ]

    def test_set_like_state_is_idempotent(self, db, customer_user):
        first = set_like_state(db, customer_user.id, "portfolio", "p1", True)
        second = set_like_state(db, customer_user.id, "portfolio", "p1", True)
        third = set_like_state(db, customer_user.id, "portfolio", "p1", False)
        assert first == {"liked": True, "count": 1}
        assert second == {"liked": True, "count": 1}
        assert third == {"liked": False, "count": 0}

    def test_db_prevents_duplicate_insert(self, db, customer_user):
        db.add(Like(user_id=customer_user.id, target_type="portfolio", target_id="p1"))
        db.commit()

        db.add(Like(user_id=customer_user.id, target_type="portfolio", target_id="p1"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


class TestHelperMethods:
    def test_get_like_count(self, db, customer_user, photographer_user):
        assert get_like_count(db, "portfolio", "p1") == 0
        toggle_like(db, customer_user.id, "portfolio", "p1")
        assert get_like_count(db, "portfolio", "p1") == 1
        toggle_like(db, photographer_user.id, "portfolio", "p1")
        assert get_like_count(db, "portfolio", "p1") == 2

    def test_is_liked(self, db, customer_user):
        assert is_liked(db, customer_user.id, "portfolio", "p1") is False
        toggle_like(db, customer_user.id, "portfolio", "p1")
        assert is_liked(db, customer_user.id, "portfolio", "p1") is True
        toggle_like(db, customer_user.id, "portfolio", "p1")
        assert is_liked(db, customer_user.id, "portfolio", "p1") is False

    def test_get_like_targets_for_user(self, db, customer_user):
        toggle_like(db, customer_user.id, "portfolio", "p1")
        toggle_like(db, customer_user.id, "portfolio", "p2")
        items = get_like_targets_for_user(db, customer_user.id, "portfolio")
        assert set(items) == {"p1", "p2"}

    def test_get_liked_works_for_user_returns_work_data_in_time_order(
        self,
        db,
        customer_user,
        photographer_user,
        photographer_profile,
    ):
        photographer_profile.portfolio = [
            {"id": "liked-old", "url": "/static/old.jpg", "title": "Old"},
            {"id": "liked-new", "url": "/static/new.jpg", "title": "New"},
        ]
        db.commit()

        toggle_like(db, customer_user.id, "portfolio", "liked-old")
        toggle_like(db, customer_user.id, "portfolio", "liked-new")

        result = get_liked_works_for_user(db, customer_user.id)

        assert result["total"] == 2
        assert [item["work_id"] for item in result["items"]] == ["liked-new", "liked-old"]
        assert result["items"][0]["work_data"]["title"] == "New"
        assert result["items"][0]["photographer_id"] == photographer_user.id

    def test_get_popular_like_targets(self, db, customer_user, photographer_user):
        toggle_like(db, customer_user.id, "portfolio", "p1")
        toggle_like(db, photographer_user.id, "portfolio", "p1")
        toggle_like(db, customer_user.id, "portfolio", "p2")

        items = get_popular_like_targets(db, "portfolio", limit=10)
        assert items[0] == {"target_id": "p1", "count": 2}
        assert any(item == {"target_id": "p2", "count": 1} for item in items)


class TestLikeAPI:
    def test_toggle_creates_like(self, client, customer_headers):
        res = client.post(
            "/api/v1/likes/toggle",
            json={"target_type": "portfolio", "target_id": "api-p1"},
            headers=customer_headers,
        )
        assert res.status_code == 200
        assert res.json() == {"liked": True, "count": 1}

    def test_toggle_then_untoggle(self, client, customer_headers):
        client.post(
            "/api/v1/likes/toggle",
            json={"target_type": "portfolio", "target_id": "api-p2"},
            headers=customer_headers,
        )
        res = client.post(
            "/api/v1/likes/toggle",
            json={"target_type": "portfolio", "target_id": "api-p2"},
            headers=customer_headers,
        )
        assert res.status_code == 200
        assert res.json() == {"liked": False, "count": 0}

    def test_batch_status_returns_correct(self, client, customer_headers):
        client.post(
            "/api/v1/likes/toggle",
            json={"target_type": "portfolio", "target_id": "api-s1"},
            headers=customer_headers,
        )
        client.post(
            "/api/v1/likes/toggle",
            json={"target_type": "portfolio", "target_id": "api-s3"},
            headers=customer_headers,
        )
        res = client.get(
            "/api/v1/likes/status",
            params={"target_type": "portfolio", "ids": "api-s1,api-s2,api-s3"},
            headers=customer_headers,
        )
        assert res.status_code == 200
        assert res.json() == {"api-s1": True, "api-s2": False, "api-s3": True}

    def test_batch_count_returns_correct(self, client, customer_headers, photographer_headers):
        client.post(
            "/api/v1/likes/toggle",
            json={"target_type": "portfolio", "target_id": "api-c1"},
            headers=customer_headers,
        )
        client.post(
            "/api/v1/likes/toggle",
            json={"target_type": "portfolio", "target_id": "api-c1"},
            headers=photographer_headers,
        )
        res = client.get(
            "/api/v1/likes/count",
            params={"target_type": "portfolio", "ids": "api-c1,api-c2"},
        )
        assert res.status_code == 200
        assert res.json() == {"api-c1": 2, "api-c2": 0}

    def test_summary_returns_count_and_status(self, client, customer_headers):
        client.post(
            "/api/v1/likes/toggle",
            json={"target_type": "portfolio", "target_id": "api-summary"},
            headers=customer_headers,
        )
        res = client.get(
            "/api/v1/likes/summary",
            params={"target_type": "portfolio", "ids": "api-summary,missing"},
            headers=customer_headers,
        )
        assert res.status_code == 200
        assert res.json() == {
            "items": {
                "api-summary": {"count": 1, "liked": True},
                "missing": {"count": 0, "liked": False},
            }
        }

    def test_liked_works_endpoint(self, db, client, customer_headers, photographer_profile):
        photographer_profile.portfolio = [
            {"id": "api-liked-work", "url": "/static/liked.jpg", "title": "Liked"}
        ]
        db.commit()
        client.post(
            "/api/v1/likes/toggle",
            json={"target_type": "portfolio", "target_id": "api-liked-work"},
            headers=customer_headers,
        )

        res = client.get("/api/v1/likes/works", headers=customer_headers)

        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 1
        assert body["items"][0]["work_id"] == "api-liked-work"
        assert body["items"][0]["work_data"]["title"] == "Liked"

    def test_count_no_auth_required(self, client):
        res = client.get(
            "/api/v1/likes/count",
            params={"target_type": "portfolio", "ids": "p1"},
        )
        assert res.status_code == 200

    def test_toggle_requires_auth(self, client):
        res = client.post(
            "/api/v1/likes/toggle",
            json={"target_type": "portfolio", "target_id": "p1"},
        )
        assert res.status_code == 401

    def test_status_without_auth_returns_false(self, client):
        res = client.get(
            "/api/v1/likes/status",
            params={"target_type": "portfolio", "ids": "p1"},
        )
        assert res.status_code == 200
        assert res.json() == {"p1": False}


class TestValidation:
    def test_invalid_target_type_toggle(self, client, customer_headers):
        res = client.post(
            "/api/v1/likes/toggle",
            json={"target_type": "invalid", "target_id": "p1"},
            headers=customer_headers,
        )
        assert res.status_code == 400

    def test_empty_target_id_toggle(self, client, customer_headers):
        res = client.post(
            "/api/v1/likes/toggle",
            json={"target_type": "portfolio", "target_id": ""},
            headers=customer_headers,
        )
        assert res.status_code == 400

    def test_empty_ids_batch(self, client, customer_headers):
        res = client.get(
            "/api/v1/likes/status",
            params={"target_type": "portfolio", "ids": ""},
            headers=customer_headers,
        )
        assert res.status_code == 400

    def test_invalid_target_type_status(self, client, customer_headers):
        res = client.get(
            "/api/v1/likes/status",
            params={"target_type": "invalid", "ids": "p1"},
            headers=customer_headers,
        )
        assert res.status_code == 400
