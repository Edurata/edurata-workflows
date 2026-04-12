"""
Validate LLM scheduling intent against allowed slots and build an Outlook-style event block payload.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _reply_from_api(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    pj = data.get("parsedJson") if isinstance(data.get("parsedJson"), dict) else {}
    if isinstance(pj, dict) and pj.get("reply") is not None:
        return str(pj.get("reply") or "").strip()
    raw = (data.get("reply") or "").strip()
    if not raw:
        return ""
    try:
        o = json.loads(raw)
        if isinstance(o, dict) and o.get("reply") is not None:
            return str(o.get("reply") or "").strip()
    except Exception:
        pass
    return raw


def _norm_iso(s: Any) -> str:
    s = (str(s or "")).strip().replace(" ", "")
    if "+00:00" in s:
        s = s.replace("+00:00", "Z")
    if "." in s and "T" in s:
        head, tail = s.split("T", 1)
        if "." in tail:
            t1, t2 = tail.split(".", 1)
            digits = ""
            for c in t2:
                if c.isdigit():
                    digits += c
                else:
                    break
            rest = t2[len(digits) :] if digits else t2
            s = head + "T" + t1 + "." + digits[:6] + rest if digits else head + "T" + t1 + rest
    return s


def _html_escape(s: Any) -> str:
    return (
        str(s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def handler(inputs: Dict[str, Any]) -> Dict[str, Any]:
    inputs = inputs or {}
    ai = inputs.get("aiResponse") or {}
    cal = inputs.get("calendarAvailability")
    allowed: List[Any] = []
    if isinstance(cal, dict):
        allowed = cal.get("slots") or []

    logger.info(
        "calendar-block-from-ai-response: start allowed_slots=%d ai_keys=%s",
        len(allowed),
        list(ai.keys()) if isinstance(ai, dict) else type(ai).__name__,
    )

    scheduling = ai.get("scheduling")
    if not isinstance(scheduling, dict):
        pj = ai.get("parsedJson") if isinstance(ai.get("parsedJson"), dict) else {}
        if isinstance(pj, dict) and isinstance(pj.get("scheduling"), dict):
            scheduling = pj.get("scheduling")
    if not isinstance(scheduling, dict):
        logger.info("calendar-block-from-ai-response: no scheduling object -> hasCalendarBlock=false")
        return {"hasCalendarBlock": False}

    if not scheduling.get("wantsScheduling"):
        logger.info(
            "calendar-block-from-ai-response: wantsScheduling=false -> hasCalendarBlock=false data=%s",
            {k: scheduling.get(k) for k in ("wantsScheduling", "requestedDayOrPreference") if k in scheduling},
        )
        return {"hasCalendarBlock": False}

    start = (scheduling.get("selectedSlotStart") or "").strip()
    end = (scheduling.get("selectedSlotEnd") or "").strip()
    if not start or not end:
        logger.info(
            "calendar-block-from-ai-response: missing slot start/end -> hasCalendarBlock=false start_len=%d end_len=%d",
            len(start),
            len(end),
        )
        return {"hasCalendarBlock": False}

    ns, ne = _norm_iso(start), _norm_iso(end)
    ok = False
    for sl in allowed:
        if not isinstance(sl, dict):
            continue
        if _norm_iso(str(sl.get("start") or "")) == ns and _norm_iso(str(sl.get("end") or "")) == ne:
            ok = True
            break
    if not ok:
        logger.info(
            "calendar-block-from-ai-response: slot not in allowed list -> hasCalendarBlock=false "
            "normalized_start=%s normalized_end=%s",
            ns,
            ne,
        )
        return {"hasCalendarBlock": False}

    tz = (inputs.get("appointmentTimeZone") or "Europe/Berlin").strip()
    attendee_email = (inputs.get("attendeeEmail") or "").strip()
    attendee_name = (inputs.get("attendeeName") or "").strip()
    subj = (inputs.get("eventSubject") or "").strip() or "Termin"
    reply_txt = _reply_from_api(ai)
    if reply_txt:
        body_html = (
            "<p>"
            + _html_escape(reply_txt).replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br/>")
            + "</p>"
        )
    else:
        body_html = "<p>Termin</p>"

    attendees: List[Dict[str, Any]] = []
    if attendee_email:
        attendees.append(
            {
                "emailAddress": {"address": attendee_email, "name": attendee_name or attendee_email},
                "type": "required",
            }
        )

    logger.info(
        "calendar-block-from-ai-response: ok hasCalendarBlock=true tz=%s subject_len=%d "
        "attendee_set=%d reply_excerpt_len=%d",
        tz,
        len(subj),
        1 if attendee_email else 0,
        len(reply_txt),
    )
    return {
        "hasCalendarBlock": True,
        "block": {
            "start": start,
            "end": end,
            "timeZone": tz,
            "subject": subj,
            "bodyHtml": body_html,
            "attendees": attendees,
        },
    }
