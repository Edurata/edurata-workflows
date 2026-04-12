"""
Compute suggested free calendar slots from explicit busy intervals.
Expects calendarFetchOutcome \"ok\" and busyIntervals[{start,end}] (ISO with offset).
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from slot_math import build_calendar_availability_from_busy_intervals

logger = logging.getLogger(__name__)


def handler(inputs: Dict[str, Any]) -> Dict[str, Any]:
    raw = inputs or {}
    busy = raw.get("busyIntervals") or []
    busy_n = len(busy) if isinstance(busy, list) else 0
    logger.info(
        "calendar-slots-from-busy-intervals: start outcome=%s busy_intervals=%d horizon=%s tz=%s",
        raw.get("calendarFetchOutcome"),
        busy_n,
        raw.get("appointmentHorizonDays"),
        raw.get("appointmentTimeZone"),
    )
    out = build_calendar_availability_from_busy_intervals(raw)
    cal = out.get("calendarAvailability")
    slot_n = len((cal or {}).get("slots") or []) if isinstance(cal, dict) else 0
    logger.info(
        "calendar-slots-from-busy-intervals: done slots=%d calendarError=%s",
        slot_n,
        out.get("calendarError"),
    )
    return out
