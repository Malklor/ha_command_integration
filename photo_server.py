#!/usr/bin/env python3
"""
Lightweight local HTTP service on port 8125 for Trail Camera Photo Viewing and Buck Tagging.
Provides:
1. /view?guid=<guid>&cam=<slug>: High-res dark-mode photo viewer with Tag as Buck toggle.
2. /tag?guid=<guid>&cam=<slug>: Toggles buck status, updates HA, and redirects back.
"""

import http.server
import json
import os
import socketserver
import subprocess
import urllib.parse
from stealthcam_api.client import StealthCamClient
from sync_to_ha import load_env

PORT = 8125
TAGGED_FILE = "/home/tgoetz/Projects/ha_command_integration/tagged_bucks.json"

class PhotoHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        guid = params.get("guid", [""])[0]
        cam_slug = params.get("cam", ["trail-cams"])[0]

        if parsed.path == "/tag":
            if guid:
                # Toggle tag
                tagged_data = {}
                if os.path.exists(TAGGED_FILE):
                    try:
                        with open(TAGGED_FILE) as f:
                            tagged_data = json.load(f)
                    except Exception:
                        pass
                
                is_tagged = not tagged_data.get(guid, False)
                if is_tagged:
                    tagged_data[guid] = True
                else:
                    tagged_data.pop(guid, None)
                    
                with open(TAGGED_FILE, "w") as f:
                    json.dump(tagged_data, f, indent=2)

                # Re-sync and update Lovelace
                subprocess.run(["python3", "/home/tgoetz/Projects/ha_command_integration/sync_to_ha.py"], check=False)
                subprocess.run(["python3", "/home/tgoetz/Projects/ha_command_integration/update_dashboard.py"], check=False)

            # Redirect back to Stand view
            redirect_url = f"/lovelace-basement/stand-{cam_slug}" if cam_slug != "trail-cams" else "/lovelace-basement/trail-cams"
            self.send_response(302)
            self.send_header("Location", redirect_url)
            self.end_headers()
            return

        elif parsed.path == "/view":
            # Show high-res photo viewer with Tag as Buck button
            tagged_data = {}
            if os.path.exists(TAGGED_FILE):
                try:
                    with open(TAGGED_FILE) as f:
                        tagged_data = json.load(f)
                except Exception:
                    pass
            is_buck = tagged_data.get(guid, False)

            # Look up image URL from HA or API
            img_url = params.get("url", [""])[0]
            time_str = params.get("time", ["Capture"])[0]

            html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Trail Cam Photo Inspector</title>
    <style>
        body {{
            background: #0e0e10;
            color: #efeff1;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 90vh;
        }}
        .container {{
            max-width: 900px;
            width: 100%;
            background: #18181b;
            border-radius: 14px;
            overflow: hidden;
            box-shadow: 0 8px 24px rgba(0,0,0,0.5);
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .header {{
            padding: 16px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #1f1f23;
            border-bottom: 1px solid rgba(255,255,255,0.08);
        }}
        .title {{
            font-size: 18px;
            font-weight: 700;
        }}
        .btn {{
            display: inline-flex;
            align-items: center;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 700;
            text-decoration: none;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .btn-back {{
            background: #2f2f35;
            color: #fff;
        }}
        .btn-buck {{
            background: {"#f39c12" if is_buck else "#2a3b5c"};
            color: {"#000" if is_buck else "#6ba4f8"};
            border: 2px solid {"#f39c12" if is_buck else "#3b82f6"};
        }}
        .img-box {{
            width: 100%;
            background: #000;
            text-align: center;
        }}
        .img-box img {{
            max-width: 100%;
            height: auto;
            max-height: 70vh;
            display: block;
            margin: 0 auto;
        }}
        .footer {{
            padding: 16px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #18181b;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <a class="btn btn-back" href="/lovelace-basement/stand-{cam_slug}">⬅️ Back to Stand</a>
            <div class="title">🕒 {time_str}</div>
            <a class="btn btn-buck" href="/tag?guid={guid}&cam={cam_slug}">
                {"🦌 VERIFIED BUCK (Click to Untag)" if is_buck else "🦌 Mark as Verified Buck"}
            </a>
        </div>
        <div class="img-box">
            <img src="{img_url}" alt="Trail Cam Capture" />
        </div>
        <div class="footer">
            <span>Stand: <strong>{cam_slug.upper()}</strong></span>
            <span>Status: <strong>{"🦌 Antlered Buck Scored" if is_buck else "📷 Standard Animal Capture"}</strong></span>
        </div>
    </div>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

def run_server():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), PhotoHandler) as httpd:
        print(f"Photo Inspector server running on port {PORT}...")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
