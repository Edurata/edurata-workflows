import re
import json
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import os
import time
from login import login_wg_gesucht

def build_base_url(city_id):
    return f"https://www.wg-gesucht.de/wohnungen-in-Berlin.8.2.1.0.html"

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
    city_id = filters.get("city_id")  # Expect city_id in the filters
    if not city_id:
        raise ValueError("city_id must be specified in filters.")
        
    base_url = build_base_url(city_id)
    
    csrf_token = fetch_csrf_token(session, base_url)
    if not csrf_token:
        print("Failed to retrieve CSRF token. Cannot proceed with search.")
        return []

    print(f"Requesting URL: {base_url} with filters: {filters}")

    move_in_earliest = filters.get("move_in_earliest")
    min_stay_days = filters.get("min_stay_days", 0)
    rm_min = filters.get("room_number_min", 1)  # Minimum room count
    max_online_time = filters.get("max_online_time", None)  # Maximum listing online time in hours

    dFr = int(datetime.strptime(move_in_earliest, "%Y-%m-%d").replace(hour=12).timestamp()) if move_in_earliest else None

    params = {
        "city_id": city_id,
        "csrf_token": csrf_token,
        "offer_filter": 1,
        "sort_column": 0,
        "sort_order": 0,
        "noDeact": 1,
        "exc": 2,
        "categories[]": 2,
        "rent_types[]": [1, 2],  # Constant rent types
        "rMax": filters.get("rent_max", 1000),
        "sMin": filters.get("room_size_min", 10),
        "rmMin": rm_min  # Minimum room count filter
    }

    # Include dates only if they are defined
    if dFr is not None:
        params["dFr"] = dFr

    # Comma-separated district codes to `ot[]` parameters
    district_codes = filters.get("district_codes", "")
    if district_codes:
        for code in district_codes.split(","):
            params[f"ot[{code.strip()}]"] = code.strip()

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

    max_online_delta = timedelta(hours=max_online_time) if max_online_time is not None else None
    current_time = datetime.now()

    for listing in soup.find_all("div", class_="offer_list_item"):
        print("\n--- New Listing Found ---")

        # Skip listings with "Verifiziertes Unternehmen" label
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

        # Filter based on max_online_time
        post_date_element = listing.find("span", class_="text-muted")
        if post_date_element and max_online_delta:
            post_time_str = post_date_element.text.strip()
            try:
                post_time = datetime.strptime(post_time_str, "%d.%m.%Y %H:%M")
                time_since_post = current_time - post_time
                if time_since_post > max_online_delta:
                    print(f"Listing exceeds max online time ({time_since_post} > {max_online_delta}). Skipping listing.")
                    continue
            except ValueError:
                print(f"Could not parse posting time for filtering: {post_time_str}")
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
#     "filter":
    # {
    #     "city_id": 8, 
    #     "rent_max": 1500,
    #     "room_size_min": 10,
    #     "room_number_min": 2,
    #     "district_codes": "132, 85079, 163, 165, 170, 171, 189",
    #     "only_furnished": False,
    #     "max_online_time": 1,
    #     "balcony": False,
    #     "move_in_earliest": "2025-01-01",
    #     "min_stay_days": 100
    # }
# }
# results = handler(inputs)
# print(results)
