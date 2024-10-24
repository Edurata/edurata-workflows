import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

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
    username = os.getenv("FREELANCERMAP_USERNAME")
    password = os.getenv("FREELANCERMAP_PASSWORD")

    if not username or not password:
        raise ValueError("Environment variables FREELANCEMAP_USERNAME or FREELANCEMAP_PASSWORD not set.")

    login_url = "https://www.freelancermap.com/login"
    session = requests.Session()

    payload = {
        "login": username,
        "password": password,
        '_remember_me': '0',
    }

    response = session.post(login_url, data=payload, headers=headers)
    if response.status_code != 200:
        raise Exception("Login failed. Please check your credentials.")

    return session

def extract_full_message(session, message_url):
    """Visits a full message page and extracts the content."""
    response = session.get(message_url, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to access message: {message_url}")

    soup = BeautifulSoup(response.text, "html.parser")
    message_content = soup.get_text(separator=' ', strip=True)
    return message_content

def extract_job_descriptions(session):
    """Extracts job descriptions and visits full messages for more details."""
    inbox_url = "https://www.freelancermap.com/app/pobox/main"
    response = session.get(inbox_url, headers=headers)
    if response.status_code != 200:
        raise Exception("Failed to access the inbox.")

    soup = BeautifulSoup(response.text, "html.parser")
    job_elements = soup.find_all("div", class_="subject d-flex table-layout-only")

    jobs = []
    for element in job_elements:
        job_title = element.find("a", class_="text-truncate").get_text(strip=True)
        message_url = element.find("a", class_="text-truncate")["href"]
        full_url = f"https://www.freelancermap.com{message_url}"

        full_content = extract_full_message(session, full_url)

        date_element = element.find_next("span", class_="date")
        date_posted = datetime.strptime(date_element.get_text(strip=True), "%d.%m.%Y, %H:%M")

        jobs.append({
            "title": job_title,
            "content": full_content,
            "date": date_posted,
        })

    return jobs

def filter_jobs(jobs, positive_keywords, negative_keywords, min_date):
    """Filters jobs based on positive/negative keywords and date."""
    matching_jobs = []
    for job in jobs:
        job_text = f"{job['title']} {job['content']}"
        if any(keyword.lower() in job_text.lower() for keyword in positive_keywords) and \
           not any(keyword.lower() in job_text.lower() for keyword in negative_keywords) and \
           job["date"] >= min_date:
            matching_jobs.append(job)
    return matching_jobs

def handler(inputs):
    """Main handler function."""
    positive_keywords = inputs.get("positive_keywords", [])
    negative_keywords = inputs.get("negative_keywords", [])

    # Default to today's date if no min_date is provided
    min_date_str = inputs.get("min_date")
    min_date = datetime.strptime(min_date_str, "%d.%m.%Y") if min_date_str else datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)

    session = login_to_freelancermap()

    jobs = extract_job_descriptions(session)

    matching_jobs = filter_jobs(jobs, positive_keywords, negative_keywords, min_date)

    return {
        "matching_jobs": matching_jobs
    }

# Sample call to the handler function (for testing)
inputs = {
    "positive_keywords": ["Python", "Remote"],
    "negative_keywords": ["Java", "On-site"]
    # No min_date specified, so it defaults to today's date
}
print(handler(inputs))
