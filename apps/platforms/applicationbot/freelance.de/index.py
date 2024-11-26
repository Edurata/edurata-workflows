import requests
from bs4 import BeautifulSoup
import time
import os

# Freelance.de URLs
BASE_URL = "https://www.freelance.de/"
LOGIN_URL = "https://www.freelance.de/login.php"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:85.0) Gecko/20100101 Firefox/85.0',
    'Referer': 'https://www.freelance.de/',
}

def login_freelance_de(username, password):
    """Logs into freelance.de and returns an authenticated session."""
    # Start a session to manage cookies and maintain state
    session = requests.Session()
    
    # Load the main page to set any required cookies
    session.get(BASE_URL)
    
    # Set up headers, mimicking a browser's request
    login_headers = headers.copy()
    login_headers.update({
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": BASE_URL,
        "Referer": LOGIN_URL,
    })
    
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
        response = session.post(LOGIN_URL, headers=login_headers, data=login_data)
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

def extract_project_info(session, project_url):
    """Extracts project description and contact details from a project page."""
    print(f"Fetching project info from: {project_url}")

    # Fetch the main project page to get the description and IDs
    try:
        response = session.get(project_url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching project page: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract project description
    description_panel = soup.find("div", class_="panel-body highlight-text")
    description = description_panel.get_text(strip=True) if description_panel else "No description available."

    # Locate the button with the `onclick` attribute for project_id and user_id
    button = soup.find("button", onclick=lambda x: x and "count_shown_contactdata_for_project" in x)
    if not button:
        print("Contact button not found.")
        return f"Description:\n{description}\n\nContact Details:\nContact details not available."

    # Extract and parse the `onclick` attribute
    onclick_attr = button["onclick"]
    try:
        args = onclick_attr.split("(")[1].split(")")[0].replace("'", "").split(",")
        project_id = args[0].strip()
        user_id = args[1].strip()
    except (IndexError, ValueError) as e:
        print(f"Error parsing onclick attribute: {onclick_attr} -> {e}")
        return f"Description:\n{description}\n\nContact Details:\nError extracting project_id or user_id."

    if not project_id or not user_id:
        print("Could not extract project_id or user_id.")
        return f"Description:\n{description}\n\nContact Details:\nContact details not available."

    # Simulate the button click to update the page dynamically
    simulate_button_click(session, project_id, user_id)

    # Wait briefly to allow the HTML to update dynamically
    time.sleep(1)  # 1-second delay to allow the changes to take effect

    # Extract the updated contact details
    contact_data_div = soup.find("div", id="contact_data")
    print()
    if contact_data_div:
        # Collect all text content in `contact_data` without tags
        contact_data = " ".join(contact_data_div.stripped_strings)
    else:
        contact_data = "Updated contact details not found."

    print(contact_data)
    # Append description and contact details into a single string
    return f"Description:\n{description}\n\nContact Details:\n{contact_data}"

def simulate_button_click(session, project_id, user_id):
    """Simulates the button click to reveal contact details using a POST request."""
    print(f"Simulating button click for project_id={project_id}, user_id={user_id}")
    ajax_url = "https://www.freelance.de/project/ajax.php"
    
    # Prepare the POST data
    post_data = {
        "action": "count_shown_contactdata_for_project",
        "project_id": project_id,
        "user_id": user_id,
    }
    
    # Custom headers for the AJAX request
    ajax_headers = headers.copy()
    ajax_headers.update({
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://www.freelance.de/Projekte/Projekt-{project_id}",
    })
    
    try:
        # Send the POST request
        response = session.post(ajax_url, data=post_data, headers=ajax_headers)
        response.raise_for_status()

        # Parse the response for contact details
        contact_data = response.text.strip()

    except requests.exceptions.RequestException as e:
        print(f"Error simulating button click: {e}")
        return "Error retrieving contact details."

def visit_project_links_and_extract(session, projects):
    """Visits each project link to extract details."""
    detailed_projects = []
    for project in projects:
        project_info = extract_project_info(session, project["link"])
        if project_info:
            detailed_projects.append(project_info)
    return detailed_projects

def handler(inputs):
    """Main handler function."""
    try:
        # Load credentials from environment variables
        username = os.getenv("FREELANCE_DE_USERNAME")
        password = os.getenv("FREELANCE_DE_PASSWORD")

        if not username or not password:
            raise ValueError("Username and password must be set in environment variables.")

        # Log in to freelance.de
        session = login_freelance_de(username, password)
        if not session:
            raise ValueError("Failed to log in to freelance.de.")

        query_url = inputs.get("query_url")
        if not query_url:
            raise ValueError("Query URL is required.")

        print(f"Fetching projects from: {query_url}")
        response = session.get(query_url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        project_cards = soup.find_all("search-project-card")
        print(f"Found {len(project_cards)} projects on the page.")

        projects = []
        for card in project_cards:
            try:
                link = card.find("a", class_="card")["href"]
                if link.startswith("http"):
                    project_link = link
                else:
                    project_link = f"https://www.freelance.de{link}"
                projects.append({"link": project_link})
            except Exception as e:
                print(f"Error parsing project card: {e}")

        detailed_projects = visit_project_links_and_extract(session, projects)
        return {"projects": detailed_projects}
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"error": str(e)}

# Example Usage
if __name__ == "__main__":
    inputs = {
        "query_url": "https://www.freelance.de/projekte?query=((AWS%20OR%20GCP)%20OR%20KUBERNETES)%20AND%20TERRAFORM%20AND%20CI&sortBy=last_update&lastUpdate=today"
    }
    result = handler(inputs)
    print(result)
