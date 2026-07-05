import os
import sys
import requests
from io import BytesIO
from PIL import Image, ImageEnhance

# Base directory setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(BASE_DIR, 'lib'))

import epd13in3E

import re

def get_high_res_spotify_art(url):
    # Matches the base URL, the 4-char size code, and the 24-char image hash
    pattern = r'(https://i\.scdn\.co/image/ab67616d0000)([a-f0-9]{4})([a-f0-9]{24})'
    max_res_code = '82c1' # 82c1 is the undocumented identifier for 1400x1400 max-res JPEG
    
    match = re.search(pattern, url)
    if match:
        base_url = match.group(1)
        image_hash = match.group(3)
        return f"{base_url}{max_res_code}{image_hash}"
    return url

def fetch_image_from_url(url):
    high_res_url = get_high_res_spotify_art(url)
    
    if high_res_url != url:
        print(f"Attempting to fetch high-res image: {high_res_url}")
        try:
            response = requests.get(high_res_url, timeout=10)
            if response.status_code == 200:
                print("Successfully fetched high-res image!")
                return Image.open(BytesIO(response.content))
            else:
                print(f"High-res image not available (HTTP {response.status_code}). Falling back to standard resolution.")
        except Exception as e:
            print(f"Error fetching high-res image: {e}. Falling back to standard resolution.")

    # Fallback to standard-res URL
    try:
        print(f"Fetching standard-res image: {url}")
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return Image.open(BytesIO(response.content))
        else:
            print(f"Failed to download image: HTTP {response.status_code}")
    except Exception as e:
        print(f"Error fetching standard image: {e}")
    return None

def draw_album_art(image_url, config):
    # Initialize display
    print("Initializing e-Paper display...")
    epd = epd13in3E.EPD()
    try:
        epd.Init()
        
        # Fetch album art image
        art_img = fetch_image_from_url(image_url)
        if not art_img:
            print("Could not fetch image, skipping display update.")
            epd.sleep()
            return False

        # Boost saturation and contrast if specified in config, defaulting to 1.0
        saturation_factor = config.get("saturation_boost", 1.0)
        contrast_factor = config.get("contrast_boost", 1.0)

        if saturation_factor != 1.0:
            print(f"Boosting color saturation by factor {saturation_factor}")
            enhancer = ImageEnhance.Color(art_img)
            art_img = enhancer.enhance(saturation_factor)

        if contrast_factor != 1.0:
            print(f"Boosting contrast by factor {contrast_factor}")
            enhancer = ImageEnhance.Contrast(art_img)
            art_img = enhancer.enhance(contrast_factor)

        # Target dimensions
        width = epd.width
        height = epd.height

        # Create canvas filled with background color
        # Default is white
        bg_color = config.get("bg_color", "white").lower()
        fill_color = (255, 255, 255) if bg_color == "white" else (0, 0, 0)
        canvas = Image.new("RGB", (width, height), fill_color)

        # Scale image to target size (default 960x960)
        scale_factor = config.get("scale_factor", 1.5)
        target_size = config.get("target_size", int(640 * scale_factor))
        
        print(f"Scaling image down from {art_img.width}x{art_img.height} to {target_size}x{target_size}...")
        art_img = art_img.resize((target_size, target_size), Image.Resampling.LANCZOS)
        
        # Calculate center coordinates
        x_offset = (width - art_img.width) // 2
        y_offset = (height - art_img.height) // 2

        # Paste the album art centered on the canvas
        print(f"Pasting album art of size {art_img.width}x{art_img.height} at ({x_offset}, {y_offset})")
        canvas.paste(art_img, (x_offset, y_offset))

        # Render on display
        print("Rendering image to display...")
        epd.display(epd.getbuffer(canvas))
        print("Rendering finished. Putting display to sleep.")
        epd.sleep()
        return True

    except Exception as e:
        print(f"Error during display rendering: {e}")
        try:
            epd.sleep()
        except:
            pass
        return False

if __name__ == '__main__':
    # Simple manual test block
    test_config = {"bg_color": "white", "scale_image": False}
    # Test image URL (standard placeholder or known image)
    test_url = "https://i.scdn.co/image/ab67616d0000b27341e31d4d8778f69e6b4f8c6b"
    draw_album_art(test_url, test_config)
