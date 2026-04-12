"""
Microsoft Graph calendarView → busy intervals → free slot suggestions.
Skips when provider is not OUTLOOK, scheduling is off, or token is missing.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, time
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from slot_math import build_calendar_availability_from_busy_intervals

logger = logging.getLogger(__name__)


def _localize_graph_dt(
    dt_str: Optional[str], ev_tz_name: Optional[str], fallback_tz: str
) -> Optional[datetime]:
    if not dt_str:
        return None
    dt_str = dt_str.strip()
    if "T" not in dt_str:
        return None
    tzname = (ev_tz_name or fallback_tz or "UTC").strip()
    try:
        z = ZoneInfo(tzname)
    except Exception:
        z = ZoneInfo("UTC")
    base = dt_str.split(".")[0].replace("Z", "")
    if len(base) < 19:
        return None
    naive = datetime.strptime(base[:19], "%Y-%m-%dT%H:%M:%S")
    return naive.replace(tzinfo=z)


def handler(inputs: Dict[str, Any]) -> Dict[str, Any]:
    inputs = inputs or {}
    provider = (inputs.get("emailProvider") or "").strip().upper()
    if provider != "OUTLOOK" or not inputs.get("scheduleAppointments"):
        logger.info(
            "outlook-calendar-free-slots: skip provider=%s scheduleAppointments=%s",
            provider or "(empty)",
            bool(inputs.get("scheduleAppointments")),
        )
        return {"calendarAvailability": None}

    token = (inputs.get("outlookToken") or "").strip()
    if not token:
        logger.warning("outlook-calendar-free-slots: missing outlookToken")
        return {"calendarAvailability": None, "calendarError": "missing_token"}

    tz_name = (inputs.get("appointmentTimeZone") or "Europe/Berlin").strip()
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Europe/Berlin")
        tz_name = "Europe/Berlin"

    horizon = int(inputs.get("appointmentHorizonDays") or 14)
    now = datetime.now(tz)
    start_day = now.date()
    end_day = start_day + timedelta(days=max(1, horizon))

    start_utc = datetime.combine(start_day, time.min, tzinfo=tz).astimezone(ZoneInfo("UTC"))
    end_utc = datetime.combine(end_day, time(23, 59, 59), tzinfo=tz).astimezone(ZoneInfo("UTC"))
    start_utc_s = start_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_utc_s = end_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    logger.info(
        "outlook-calendar-free-slots: graph range start=%s end=%s tz=%s horizon_days=%d workday=%s-%s duration_min=%s",
        start_utc_s,
        end_utc_s,
        tz_name,
        horizon,
        inputs.get("appointmentWorkdayStart"),
        inputs.get("appointmentWorkdayEnd"),
        inputs.get("appointmentDurationMinutes"),
    )

    events: List[Dict[str, Any]] = []
    url = "https://graph.microsoft.com/v1.0/me/calendarView?" + urllib.parse.urlencode(
        {
            "startDateTime": start_utc_s,
            "endDateTime": end_utc_s,
            "$select": "start,end,subject,showAs,isAllDay",
            "$top": "100",
        }
    )
    safe_pref = tz_name.replace('"', "")
    while url:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": "Bearer " + token,
                "Prefer": 'outlook.timezone="' + safe_pref + '"',
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            logger.exception(
                "outlook-calendar-free-slots: Graph request failed page=%d error=%s",
                len(events),
                str(e)[:500],
            )
            return {"calendarAvailability": None, "calendarError": str(e)[:500]}
        batch = data.get("value") or []
        events.extend(batch)
        logger.info(
            "outlook-calendar-free-slots: graph page events=%d total_so_far=%d has_next=%s",
            len(batch),
            len(events),
            bool(data.get("@odata.nextLink")),
        )
        url = data.get("@odata.nextLink")

    busy_intervals: List[Dict[str, str]] = []
    for ev in events:
        if (ev.get("showAs") or "").lower() == "free":
            continue
        s = ev.get("start") or {}
        e = ev.get("end") or {}
        st = _localize_graph_dt(s.get("dateTime"), s.get("timeZone"), tz_name)
        en = _localize_graph_dt(e.get("dateTime"), e.get("timeZone"), tz_name)
        if not st or not en or en <= st:
            continue
        busy_intervals.append(
            {
                "start": st.astimezone(tz).isoformat(),
                "end": en.astimezone(tz).isoformat(),
            }
        )

    logger.info(
        "outlook-calendar-free-slots: busy_intervals=%d from_events=%d",
        len(busy_intervals),
        len(events),
    )

    out = build_calendar_availability_from_busy_intervals(
        {
            **inputs,
            "calendarFetchOutcome": "ok",
            "busyIntervals": busy_intervals,
        }
    )
    cal = out.get("calendarAvailability")
    slot_n = len((cal or {}).get("slots") or []) if isinstance(cal, dict) else 0
    logger.info(
        "outlook-calendar-free-slots: done free_slots=%s calendarError=%s",
        slot_n,
        out.get("calendarError"),
    )
    return out
