import requests
import os

# Freelance.de URLs
BASE_URL = "https://www.freelance.de/"
LOGIN_URL = "https://www.freelance.de/login.php"

def login_freelance_de(username, password):
    """Logs into freelance.de and returns an authenticated session."""
    # Start a session to manage cookies and maintain state
    session = requests.Session()
    
    # Load the main page to set any required cookies
    session.get(BASE_URL)
    
    # Set up headers, mimicking a browser's request
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://www.freelance.de",
        "Referer": "https://www.freelance.de/login.php",
        "Sec-Ch-Ua": "\"Chromium\";v=\"122\", \"Not(A:Brand\";v=\"24\", \"Google Chrome\";v=\"122\"",
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": "\"Windows\"",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }
    
    # Prepare login data
    login_data = {
        "action": "login",
        "username": username,
        "password": password,
        "seal": "",  # Include the seal if required; scrape it dynamically if necessary
        "fromPage": "",
        "service": "",
        "redirect_url": "",
        "r": "1zXjglIVLLbLaivaTsyhY4YIKReXEj7BU2_IEXYyPPCSio-zjob4zfGz4DUJPAMdXk7FiX_IcgvYDSHtfjiHS6Sc3207HUMMouZOmJUKEBLKOFg1vRt46zJgE49O_Ig3TCeLvOTSz2NBhLrgmhxn1HMjTSaOrBYU0ENPZ1YF7LL9XljFXUo",
        "remember": "",
        "login": "Anmelden",
    }

    # Submit the login request
    try:
        response = session.post(LOGIN_URL, headers=headers, data=login_data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error during login: {e}")
        return None

    # Check for successful login
    if "Kontaktdaten anzeigen" in response.text or "logout" in response.text:
        print("Login successful!")
        return session
    else:
        print("Login failed. Please check your credentials.")
        return None

# Usage example
if __name__ == "__main__":
    username = os.getenv("FREELANCE_DE_USERNAME")
    password = os.getenv("FREELANCE_DE_PASSWORD")

    if username and password:
        session = login_freelance_de(username, password)
        if session:
            print("Session established. You can now use this session for authenticated requests.")
        else:
            print("Login failed.")
    else:
        print("FREELANCE_DE_USERNAME and FREELANCE_DE_PASSWORD environment variables are required.")
