"""
Fetch listing context for copilot replies: Airtable lookup by URL, scrape + cache on miss.
Uses stdlib only (urllib, re, json, html).
"""

from __future__ import annotations

import html as html_module
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _empty_response(error: Optional[str] = None) -> Dict[str, Any]:
    data: Dict[str, Any] = {"records": []}
    if error:
        data["_error"] = error[:500]
    return {"response": {"data": data}, "listingUrl": "", "scraped": False}


def _strip_html_text(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = html_module.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_listing_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    u = u.rstrip(").,;\"'")
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u.lstrip("/")
    parsed = urllib.parse.urlparse(u)
    if not parsed.netloc:
        return u
    path = parsed.path.rstrip("/") or parsed.path
    return urllib.parse.urlunparse(
        (parsed.scheme or "https", parsed.netloc.lower(), path, "", "", "")
    )


def _extract_url_from_messages(messages: Any, url_regex: str) -> str:
    if not url_regex or not messages:
        return ""
    try:
        pattern = re.compile(url_regex, re.I | re.MULTILINE)
    except re.error:
        return ""
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        m = pattern.search(content)
        if not m:
            continue
        raw = (m.group(1) if m.lastindex else m.group(0)) or ""
        normalized = _normalize_listing_url(raw)
        if normalized:
            return normalized
    return ""


def _airtable_get(
    base: str, table: str, token: str, filter_field: str, listing_url: str
) -> Tuple[Dict[str, Any], Optional[str]]:
    esc = listing_url.replace("\\", "\\\\").replace("'", "\\'")
    formula = "AND(LEN('%s') > 0, {%s} = '%s')" % (esc, filter_field, esc)
    q = urllib.parse.urlencode({"filterByFormula": formula})
    url = "https://api.airtable.com/v0/%s/%s?%s" % (base, table, q)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode()), None
    except urllib.error.HTTPError as e:
        detail = e.read().decode() if e.fp else str(e)
        return {"records": []}, "http_" + str(getattr(e, "code", "")) + ":" + detail[:500]
    except Exception as e:
        return {"records": []}, str(e)[:500]


def _airtable_create(
    base: str, table: str, token: str, fields: Dict[str, Any]
) -> Tuple[Dict[str, Any], Optional[str]]:
    url = "https://api.airtable.com/v0/%s/%s" % (base, table)
    body = json.dumps({"fields": fields}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            record = json.loads(resp.read().decode())
            return {"records": [record]}, None
    except urllib.error.HTTPError as e:
        detail = e.read().decode() if e.fp else str(e)
        return {"records": []}, "create_" + str(getattr(e, "code", "")) + ":" + detail[:500]
    except Exception as e:
        return {"records": []}, str(e)[:500]


def _fetch_html_direct(url: str) -> Optional[str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")
    except Exception:
        return None


def _fetch_html_crawlbase(url: str, token: str) -> Optional[str]:
    if not token:
        return None
    api = "https://api.crawlbase.com/?" + urllib.parse.urlencode(
        {"token": token, "url": url, "format": "json"}
    )
    req = urllib.request.Request(api, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            payload = json.loads(resp.read().decode())
            body = payload.get("body")
            return body if isinstance(body, str) else None
    except Exception:
        return None


def _fetch_listing_html(url: str, crawl_password: str) -> Optional[str]:
    html_text = _fetch_html_crawlbase(url, crawl_password) if crawl_password else None
    if not html_text:
        html_text = _fetch_html_direct(url)
    return html_text


def _parse_json_ld(html_text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for block in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text,
        re.I | re.S,
    ):
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if name and "title" not in out:
                out["title"] = _strip_html_text(str(name))
            offers = item.get("offers")
            if isinstance(offers, dict):
                price = offers.get("price")
                if price is not None and "price" not in out:
                    cur = offers.get("priceCurrency") or ""
                    out["price"] = ("%s %s" % (price, cur)).strip()
            elif isinstance(offers, list):
                for o in offers:
                    if isinstance(o, dict) and o.get("price") is not None:
                        out.setdefault("price", str(o.get("price")))
                        break
            desc = item.get("description")
            if desc and "description" not in out:
                out["description"] = _strip_html_text(str(desc))
    return out


def _regex_field(html_text: str, patterns: List[str]) -> str:
    for pat in patterns:
        m = re.search(pat, html_text, re.I | re.S)
        if m:
            val = _strip_html_text(m.group(1))
            if val:
                return val
    return ""


def _parse_listing_page(html_text: str, listing_url: str) -> Dict[str, str]:
    parsed = _parse_json_ld(html_text)
    title = parsed.get("title") or _regex_field(
        html_text,
        [
            r'id=["\']viewad-title["\'][^>]*>([^<]+)',
            r'<h1[^>]*class="[^"]*boxedarticle[^"]*"[^>]*>([^<]+)',
            r"<h1[^>]*>([^<]{4,200})</h1>",
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
        ],
    )
    price = parsed.get("price") or _regex_field(
        html_text,
        [
            r'id=["\']viewad-price["\'][^>]*>([^<]+)',
            r'itemprop=["\']price["\'][^>]*content=["\']([^"\']+)',
            r'class="[^"]*boxedarticle--price[^"]*"[^>]*>([^<]+)',
        ],
    )
    location = _regex_field(
        html_text,
        [
            r'id=["\']viewad-locality["\'][^>]*>([^<]+)',
            r'itemprop=["\']addressLocality["\'][^>]*content=["\']([^"\']+)',
        ],
    )
    description = parsed.get("description") or _regex_field(
        html_text,
        [
            r'id=["\']viewad-description-text["\'][^>]*>(.*?)</p>',
            r'itemprop=["\']description["\'][^>]*content=["\']([^"\']+)',
        ],
    )
    if description and len(description) > 4000:
        description = description[:4000] + "..."

    fields: Dict[str, str] = {"url": listing_url}
    if title:
        fields["title"] = title
    if price:
        fields["price"] = price
    if location:
        fields["location"] = location
    if description:
        fields["description"] = description
    return fields


def handler(inputs: Dict[str, Any]) -> Dict[str, Any]:
    messages = inputs.get("messages") or []
    url_regex = (inputs.get("anzeigeUrlRegex") or "").strip()
    base = (inputs.get("airtable_base_id") or "").strip()
    table = (inputs.get("airtable_table_id") or "").strip()
    token = (inputs.get("token") or "").strip()
    filter_field = (inputs.get("airtable_filter_field") or "url").strip() or "url"
    crawl_password = (inputs.get("crawlPassword") or "").strip()

    listing_url = _extract_url_from_messages(messages, url_regex)
    if not listing_url:
        return _empty_response("no_listing_url")

    if not base or not table or not token:
        return {
            "response": {"data": {"records": [], "_note": "airtable_not_configured"}},
            "listingUrl": listing_url,
            "scraped": False,
        }

    body, err = _airtable_get(base, table, token, filter_field, listing_url)
    if body.get("records"):
        if err:
            body["_lookup_warning"] = err
        return {"response": {"data": body}, "listingUrl": listing_url, "scraped": False}

    html_text = _fetch_listing_html(listing_url, crawl_password)
    if not html_text:
        out = _empty_response("fetch_failed")
        out["listingUrl"] = listing_url
        if err:
            out["response"]["data"]["_lookup_error"] = err
        return out

    fields = _parse_listing_page(html_text, listing_url)
    fields[filter_field] = listing_url

    created, create_err = _airtable_create(base, table, token, fields)
    if create_err and not created.get("records"):
        out = _empty_response(create_err)
        out["listingUrl"] = listing_url
        out["response"]["data"]["_scraped_fields"] = fields
        return out

    return {
        "response": {"data": created},
        "listingUrl": listing_url,
        "scraped": True,
    }


if __name__ == "__main__":
    sample = handler(
        {
            "messages": [
                {
                    "content": "Link: https://www.kleinanzeigen.de/s-anzeige/test/1234567890-123-4567",
                }
            ],
            "anzeigeUrlRegex": r"https?://(?:www\.)?kleinanzeigen\.de/s-anzeige/[^\s\"'<>]+",
            "airtable_base_id": "",
            "airtable_table_id": "",
            "token": "",
        }
    )
    print(json.dumps(sample, ensure_ascii=False, indent=2))
