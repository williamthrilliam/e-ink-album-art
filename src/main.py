import os
import sys
import json
import time
import signal
import requests

# Base directory setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from src.auth import get_access_token, load_config
from src.display import draw_album_art

LAST_TRACK_PATH = os.path.join(BASE_DIR, 'config', 'last_track.txt')

class SpotifyDaemon:
    def __init__(self):
        self.running = True
        self.config = load_config()
        self.last_track_id = self.load_last_track()
        
        # Register signals for clean shutdown
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

    def handle_shutdown(self, signum, frame):
        print(f"Received signal {signum}. Shutting down daemon...")
        self.running = False

    def load_last_track(self):
        if os.path.exists(LAST_TRACK_PATH):
            try:
                with open(LAST_TRACK_PATH, 'r') as f:
                    return f.read().strip()
            except Exception as e:
                print(f"Error loading last track ID: {e}")
        return None

    def save_last_track(self, track_id):
        try:
            with open(LAST_TRACK_PATH, 'w') as f:
                f.write(track_id)
            self.last_track_id = track_id
        except Exception as e:
            print(f"Error saving last track ID: {e}")

    def fetch_currently_playing(self, access_token):
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        try:
            response = requests.get(
                "https://api.spotify.com/v1/me/player/currently-playing",
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 204:
                # No active playback
                return None
            elif response.status_code == 401:
                print("Access token expired or invalid (HTTP 401).")
                return {"error": "unauthorized"}
            else:
                print(f"Spotify API returned HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"Error calling Spotify API: {e}")
            return None

    def run(self):
        print("Spotify E-Ink Album Art Display daemon started.")
        poll_interval = self.config.get("poll_interval", 5)
        
        while self.running:
            access_token = get_access_token()
            if not access_token:
                print("Could not retrieve access token. Retrying in 10 seconds...")
                time.sleep(10)
                continue

            playback_data = self.fetch_currently_playing(access_token)
            
            # Handle token expiration dynamically
            if playback_data and isinstance(playback_data, dict) and playback_data.get("error") == "unauthorized":
                # Token error, get_access_token() will refresh it on next loop
                continue

            if playback_data and playback_data.get("is_playing") and playback_data.get("item"):
                item = playback_data["item"]
                track_id = item.get("id")
                track_name = item.get("name")
                artists = ", ".join([artist["name"] for artist in item.get("artists", [])])
                
                # Check if it's a new track
                if track_id != self.last_track_id:
                    print(f"\nNew track detected: {track_name} - {artists}")
                    
                    # Fetch album art URL (usually index 0 is the highest res 640x640 image)
                    images = item.get("album", {}).get("images", [])
                    if images:
                        album_art_url = images[0]["url"]
                        success = draw_album_art(album_art_url, self.config)
                        if success:
                            self.save_last_track(track_id)
                    else:
                        print("No album art images found for this track.")
            else:
                # Idle state, nothing playing or active
                pass

            # Sleep in small increments to remain responsive to SIGTERM
            for _ in range(poll_interval):
                if not self.running:
                    break
                time.sleep(1)

        print("Daemon stopped.")

if __name__ == '__main__':
    daemon = SpotifyDaemon()
    daemon.run()
