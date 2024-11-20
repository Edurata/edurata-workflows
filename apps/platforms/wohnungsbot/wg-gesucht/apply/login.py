import requests
import os

# WG-Gesucht URLs
BASE_URL = "https://www.wg-gesucht.de/"
LOGIN_URL = "https://www.wg-gesucht.de/ajax/sessions.php?action=login"

def login_wg_gesucht(username, password):
    # Start a session to manage cookies and maintain state
    session = requests.Session()
    
    # Load the main page to set any required cookies
    session.get(BASE_URL)
    
    # Set up headers, excluding HTTP/2 pseudo-headers
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "Origin": BASE_URL,
        "Referer": BASE_URL,
        "Sec-Ch-Ua": "\"Chromium\";v=\"122\", \"Not(A:Brand\";v=\"24\", \"Google Chrome\";v=\"122\"",
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": "\"Windows\"",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "X-Authorization": "Bearer",
        "X-Client-Id": "wg_desktop_website",
        "X-Requested-With": "XMLHttpRequest",
        "X-Smp-Client": "WG-Gesucht"
    }
    
    # Prepare login data as JSON
    login_data = {
        "login_email_username": username,
        "login_password": password,
        "login_form_auto_login": "1",
        "display_language": "de"
    }

    # Submit the login request
    response = session.post(LOGIN_URL, headers=headers, json=login_data)
    
    # Parse the response for tokens
    if response.status_code == 200:
        print(response.json())
        response_data = response.json()
        access_token = response_data.get("access_token")
        csrf_token = response_data.get("csrf_token")
        user_id = response_data.get("user_id")  # Adjust key based on actual response

        # Store tokens in headers for authenticated requests
        session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "X-CSRF-Token": csrf_token  # if required for future requests
        })
        
        print("Login successful!")
        return session, csrf_token, user_id
    else:
        print("Request failed with status:", response.status_code)
        try:
            print("Response detail:", response.json())
        except Exception:
            print("Failed to parse error response.")
        raise Exception("Failed to log in to WG-Gesucht.")

# Usage example
if __name__ == "__main__":
    username = os.getenv("WG_USERNAME")
    password = os.getenv("WG_PASSWORD")

    if username and password:
        try:
            session, csrf_token, user_id = login_wg_gesucht(username, password)
            print("CSRF Token:", csrf_token)
            print("User ID:", user_id)
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("WG_USERNAME and WG_PASSWORD environment variables are required.")
