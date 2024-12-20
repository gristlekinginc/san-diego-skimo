import requests
import os
import re
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
        activities = response.json()
        # Debug: Print the first activity's data to inspect fields
        print("First activity data:", activities[0])
        return activities
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
    activity_url = f"https://www.strava.com/activities/{activity['id']}"
    description = activity.get("description", "No description.")  # Safely get the description
    template = f"""
    <div class="workout-card">
        <h2>{activity["name"]}</h2>
        <p><strong>Date:</strong> {datetime.strptime(activity["start_date"], "%Y-%m-%dT%H:%M:%SZ").strftime("%B %d, %Y")}</p>
        <p><strong>Distance:</strong> {activity["distance"] / 1000:.2f} km</p>
        <p><strong>Elevation Gain:</strong> {activity["total_elevation_gain"]} m</p>
        <p><strong>Moving Time:</strong> {activity["moving_time"] // 60} min</p>
        <p><strong>Avg HR:</strong> {activity.get("average_heartrate", "N/A")}</p>
        <p><strong>Max HR:</strong> {activity.get("max_heartrate", "N/A")}</p>
        <p><strong>Description:</strong> {description}</p>
        <a href="{activity_url}" target="_blank">View on Strava</a>
    </div>
    """
    return template

# Extract existing workout IDs
def get_existing_workout_ids(file_path):
    try:
        with open(file_path, "r") as file:
            content = file.read()
            return re.findall(r"https://www.strava.com/activities/(\d+)", content)
    except FileNotFoundError:
        print(f"{file_path} not found. Assuming no existing workouts.")
        return []

# Filter new workouts
def filter_new_workouts(activities, existing_ids):
    return [a for a in activities if str(a["id"]) not in existing_ids]

# Prepend new workouts
def prepend_new_workouts(file_path, new_snippets):
    try:
        with open(file_path, "r") as file:
            content = file.read()

        # Attempt to split the content
        try:
            before_cards, cards_section, after_cards = re.split(
                r"(<section id=\"workout-cards\">.*?</section>)", content, flags=re.DOTALL
            )
            existing_cards = re.search(
                r"<section id=\"workout-cards\">(.*?)</section>", cards_section, flags=re.DOTALL
            ).group(1)
        except (ValueError, AttributeError):
            # If no <section> exists, initialize the structure
            print("No workout cards section found. Initializing new section.")
            before_cards = content
            existing_cards = ""
            after_cards = ""

        # Combine new cards with existing cards
        updated_cards = "\n".join(new_snippets) + "\n" + existing_cards

        # Reconstruct the HTML file
        updated_content = (
            before_cards +
            f"<section id=\"workout-cards\">{updated_cards}</section>" +
            after_cards
        )

        # Write back to the file
        with open(file_path, "w") as file:
            file.write(updated_content)

    except FileNotFoundError:
        print(f"{file_path} not found. Creating a new file.")
        # Create a new file with a default structure if it doesn't exist
        with open(file_path, "w") as file:
            file.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Action Journal</title>
    <link rel="stylesheet" href="/static/css/styles.css">
</head>
<body>
    <nav class="navbar">
        <ul>
            <li><a href="index.html">Home</a></li>
            <li><a href="action-journal.html">Action Journal</a></li>
            <li><a href="about.html">About</a></li>
            <li><a href="faq.html">FAQ</a></li>
        </ul>
    </nav>
    <h1>Action Journal</h1>
    <section id="workout-cards">
        {"".join(new_snippets)}
    </section>
</body>
</html>""")



# Main function
def main():
    token = refresh_access_token()
    if not token:
        print("Failed to refresh access token. Exiting.")
        return
    
    activities = fetch_activities(token)
    filtered_activities = filter_rollerski_activities(activities)
    existing_ids = get_existing_workout_ids("templates/action-journal.html")
    new_activities = filter_new_workouts(filtered_activities, existing_ids)
    new_snippets = [generate_html_snippet(a) for a in new_activities]
    prepend_new_workouts("templates/action-journal.html", new_snippets)

if __name__ == "__main__":
    main()
