# Spotify E-Ink Album Art Display

A DIY digital photo frame project that pulls the currently playing song from your Spotify account and renders the album art dynamically onto a **13.3" Waveshare Spectra 6 (E6) E-Paper display** driven by a **Raspberry Pi 4b**.

The art is centered with customizable margins (no image stretching) and is rendered using the panel's native 6-color palette (Black, White, Red, Yellow, Blue, Green).

---

## Hardware Requirements

- **Controller:** Raspberry Pi 4b (running Raspberry Pi OS / Debian)
- **Screen:** 13.3" Six-Color E-Ink Display (1600x1200 resolution, Spectra 6)
- **Driver Board:** Waveshare e-Paper HAT+
- **Wiring:** Directly connected to the Pi's 40-pin GPIO header.

---

## Features

- **Dynamic Polling:** Automatically updates the screen when a new song starts playing on your active Spotify session.
- **Bistable & Energy Efficient:** The screen is put to sleep after every render. E-Paper draws zero power to hold an image, meaning your display stays active even if the Raspberry Pi is shut down.
- **Custom Scaling:** Displays the album art centered on the portrait screen. Includes config options for no scaling (original 640x640) or custom scale multipliers (e.g. 50% size increase to 960x960).
- **Protected Secrets:** Credentials (`secrets.json`) and active OAuth tokens (`tokens.json`) are kept in separate config files ignored by Git to prevent public credential leaks.
- **Systemd Background Daemon:** Runs continuously in the background, starting automatically when the Pi boots up.

---

## Project Structure

```
e-ink-album-art/
├── config/
│   ├── config.json         # Main settings (orientation, scaling, port)
│   └── secrets.json        # Spotify Client ID and Secret (IGNORED BY GIT)
├── lib/
│   ├── epd13in3E.py        # 13.3" Spectra 6 Driver
│   ├── epdconfig.py        # GPIO & SPI communication
│   └── DEV_Config_64_b.so  # C configuration helper (Pi 4 64-bit)
├── src/
│   ├── auth.py             # Spotify OAuth2 authentication flow
│   ├── display.py          # Image downloading, padding, and e-paper drawing
│   └── main.py             # Main daemon loop
├── LICENSE                 # MIT License
├── README.md               # Project documentation
├── requirements.txt        # Python dependencies
└── spotify-album-art.service # Systemd service file
```

---

## Setup Instructions

### 1. Enable SPI on the Raspberry Pi
Ensure the SPI interface is enabled on the Pi:
```bash
sudo raspi-config nonint do_spi 0
```
Or ensure `dtparam=spi=on` is uncommented in `/boot/firmware/config.txt` and reboot the Pi.

### 2. Install Package Dependencies
Install the required packages via `apt-get` (preferred on modern Debian/Raspberry Pi OS):
```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-pil python3-numpy python3-requests
```

### 3. Setup Spotify Developer App
1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and log in.
2. Click **Create App**.
3. Under **Redirect URIs**, add exactly: `http://127.0.0.1:8080/callback`
4. Select **Web API** under the APIs section.
5. Save the app, and open its **Settings** to retrieve your **Client ID** and **Client Secret**.

### 4. Configure Secrets & Settings
Create a secrets configuration file under `config/secrets.json`:
```json
{
  "client_id": "YOUR_SPOTIFY_CLIENT_ID",
  "client_secret": "YOUR_SPOTIFY_CLIENT_SECRET"
}
```
*Note: This file is ignored by Git and will not be pushed to public repositories.*

Customize your display settings in `config/config.json`:
```json
{
  "client_id": "",
  "client_secret": "",
  "redirect_uri": "http://127.0.0.1:8080/callback",
  "port": 8080,
  "poll_interval": 5,
  "orientation": "portrait",
  "bg_color": "white",
  "scale_image": false,
  "scale_factor": 1.5
}
```

### 5. Run Authentication
Run the authentication script manually to authorize your Spotify account:
```bash
python3 src/auth.py
```
This starts a local callback server. Follow the authorization link printed in the terminal, click **Agree**, and copy the redirected URL (even if the page fails to load). Paste the URL back into the terminal prompt to complete token generation. The credentials will be saved in `config/tokens.json`.

---

## Running as a Background Service

To configure the display to run continuously in the background on startup:

1. Copy the systemd service file:
   ```bash
   sudo cp spotify-album-art.service /etc/systemd/system/
   ```
2. Reload systemd, enable, and start the daemon:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable spotify-album-art.service
   sudo systemctl start spotify-album-art.service
   ```
3. Check status and log outputs:
   ```bash
   sudo systemctl status spotify-album-art.service
   journalctl -u spotify-album-art.service -n 50 -f
   ```

---

## License

This project is licensed under the [MIT License](LICENSE).
