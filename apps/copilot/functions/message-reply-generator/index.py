"""
Message reply: scheduling classification + single-shot reply via POST {apiUrl}/copilot/generate-response.
Prompt construction and both API calls live here; see message-reply-generator.edufc.yaml.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

CLASSIFY_SYSTEM = (
    "Du klassifizierst E-Mail-Konversationen. Entscheide, ob es um Termine, Uhrzeiten, Treffen, Besichtigungen, "
    "Rückrufzeiten, Verfügbarkeit oder Kalender geht (auch indirekt, z. B. „nächste Woche“, „wann passt es“).\n"
    'Antworte ausschließlich mit einem JSON-Objekt mit genau einem booleschen Schlüssel: "needsSchedulingContext" (true oder false).\n'
    "Kein Markdown, keine Code-Blöcke, kein weiterer Text."
)

DEFAULT_REPLY_BASE = [
    "Dir wird ein Email verlauf als Kontext von dir mit einer anderen Person gegeben. Du agierst im Namen eines Unternehmens und antwortest auf die letzte(n) unbeantwortete(n) Nachricht(en) der anderen Person.",
    "Die andere Person ist ein Kundin/Kunde oder Interessent des Unternehmens.",
    "1. Formuliere eine passende, freundliche Chat-Antwort (reply). Nutze dazu die dir gegebenen Informationen zur Beantwortung.",
    "1.1. Fasse dich so kurz wie möglich und ähnlich in der Länge wie die letzte Nachricht der anderen Person.",
    "1.2. Passe deinen Schreibstil an den der anderen Person an aber bleibe stehts professionell und freundlich.",
    "1.3. Antworte nur auf Produkt und Serviceangelegenheiten des Unternehmens, nicht auf allgemeine Themen.",
    "1.4. Sprich die andere Person nicht mit dem Nutzernamen an, sondern nur am Anfang mit seinem Namen und dann mit der Bezeichnung 'Sie'.",
]


def _post_generate_response(
    api_base: str,
    token: str,
    system_message: str,
    message: str,
    timeout: int = 120,
) -> Dict[str, Any]:
    url = api_base.rstrip("/") + "/copilot/generate-response"
    body = json.dumps(
        {
            "systemMessage": system_message,
            "message": message,
            "parseResponseToJson": True,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": "Bearer " + token.strip(),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace") if e.fp else str(e)
        raise RuntimeError(
            "generate-response HTTP %s: %s" % (getattr(e, "code", "?"), detail[:2000])
        ) from e


def _normalize_categories(raw: Any) -> Optional[List[Dict[str, Any]]]:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return None
    if not isinstance(raw, list) or len(raw) == 0:
        return None
    out: List[Dict[str, Any]] = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        d = dict(c)
        d["values"] = d.get("values") if d.get("values") is not None else []
        out.append(d)
    return out or None


def _build_user_message(combined_text: str, user_info: str, airtable_data: Any, primary_key: str) -> str:
    parts = [combined_text]
    ui = (user_info or "").strip()
    if ui:
        parts.append("Informationen zur Beantwortung (bitte nutzen):\n" + ui)
    pk = (primary_key or "").strip()
    if pk and airtable_data is not None:
        if isinstance(airtable_data, dict) or isinstance(airtable_data, list):
            ads = json.dumps(airtable_data, ensure_ascii=False)
        else:
            ads = str(airtable_data)
        parts.append("Airtable-Daten (Primary Key: " + pk + "):\n" + ads)
    return "\n\n---\n\n".join(parts)


def _as_bool(v: Any) -> bool:
    if v is True:
        return True
    if v is False or v is None:
        return False
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return bool(v)


def _format_free_slots_section(cal: Any) -> str:
    if not cal or not isinstance(cal, dict):
        return ""
    slots = cal.get("slots") or []
    if not slots:
        return ""
    tz = (cal.get("timeZone") or "UTC").strip()
    lines: List[str] = []
    for i, s in enumerate(slots):
        if not isinstance(s, dict):
            continue
        lines.append("%d. %s – %s (%s)" % (i + 1, s.get("start", ""), s.get("end", ""), tz))
    header = "Freie Zeitfenster (nur diese Slots sind verfügbar; Zeitzone " + tz + "):\n" + "\n".join(lines)
    st = (cal.get("summaryText") or "").strip()
    if st:
        return header + "\n\n" + st
    return header


def _category_block_lines(listener_settings: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    cats = (listener_settings or {}).get("customCategories") or []
    lines: List[str] = []
    cat_names = [str((c or {}).get("name") or "") for c in cats]
    cat_names = [n for n in cat_names if n]
    cat_desc: List[str] = []
    for c in cats:
        if not isinstance(c, dict):
            continue
        name = c.get("name") or ""
        desc = (c.get("description") or "").strip()
        vals = c.get("values") if c.get("values") is not None else c.get("possibleValues") or []
        val_names: List[str] = []
        for v in vals or []:
            if isinstance(v, dict) and v.get("name") is not None:
                val_names.append(str(v.get("name")))
            else:
                val_names.append(str(v))
        s = "- " + str(name)
        if desc:
            s += ": " + desc
        if val_names:
            s += " (Mögliche Werte: " + ", ".join(val_names) + ")"
        cat_desc.append(s)
    if cat_names and cat_desc:
        lines.append(
            "2. Ordne die Konversation den folgenden Kategorien zu (categories): "
            + ", ".join(cat_names)
            + ".\n"
            + "\n".join(cat_desc)
        )
    return lines, cat_names


def _build_unified_system_prompt(
    has_categories: bool,
    listener_settings: Dict[str, Any],
    include_scheduling: bool,
) -> str:
    base_block = "\n".join(DEFAULT_REPLY_BASE)
    lines: List[str] = [base_block]
    cat_lines, _ = _category_block_lines(listener_settings)
    lines.extend(cat_lines)

    if include_scheduling:
        lines.append(
            "3. Terminfindung (nur wenn im User-Message-Block freie Slots aufgeführt sind): "
            "Du kennst kein konkretes Kalenderprodukt (weder Outlook noch Google). "
            "Nutze ausschließlich die angegebenen freien Zeitfenster für konkrete Uhrzeiten.\n"
            "- Formuliere im Feld \"reply\" **eine** zusammenhängende Nachricht: zuerst die inhaltliche Antwort auf die Konversation, "
            "dann ggf. einen kurzen Abschnitt zur Terminvereinbarung (1–3 Optionen aus der Liste oder Bestätigung/Alternativen).\n"
            "- Wenn du konkrete Slots aus der Liste vorschlägst oder einen Slot bestätigen willst, setze zusätzlich \"scheduling\" als Objekt mit "
            "wantsScheduling, requestedDayOrPreference, selectedSlotStart, selectedSlotEnd (Start/End exakt wie in der Slot-Liste, damit das System den Slot blockieren kann). "
            "Sonst \"scheduling\": null.\n"
            "- Wenn die andere Person einen Wunschtermin nennt: vergleiche mit der Liste; im reply kurz Feedback, scheduling nur bei Bestätigung eines Listen-Slots."
        )
        if has_categories:
            lines.append(
                'Antworte ausschließlich mit einem JSON-Objekt mit genau drei Schlüsseln: "reply" (string), '
                '"categories" (Objekt mit Kategoriename als Schlüssel und gewähltem Wert als String), '
                '"scheduling" (Objekt oder null).'
            )
        else:
            lines.append(
                'Antworte ausschließlich mit einem JSON-Objekt mit genau zwei Schlüsseln: "reply" (string) und "scheduling" (Objekt oder null).'
            )
    else:
        if has_categories:
            lines.append(
                'Antworte ausschließlich mit einem JSON-Objekt mit genau drei Schlüsseln: "reply" (Antworttext), "categories" '
                '(Objekt mit Kategoriename als Schlüssel und gewähltem Wert als String) und "scheduling" (immer null).'
            )
        else:
            lines.append(
                'Antworte ausschließlich mit einem JSON-Objekt mit genau zwei Schlüsseln: "reply" (Antworttext) und "scheduling" (immer null).'
            )

    lines.extend(
        [
            "Wichtig: Gib nur das reine JSON-Objekt aus, ohne Markdown, ohne Code-Blöcke (keine ```) und ohne weiteren Text davor oder danach.",
            "Wichtig: verwende keine Platzhalter wie [Name], ${user.email} oder ähnliches.",
            'Kein Feld "summary".',
        ]
    )
    return "\n".join(lines)


def _build_single_shot_messages(inputs: Dict[str, Any], detection_response: Dict[str, Any]) -> Dict[str, str]:
    combined = (inputs.get("combinedText") or "").strip()
    if not combined:
        return {"systemMessage": "", "userMessage": ""}

    schedule_on = _as_bool(inputs.get("scheduleAppointments"))
    dpj = detection_response.get("parsedJson") if isinstance(detection_response.get("parsedJson"), dict) else {}
    needs_sched = dpj.get("needsSchedulingContext") is True
    cal = inputs.get("calendarAvailability")
    has_slots = isinstance(cal, dict) and bool(cal.get("slots") or [])
    include_scheduling = needs_sched and schedule_on and has_slots

    user_info = inputs.get("customInfo") or ""
    primary_key = (inputs.get("primaryKey") or "").strip()
    airtable_data = inputs.get("airtableData")
    normalized_cats = _normalize_categories(inputs.get("customCategories"))
    listener_settings = {"customCategories": normalized_cats or []}
    has_categories = bool(normalized_cats)

    user_message = _build_user_message(combined, user_info, airtable_data, primary_key)
    if include_scheduling:
        slot_block = _format_free_slots_section(cal)
        user_message = user_message + "\n\n---\n\n" + (slot_block or "(keine Slots)")

    system_message = _build_unified_system_prompt(has_categories, listener_settings, include_scheduling)
    return {"systemMessage": system_message, "userMessage": user_message}


def handler(inputs: Dict[str, Any]) -> Dict[str, Any]:
    api = (inputs.get("apiUrl") or "").strip()
    token = (inputs.get("executionToken") or "").strip()
    combined = (inputs.get("combinedText") or "").strip()

    empty_out: Dict[str, Any] = {
        "response": {
            "data": {
                "reply": "",
                "parsedJson": {"reply": "", "scheduling": None},
            }
        }
    }

    if not combined:
        return empty_out
    if not api or not token:
        raise ValueError("apiUrl and executionToken are required")

    classify = _post_generate_response(api, token, CLASSIFY_SYSTEM, combined, timeout=90)
    msgs = _build_single_shot_messages(inputs, classify)
    if not (msgs.get("systemMessage") or "").strip():
        return empty_out

    generated = _post_generate_response(
        api,
        token,
        msgs["systemMessage"],
        msgs["userMessage"],
        timeout=120,
    )
    return {"response": {"data": generated}}
