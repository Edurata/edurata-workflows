"""
Compute suggested free calendar slots from explicit busy intervals.
Expects calendarFetchOutcome \"ok\" and busyIntervals[{start,end}] (ISO with offset).
"""
from __future__ import annotations

from typing import Any, Dict

from slot_math import build_calendar_availability_from_busy_intervals


def handler(inputs: Dict[str, Any]) -> Dict[str, Any]:
    return build_calendar_availability_from_busy_intervals(inputs or {})
