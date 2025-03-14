"""
test_iss_tracker.py
-------------------
Unit tests for the iss_tracker.py module.

Tests:
- test_calculate_speed(): Tests speed calculation from velocity components.
- test_compute_average_speed(): Verifies the average speed calculation.
- test_find_closest_epoch(): Ensures the function finds the closest ISS state vector.
- test_convert_epoch_to_datetime(): Tests conversion of epoch timestamps.

Author: Dominic Nguyen
Date: 02/24/2025

Usage:
Run tests using pytest:
```bash
pytest -v test_iss_tracker.py
"""

import pytest
from datetime import datetime, timezone

# Import functions from `iss_module.py` (renamed from `iss_tracker.py`)
from iss_tracker import calculate_speed, compute_average_speed, find_closest_epoch, convert_epoch_to_datetime

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
    now = datetime.utcnow().replace(tzinfo=timezone.utc)  # Use current UTC time
    closest = find_closest_epoch(mock_data)
    
    # Determine expected closest epoch dynamically
    expected_closest = min(mock_data, key=lambda sv: abs(convert_epoch_to_datetime(sv["epoch"]) - now))
    
    assert closest["epoch"] == expected_closest["epoch"], (
        f"Expected closest epoch to be {expected_closest['epoch']}, but got {closest['epoch']}"
    )

def test_convert_epoch_to_datetime():
    """Tests if epoch conversion from YYYY-DDD format works properly."""
    test_epoch = "2025-055T12:00:00.000Z"
    expected = datetime(2025, 2, 24, 12, 0, 0, tzinfo=timezone.utc)  # 2025-055 is Feb 24, 2025
    assert convert_epoch_to_datetime(test_epoch) == expected

