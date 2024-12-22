import requests
import os
import re
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')

# Constants for Strava API
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
TOKEN_URL = "https://www.strava.com/oauth/token"
ACTIVITIES_URL = "https://www.strava.com/api/v3/activities"
HTML_FILE_PATH = "templates/action-journal.html"


def refresh_access_token():
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
        )
        response.raise_for_status()
        return response.json().get("access_token")
    except Exception as e:
        logging.error(f"Error refreshing access token: {e}")
        return None


def fetch_activities(access_token):
    """Fetch recent activities from Strava."""
    try:
        response = requests.get(ACTIVITIES_URL, headers={"Authorization": f"Bearer {access_token}"})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Error fetching activities: {e}")
        return []


def append_workouts_to_html(workouts):
    """Append new workouts to the HTML file."""
    try:
        with open(HTML_FILE_PATH, "r+") as file:
            content = file.read()

            # Check existing workout IDs
            existing_ids = set(re.findall(r'data-id="(\d+)"', content))
            new_workouts = [
                w for w in workouts if str(w["id"]) not in existing_ids
            ]

            # Generate new workout cards
            workout_cards = ""
            for workout in new_workouts:
                workout_cards += f'''
                <div class="card" data-id="{workout["id"]}">
                    <h2>{workout["name"]}</h2>
                    <p>Date: {datetime.strptime(workout["start_date"], "%Y-%m-%dT%H:%M:%SZ").strftime("%B %d, %Y")}</p>
                    <p>Distance (miles): {workout["distance"] / 1609.34:.2f}</p>
                    <p>Elevation Gain (feet): {workout["total_elevation_gain"] * 3.28084:.0f}</p>
                    <p>Moving Time: {workout["moving_time"] // 60}:{workout["moving_time"] % 60:02}</p>
                    <p>Avg HR: {workout.get("average_heartrate", "N/A")}</p>
                    <p>Max HR: {workout.get("max_heartrate", "N/A")}</p>
                    <a href="https://www.strava.com/activities/{workout['id']}" target="_blank">View on Strava</a>
                </div>
                '''

            # Append new cards before closing </main> tag
            updated_content = content.replace("</main>", workout_cards + "</main>")
            file.seek(0)
            file.write(updated_content)
            file.truncate()

            logging.info(f"Added {len(new_workouts)} new workouts.")
    except Exception as e:
        logging.error(f"Error updating HTML file: {e}")


def main():
    access_token = refresh_access_token()
    if not access_token:
        return

    activities = fetch_activities(access_token)
    if activities:
        append_workouts_to_html(activities)


if __name__ == "__main__":
    main()
