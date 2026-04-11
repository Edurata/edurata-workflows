"""
Microsoft Graph calendarView → busy intervals → free slot suggestions.
Skips when provider is not OUTLOOK, scheduling is off, or token is missing.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, time
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from slot_math import build_calendar_availability_from_busy_intervals


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
        return {"calendarAvailability": None}

    token = (inputs.get("outlookToken") or "").strip()
    if not token:
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
            return {"calendarAvailability": None, "calendarError": str(e)[:500]}
        events.extend(data.get("value") or [])
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

    return build_calendar_availability_from_busy_intervals(
        {
            **inputs,
            "calendarFetchOutcome": "ok",
            "busyIntervals": busy_intervals,
        }
    )
