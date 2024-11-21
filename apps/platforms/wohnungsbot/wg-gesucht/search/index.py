import re
import json
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import os
import time
from login import login_wg_gesucht
import random

def build_base_url():
    return f"https://www.wg-gesucht.de/wohnungen-in-Berlin.8.2.1.0.html"

def parse_online_duration(noprint_text):
    """Parse the noprint date field text to get the online duration in hours."""
    date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", noprint_text)
    if date_match:
        post_date = datetime.strptime(date_match.group(1), "%d.%m.%Y")
        now = datetime.now()
        duration = now - post_date
        return duration  # timedelta

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
            print(f"Attempting to retrieve CSRF token, attempt {attempt + 1}")
            response = session.get(base_url, headers={
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": base_url
            })
            if response.status_code != 200:
                print(f"Failed to load page (status code: {response.status_code})")
                time.sleep(wait)
                continue

            csrf_token = response.cookies.get("csrf_token")
            if not csrf_token:
                soup = BeautifulSoup(response.text, 'html.parser')
                csrf_token_input = soup.find("input", {"name": "csrf_token"})
                csrf_token = csrf_token_input["value"] if csrf_token_input else None

            if csrf_token:
                print(f"CSRF token retrieved: {csrf_token}")
                session.cookies.set("csrf_token", csrf_token)
                break
            else:
                print("CSRF token not found, retrying...")

            time.sleep(wait)
        except Exception as e:
            print(f"Error fetching CSRF token: {e}")
            time.sleep(wait)

    if not csrf_token:
        print("Failed to retrieve CSRF token after multiple attempts.")
    return csrf_token

def search_listings(session, filters):
    categories = filters.get("categories", ["Wohnung"])
    city_name = filters.get("city_name", "Berlin")
    gender = filters.get("gender")
    age = filters.get("age")
    city_id = 8  # Berlin
    district_names = filters.get("district_names", [])
    script_dir = os.path.dirname(__file__)
    district_mapping = json.load(open(os.path.join(script_dir, "district_mapping.json")))  # Load your mapping JSON
    city_mapping = json.load(open(os.path.join(script_dir, "city_mapping.json")))  # Load your mapping JSON
    categories_mapping = json.load(open(os.path.join(script_dir, "categories_mapping.json")))
    gender_mapping = json.load(open(os.path.join(script_dir, "gender_mapping.json")))
    gender_id = False
    district_codes = []

    try:
        district_codes = [district_mapping[city_name][district_name] for district_name in district_names]
        city_id = city_mapping[city_name]
        category_ids = [categories_mapping[category] for category in categories]
        if gender:
            gender_id = gender_mapping[gender]
    except KeyError as e:
        raise ValueError(f"Invalid city or district name provided: {e}")

    base_url = build_base_url()
    csrf_token = fetch_csrf_token(session, base_url)
    if not csrf_token:
        print("Failed to retrieve CSRF token. Cannot proceed with search.")
        return []

    move_in_earliest = filters.get("move_in_earliest")
    move_in_latest = filters.get("move_in_latest")
    min_stay_days = filters.get("min_stay_days", 0)
    rm_min = filters.get("room_number_min", 1)
    max_online_hours = filters.get("max_online_hours", None)

    dFr = int(datetime.strptime(move_in_earliest, "%Y-%m-%d").replace(hour=12).timestamp()) if move_in_earliest else None
    dTo = int(datetime.strptime(move_in_latest, "%Y-%m-%d").replace(hour=12).timestamp()) if move_in_latest else None

    params = {
        "city_id": city_id,
        "csrf_token": csrf_token,
        "offer_filter": 1,
        "sort_column": 0,
        "sort_order": 0,
        "noDeact": 1,
        "exc": 2,
        "categories[]": category_ids,
        "rent_types[]": [1, 2],
        "rMax": filters.get("rent_max", 1000),
        "sMin": filters.get("room_size_min", 10),
        "rmMin": rm_min
    }

    if gender_id:
        params["wgSea"] = gender_id

    if age:
        params["wgAge"] = age

    # Add district codes to params as an array
    if district_codes:
        params["ot[]"] = sorted(district_codes)  # Pass the array of district codes directly

    if dFr is not None:
        params["dFr"] = dFr

    # if "only_furnished" in filters:
    #     params["fur"] = 1 if filters["only_furnished"] else 0
    # if "balcony" in filters:
    #     params["bal_or_ter"] = 1 if filters["balcony"] else 0

    full_url = requests.Request("GET", base_url, params=params).prepare().url
    print(f"Constructed URL for request: {full_url}")

    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0",
        "Referer": base_url
    }

    response = session.get(base_url, params=params, headers=headers)
    print(f"Response status code: {response.status_code}")

    if response.status_code != 200:
        print("Failed to retrieve listings. Please check the URL and parameters.")
        return []

    # Check if the URL has changed
    if response.url != full_url:
        print(f"Detected URL change. New URL: {response.url}")

        # wait for random seconds before making the next request
        time.sleep(random.uniform(0, 2))

        # Make a new request to the redirected URL
        response = session.get(response.url, headers=headers)
        print(f"Refreshed response status code: {response.status_code}")

        if response.status_code != 200:
            print("Failed to retrieve listings after redirection. Exiting.")
            return []

    soup = BeautifulSoup(response.text, 'html.parser')
    listings = []
    max_online_delta = timedelta(hours=max_online_hours) if max_online_hours is not None else None

    for listing in soup.find_all("div", class_="offer_list_item"):
        print("\n--- New Listing Found ---")

        verified_label = listing.find("a", class_="label_verified")
        if verified_label:
            print("Skipping listing with 'Verifiziertes Unternehmen' label.")
            continue

        title_element = listing.find("h3", class_="truncate_title")
        title = title_element.text.strip() if title_element else "No title"
        link_element = title_element.find("a", href=True) if title_element else None
        relative_link = link_element["href"] if link_element else None
        link = "https://www.wg-gesucht.de" + relative_link if relative_link else None
        print(f"Title: {title}, Link: {link}")

        rent_element = listing.find("div", class_="col-xs-3")
        rent_text = rent_element.text.strip() if rent_element else "0"
        rent = int(''.join(filter(str.isdigit, rent_text)))
        print(f"Rent: {rent}")

        room_size_element = listing.find("div", class_="col-xs-3 text-right")
        room_size_text = room_size_element.text.strip() if room_size_element else "0"
        room_size_match = re.search(r'(\d+)', room_size_text)
        room_size = int(room_size_match.group(1)) if room_size_match else 0
        print(f"Room Size: {room_size} m²")

        location_element = listing.find("div", class_="col-xs-11")
        location_text = location_element.text.replace("\n", " ").strip() if location_element else ""
        location_text = re.sub(r'\s+', ' ', location_text)
        location_parts = [part.strip() for part in location_text.split('|')]

        room_count_text = location_parts[0] if len(location_parts) > 0 else None
        room_count = int(re.search(r'(\d+)', room_count_text).group(1)) if room_count_text and re.search(r'(\d+)', room_count_text) else None
        city_area = location_parts[1] if len(location_parts) > 1 else None
        street = location_parts[2] if len(location_parts) > 2 else None
        print(f"Room Count: {room_count}, City Area: {city_area}, Street: {street}")

        post_date_element = listing.find("span", style=lambda value: value and ("#218700" in value or "#898989" in value))
        online_duration = parse_online_duration(post_date_element.text.strip()) if post_date_element else float('inf')
        print(f"Online Duration: {online_duration}")

        if max_online_delta and online_duration > max_online_delta:
            print(f"Listing exceeds max online hours ({online_duration} > {max_online_delta}). Skipping listing.")
            continue

        availability_dates = listing.find("div", class_="col-xs-5 text-center").text.strip() if listing.find("div", class_="col-xs-5 text-center") else ""
        start_date_text, end_date_text = availability_dates.split(" - ") if " - " in availability_dates else (availability_dates, None)
        start_date_text = start_date_text.strip()
        end_date_text = end_date_text.strip() if end_date_text else None

        stay_days = None
        if start_date_text and end_date_text:
            try:
                start_date = datetime.strptime(start_date_text, "%d.%m.%Y")
                end_date = datetime.strptime(end_date_text, "%d.%m.%Y")
                stay_days = (end_date - start_date).days
                if stay_days < min_stay_days:
                    print(f"Stay duration ({stay_days} days) is less than minimum required ({min_stay_days} days). Skipping listing.")
                    continue

                if move_in_latest:
                    move_in_latest_dt = datetime.strptime(move_in_latest, "%Y-%m-%d")
                    if start_date < datetime.strptime(move_in_earliest, "%Y-%m-%d") or start_date > move_in_latest_dt:
                        print("Availability start date is outside the allowed move-in range. Skipping listing.")
                        continue

            except ValueError:
                continue

        ad_person_element = listing.find("span", class_="ml5")
        ad_person = ad_person_element.text.strip() if ad_person_element else "Unknown"
        current_listing = {
            "title": title,
            "link": link,
            "rent": rent,
            "room_size": room_size,
            "availability_start": start_date_text,
            "availability_end": end_date_text,
            "stay_days": stay_days,
            "room_count": room_count,
            "city_area": city_area,
            "street": street,
            "lister_name": ad_person,
            "online_duration": str(online_duration),
            "description": "Description not available in list view"
        }
        # Fetch description from the detailed listing page
        if link:
            try:
                wait_time = random.uniform(0, 2)
                time.sleep(wait_time)
                response = session.get(link, headers={"User-Agent": "Mozilla/5.0"})
                if response.status_code == 200:
                    detail_soup = BeautifulSoup(response.text, "html.parser")
                    description_div = detail_soup.find("div", id="freitext_0")
                    description_paragraph = description_div.find("p") if description_div else None
                    description = description_paragraph.get_text(strip=True) if description_paragraph else "No description found."
                    current_listing["description"] = description
                    print(f"Updated description for {title}: {description[:50]}...")
                else:
                    print(f"Failed to fetch description for {title} (Status Code: {response.status_code})")
            except Exception as e:
                print(f"Error fetching description for {title}: {e}")
        listings.append(current_listing)

    return listings

def handler(inputs):
    username = os.getenv("WG_USERNAME")
    password = os.getenv("WG_PASSWORD")
    if not username or not password:
        raise ValueError("WG_USERNAME and WG_PASSWORD must be set as environment variables.")
    print("Logging in with provided credentials...")
    
    session, _ = login_wg_gesucht(username, password)

    filters = inputs.get("filter", {})
    listings = search_listings(session, filters)

    return {"listings": listings}

# Sample usage:
inputs = {
    "filter":
    {
        "gender": "Mann",
        "categories": ["WG-Zimmer"],
        "city_name": "Berlin",
        "district_names": [],
        "rent_max": 1500,
        "room_size_min": 10,
        "room_number_min": 2,
        "only_furnished": False,
        "max_online_hours": 10,
        "balcony": False,
        "move_in_earliest": "2024-12-01",
        "move_in_latest": "2025-01-01",
        "min_stay_days": 20
    }
}
results = handler(inputs)
print(results)
