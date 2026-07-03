import os
import sys
import json
import time
import base64
import urllib.parse
import http.server
import requests
import threading
import select

# Base directory setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'config.json')
TOKENS_PATH = os.path.join(BASE_DIR, 'config', 'tokens.json')
SECRETS_PATH = os.path.join(BASE_DIR, 'config', 'secrets.json')

auth_completed = False

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"Error: Configuration file not found at {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    
    # Merge secrets if they exist
    if os.path.exists(SECRETS_PATH):
        try:
            with open(SECRETS_PATH, 'r') as f:
                secrets = json.load(f)
                config.update(secrets)
        except Exception as e:
            print(f"Warning: Failed to load secrets.json: {e}")
            
    return config

def get_auth_url(client_id, redirect_uri):
    scopes = "user-read-currently-playing user-read-playback-state"
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": scopes,
        "show_dialog": "true"
    }
    return "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)

def exchange_code_for_tokens(client_id, client_secret, code, redirect_uri):
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri
    }
    response = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=data)
    if response.status_code != 200:
        print(f"Token exchange failed: {response.status_code} - {response.text}")
        return None
    
    tokens = response.json()
    tokens['expires_at'] = int(time.time()) + tokens['expires_in']
    return tokens

def refresh_spotify_token(client_id, client_secret, refresh_token):
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    response = requests.post("https://accounts.spotify.com/api/token", headers=headers, data=data)
    if response.status_code != 200:
        print(f"Token refresh failed: {response.status_code} - {response.text}")
        return None
    
    new_tokens = response.json()
    if 'refresh_token' not in new_tokens:
        new_tokens['refresh_token'] = refresh_token
    new_tokens['expires_at'] = int(time.time()) + new_tokens['expires_in']
    
    with open(TOKENS_PATH, 'w') as f:
        json.dump(new_tokens, f, indent=2)
    
    return new_tokens['access_token']

def get_access_token():
    config = load_config()
    client_id = config.get('client_id')
    client_secret = config.get('client_secret')
    
    if not client_id or not client_secret:
        print("Error: Spotify Client ID or Client Secret is not set in config/config.json!")
        return None

    if not os.path.exists(TOKENS_PATH):
        print("Tokens file not found. Running authentication server...")
        run_auth_flow(config)
        
    if not os.path.exists(TOKENS_PATH):
        print("Error: Authentication flow was not completed successfully.")
        return None

    with open(TOKENS_PATH, 'r') as f:
        tokens = json.load(f)

    if tokens.get('expires_at', 0) - time.time() < 60:
        print("Access token is expired or expiring soon. Refreshing...")
        return refresh_spotify_token(client_id, client_secret, tokens.get('refresh_token'))
    
    return tokens.get('access_token')

class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        global auth_completed
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        
        if 'code' in params:
            code = params['code'][0]
            config = load_config()
            tokens = exchange_code_for_tokens(
                config['client_id'],
                config['client_secret'],
                code,
                config['redirect_uri']
            )
            
            if tokens:
                with open(TOKENS_PATH, 'w') as f:
                    json.dump(tokens, f, indent=2)
                
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                success_html = """
                <html>
                <head>
                    <title>Spotify Auth Success</title>
                    <style>
                        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: white; text-align: center; padding-top: 100px; }
                        h1 { color: #1DB954; font-size: 48px; }
                        p { font-size: 20px; color: #b3b3b3; }
                        .container { max-width: 600px; margin: 0 auto; background-color: #181818; padding: 40px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>Authentication Successful!</h1>
                        <p>Tokens have been saved successfully to the Raspberry Pi. The E-Ink Album Art Display will now begin updating.</p>
                        <p>You can close this tab now.</p>
                    </div>
                </body>
                </html>
                """
                self.wfile.write(success_html.encode())
                print("\nTokens exchanged and saved successfully via callback server!")
                auth_completed = True
                
                class ServerShutdown(threading.Thread):
                    def __init__(self, server):
                        super().__init__()
                        self.server = server
                    def run(self):
                        time.sleep(1)
                        self.server.shutdown()
                
                ServerShutdown(self.server).start()
            else:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"Error: Failed to exchange authorization code for tokens.")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Error: Missing authorization code in request.")

def run_auth_flow(config):
    global auth_completed
    port = config.get('port', 8080)
    auth_url = get_auth_url(config['client_id'], config['redirect_uri'])
    
    print("\n" + "="*80)
    print("SPOTIFY AUTHENTICATION REQUIRED")
    print("="*80)
    print("Please open the following URL in a browser to authorize the display:")
    print(f"\n{auth_url}\n")
    print("="*80)
    
    server = http.server.HTTPServer(('0.0.0.0', port), CallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    
    print(f"Waiting for callback on http://localhost:{port}/callback (e.g. via SSH port forwarding)...")
    print("Alternatively, if the page fails to load, copy the full redirected URL from your browser's address bar and paste it below:")
    print("="*80)
    
    try:
        while not os.path.exists(TOKENS_PATH) and not auth_completed:
            # Check if there is stdin input available (with 0.5s timeout)
            rlist, _, _ = select.select([sys.stdin], [], [], 0.5)
            if rlist:
                line = sys.stdin.readline().strip()
                if line:
                    code = line
                    if "code=" in line:
                        parsed = urllib.parse.urlparse(line)
                        params = urllib.parse.parse_qs(parsed.query)
                        code = params.get('code', [None])[0]
                    
                    if code:
                        print("Exchanging manually entered code for tokens...")
                        tokens = exchange_code_for_tokens(
                            config['client_id'],
                            config['client_secret'],
                            code,
                            config['redirect_uri']
                        )
                        if tokens:
                            with open(TOKENS_PATH, 'w') as f:
                                json.dump(tokens, f, indent=2)
                            print("Tokens exchanged and saved successfully!")
                            auth_completed = True
                            break
                        else:
                            print("Failed to exchange the pasted code/URL. Please check and try again.")
                    else:
                        print("Could not find authorization code in the input. Please paste the full URL.")
    except KeyboardInterrupt:
        print("\nAuthentication cancelled.")
    finally:
        server.shutdown()
        server.server_close()

if __name__ == '__main__':
    get_access_token()
