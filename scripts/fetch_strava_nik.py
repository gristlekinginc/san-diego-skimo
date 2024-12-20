import requests
import os
from datetime import datetime

# Strava API setup
CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")
TOKEN_URL = "https://www.strava.com/oauth/token"
ACTIVITIES_URL = "https://www.strava.com/api/v3/activities"

# Refresh access token
def refresh_access_token():
    try:
        response = requests.post(TOKEN_URL, data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN,
            "grant_type": "refresh_token"
        })
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.exceptions.RequestException as e:
        print(f"Error refreshing token: {e}")
        return None

# Fetch activities
def fetch_activities(token):
    try:
        params = {"per_page": 30}  # Adjust as needed
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(ACTIVITIES_URL, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching activities: {e}")
        return []

# Filter rollerski activities within San Diego boundaries
def filter_rollerski_activities(activities):
    san_diego_bounds = {
        "lat_min": 32.5343, "lat_max": 33.1144,
        "lon_min": -117.292, "lon_max": -116.984
    }
    return [
        a for a in activities
        if "RollerSki" in a.get("type", "") and
           san_diego_bounds["lat_min"] <= a["start_latlng"][0] <= san_diego_bounds["lat_max"] and
           san_diego_bounds["lon_min"] <= a["start_latlng"][1] <= san_diego_bounds["lon_max"]
    ]

# Generate HTML snippet
def generate_html_snippet(activity):
    activity_url = f"https://www.strava.com/activities/{activity['id']}"  # Construct URL using the activity ID
    template = f"""
    <div class="workout-card">
        <h2>{activity["name"]}</h2>
        <p><strong>Date:</strong> {datetime.strptime(activity["start_date"], "%Y-%m-%dT%H:%M:%SZ").strftime("%B %d, %Y")}</p>
        <p><strong>Distance:</strong> {activity["distance"] / 1000:.2f} km</p>
        <p><strong>Elevation Gain:</strong> {activity["total_elevation_gain"]} m</p>
        <p><strong>Moving Time:</strong> {activity["moving_time"] // 60} min</p>
        <p><strong>Avg HR:</strong> {activity.get("average_heartrate", "N/A")}</p>
        <p><strong>Max HR:</strong> {activity.get("max_heartrate", "N/A")}</p>
        <p><strong>Description:</strong> {activity.get("description", "No description.")}</p>
        <a href="{activity_url}" target="_blank">View on Strava</a>
    </div>
    """
    return template


# Main function
def main():
    token = refresh_access_token()
    if not token:
        print("Failed to refresh access token. Exiting.")
        return
    
    activities = fetch_activities(token)
    filtered_activities = filter_rollerski_activities(activities)
    snippets = [generate_html_snippet(a) for a in filtered_activities]

    try:
        with open("../templates/action-journal.html", "r+") as file:
            content = file.read()
            file.seek(0)
            file.write("\n".join(snippets) + "\n" + content)
    except FileNotFoundError as e:
        print(f"Error updating action-journal.html: {e}")

if __name__ == "__main__":
    main()
