import os
import requests
from bs4 import BeautifulSoup
import json
import time
import random
from login import login_wg_gesucht  # Assuming you already have a login function
from urllib.parse import urlparse, parse_qs

def extract_ad_details(session, listing_url, debug_file="response.html"):
    """
    Extracts the ad ID and ad type from multiple possible locations in the WG-Gesucht HTML.

    Args:
        session (requests.Session): Authenticated session object.
        listing_url (str): URL of the WG-Gesucht listing.
        debug_file (str): Path to save the HTML response for debugging.

    Returns:
        tuple: A tuple containing the ad ID and ad type.
    """
    try:
        # Fetch the listing page
        response = session.get(listing_url)
        response.raise_for_status()  # Raise an error for HTTP issues

        # Save the raw HTML response to a file for debugging
        with open(debug_file, "w", encoding="utf-8") as file:
            file.write(response.text)

        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')

        # Primary method: extract from the "Anzeige beanstanden" link
        report_link = soup.find('a', href=True, title="Anzeige beanstanden")
        if report_link:
            href = report_link['href']
            query_params = parse_qs(urlparse(href).query)
            ad_id = query_params.get('id', [None])[0]
            ad_type = query_params.get('ad_type', [None])[0]
            if ad_id and ad_type:
                return ad_id, ad_type

        # Fallback 1: extract from hidden input fields
        ad_id_input = soup.find('input', id='ad_id')
        ad_type_input = soup.find('input', id='ad_type')
        if ad_id_input and ad_type_input:
            ad_id = ad_id_input.get('value')
            ad_type = ad_type_input.get('value')
            if ad_id and ad_type:
                return ad_id, ad_type

        # Fallback 2: extract from the favorites button
        favorite_button = soup.find('a', class_='ad_to_favourites_utilities_mobile')
        if favorite_button:
            ad_id = favorite_button.get('data-ad_id')
            ad_type = favorite_button.get('data-ad_type')
            if ad_id and ad_type:
                return ad_id, ad_type

        # Fallback 3: extract from the favourite_btn_icon class
        favourite_icon = soup.find('i', class_='favourite_btn_icon')
        if favourite_icon:
            ad_id = favourite_icon.get('data-ad_id')
            ad_type = favourite_icon.get('data-ad_type')
            if ad_id and ad_type:
                return ad_id, ad_type

        # Fallback 4: extract from specific hidden inputs
        conversation_ad_id_input = soup.find('input', id='conversation_ad_id')
        conversation_ad_type_input = soup.find('input', id='conversation_ad_type')
        if conversation_ad_id_input and conversation_ad_type_input:
            ad_id = conversation_ad_id_input.get('value')
            ad_type = conversation_ad_type_input.get('value')
            if ad_id and ad_type:
                return ad_id, ad_type

        # If all methods fail
        raise ValueError("Failed to extract ad ID and ad type from the page.")

    except requests.exceptions.RequestException as e:
        print(f"Error fetching the listing page: {e}")
        return None, None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None, None

def send_application_via_http(application_list):
    """Processes the application list by logging into the platform and sending each application."""
    username = os.getenv("WG_USERNAME")
    password = os.getenv("WG_PASSWORD")
    if not username or not password:
        raise ValueError("WG_USERNAME and WG_PASSWORD must be set as environment variables.")
    
    session, csrf_token, user_id = login_wg_gesucht(username, password)

    for application in application_list:
        listing_url = application["listing_url"]
        recipient_name = application["recipient_name"]
        application_text = application["application"]

        # Transform listing URL to the message URL
        message_url = listing_url.replace("wohnungen-in-", "nachricht-senden/wohnungen-in-")
        ad_id, ad_type = extract_ad_details(session, message_url)
        messages = [{"content": application_text, "message_type": "text"}]

        # Construct payload and headers
        payload = {
            "user_id": user_id,
            "csrf_token": csrf_token,
            "messages": messages,
            "ad_type": ad_type,
            "ad_id": ad_id
        }
        headers = {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest"
        }

        # Send the POST request to submit the conversation
        submit_url = "https://www.wg-gesucht.de/ajax/conversations.php?action=conversations"
        response = session.post(submit_url, headers=headers, data=json.dumps(payload))

        if response.status_code == 200:
            print(f"Message sent successfully to {recipient_name} at {message_url}")
        else:
            print(f"Failed to send message to {recipient_name} at {message_url} with status code {response.status_code}")
            print("Response:", response.text)
            if response.status_code == 400 and "detail" in response.json() and ("Conversation already" in response.json()["detail"] or "Restricted request" in response.json()["detail"]):
                print("Skipping this application as the conversation already exists or restricted request.")
            else:
                raise Exception("Failed to send message")

        # Random delay between requests
        delay = random.uniform(2, 10)  # Random delay between 2 and 5 seconds
        print(f"Waiting for {delay:.2f} seconds before the next application...")
        time.sleep(delay)

def handler(inputs):
    """Handler function to facilitate the structured interface for the send_application_via_http function."""
    application_list = inputs.get("application_list")
    if not application_list:
        raise ValueError("application_list is required in inputs.")
    
    # Call the main function with the provided application list
    send_application_via_http(application_list)
    
    return {"status": "Applications sent successfully"}

# Sample function call (uncomment to use)
# handler({
#     "application_list": [
#         {"listing_url": "https://www.wg-gesucht.de/wg-zimmer-in-Berlin-Friedrichshain.10790722.html", 
#          "application": "Hallo Sandro! 🌟\n\nIch bin Surya und habe deine Anzeige für das Zimmer gesehen. Deine Leidenschaft für Techno, Filme und gutes Essen spricht mich total an! 🎶🍿🍲\n\nAls Masterstudent bei OVGU Magdeburg und derzeit Praktikant bei DB in Berlin, plane ich für meine Masterarbeit im Dezember nach Berlin zu ziehen. Deine Wohnung klingt perfekt für mich, da ich gerne eine nette und aufgeschlossene Mitbewohnerin hätte, mit der man Zeit verbringen, zusammen kochen und Filme schauen kann.\n\nIch bin 26 Jahre alt, spiele in meiner Freizeit gerne Klavier, koche regelmäßig indisches vegetarisches Essen und verbringe gerne Zeit mit anderen. Sauberkeit ist mir wichtig und ich bin auch sportbegeistert. Ich würde mich freuen, dich persönlich kennenzulernen und mehr über das Zimmer zu erfahren.\n\nMeine Telefonnummer lautet: 015906104976. Ich würde mich freuen, von dir zu hören! 🌟\n\nViele Grüße und bis bald! 🌼✨🎬", 
#          "recipient_name": "Albian Mustafa"},
#     ]
# })

