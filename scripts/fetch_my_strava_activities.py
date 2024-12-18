import os
import requests
import datetime
import json
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

# --- Create Markdown Post ---
def create_markdown(activity):
    date = datetime.datetime.strptime(activity["start_date"], "%Y-%m-%dT%H:%M:%SZ").date()
    title = activity["name"]
    description = activity.get("description", "No description provided")  # Extract the description
    distance = round(activity["distance"] / 1609, 2)  # meters to miles
    elevation = round(activity["total_elevation_gain"], 1)
    time = round(activity["moving_time"] / 60, 1)  # seconds to minutes

    content = f"""---
title: "{title}"
date: {date}
tags: roller ski, san diego
---

### Stats
- **Distance**: {distance} miles
- **Elevation Gain**: {elevation} ft
- **Time**: {time} minutes

### Description
{description}

### Map
[View Activity on Strava](https://www.strava.com/activities/{activity['id']})
"""
    filename = f"{POSTS_DIR}/{date}-{title.replace(' ', '-').lower()}.md"
    return filename, content

# --- Generate index.json ---
def generate_index(posts_dir):
    posts = []
    for filename in os.listdir(posts_dir):
        if filename.endswith(".md"):
            # Extract the date and title from filename
            parts = filename.replace('.md', '').split('-')
            date = '-'.join(parts[:3])  # Extract YYYY-MM-DD
            title = ' '.join(parts[3:]).capitalize()
            
            posts.append({
                "title": title,
                "date": date,
                "filename": filename
            })

    # Sort posts by date (latest first)
    posts.sort(key=lambda x: x["date"], reverse=True)

    # Save the sorted posts to index.json
    with open(os.path.join(posts_dir, "index.json"), "w") as f:
        json.dump(posts, f, indent=4)
    print("Generated index.json successfully!")


# --- Push to GitHub ---
def push_to_github(files):
    print("Repository Name:", REPO_NAME)
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)

    for filepath, content in files:
        try:
            existing_file = None
            try:
                # Check if the file already exists
                existing_file = repo.get_contents(filepath)
            except Exception:
                pass  # File does not exist
            
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
        filename, content = create_markdown(activity)
        with open(filename, "w") as f:
            f.write(content)
        files_to_push.append((filename, content))

    # Generate index.json
    generate_index(POSTS_DIR)
    with open(f"{POSTS_DIR}/index.json", "r") as f:
        files_to_push.append((f"{POSTS_DIR}/index.json", f.read()))

    # Push all files to GitHub
    if files_to_push:
        push_to_github(files_to_push)
    else:
        print("No new Roller Ski activities found.")

