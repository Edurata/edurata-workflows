import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:85.0) Gecko/20100101 Firefox/85.0',
    'Referer': 'https://www.freelancermap.com/login',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

def login_to_freelancermap():
    """Logs into Freelancermap and returns a session object."""
    print("Starting login process...")
    username = os.getenv("FREELANCERMAP_USERNAME")
    password = os.getenv("FREELANCERMAP_PASSWORD")

    if not username or not password:
        raise ValueError("Environment variables FREELANCERMAP_USERNAME or FREELANCERMAP_PASSWORD not set.")

    login_url = "https://www.freelancermap.com/login"
    session = requests.Session()

    payload = {
        "login": username,
        "password": password,
        '_remember_me': '0',
    }

    response = session.post(login_url, data=payload, headers=headers)
    print(f"Login response status: {response.status_code}")
    if response.status_code != 200:
        raise Exception("Login failed. Please check your credentials.")

    print("Login successful!")
    return session

def extract_full_message(session, message_url):
    """Visits a full message page and extracts the content."""
    print(f"Extracting message from URL: {message_url}")
    response = session.get(message_url, headers=headers)
    print(f"Message page response status: {response.status_code}")
    if response.status_code != 200:
        raise Exception(f"Failed to access message: {message_url}")

    soup = BeautifulSoup(response.text, "html.parser")
    message_content = soup.get_text(separator=' ', strip=True)
    print(f"Extracted message content: {message_content[:100]}...")  # Display first 100 chars for brevity
    return message_content

def extract_job_descriptions(session):
    """Extracts job descriptions and visits full messages for more details."""
    inbox_url = "https://www.freelancermap.com/app/pobox/main"
    print(f"Accessing inbox at: {inbox_url}")
    response = session.get(inbox_url, headers=headers)
    print(f"Inbox response status: {response.status_code}")
    if response.status_code != 200:
        raise Exception("Failed to access the inbox.")

    soup = BeautifulSoup(response.text, "html.parser")
    job_elements = soup.find_all("div", class_="subject d-flex table-layout-only")
    print(f"Found {len(job_elements)} job elements")

    jobs = []
    for element in job_elements:
        job_title = element.find("a", class_="text-truncate").get_text(strip=True)
        message_url = element.find("a", class_="text-truncate")["href"]
        full_url = f"https://www.freelancermap.com{message_url}"

        print(f"Processing job: {job_title}")
        full_content = extract_full_message(session, full_url)

        date_element = element.find_next("span", class_="date")
        date_posted = datetime.strptime(date_element.get_text(strip=True), "%d.%m.%Y, %H:%M")
        print(f"Job posted on: {date_posted}")

        jobs.append({
            "title": job_title,
            "content": full_content,
            "date": date_posted,
        })

    print("Completed job extraction")
    return jobs

def filter_jobs(jobs, positive_keywords, negative_keywords, max_elapsed_days):
    """Filters jobs based on comma-separated positive/negative keywords and elapsed days since posting."""
    print("Starting job filtering...")
    # Convert keyword lists to lowercase for case-insensitive matching
    positive_keywords = positive_keywords.lower().split(",") if isinstance(positive_keywords, str) else []
    negative_keywords = negative_keywords.lower().split(",") if isinstance(negative_keywords, str) else []
    
    today = datetime.today()
    matching_jobs = []
    for job in jobs:
        job_text = f"{job['title']} {job['content']}".lower()
        days_elapsed = (today - job["date"]).days
        print(f"Evaluating job '{job['title']}' posted {days_elapsed} days ago")

        # Check if any positive keyword is present and no negative keyword is present
        if any(keyword.strip() in job_text for keyword in positive_keywords) and \
           not any(keyword.strip() in job_text for keyword in negative_keywords) and \
           days_elapsed <= max_elapsed_days:
            print(f"Job '{job['title']}' matches criteria")
            matching_jobs.append(job)
        else:
            print(f"Job '{job['title']}' does not match criteria")

    print(f"Filtering complete, {len(matching_jobs)} jobs matched")
    return matching_jobs

def handler(inputs):
    """Main handler function."""
    try:
        print("Handler started with inputs:", inputs)
        positive_keywords = inputs.get("positive_keywords", [])
        negative_keywords = inputs.get("negative_keywords", [])
        max_elapsed_days = inputs.get("max_elapsed_days", 30)  # Default to 30 days if not provided

        session = login_to_freelancermap()

        jobs = extract_job_descriptions(session)

        matching_jobs = filter_jobs(jobs, positive_keywords, negative_keywords, max_elapsed_days)

        print("Handler finished, returning matching jobs", len(matching_jobs))
        print("Sample job:", matching_jobs[0] if matching_jobs else None)
        # print mb size of the whole job list
        print(f"Total size of jobs: {round(sum(len(job['content']) for job in jobs) / 1024, 2)} KB")

        return {
            "matching_jobs": matching_jobs
        }
    except Exception as e:
        print(f"An error occurred: {e}")
        return {
            "error": str(e)
        }

# Sample call to the handler function (for testing)
# inputs = {
#     "positive_keywords": "Python, Remote",
#     "negative_keywords": "Senior, Manager",
#     "max_elapsed_days": 15  # Only jobs posted within the last 15 days
# }
# print(handler(inputs))
