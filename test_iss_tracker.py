"""
test_iss_tracker.py
-------------------
Unit tests for the iss_tracker.py module.

Tests:
- test_calculate_speed(): Tests speed calculation from velocity components.
- test_compute_average_speed(): Verifies the average speed calculation.
- test_find_closest_epoch(): Ensures the function finds the closest ISS state vector.
- test_convert_epoch_to_datetime(): Tests conversion of epoch timestamps.
- test_calculate_speed_zero_velocity(): Ensures correct behavior when velocity is zero.
- test_compute_average_speed_empty_list(): Checks handling of empty velocity list.
- test_find_closest_epoch_empty_list(): Ensures function handles an empty state vector list.
- test_convert_epoch_to_datetime_invalid_format(): Tests error handling for incorrect epoch format.

Author: Dominic Nguyen
Date: 02/24/2025

Usage:
Run tests using pytest:
```bash
pytest -v test_iss_tracker.py
"""

import pytest
import json
from datetime import datetime, timezone

# Import functions from `iss_tracker.py`
#from iss_tracker import app

from iss_tracker import (
    calculate_speed,
    compute_average_speed,
    find_closest_epoch,
    convert_epoch_to_datetime,
    app
    )

# Mock ISS trajectory data
mock_data = [
    {
        "epoch": "2025-055T12:00:00.000Z",
        "position": (-4488.3365, 5094.0272, -251.5952),
        "velocity": (-3.7069, -2.9739, 6.0133)
    },
    {
        "epoch": "2025-056T14:30:00.000Z",
        "position": (-4499.003, 5000.234, -400.123),
        "velocity": (-3.5000, -2.9000, 6.0500)
    }
]

def test_calculate_speed():
    """Tests speed calculation from velocity components."""
    assert round(calculate_speed(mock_data[0]["velocity"]), 2) == 7.66

def test_compute_average_speed():
    """Tests if average speed calculation is correct."""
    assert round(compute_average_speed(mock_data), 2) == 7.62

def test_find_closest_epoch():
    """Tests finding the closest epoch to a given time."""
    now = datetime.now(timezone.utc)  # Corrected per deprecation warning
    closest = find_closest_epoch(mock_data)

    # Determine expected closest epoch dynamically
    expected_closest = min(mock_data, key=lambda sv: abs(convert_epoch_to_datetime(sv["epoch"]) - now))

    assert closest["epoch"] == expected_closest["epoch"], (
        f"Expected closest epoch to be {expected_closest['epoch']}, but got {closest['epoch']}"
    )

def test_find_closest_epoch_empty_list():
    """Ensures function handles an empty state vector list properly."""
    with pytest.raises(ValueError):  # Expecting a ValueError due to min() on empty list
        find_closest_epoch([])  # Passing an empty list


def test_convert_epoch_to_datetime():
    """Tests if epoch conversion from YYYY-DDD format works properly."""
    test_epoch = "2025-055T12:00:00.000Z"
    expected = datetime(2025, 2, 24, 12, 0, 0, tzinfo=timezone.utc)  # 2025-055 is Feb 24, 2025
    assert convert_epoch_to_datetime(test_epoch) == expected

# === Additional Tests for Edge Cases === #

def test_calculate_speed_zero_velocity():
    """Ensures correct behavior when velocity is zero (should return 0 speed)."""
    assert calculate_speed((0, 0, 0)) == 0

def test_compute_average_speed_empty_list():
    """Checks handling of empty velocity list (should return 0)."""
    assert compute_average_speed([]) == 0

def test_convert_epoch_to_datetime_invalid_format():
    """Tests error handling for incorrectly formatted epoch strings."""
    with pytest.raises(ValueError):
        convert_epoch_to_datetime("Invalid-Epoch-Format")

"""
@pytest.fixture
def client():
    
    #Flask test client setup
    
    with app.test_client() as client:
        yield client

def test_get_epochs(client):
    #Test /epochs endpoint returns data
    response = client.get("/epochs")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data["epochs"], list)  # Should be a list

def test_get_epoch(client):
    #Test /epochs/<epoch> returns correct structure
    epoch = "2025-088T12:00:00.000Z"
    response = client.get(f"/epochs/{epoch}")
    assert response.status_code in [200, 404]
    data = response.get_json()
    if response.status_code == 200:
        assert "position" in data
        assert "velocity" in data

def test_get_epoch_speed(client):
    #Test /epochs/<epoch>/speed
    epoch = "2025-088T12:00:00.000Z"
    response = client.get(f"/epochs/{epoch}/speed")
    assert response.status_code in [200, 404]
    data = response.get_json()
    if response.status_code == 200:
        assert isinstance(data["speed"], float)

def test_get_epoch_location(client):
    #Test /epochs/<epoch>/location
    epoch = "2025-088T12:00:00.000Z"
    response = client.get(f"/epochs/{epoch}/location")
    assert response.status_code in [200, 404]
    data = response.get_json()
    if response.status_code == 200:
        assert "latitude" in data
        assert "longitude" in data
        assert "altitude" in data
        assert "geoposition" in data

def test_get_now(client):
    #Test /now endpoint returns real-time data
    response = client.get("/now")
    assert response.status_code == 200
    data = response.get_json()
    assert "speed" in data
    assert "latitude" in data
    assert "longitude" in data

def test_redis_key_exists(client):
    #Test if specific Redis key exists
    redis_key = "epoch:2025-074T06:07:48.000Z"
    response = client.get(f"/epochs/2025-074T06:07:48.000Z")
    assert response.status_code in [200, 404]
"""
