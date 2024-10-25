import re
import json
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import os
from login import login_wg_gesucht  # Import the login function from login.py

# WG-Gesucht base URL
BASE_URL = "https://www.wg-gesucht.de"

def parse_date(date_string):
    if date_string:  
        try:
            return datetime.strptime(date_string.strip(), "%d.%m.%Y")
        except ValueError:
            return None
    return None

def calculate_stay_length(start_date, end_date):
    if start_date and end_date:
        return (end_date - start_date).days
    return None

def search_listings(session, filters):
    search_url = f"{BASE_URL}/wohnungen-in-Berlin.8.2.1.0.html"
    response = session.get(search_url, params={
        "offer_filter": 1,
        "city_id": 8,
        "sort_order": 0,
        "noDeact": 1,
        "categories[]": 2,
        "sMin": filters.get("sMin", 0),
        "rMax": filters.get("rMax", 10000),
        "fur": 1 if filters.get("furnished") else 0,
        "bal_or_ter": 1 if filters.get("balcony") else 0
    })
    soup = BeautifulSoup(response.text, 'html.parser')

    listings = []

    for listing in soup.find_all("div", class_="offer_list_item"):
        # Title and link
        title_element = listing.find("h3", class_="truncate_title")
        title = title_element.text.strip() if title_element else "No title"
        link_element = title_element.find("a", href=True) if title_element else None
        relative_link = link_element["href"] if link_element else None
        link = BASE_URL + relative_link if relative_link else None

        # Price
        price_element = listing.find("div", class_="col-xs-3")
        price_text = price_element.text.strip() if price_element else "0"
        price = int(''.join(filter(str.isdigit, price_text)))

        # Room size
        room_size_element = listing.find("div", class_="col-xs-3 text-right")
        room_size_text = room_size_element.text.strip() if room_size_element else "0"
        room_size_match = re.search(r'\d+', room_size_text)
        room_size = int(room_size_match.group()) if room_size_match else 0

        # Room count, city area, and street
        location_element = listing.find("div", class_="col-xs-11")
        location_text = location_element.text.replace("\n", " ").strip() if location_element else ""
        location_text = re.sub(r'\s+', ' ', location_text)  # Remove excessive whitespace
        room_count_match = re.search(r'(\d+)-Zimmer', location_text)
        room_count = int(room_count_match.group(1)) if room_count_match else None

        # Split location text on '|'
        location_parts = [part.strip() for part in location_text.split('|') if part.strip()]
        city_area = location_parts[1] if len(location_parts) > 1 else "Unknown"
        street = location_parts[2] if len(location_parts) > 2 else "Unknown"

        # Availability dates
        availability_dates = listing.find("div", class_="col-xs-5 text-center").text.strip() if listing.find("div", class_="col-xs-5 text-center") else ""
        start_date_text, end_date_text = availability_dates.split(" - ") if " - " in availability_dates else (availability_dates, None)
        start_date_text = start_date_text.replace("\n", " ").strip() if start_date_text else None
        end_date_text = end_date_text.replace("\n", " ").strip() if end_date_text else None
        start_date = parse_date(start_date_text)
        end_date = parse_date(end_date_text)
        stay_length = calculate_stay_length(start_date, end_date)

        # Furnished check
        furnished = "möbliert" in listing.text.lower()

        # Ad person name
        ad_person_element = listing.find("span", class_="ml5")
        ad_person = ad_person_element.text.strip() if ad_person_element else "Unknown"

        listings.append({
            "title": title,
            "link": link,
            "price": price,
            "room_size": room_size,
            "room_count": room_count,
            "city_area": city_area,
            "street": street,
            "availability_start": start_date_text,
            "availability_end": end_date_text,
            "stay_length_days": stay_length,
            "furnished": furnished,
            "ad_person": ad_person
        })

    return listings

def handler(inputs):
    username = os.getenv("WG_USERNAME")
    password = os.getenv("WG_PASSWORD")

    if not username or not password:
        raise ValueError("WG_USERNAME and WG_PASSWORD must be set as environment variables.")

    session, _ = login_wg_gesucht(username, password)
    filters = inputs.get("filter", {})
    listings = search_listings(session, filters)

    return {"listings": {"data": listings}}

if __name__ == "__main__":
    inputs = {
        "filter": {
            "sMin": 30,
            "rMax": 1000,
            "furnished": True,
            "balcony": True
        }
    }
    
    results = handler(inputs)
    with open("listings.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    print("Listings saved to listings.json")
