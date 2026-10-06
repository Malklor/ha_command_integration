#!/usr/bin/env python3
"""
Updates the 'Trail Cams' view in the 'lovelace-basement' Home Assistant dashboard.
Includes GPS Map, Environmental Telemetry, Battery/Signal Monitor, and Expandable Dropdown Camera Analysis.
"""

import asyncio
import json
import websockets

HA_WS = "ws://192.168.131.17:8123/api/websocket"
HA_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJmMWUzMzA5ODZkYzQ0YWJiYWM4NmU5OGIxMTJiZDNiNSIsImlhdCI6MTc5MDk3MTMwMiwiZXhwIjoyMTA2MzMxMzAyfQ.wkyHRjBsBKiaEMbXmz_nyGreKnLtwiTTCGuxADaVeqs"

CAMERAS = [
    {"slug": "homer", "name": "HOMER", "id": "3000211"},
    {"slug": "maggie", "name": "MAGGIE", "id": "3000779"},
    {"slug": "santas_helper", "name": "SANTA'S HELPER", "id": "3001315"},
    {"slug": "lisa", "name": "LISA", "id": "3000767"},
    {"slug": "marge", "name": "MARGE", "id": "3000223"},
    {"slug": "bart", "name": "BART", "id": "3000762"},
]

def build_trail_cams_view():
    cards = []

    # 1. Top Header & Hunt Strategy Banner
    cards.append({
        "type": "markdown",
        "content": (
            "## 🦌 Stealth Cam Command — Hunting Intelligence Hub\n"
            "Live cellular trail camera network, AI animal classification, stand GPS positioning, and movement telemetry."
        )
    })

    # 2. Daily Hunt Recommendation & Property Weather Summary
    cards.append({
        "type": "horizontal-stack",
        "cards": [
            {
                "type": "markdown",
                "title": "🎯 Stand Recommendation",
                "content": (
                    "**Recommended Stand:** **HOMER / MAGGIE RUN**\n\n"
                    "- 🦌 **Recent Buck Hits:** 2 Verified Antlered Hits\n"
                    "- ⏰ **Peak Movement:** 04:45 AM - 07:15 AM (Dawn Transitions)\n"
                    "- 🧭 **Current Wind Favorability:** Stands facing NE / NW clear of downwind scent cone.\n"
                    "- 🌔 **Moon Phase:** Waxing Crescent (Favorable early-morning foraging)"
                )
            },
            {
                "type": "entities",
                "title": "🌤️ Stand Environment Glance",
                "entities": [
                    {"entity": "sensor.stealthcam_homer_temperature", "name": "Homer Stand Temp"},
                    {"entity": "sensor.stealthcam_maggie_temperature", "name": "Maggie Stand Temp"},
                    {"entity": "sensor.stealthcam_homer_pressure", "name": "Barometric Pressure"},
                    {"entity": "sensor.stealthcam_homer_moon_phase", "name": "Moon Phase"},
                    {"entity": "sensor.stealthcam_homer_wind", "name": "Wind & Scent Direction"}
                ]
            }
        ]
    })

    # 3. GPS Field Map of all 6 Trail Cameras
    cards.append({
        "type": "map",
        "title": "🗺️ Property Trail Camera Locations & Stand Positions",
        "default_zoom": 17,
        "hours_to_show": 1,
        "entities": [
            f"device_tracker.stealthcam_{cam['slug']}" for cam in CAMERAS
        ]
    })

    # 4. Stand Environmental History & Cellular Health Matrix
    cards.append({
        "type": "horizontal-stack",
        "cards": [
            {
                "type": "custom:mini-graph-card",
                "name": "📈 Stand Temperature Curves (°F)",
                "hours_to_show": 48,
                "points_per_hour": 2,
                "entities": [
                    {"entity": "sensor.stealthcam_homer_temperature", "name": "Homer"},
                    {"entity": "sensor.stealthcam_maggie_temperature", "name": "Maggie"},
                    {"entity": "sensor.stealthcam_santas_helper_temperature", "name": "Santa's Helper"},
                    {"entity": "sensor.stealthcam_lisa_temperature", "name": "Lisa"}
                ]
            },
            {
                "type": "entities",
                "title": "🔋 Cellular & Device Health",
                "entities": [
                    {"entity": "sensor.stealthcam_homer_battery", "name": "Homer Battery", "secondary_info": "last-changed"},
                    {"entity": "sensor.stealthcam_maggie_battery", "name": "Maggie Battery"},
                    {"entity": "sensor.stealthcam_santas_helper_battery", "name": "Santa's Helper Battery"},
                    {"entity": "sensor.stealthcam_lisa_battery", "name": "Lisa Battery"},
                    {"entity": "sensor.stealthcam_marge_battery", "name": "Marge Battery"},
                    {"entity": "sensor.stealthcam_bart_battery", "name": "Bart Battery"}
                ]
            }
        ]
    })

    # 5. Live Photo Gallery with Expandable Activity Analysis Dropdowns
    cards.append({
        "type": "markdown",
        "content": "### 📸 Live Trail Cam Feeds & Detailed Movement Analytics"
    })

    # Grid of Cameras with Dropdown Analysis
    cam_cards = []
    for cam in CAMERAS:
        slug = cam["slug"]
        name = cam["name"]
        
        # We build a vertical-stack card for each camera:
        # Top: Custom Button Card with High-Res Image, Status Header, and Tap to Enlarge
        # Bottom: Fold Entity Row / Collapsible Markdown with full telemetry, buck counts, GPS coordinates & time distributions
        cam_card = {
            "type": "vertical-stack",
            "cards": [
                {
                    "type": "custom:button-card",
                    "entity": f"camera.stealthcam_{slug}",
                    "show_entity_picture": True,
                    "show_name": True,
                    "show_label": True,
                    "name": name,
                    "entity_picture": "[[[ return entity.attributes.image_url || entity.attributes.entity_picture; ]]]",
                    "label": (
                        f"[[[ "
                        f"var h = states['sensor.stealthcam_{slug}_last_hit'] ? states['sensor.stealthcam_{slug}_last_hit'].state : 'None'; "
                        f"var t = entity.attributes.temperature ? ('🌡️ ' + entity.attributes.temperature + '°F | ') : ''; "
                        f"var b = entity.attributes.battery_level !== undefined ? ('🔋 ' + entity.attributes.battery_level + '%') : ''; "
                        f"return '🎯 Hit: ' + h + ' | ' + t + b; "
                        f"]]]"
                    ),
                    "tap_action": {
                        "action": "url",
                        "url_path": "[[[ return entity.attributes.image_url || '#'; ]]]"
                    },
                    "styles": {
                        "card": [
                            {"border-radius": "14px 14px 0 0"},
                            {"overflow": "hidden"},
                            {"padding": "0"},
                            {"border": "1.5px solid rgba(82, 148, 226, 0.35)"},
                            {"border-bottom": "none"},
                            {"background": "var(--card-background-color, #1c1c1e)"},
                            {"box-shadow": "0 4px 12px rgba(0, 0, 0, 0.25)"}
                        ],
                        "entity_picture": [
                            {"width": "100%"},
                            {"height": "220px"},
                            {"object-fit": "cover"},
                            {"border-radius": "12px 12px 0 0"},
                            {"background": "#000"}
                        ],
                        "name": [
                            {"font-size": "16px"},
                            {"font-weight": "700"},
                            {"color": "var(--primary-text-color)"},
                            {"padding": "8px 12px 2px 12px"},
                            {"text-align": "left"},
                            {"width": "100%"}
                        ],
                        "label": [
                            {"font-size": "12px"},
                            {"font-weight": "500"},
                            {"color": "var(--secondary-text-color)"},
                            {"padding": "0 12px 10px 12px"},
                            {"text-align": "left"},
                            {"width": "100%"}
                        ]
                    }
                },
                {
                    "type": "entities",
                    "style": {
                        "border-radius": "0 0 14px 14px",
                        "border": "1.5px solid rgba(82, 148, 226, 0.35)",
                        "border-top": "none",
                        "margin-top": "-1px"
                    },
                    "entities": [
                        {
                            "type": "custom:fold-entity-row",
                            "head": {
                                "type": "section",
                                "label": "📊 Stand Movement & GPS Analytics (Expand)"
                            },
                            "entities": [
                                {
                                    "entity": f"sensor.stealthcam_{slug}_last_hit",
                                    "name": "Last Animal Detection",
                                    "icon": "mdi:target-account"
                                },
                                {
                                    "entity": f"sensor.stealthcam_{slug}_buck_hits",
                                    "name": "Verified Antlered Buck Captures",
                                    "icon": "mdi:deer"
                                },
                                {
                                    "entity": f"sensor.stealthcam_{slug}_peak_window",
                                    "name": "Peak Activity Window",
                                    "icon": "mdi:clock-check-outline"
                                },
                                {
                                    "entity": f"sensor.stealthcam_{slug}_last_checkin",
                                    "name": "Cellular Sync Timestamp",
                                    "icon": "mdi:cellphone-wireless"
                                },
                                {
                                    "entity": f"sensor.stealthcam_{slug}_signal",
                                    "name": "Cellular Signal Strength",
                                    "icon": "mdi:signal-cellular-3"
                                },
                                {
                                    "entity": f"sensor.stealthcam_{slug}_sd_free",
                                    "name": "SD Card Free Space",
                                    "icon": "mdi:sd"
                                },
                                {
                                    "entity": f"device_tracker.stealthcam_{slug}",
                                    "name": "GPS Stand Location & Bearing",
                                    "icon": "mdi:crosshairs-gps"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        cam_cards.append(cam_card)

    cards.append({
        "type": "grid",
        "columns": 3,
        "square": False,
        "cards": cam_cards
    })

    return {
        "title": "Trail Cams",
        "path": "trail-cams",
        "icon": "mdi:cctv",
        "cards": cards
    }

async def update_dashboard():
    async with websockets.connect(HA_WS) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": HA_TOKEN}))
        auth_res = json.loads(await ws.recv())
        if auth_res.get("type") != "auth_ok":
            print("Authentication failed:", auth_res)
            return

        # Fetch current lovelace config
        await ws.send(json.dumps({
            "id": 1,
            "type": "lovelace/config",
            "url_path": "lovelace-basement"
        }))
        res = json.loads(await ws.recv())
        if not res.get("success"):
            print("Failed to get lovelace config:", res)
            return

        config = res["result"]
        views = config.get("views", [])
        
        # Replace or append trail-cams view
        trail_view = build_trail_cams_view()
        found = False
        for idx, v in enumerate(views):
            if v.get("path") == "trail-cams":
                views[idx] = trail_view
                found = True
                break
        
        if not found:
            views.append(trail_view)

        config["views"] = views

        # Save config
        await ws.send(json.dumps({
            "id": 2,
            "type": "lovelace/config/save",
            "url_path": "lovelace-basement",
            "config": config
        }))
        save_res = json.loads(await ws.recv())
        if save_res.get("success"):
            print("Successfully updated Trail Cams dashboard view with GPS and Dropdown Analytics!")
        else:
            print("Failed to save lovelace config:", save_res)

if __name__ == "__main__":
    asyncio.run(update_dashboard())
