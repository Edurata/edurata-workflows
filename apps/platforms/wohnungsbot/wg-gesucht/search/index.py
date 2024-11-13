import re
import requests
from bs4 import BeautifulSoup
import os
import time
from datetime import datetime, timedelta
from login import login_wg_gesucht

def build_base_url(city_id):
    return f"https://www.wg-gesucht.de/wohnungen-in-Berlin-gesucht.{city_id}.2.1.0.html"

def parse_online_duration(noprint_text):
    """Parse the noprint date field text to get the online duration in hours."""
    date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", noprint_text)
    if date_match:
        post_date = datetime.strptime(date_match.group(1), "%d.%m.%Y")
        now = datetime.now()
        duration = now - post_date
        return duration

    if "Tag" in noprint_text:
        days = int(re.search(r"(\d+)", noprint_text).group(1)) if re.search(r"(\d+)", noprint_text) else 1
        return timedelta(hours=days * 24)
    elif "Stunde" in noprint_text:
        hours = int(re.search(r"(\d+)", noprint_text).group(1)) if re.search(r"(\d+)", noprint_text) else 1
        return timedelta(hours=hours)
    
    return timedelta(hours=0)

def fetch_csrf_token(session, base_url, max_retries=3, wait=2):
    csrf_token = None
    for attempt in range(max_retries):
        try:
            response = session.get(base_url, headers={
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": base_url
            })
            if response.status_code != 200:
                time.sleep(wait)
                continue

            csrf_token = response.cookies.get("csrf_token")
            if not csrf_token:
                soup = BeautifulSoup(response.text, 'html.parser')
                csrf_token_input = soup.find("input", {"name": "csrf_token"})
                csrf_token = csrf_token_input["value"] if csrf_token_input else None

            if csrf_token:
                session.cookies.set("csrf_token", csrf_token)
                break
            time.sleep(wait)
        except Exception as e:
            time.sleep(wait)

    return csrf_token

def search_people(session, city_id, max_online_hours=None):
    base_url = build_base_url(city_id)
    csrf_token = fetch_csrf_token(session, base_url)
    if not csrf_token:
        return []

    params = {
        "csrf_token": csrf_token,
        "city_id": city_id,
        "sort_column": 0,
        "sort_order": 0,
        "noDeact": 1,
        "categories[]": 2,
        "exContAds": 1,
    }

    response = session.get(base_url, params=params, headers={
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0",
        "Referer": base_url
    })

    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    people_listings = []
    max_online_delta = timedelta(hours=max_online_hours) if max_online_hours is not None else None

    for person in soup.find_all("div", class_="wgg_card request_list_item"):
        denied_image = person.find("img", {"class": "overlay placeholder_denied_female"})
        if denied_image:
            continue

        # Extract name and age
        name_age_element = person.find("div", class_="col-sm-12 flex_space_between").find("span")
        name_age_text = name_age_element.text.strip() if name_age_element else "Unknown"
        name, age = None, None
        if ", " in name_age_text:
            name, age = name_age_text.split(", ")
            age = int(age)

        # Extract online duration and filter by max_online_hours if specified
        online_duration_element = person.find("span", style=lambda value: value and "#218700" in value)
        online_duration = parse_online_duration(online_duration_element.text.strip()) if online_duration_element else timedelta(hours=float('inf'))
        
        if max_online_delta and online_duration > max_online_delta:
            continue

        # Extract title and link
        title_element = person.find("h3", class_="truncate_title")
        title = title_element.text.strip() if title_element else "No title"
        link_element = title_element.find("a", href=True) if title_element else None
        relative_link = link_element["href"] if link_element else None
        link = "https://www.wg-gesucht.de/" + relative_link if relative_link else None

        description = fetch_person_description(session, link) if link else "Description unavailable."

        people_listings.append({
            "title": title,
            "link": link,
            "name": name,
            "age": age,
            "online_duration": str(online_duration),
            "description": description
        })

    return people_listings

def fetch_person_description(session, link):
    try:
        response = session.get(link, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": link
        })
        if response.status_code != 200:
            return "Description unavailable."

        soup = BeautifulSoup(response.text, 'html.parser')
        description_tag = soup.find("div", {"id": "freetext_description"})
        if description_tag:
            description_text = description_tag.find("p", {"class": "original_text"}).get_text(separator="\n").strip()
            return description_text
        else:
            return "Description unavailable."
    except Exception as e:
        return "Description unavailable."

def handler(inputs):
    username = os.getenv("WG_USERNAME")
    password = os.getenv("WG_PASSWORD")
    if not username or not password:
        raise ValueError("WG_USERNAME and WG_PASSWORD must be set as environment variables.")
    print("Logging in with provided credentials...")
    
    session, _ = login_wg_gesucht(username, password)

    city_id = inputs.get("city_id")
    max_online_hours = inputs.get("max_online_hours")
    if not city_id:
        raise ValueError("city_id must be specified.")
    
    people = search_people(session, city_id, max_online_hours)

    return {"people_listings": people}

# Sample usage:
# inputs = {"city_id": 8, "max_online_hours": 2}
# results = handler(inputs)
# print(results)
