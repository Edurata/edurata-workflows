"""Free-slot computation from busy intervals (timezone + workday window)."""
from __future__ import annotations

from datetime import datetime, timedelta, time
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo


def _parse_hhmm(s: Any) -> Tuple[int, int]:
    parts = (str(s or "09:00")).strip().split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    return h, m


def _parse_iso_to_dt(s: Any) -> Optional[datetime]:
    if s is None:
        return None
    t = str(s).strip()
    if not t:
        return None
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(t)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt


def build_calendar_availability_from_busy_intervals(inputs: Dict[str, Any]) -> Dict[str, Any]:
    outcome = inputs.get("calendarFetchOutcome")
    if outcome != "ok":
        out: Dict[str, Any] = {"calendarAvailability": None}
        if inputs.get("calendarError"):
            out["calendarError"] = inputs["calendarError"]
        return out

    tz_name = (inputs.get("appointmentTimeZone") or "Europe/Berlin").strip()
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Europe/Berlin")
        tz_name = "Europe/Berlin"

    horizon = int(inputs.get("appointmentHorizonDays") or 14)
    dur_min = int(inputs.get("appointmentDurationMinutes") or 30)
    mr = inputs.get("maxSchedulingRecommendations")
    if mr is None or str(mr).strip() == "":
        max_recs = 3
    else:
        max_recs = max(1, min(3, int(mr)))
    wh_start_h, wh_start_m = _parse_hhmm(inputs.get("appointmentWorkdayStart"))
    wh_end_h, wh_end_m = _parse_hhmm(inputs.get("appointmentWorkdayEnd"))

    now = datetime.now(tz)
    start_day = now.date()
    end_day = start_day + timedelta(days=max(1, horizon))

    busy_pairs: List[Tuple[datetime, datetime]] = []
    for row in inputs.get("busyIntervals") or []:
        if not isinstance(row, dict):
            continue
        st = _parse_iso_to_dt(row.get("start"))
        en = _parse_iso_to_dt(row.get("end"))
        if not st or not en or en <= st:
            continue
        busy_pairs.append((st.astimezone(tz), en.astimezone(tz)))

    busy_pairs.sort(key=lambda x: x[0])
    merged: List[List[datetime]] = []
    for s, e in busy_pairs:
        if not merged or s > merged[-1][1]:
            merged.append([s, e])
        else:
            merged[-1][1] = max(merged[-1][1], e)

    slots: List[Dict[str, str]] = []
    delta = timedelta(minutes=dur_min)
    d = start_day
    while d <= end_day and len(slots) < max_recs:
        day_start = datetime.combine(d, time(wh_start_h, wh_start_m), tzinfo=tz)
        day_end = datetime.combine(d, time(wh_end_h, wh_end_m), tzinfo=tz)
        if day_end <= day_start:
            d += timedelta(days=1)
            continue

        day_busy: List[List[datetime]] = []
        for bs, be in merged:
            seg_s = max(bs, day_start)
            seg_e = min(be, day_end)
            if seg_e > seg_s:
                day_busy.append([seg_s, seg_e])
        day_busy.sort(key=lambda x: x[0])
        merged_day: List[List[datetime]] = []
        for s, e in day_busy:
            if not merged_day or s > merged_day[-1][1]:
                merged_day.append([s, e])
            else:
                merged_day[-1][1] = max(merged_day[-1][1], e)

        cursor = day_start
        for s, e in merged_day:
            while cursor + delta <= s and len(slots) < max_recs:
                slots.append(
                    {
                        "start": cursor.isoformat(),
                        "end": (cursor + delta).isoformat(),
                    }
                )
                cursor += delta
            if cursor < e:
                cursor = e
        while cursor + delta <= day_end and len(slots) < max_recs:
            slots.append(
                {
                    "start": cursor.isoformat(),
                    "end": (cursor + delta).isoformat(),
                }
            )
            cursor += delta

        d += timedelta(days=1)

    summary = (
        "%d freie Zeitoption(en) à %d Min (max. %d Optionen), nächste %d Tage, Zeitzone %s."
        % (len(slots), dur_min, max_recs, horizon, tz_name)
    )
    return {
        "calendarAvailability": {
            "timeZone": tz_name,
            "slots": slots,
            "summaryText": summary,
            "reservationMinutes": dur_min,
            "maxRecommendations": max_recs,
        }
    }
