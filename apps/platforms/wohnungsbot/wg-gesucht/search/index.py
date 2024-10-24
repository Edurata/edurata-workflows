import requests
from bs4 import BeautifulSoup
import os
import json
import pickle

# WG-Gesucht URL
BASE_URL = "https://www.wg-gesucht.de/"

def login_wg_gesucht(username, password):
    session = requests.Session()
    login_url = BASE_URL + "ajax/logon.php"

    response = session.post(login_url, data={
        "login_email_username": username,
        "login_password": password,
    })

    if "Erfolgreich eingeloggt" not in response.text:
        raise Exception("Login failed. Check credentials.")
    
    return session

def search_listings(session, filter):
    city = filter.get("city", "")
    rent_min = filter.get("rent_min", "")
    rent_max = filter.get("rent_max", "")
    room_size_min = filter.get("room_size_min", "")
    room_size_max = filter.get("room_size_max", "")
    available_from = filter.get("available_from", "")
    only_furnished = filter.get("only_furnished", False)

    search_url = f"{BASE_URL}wohnungsmarkt.html?city={city}"
    response = session.get(search_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    listings = []

    for listing in soup.find_all("div", class_="offer_list_item"):
        title_element = listing.find("a", class_="headline")
        title = title_element.text.strip()
        link = BASE_URL + title_element["href"]

        rent_text = listing.find("div", class_="offer_list_item_header").text
        rent = int(''.join(filter(str.isdigit, rent_text)))

        room_size_text = listing.find("span", class_="noprint").text
        room_size = int(''.join(filter(str.isdigit, room_size_text)))

        location = listing.find("div", class_="col-xs-11").text.strip()
        furnished = "möbliert" in listing.text.lower()

        available_element = listing.find("div", class_="col-xs-6")
        available_from_text = available_element.text.strip() if available_element else ""
        available_from_parsed = available_from_text.split(": ")[1] if ": " in available_from_text else ""

        description = listing.find("p", class_="text").text.strip() if listing.find("p", class_="text") else ""

        # Apply filters to the extracted data
        if (not rent_min or rent >= rent_min) and (not rent_max or rent <= rent_max):
            if (not room_size_min or room_size >= room_size_min) and (not room_size_max or room_size <= room_size_max):
                if not available_from or available_from in available_from_parsed:
                    if not only_furnished or furnished:
                        listings.append({
                            "title": title,
                            "link": link,
                            "rent": rent,
                            "room_size": room_size,
                            "available_from": available_from_parsed,
                            "description": description,
                            "furnished": furnished,
                            "location": location,
                        })

    return listings

def handler(inputs):
    username = os.getenv("WG_USERNAME")
    password = os.getenv("WG_PASSWORD")

    if not username or not password:
        raise ValueError("WG_USERNAME and WG_PASSWORD must be set as environment variables.")

    session_file = inputs.get("session_file")
    filter = inputs.get("filter", {})

    if session_file and os.path.exists(session_file):
        with open(session_file, "rb") as f:
            session = requests.Session()
            session.cookies.update(pickle.load(f))
    else:
        session = login_wg_gesucht(username, password)

    listings = search_listings(session, filter)

    return {"listings": {"data": listings}}

# Sample function call
# inputs = {
#     "filter": {
#         "city": "Berlin",
#         "rent_min": 300,
#         "rent_max": 700,
#         "room_size_min": 10,
#         "room_size_max": 30,
#         "available_from": "2024-11-01",
#         "only_furnished": True
#     }
# }
# print(handler(inputs))
