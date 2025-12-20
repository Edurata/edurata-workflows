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
        "Origin": "https://www.wg-gesucht.de",
        "Pragma": "no-cache",
        "Referer": "https://www.wg-gesucht.de/",
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
    # Accept both 200 (OK) and 202 (Accepted) as successful login responses
    if response.status_code in [200, 202]:
        response_data = response.json()
        
        # Handle different response structures
        # Standard response (200): access_token, refresh_token, csrf_token at root
        # Alternative response (202): token in detail.token
        access_token = response_data.get("access_token")
        if not access_token and "detail" in response_data:
            access_token = response_data["detail"].get("token")
        
        refresh_token = response_data.get("refresh_token")
        csrf_token = response_data.get("csrf_token")
        
        # Store tokens in headers for authenticated requests
        if access_token:
            session.headers.update({
                "Authorization": f"Bearer {access_token}",
            })
        if csrf_token:
            session.headers.update({
                "X-CSRF-Token": csrf_token  # if future requests require it
            })
        
        print("Login successful!")
        return session, response_data  # Return the session and token data if login was successful
    else:
        print("Request failed with status:", response.status_code)
        try:
            print("Response detail:", response.json())
        except:
            print("Response text:", response.text)
        raise Exception("Failed to reach the login endpoint.")

# Usage example
if __name__ == "__main__":
    username = os.getenv("WG_USERNAME")
    password = os.getenv("WG_PASSWORD")

    if username and password:
        try:
            session, tokens = login_wg_gesucht(username, password)
            print("Tokens received:", tokens)
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("WG_USERNAME and WG_PASSWORD environment variables are required.")
