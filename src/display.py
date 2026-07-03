import os
import sys
import requests
from io import BytesIO
from PIL import Image

# Base directory setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(BASE_DIR, 'lib'))

import epd13in3E

def fetch_image_from_url(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return Image.open(BytesIO(response.content))
        else:
            print(f"Failed to download image: HTTP {response.status_code}")
    except Exception as e:
        print(f"Error fetching image: {e}")
    return None

def draw_album_art(image_url, config):
    # Initialize display
    print("Initializing e-Paper display...")
    epd = epd13in3E.EPD()
    try:
        epd.Init()
        
        # Fetch album art image
        print(f"Fetching album art from URL: {image_url}")
        art_img = fetch_image_from_url(image_url)
        if not art_img:
            print("Could not fetch image, skipping display update.")
            epd.sleep()
            return False

        # Target dimensions
        width = epd.width
        height = epd.height

        # Create canvas filled with background color
        # Default is white
        bg_color = config.get("bg_color", "white").lower()
        fill_color = (255, 255, 255) if bg_color == "white" else (0, 0, 0)
        canvas = Image.new("RGB", (width, height), fill_color)

        # Scale image if enabled in config, otherwise use scale_factor if set
        scale_factor = config.get("scale_factor", 1.0)
        if config.get("scale_image", False):
            # Scale to fit display smaller dimension
            min_dim = min(width, height)
            art_img = art_img.resize((min_dim, min_dim), Image.Resampling.LANCZOS)
        elif scale_factor != 1.0:
            new_width = int(art_img.width * scale_factor)
            new_height = int(art_img.height * scale_factor)
            if new_width <= width and new_height <= height:
                print(f"Scaling image by factor {scale_factor} to {new_width}x{new_height}")
                art_img = art_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            else:
                print(f"Warning: Scaled image ({new_width}x{new_height}) exceeds display bounds. Skipping scaling.")
        
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
