import re
import requests
from bs4 import BeautifulSoup
import os
import time
import logging
from datetime import datetime, timedelta
from login import login_wg_gesucht, get_random_headers  # Import the get_random_headers function

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")

def build_base_url(city_id):
    url = f"https://www.wg-gesucht.de/wohnungen-in-Berlin-gesucht.{city_id}.2.1.0.html"
    logging.info(f"Built base URL: {url}")
    return url

def check_for_captcha(soup):
    """Check if the page contains a CAPTCHA element, indicating that user intervention is required."""
    if soup.find(class_="g-recaptcha"):
        logging.error("CAPTCHA detected. Manual intervention required.")
        raise Exception("CAPTCHA detected. Manual intervention required.")

def parse_online_duration(noprint_text):
    """Parse the online duration from the 'noprint' text and convert it to hours."""
    logging.debug(f"Parsing online duration from text: {noprint_text}")
    date_match = re.search(r"(\d{2}\.\d{2}\.\d{4})", noprint_text)
    if date_match:
        post_date = datetime.strptime(date_match.group(1), "%d.%m.%Y")
        duration = datetime.now() - post_date
        logging.info(f"Parsed online duration: {duration}")
        return duration

    if "Tag" in noprint_text:
        days = int(re.search(r"(\d+)", noprint_text).group(1)) if re.search(r"(\d+)", noprint_text) else 1
        duration = timedelta(days=days)
        logging.info(f"Online duration in days converted to hours: {duration}")
        return duration
    elif "Stunde" in noprint_text:
        hours = int(re.search(r"(\d+)", noprint_text).group(1)) if re.search(r"(\d+)", noprint_text) else 1
        duration = timedelta(hours=hours)
        logging.info(f"Online duration in hours: {duration}")
        return duration

    logging.warning("Could not parse online duration; defaulting to 0 hours.")
    return timedelta(hours=0)

def search_people(session, city_id, csrf_token, max_online_hours=None):
    base_url = build_base_url(city_id)

    # Define request parameters with the CSRF token
    params = {
        "csrf_token": csrf_token,
        "city_id": city_id,
        "sort_column": 0,
        "sort_order": 0,
        "noDeact": 1,
        "categories[]": 2,
        "exContAds": 1
    }

    try:
        logging.info("Starting people search...")
        # Use randomized headers for this request
        response = session.get(base_url, params=params, headers=get_random_headers())
        response.raise_for_status()

        # Parse the response and check for CAPTCHA
        soup = BeautifulSoup(response.text, 'html.parser')
        # check_for_captcha(soup)

    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching people listings: {e}")
        return []

    people_listings = []
    max_online_delta = timedelta(hours=max_online_hours) if max_online_hours is not None else None

    for person in soup.find_all("div", class_="wgg_card request_list_item"):
        denied_image = person.find("img", {"class": "overlay placeholder_denied_female"})
        if denied_image:
            logging.info("Skipping denied listing.")
            continue

        # Extract name and age
        name_age_element = person.find("div", class_="col-sm-12 flex_space_between", style="min-height: 18px;").find("span")
        name_age_text = name_age_element.text.strip() if name_age_element else "Unknown"
        name, age = None, None
        if ", " in name_age_text:
            name, age = name_age_text.split(", ")
            age = int(age)
            logging.debug(f"Extracted name and age: {name}, {age}")

        # Extract and filter by online duration if applicable
        online_duration_element = person.find("span", style=lambda value: value and "#218700" in value)
        online_duration = parse_online_duration(online_duration_element.text.strip()) if online_duration_element else timedelta(hours=float('inf'))
        if max_online_delta and online_duration > max_online_delta:
            logging.info("Listing filtered out by max online hours.")
            continue

        # Extract title and link
        title_element = person.find("h3", class_="truncate_title")
        title = title_element.text.strip() if title_element else "No title"
        link_element = title_element.find("a", href=True) if title_element else None
        relative_link = link_element["href"] if link_element else None
        link = "https://www.wg-gesucht.de/" + relative_link if relative_link else None

        # Retrieve and add description
        description = fetch_person_description(session, link) if link else "Description unavailable."
        people_listings.append({
            "title": title,
            "link": link,
            "name": name,
            "age": age,
            "online_duration": str(online_duration),
            "description": description
        })
        logging.info(f"Added listing: {title}")

    logging.info(f"Total listings found: {len(people_listings)}")
    return people_listings

def fetch_person_description(session, link):
    """Fetches the description of a specific listing."""
    try:
        logging.debug(f"Fetching description from: {link}")
        # Use randomized headers for this request
        response = session.get(link, headers=get_random_headers())
        response.raise_for_status()

        # Parse response and check for CAPTCHA
        soup = BeautifulSoup(response.text, 'html.parser')
        # check_for_captcha(soup)

        description_tag = soup.find("div", {"id": "freetext_description"})
        if description_tag:
            description_text = description_tag.find("p", {"class": "freitext"}).get_text(separator="\n").strip()
            logging.debug("Description fetched successfully.")
            return description_text
        else:
            logging.warning("Description not found.")
            return "Description unavailable."
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching description: {e}")
        return "Description unavailable."
    except Exception as e:
        logging.error(f"CAPTCHA encountered when fetching description: {e}")
        return "CAPTCHA encountered, description unavailable."

def handler(inputs):
    username = os.getenv("WG_USERNAME")
    password = os.getenv("WG_PASSWORD")
    if not username or not password:
        logging.error("WG_USERNAME and WG_PASSWORD must be set as environment variables.")
        raise ValueError("WG_USERNAME and WG_PASSWORD must be set as environment variables.")
    
    logging.info("Logging in with provided credentials...")
    session, csrf_token = login_wg_gesucht(username, password)

    city_id = inputs.get("city_id")
    max_online_hours = inputs.get("max_online_hours")
    if not city_id:
        logging.error("city_id must be specified.")
        raise ValueError("city_id must be specified.")
    
    # Pass the CSRF token directly to the search function
    people = search_people(session, city_id, csrf_token, max_online_hours)

    return {"people_listings": people}

# Sample usage:
# inputs = {"city_id": 8, "max_online_hours": 2}
# results = handler(inputs)
# print(results)
