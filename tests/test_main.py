"""Tests for `src.main`.

Only the consecutive-error counter and the maintenance scheduling helper are
covered here: both are pure functions with no signal or wall-clock
dependency. The signal handlers and the main loop itself are deliberately
left untested at the unit level -- exercising them meaningfully would
require sending real OS signals or patching `time.sleep`/`time.monotonic`,
which tends to produce brittle, timing-sensitive tests for very little
assurance.
"""

import pytest

from src.main import _maintenance_due, _record_error


@pytest.mark.parametrize(
    ("consecutive_errors", "threshold", "expected_count", "expected_exceeded"),
    [
        (0, 5, 1, False),
        (4, 5, 5, False),
        (5, 5, 6, True),
        (10, 5, 11, True),
        (0, 0, 1, True),
    ],
)
def test_record_error(
    consecutive_errors: int,
    threshold: int,
    expected_count: int,
    expected_exceeded: bool,
) -> None:
    """`_record_error` increments the counter and flags once past `threshold`."""
    new_count, exceeded = _record_error(consecutive_errors, threshold)
    assert new_count == expected_count
    assert exceeded is expected_exceeded


def test_maintenance_due_after_interval_elapsed() -> None:
    """Maintenance is due once at least `interval_seconds` have elapsed."""
    assert _maintenance_due(last_run=0.0, now=3600.0, interval_seconds=3600.0) is True
    assert _maintenance_due(last_run=0.0, now=3601.0, interval_seconds=3600.0) is True


def test_maintenance_due_before_interval_elapsed() -> None:
    """Maintenance is not due before `interval_seconds` have elapsed."""
    assert (
        _maintenance_due(last_run=1_000.0, now=1_100.0, interval_seconds=3600.0)
        is False
    )
