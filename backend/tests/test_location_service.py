from types import SimpleNamespace

import pytest

from backend.app.services.location_service import distance_label, haversine_km, package_coordinates, validate_coordinates


def test_haversine_same_point_is_zero():
    assert haversine_km(22.3193, 114.1694, 22.3193, 114.1694) == pytest.approx(0)


def test_haversine_known_cities_is_reasonable():
    # Hong Kong to Chengdu is roughly 1,300 km.
    assert 1200 < haversine_km(22.3193, 114.1694, 30.5728, 104.0668) < 1500


def test_invalid_coordinates_are_rejected():
    with pytest.raises(ValueError):
        validate_coordinates(91, 0)
    with pytest.raises(ValueError):
        validate_coordinates(0, 181)


def test_unknown_distance_never_looks_precise():
    assert distance_label(None) == "同城，距离未知"


def test_package_coordinates_override_profile_coordinates():
    profile = SimpleNamespace(service_latitude=22.3, service_longitude=114.1)
    package = {"service_latitude": 30.6, "service_longitude": 104.0}
    assert package_coordinates(package, profile) == (30.6, 104.0)
