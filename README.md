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
- **High-Resolution Art Extraction:** Bypasses Spotify's official 640x640 API limit by swapping the CDN resolution code to `82c1` to download the original uncompressed source files (up to 2000x2000+ pixels) directly from Spotify's servers, with automatic fallback to standard resolution.
- **Crisp Downscaling:** Resizes the high-resolution source art to exactly `1200x1200` pixels (scaling factor `1.875`) using high-quality Lanczos resampling, rendering a much sharper image that extends all the way to the side edges of the screen.
- **Optional Image Enhancements:** `saturation_boost` and `contrast_boost` in `config/config.json` can boost color saturation and contrast before conversion. Both default to `1.0` (off).
- **Protected Secrets:** Credentials (`secrets.json`) and active OAuth tokens (`tokens.json`) are kept in separate config files ignored by Git to prevent public credential leaks.
- **Systemd Background Daemon:** Runs continuously in the background, starting automatically when the Pi boots up.

---

## Project Structure

```
e-ink-album-art/
├── config/
│   ├── config.json         # Main settings (orientation, scaling, port)
│   ├── palette.json        # Ink colors for the optional dithered conversion
│   └── secrets.json        # Spotify Client ID and Secret (IGNORED BY GIT)
├── lib/
│   ├── epd13in3E.py        # 13.3" Spectra 6 Driver
│   ├── epdconfig.py        # GPIO & SPI communication
│   └── DEV_Config_64_b.so  # C configuration helper (Pi 4 64-bit)
├── src/
│   ├── auth.py             # Spotify OAuth2 authentication flow
│   ├── color_convert.py    # Optional palette-dithered color conversion
│   ├── display.py          # Image downloading, padding, and e-paper drawing
│   └── main.py             # Main daemon loop
├── tools/
│   └── compare_color.py    # Preview legacy vs dithered conversion without the panel
├── LICENSE                 # MIT License
├── README.md               # Project documentation
├── requirements.txt        # Python dependencies
└── spotify-album-art.service # Systemd service file
```

*Note: All required hardware drivers for the 13.3" Waveshare Spectra 6 (E6) display (along with precompiled 32-bit/64-bit C helper library files) are fully pre-packaged and included inside the `lib/` directory. You do not need to download or compile any external display drivers.*

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
  "scale_factor": 1.875,
  "saturation_boost": 1.0,
  "contrast_boost": 1.0
}
```

### 5. Run Authentication
Run the authentication script manually to authorize your Spotify account:
```bash
python3 src/auth.py
```
This starts a local callback server. Follow the authorization link printed in the terminal, click **Agree**, and copy the redirected URL (even if the page fails to load). Paste the URL back into the terminal prompt to complete token generation. The credentials will be saved in `config/tokens.json`.

### 6. (Optional) Palette-dithered color conversion

By default the driver snaps every pixel to the six *ideal* primaries (pure `#00ff00` green, `#0000ff` blue, ...). Real Spectra 6 inks are much duller. Setting `"color_mode": "dither"` in `config/config.json` instead error-diffuses against `config/palette.json`, which describes how the inks actually look, using [epaper-dithering](https://github.com/OpenDisplay-org/epaper-dithering) (MIT).

**Install** (Python 3.11+). Raspberry Pi OS blocks system-wide `pip install`, so use a virtual environment that can still see the apt packages from step 2. Run this in the project directory:

```bash
python3 -m venv --system-site-packages venv
venv/bin/pip install -r requirements.txt
```

**Run the service with the venv.** After installing the service (below), add a systemd drop-in so the unit file itself stays unchanged:

```bash
sudo mkdir -p /etc/systemd/system/spotify-album-art.service.d
printf '[Service]\nExecStart=\nExecStart=%s/venv/bin/python -u src/main.py\n' "$PWD" \
  | sudo tee /etc/systemd/system/spotify-album-art.service.d/venv.conf
sudo systemctl daemon-reload
sudo systemctl restart spotify-album-art.service
```

**Enable it** in `config/config.json`:

```json
{
  "color_mode": "dither",
  "dither": { "mode": "floyd_steinberg" }
}
```

`dither` accepts any `DitherOptions` field (`mode`, `tone`, `gamut`, `saturation`, `exposure`, `shadows`, `highlights`, `anchor`, `snap`, ...). If the library is missing or the palette is invalid, the daemon logs the error and falls back to the driver's conversion. Leaving `color_mode` unset keeps the original behavior.

**Palette:** `config/palette.json` is the 7.3" Spectra 6 example palette from [epaper-dithering](https://github.com/OpenDisplay-org/epaper-dithering) (MIT, Copyright (c) 2026 OpenDisplay.org), measured on a different panel than the 13.3" one, so treat it as a starting point. For best results measure your own panel (see that project's `docs/CALIBRATION.md`) and replace the file; `palette_path` points elsewhere if you prefer.

**Preview without touching the panel** (needs `pip install -r requirements.txt` wherever you run it):

```bash
python3 tools/compare_color.py cover.png -o compare.png \
  --variant "fs=floyd_steinberg" --variant "tone=floyd_steinberg,tone=0.5"
```

This draws the source, the legacy conversion and each variant using the palette's ink colors. It is only as accurate as the palette.

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
