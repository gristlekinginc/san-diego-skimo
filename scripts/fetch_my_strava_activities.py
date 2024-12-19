import os
import requests
import datetime
import json
import markdown  # Import the markdown library to convert Markdown to HTML
from github import Github

# --- Configuration ---
TOKEN_FILE = "strava_tokens.json"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = "gristlekinginc/san-diego-skimo"  # Replace with your repo name
POSTS_DIR = "posts"  # Directory for blog posts

# San Diego County Bounding Box
SAN_DIEGO_BOUNDS = {
    "sw_lat": 32.5343,
    "sw_lng": -117.1219,
    "ne_lat": 33.1145,
    "ne_lng": -116.0856,
}

# --- Refresh Access Token ---
def refresh_access_token():
    url = "https://www.strava.com/oauth/token"
    payload = {
        "client_id": os.getenv("STRAVA_CLIENT_ID"),
        "client_secret": os.getenv("STRAVA_CLIENT_SECRET"),
        "grant_type": "refresh_token",
        "refresh_token": os.getenv("STRAVA_REFRESH_TOKEN"),
    }

    response = requests.post(url, data=payload)
    response.raise_for_status()
    tokens = response.json()

    # Save updated tokens to file
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f)
    
    print("Access token refreshed successfully!")
    return tokens["access_token"]

# --- Load Access Token ---
def load_access_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            tokens = json.load(f)
        return tokens["access_token"]
    return refresh_access_token()

# Assign the ACCESS_TOKEN here
ACCESS_TOKEN = load_access_token()

# --- Strava API ---
def fetch_my_activities():
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    params = {"per_page": 30}
    
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

def filter_roller_ski(activities):
    filtered = []
    for activity in activities:
        if activity["type"] == "RollerSki":
            latlng = activity.get("start_latlng", [])
            if latlng and (
                SAN_DIEGO_BOUNDS["sw_lat"] <= latlng[0] <= SAN_DIEGO_BOUNDS["ne_lat"]
                and SAN_DIEGO_BOUNDS["sw_lng"] <= latlng[1] <= SAN_DIEGO_BOUNDS["ne_lng"]
            ):
                filtered.append(activity)
    return filtered

# --- Create HTML Post ---
def create_html(activity):
    date = datetime.datetime.strptime(activity["start_date"], "%Y-%m-%dT%H:%M:%SZ").date()
    title = activity["name"]
    description = activity.get("description", "No description provided")
    distance = round(activity["distance"] / 1609, 2)  # meters to miles
    elevation = round(activity["total_elevation_gain"], 1)
    time = round(activity["moving_time"] / 60, 1)

    content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="../assets/css/style.css">
    <link rel="icon" href="../assets/favicon.ico" type="image/x-icon"> <!-- Favicon link -->
</head>
<body>
    <header>
        <h1>Action Journal</h1>
        <nav>
            <ul class="nav-list">
                <li><a href="../index.html">Home</a></li>
                <li><a href="../action-journal.html">Action Journal</a></li>
                <li><a href="../contact.html">Contact</a></li>
            </ul>
        </nav>
    </header>

    <div class="post-container">
        <h1>{title}</h1>
        <p><strong>Date:</strong> {date}</p>
        <p><strong>Distance:</strong> {distance} miles</p>
        <p><strong>Elevation Gain:</strong> {elevation} ft</p>
        <p><strong>Time:</strong> {time} minutes</p>
        <h2>Description</h2>
        <p>{description}</p>
        <h2>Map</h2>
        <p><a href="https://www.strava.com/activities/{activity['id']}" target="_blank">View Activity on Strava</a></p>
    </div>
</body>
</html>
"""
    filename = f"{POSTS_DIR}/{date}-{title.replace(' ', '-').lower()}.html"
    return filename, content



# --- Generate index.json ---
def generate_index(posts_dir):
    posts = []
    for filename in os.listdir(posts_dir):
        if filename.endswith(".html"):
            parts = filename.replace('.html', '').split('-')
            date = '-'.join(parts[:3])  # Extract YYYY-MM-DD
            title = ' '.join(parts[3:]).capitalize()

            # Extract metadata directly from HTML file
            with open(os.path.join(posts_dir, filename), "r") as f:
                content = f.read()
                distance = extract_metadata(content, "Distance:")
                elevation = extract_metadata(content, "Elevation Gain:")
                time = extract_metadata(content, "Time:")

            posts.append({
                "title": title,
                "date": date,
                "distance": distance,
                "elevation": elevation,
                "time": time,
                "filename": filename
            })

    posts.sort(key=lambda x: x["date"], reverse=True)

    with open(os.path.join(posts_dir, "index.json"), "w") as f:
        json.dump(posts, f, indent=4)
    print("Generated index.json successfully!")

def extract_metadata(content, key):
    """Extract metadata value for a given key from HTML content."""
    import re
    match = re.search(f"<p><strong>{key}</strong> (.*?)</p>", content)
    return match.group(1) if match else "N/A"


# --- Push to GitHub ---
def push_to_github(files):
    print("Repository Name:", REPO_NAME)
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)

    for filepath, content in files:
        try:
            existing_file = None
            try:
                existing_file = repo.get_contents(filepath)
            except Exception:
                pass
            
            if existing_file:
                repo.update_file(filepath, f"Update file: {filepath}", content, existing_file.sha)
                print(f"Updated: {filepath}")
            else:
                repo.create_file(filepath, f"Add file: {filepath}", content)
                print(f"Created: {filepath}")
        except Exception as e:
            print(f"Error creating/updating {filepath}: {e}")

# --- Main ---
if __name__ == "__main__":
    os.makedirs(POSTS_DIR, exist_ok=True)
    activities = fetch_my_activities()
    roller_ski_activities = filter_roller_ski(activities)

    files_to_push = []
    for activity in roller_ski_activities:
        filename, content = create_html(activity)
        with open(filename, "w") as f:
            f.write(content)
        files_to_push.append((filename, content))

    generate_index(POSTS_DIR)
    with open(f"{POSTS_DIR}/index.json", "r") as f:
        files_to_push.append((f"{POSTS_DIR}/index.json", f.read()))

    if files_to_push:
        push_to_github(files_to_push)
    else:
        print("No new Roller Ski activities found.")
