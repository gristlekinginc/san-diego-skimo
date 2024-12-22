import requests
import os
import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')

# Constants for Strava API
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
TOKEN_URL = "https://www.strava.com/oauth/token"
ACTIVITIES_URL = "https://www.strava.com/api/v3/activities"

SAN_DIEGO_BOUNDS = {
    "lat_min": 32.5343,
    "lat_max": 33.1144,
    "lon_min": -117.292,
    "lon_max": -116.984,
}

HTML_FILE_PATH = "templates/action-journal.html"


def refresh_access_token() -> Optional[str]:
    """Fetch a new access token using the refresh token."""
    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": REFRESH_TOKEN,
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            logging.error("No access_token found in the refresh token response.")
        return token
    except requests.exceptions.RequestException as e:
        logging.error(f"Error refreshing token: {e}")
        return None


def fetch_summary_activities(token: str, per_page: int = 30) -> List[Dict[str, Any]]:
    """Fetch a summary of activities from the Strava API."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(ACTIVITIES_URL, headers=headers, params={"per_page": per_page}, timeout=10)
        response.raise_for_status()
        activities = response.json()
        logging.info(f"Fetched {len(activities)} summary activities.")
        return activities
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching activities: {e}")
        return []


def is_activity_in_san_diego(activity: Dict[str, Any]) -> bool:
    """Check if the activity start location is within San Diego boundaries."""
    start_latlng = activity.get("start_latlng", [None, None])
    lat, lon = start_latlng[0], start_latlng[1]
    return (
        lat is not None
        and lon is not None
        and SAN_DIEGO_BOUNDS["lat_min"] <= lat <= SAN_DIEGO_BOUNDS["lat_max"]
        and SAN_DIEGO_BOUNDS["lon_min"] <= lon <= SAN_DIEGO_BOUNDS["lon_max"]
    )


def filter_rollerski_activities(activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter activities for RollerSki type within San Diego boundaries."""
    filtered = [
        a for a in activities
        if a.get("type") == "RollerSki" and is_activity_in_san_diego(a)
    ]
    logging.info(f"Filtered down to {len(filtered)} RollerSki activities in San Diego.")
    return filtered


def generate_html_snippet(activity: Dict[str, Any]) -> str:
    """Generate an HTML snippet for a given activity."""
    def format_moving_time(total_seconds: int) -> str:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"

    distance_miles = activity["distance"] * 0.000621371
    elevation_feet = activity["total_elevation_gain"] * 3.28084
    activity_url = f"https://www.strava.com/activities/{activity['id']}"
    formatted_date = datetime.strptime(activity["start_date"], "%Y-%m-%dT%H:%M:%SZ").strftime("%B %d, %Y")
    
    return f"""
    <div class="card">
        <h2>{activity.get("name", "Untitled")}</h2>
        <p><strong>Date:</strong> {formatted_date}</p>
        <p><strong>Distance (miles):</strong> {distance_miles:.2f} miles</p>
        <p><strong>Elevation Gain (feet):</strong> {elevation_feet:.0f} ft</p>
        <p><strong>Moving Time:</strong> {format_moving_time(activity["moving_time"])}</p>
        <p><strong>Avg HR:</strong> {activity.get("average_heartrate", "N/A")}</p>
        <p><strong>Max HR:</strong> {activity.get("max_heartrate", "N/A")}</p>
        <a href="{activity_url}" target="_blank" rel="noopener noreferrer">View on Strava</a>
    </div>
    """


def prepend_new_workouts(file_path: str, new_snippets: List[str]) -> None:
    """Prepend new workout snippets to the HTML file."""
    if not new_snippets:
        logging.info("No new snippets to prepend.")
        return

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()

        match = re.search(r"<main id=\"workouts\">(.*?)</main>", content, flags=re.DOTALL)
        if match:
            existing_content = match.group(1)
            updated_section = f"<main id=\"workouts\">\n<section id=\"workout-cards\">\n{''.join(new_snippets)}\n{existing_content}\n</section>\n</main>"
            updated_content = content.replace(match.group(0), updated_section)
        else:
            updated_section = f"<main id=\"workouts\">\n<section id=\"workout-cards\">\n{''.join(new_snippets)}\n</section>\n</main>"
            updated_content = content.replace("</body>", f"{updated_section}\n</body>")

        with open(file_path, "w", encoding="utf-8") as file:
            file.write(updated_content)
        logging.info("Prepended new workouts successfully.")
    except FileNotFoundError:
        logging.error(f"{file_path} not found. Unable to prepend workouts.")


def main():
    token = refresh_access_token()
    if not token:
        logging.error("Failed to refresh access token. Exiting.")
        return

    summary_activities = fetch_summary_activities(token)
    filtered_activities = filter_rollerski_activities(summary_activities)
    new_snippets = [generate_html_snippet(a) for a in filtered_activities]
    prepend_new_workouts(HTML_FILE_PATH, new_snippets)


if __name__ == "__main__":
    main()
