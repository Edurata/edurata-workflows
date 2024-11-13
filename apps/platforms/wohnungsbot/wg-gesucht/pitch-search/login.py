import requests
import os
import logging
import random

# WG-Gesucht URLs
BASE_URL = "https://www.wg-gesucht.de/"
LOGIN_URL = "https://www.wg-gesucht.de/ajax/sessions.php?action=login"

# Different User-Agent strings to simulate various browsers
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:98.0) Gecko/20100101 Firefox/98.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
]

# Different Accept-Language values to simulate various regional settings
ACCEPT_LANGUAGES = [
    "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "en-US,en;q=0.9,de;q=0.8,fr;q=0.7",
    "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "en-GB,en;q=0.9,en-US;q=0.8,de;q=0.7",
]

def get_random_headers():
    """Generate randomized headers to simulate different browser sessions."""
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": random.choice(["gzip, deflate, br", "gzip, deflate"]),
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "Origin": "https://www.wg-gesucht.de",
        "Pragma": "no-cache",
        "Referer": "https://www.wg-gesucht.de/",
        "User-Agent": random.choice(USER_AGENTS),
        "X-Client-Id": "wg_desktop_website",
        "X-Requested-With": "XMLHttpRequest",
        "X-Smp-Client": "WG-Gesucht"
    }
    return headers

def login_wg_gesucht(username, password):
    logging.info("Starting login process...")

    # Start a session to manage cookies and maintain state
    session = requests.Session()
    
    # Load the main page to set any required cookies
    logging.debug("Accessing base URL to initialize session cookies.")
    session.get(BASE_URL)
    
    # Generate randomized headers for each login attempt
    headers = get_random_headers()

    # Prepare login data as JSON
    login_data = {
        "login_email_username": username,
        "login_password": password,
        "login_form_auto_login": "1",
        "display_language": "de"
    }

    # Submit the login request with randomized headers
    try:
        logging.debug("Submitting login request with randomized headers.")
        response = session.post(LOGIN_URL, headers=headers, json=login_data)
        
        # Parse the response for tokens
        if response.status_code == 200:
            response_data = response.json()
            access_token = response_data.get("access_token")
            csrf_token = response_data.get("csrf_token")
            
            # Log tokens retrieved
            logging.debug(f"Access token: {access_token}")
            logging.debug(f"CSRF token: {csrf_token}")

            # Store tokens in headers for authenticated requests
            session.headers.update({
                "Authorization": f"Bearer {access_token}",
                "X-CSRF-Token": csrf_token  # Set CSRF token in session headers
            })
            
            logging.info("Login successful and tokens stored in session.")
            return session, csrf_token  # Return the session and CSRF token
        else:
            logging.error(f"Login failed with status code {response.status_code}")
            logging.debug(f"Response content: {response.json()}")
            raise Exception("Failed to reach the login endpoint.")
    except Exception as e:
        logging.error(f"Error during login: {e}")
        raise

# Usage example
if __name__ == "__main__":
    username = os.getenv("WG_USERNAME")
    password = os.getenv("WG_PASSWORD")

    if username and password:
        try:
            session, tokens = login_wg_gesucht(username, password)
            logging.info("Tokens received and session ready for use.")
        except Exception as e:
            logging.error(f"Error: {e}")
    else:
        logging.error("WG_USERNAME and WG_PASSWORD environment variables are required.")
