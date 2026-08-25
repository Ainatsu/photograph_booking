import json
from datetime import datetime, timezone, timedelta

from backend.app.core.timezone import UTCJSONResponse, isoformat_utc


def render_json(content):
    return json.loads(UTCJSONResponse(content=content).body)


def test_isoformat_utc_marks_naive_datetime_as_utc():
    assert isoformat_utc(datetime(2026, 7, 2, 12, 0, 0)) == "2026-07-02T12:00:00Z"


def test_isoformat_utc_converts_aware_datetime_to_utc():
    value = datetime(2026, 7, 2, 20, 30, 0, tzinfo=timezone(timedelta(hours=8)))

    assert isoformat_utc(value) == "2026-07-02T12:30:00Z"


def test_utc_json_response_normalizes_datetime_strings_on_datetime_keys():
    payload = render_json(
        {
            "created_at": "2026-07-02 12:00:00",
            "updated_at": "2026-07-02T20:30:00+08:00",
            "appointment_time": "2026-07-02T12:30:00Z",
        }
    )

    assert payload == {
        "created_at": "2026-07-02T12:00:00Z",
        "updated_at": "2026-07-02T12:30:00Z",
        "appointment_time": "2026-07-02T12:30:00Z",
    }


def test_utc_json_response_does_not_change_plain_dates_or_other_strings():
    payload = render_json(
        {
            "date": "2026-07-02",
            "title": "2026-07-02T12:00:00",
        }
    )

    assert payload == {
        "date": "2026-07-02",
        "title": "2026-07-02T12:00:00",
    }
