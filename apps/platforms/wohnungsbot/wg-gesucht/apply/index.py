import os
import requests
from bs4 import BeautifulSoup
import json
import time
import random
from login import login_wg_gesucht  # Assuming you already have a login function

def fetch_csrf_token_and_data(session, message_url, application_text):
    """Fetches the CSRF token, user ID, ad ID, ad type, and constructs the messages array from the HTML page."""
    response = session.get(message_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    csrf_token = soup.find("input", {"name": "csrf_token"})
    user_id = soup.find("input", {"name": "user_id"})
    ad_id = soup.find("input", {"name": "ad_id"})
    ad_type = soup.find("input", {"name": "ad_type"})
    
    # Extract values, with a fallback if elements are missing
    csrf_token_value = csrf_token["value"] if csrf_token else None
    user_id_value = user_id["value"] if user_id else None
    ad_id_value = ad_id["value"] if ad_id else None
    ad_type_value = ad_type["value"] if ad_type else None
    
    # Build the messages array similar to JavaScript
    messages = [{"content": application_text, "message_type": "text"}]

    # Ensure all required values were found
    if not csrf_token_value or not user_id_value or not ad_id_value or not ad_type_value:
        print("Failed to retrieve one or more required values: CSRF token, user ID, ad ID, or ad type.")
    
    return csrf_token_value, user_id_value, ad_id_value, ad_type_value, messages

def send_application_via_http(application_list):
    """Processes the application list by logging into the platform and sending each application."""
    username = os.getenv("WG_USERNAME")
    password = os.getenv("WG_PASSWORD")
    if not username or not password:
        raise ValueError("WG_USERNAME and WG_PASSWORD must be set as environment variables.")
    
    session, _ = login_wg_gesucht(username, password)

    for application in application_list:
        listing_url = application["listing_url"]
        recipient_name = application["recipient_name"]
        application_text = application["application"]

        # Transform listing URL to the message URL
        message_url = listing_url.replace("wohnungen-in-", "nachricht-senden/wohnungen-in-")
        csrf_token, user_id, ad_id, ad_type, messages = fetch_csrf_token_and_data(session, message_url, application_text)

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

        # Random delay between requests
        delay = random.uniform(2, 5)  # Random delay between 2 and 5 seconds
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
handler({
    "application_list": [
        {"listing_url": "https://www.wg-gesucht.de/wohnungen-in-Berlin.8.2.1.0.html?asset_id=11219738&pu=22446810&sort_column=1&sort_order=0", 
         "application": "Hello, I'm interested in renting your flat.", 
         "recipient_name": "Albian Mustafa"},
    ]
})
