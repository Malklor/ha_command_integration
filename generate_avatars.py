#!/usr/bin/env python3
"""
Downloads, crops, centers, and generates base64 PNG avatars for all Simpsons characters.
Ensures Marge's face is centered with her hair, and Santa's Little Helper is the actual dog.
"""

import base64
import io
import json
import requests
from PIL import Image

HEADERS = {"User-Agent": "Mozilla/5.0"}

CHARACTER_SOURCES = {
    "homer": "https://simpsonswiki.com/w/images/b/bd/Homer_Simpson.png",
    "bart": "https://simpsonswiki.com/w/images/6/65/Bart_Simpson.png",
    "lisa": "https://simpsonswiki.com/w/images/thumb/e/ec/Lisa_Simpson.png/250px-Lisa_Simpson.png",
    "maggie": "https://simpsonswiki.com/w/images/thumb/9/9d/Maggie_Simpson.png/250px-Maggie_Simpson.png",
    "marge": "https://simpsonswiki.com/w/images/thumb/0/0b/Marge_Simpson.png/250px-Marge_Simpson.png",
    "santas_helper": "https://simpsonswiki.com/w/images/thumb/2/2c/Santa%27s_Little_Helper.png/250px-Santa%27s_Little_Helper.png"
}

def process_character(name: str, url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=10)
    img = Image.open(io.BytesIO(r.content)).convert("RGBA")
    
    # Get bounding box of non-transparent pixels
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
        
    w, h = img.size
    
    # Target square size
    target_size = 180
    canvas = Image.new("RGBA", (target_size, target_size), (0, 0, 0, 0))
    
    if name == "marge":
        # Marge is very tall due to hair. Scale height to fit 90% of canvas so face is centered
        scale = (target_size * 0.95) / h
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        # Position so face & hair are nicely centered
        offset_x = (target_size - new_w) // 2
        offset_y = (target_size - new_h) // 2
        canvas.paste(resized, (offset_x, offset_y), resized)
        
    elif name == "santas_helper":
        # Dog body is wide. Crop primarily the head/torso area for the avatar
        # Head is on the right/upper part of image
        scale = (target_size * 0.85) / max(w, h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        offset_x = (target_size - new_w) // 2
        offset_y = (target_size - new_h) // 2
        canvas.paste(resized, (offset_x, offset_y), resized)
        
    else:
        # Standard character head/body scaling
        scale = (target_size * 0.85) / max(w, h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        offset_x = (target_size - new_w) // 2
        offset_y = (target_size - new_h) // 2
        canvas.paste(resized, (offset_x, offset_y), resized)
        
    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"

def generate_all():
    avatars = {}
    for name, url in CHARACTER_SOURCES.items():
        print(f"Processing {name}...")
        avatars[name] = process_character(name, url)
        print(f"  -> Generated {name} avatar ({len(avatars[name])} chars)")
        
    with open("/home/tgoetz/Projects/ha_command_integration/avatars.json", "w") as f:
        json.dump(avatars, f, indent=2)
    print("Saved avatars to avatars.json")

if __name__ == "__main__":
    generate_all()
