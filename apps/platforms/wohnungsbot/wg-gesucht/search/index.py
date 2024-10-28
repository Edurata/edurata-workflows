import re
import json
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import os
import time
from login import login_wg_gesucht

def build_base_url(city):
    city_slug = city.lower().replace(" ", "-")
    return f"https://www.wg-gesucht.de/wohnungen-in-{city_slug}.8.2.1.0.html"

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

def get_listing_text(session, link, base_url):
    try:
        response = session.get(link, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": base_url
        })
        if response.status_code != 200:
            print(f"Failed to retrieve listing page at {link}")
            return "Description not available"

        soup = BeautifulSoup(response.text, 'html.parser')
        description_element = soup.find("div", {"id": "ad_description_text"})
        description_text = description_element.get_text(separator=" ", strip=True) if description_element else "Description not available"
        return description_text
    except Exception as e:
        print(f"Error retrieving listing description: {e}")
        return "Description not available"

def search_listings(session, filters):
    city = filters.get("city", "Berlin")  # Default to Berlin if no city is provided
    base_url = build_base_url(city)
    
    csrf_token = fetch_csrf_token(session, base_url)
    if not csrf_token:
        print("Failed to retrieve CSRF token. Cannot proceed with search.")
        return []

    print(f"Requesting URL: {base_url} with filters: {filters}")

    move_in_earliest = filters.get("move_in_earliest")
    move_in_latest = filters.get("move_in_latest")
    min_stay_days = filters.get("min_stay_days", 0)

    dFr = int(datetime.strptime(move_in_earliest, "%Y-%m-%d").replace(hour=12).timestamp()) if move_in_earliest else None
    dTo = int(datetime.strptime(move_in_latest, "%Y-%m-%d").replace(hour=12).timestamp()) if move_in_latest else None

    params = {
        "csrf_token": csrf_token,
        "offer_filter": 1,
        "city_id": 8,
        "sort_column": 0,
        "sort_order": 0,
        "noDeact": 1,
        "dFr": dFr,
        "dTo": dTo,
        "exc": 2,
        "categories[]": 2,
        "rMax": filters.get("rent_max", 1000),
        "sMin": filters.get("room_size_min", 10)
    }

    if "only_furnished" in filters:
        params["fur"] = 1 if filters["only_furnished"] else 0
    if "balcony" in filters:
        params["bal_or_ter"] = 1 if filters["balcony"] else 0

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

    soup = BeautifulSoup(response.text, 'html.parser')
    listings = []

    for listing in soup.find_all("div", class_="offer_list_item"):
        print("\n--- New Listing Found ---")

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
                    continue
            except ValueError:
                continue

        ad_person_element = listing.find("span", class_="ml5")
        ad_person = ad_person_element.text.strip() if ad_person_element else "Unknown"

        description_text = get_listing_text(session, link, base_url) if link else "No link available"

        listings.append({
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
            "description": description_text
        })

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
# inputs = {
#     "filter": {
#         "city": "Munich",
#         "rent_max": 1000,
#         "room_size_min": 10,
#         "only_furnished": False,
#         "max_online_time": 48,
#         "balcony": False,
#         "move_in_earliest": "2025-02-01",
#         "move_in_latest": "2025-02-20",
#         "min_stay_days": 100
#     }
# }
# results = handler(inputs)
# print(results)
