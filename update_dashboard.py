#!/usr/bin/env python3
"""
Fully responsive Lovelace view for Stealth Cam Trail Cameras.
Renders responsive columns on Desktop and 1 clean column on Mobile.
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

def make_cam_card(cam):
    slug = cam["slug"]
    name = cam["name"]
    return {
        "type": "custom:vertical-stack-in-card",
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
                    f"var t = entity.attributes.temperature ? ('🌡️ ' + entity.attributes.temperature + '°F  •  ') : ''; "
                    f"var b = entity.attributes.battery_level !== undefined ? ('🔋 ' + entity.attributes.battery_level + '%') : ''; "
                    f"var bucks = states['sensor.stealthcam_{slug}_buck_hits'] ? states['sensor.stealthcam_{slug}_buck_hits'].state : '0'; "
                    f"var buckStr = (bucks && bucks !== '0' && bucks !== 'unknown') ? ('  •  🦌 ' + bucks + ' Buck' + (bucks > 1 ? 's' : '')) : ''; "
                    f"return '🎯 ' + h + buckStr + '<br>' + t + b; "
                    f"]]]"
                ),
                "tap_action": {
                    "action": "url",
                    "url_path": "[[[ return entity.attributes.image_url || '#'; ]]]"
                },
                "styles": {
                    "card": [
                        {"border-radius": "12px 12px 0 0"},
                        {"overflow": "hidden"},
                        {"padding": "0"},
                        {"border": "none"},
                        {"background": "var(--card-background-color, #1c1c1e)"}
                    ],
                    "entity_picture": [
                        {"width": "100%"},
                        {"height": "200px"},
                        {"object-fit": "cover"},
                        {"border-radius": "12px 12px 0 0"},
                        {"background": "#111"}
                    ],
                    "name": [
                        {"font-size": "16px"},
                        {"font-weight": "700"},
                        {"letter-spacing": "0.5px"},
                        {"color": "#fff"},
                        {"padding": "8px 12px 0px 12px"},
                        {"text-align": "left"},
                        {"width": "100%"}
                    ],
                    "label": [
                        {"font-size": "12px"},
                        {"line-height": "1.4"},
                        {"font-weight": "500"},
                        {"color": "#a0a0a0"},
                        {"padding": "2px 12px 8px 12px"},
                        {"text-align": "left"},
                        {"width": "100%"}
                    ]
                }
            },
            {
                "type": "entities",
                "entities": [
                    {
                        "type": "custom:fold-entity-row",
                        "head": {
                            "type": "section",
                            "label": "📍 Stand Intel & GPS (Expand)"
                        },
                        "entities": [
                            {
                                "entity": f"sensor.stealthcam_{slug}_buck_hits",
                                "name": "Verified Buck Hits",
                                "icon": "mdi:deer"
                            },
                            {
                                "entity": f"sensor.stealthcam_{slug}_peak_window",
                                "name": "Peak Movement Window",
                                "icon": "mdi:clock-outline"
                            },
                            {
                                "entity": f"sensor.stealthcam_{slug}_location",
                                "name": "GPS Coordinates & Heading",
                                "icon": "mdi:crosshairs-gps"
                            },
                            {
                                "entity": f"sensor.stealthcam_{slug}_signal",
                                "name": "Cellular Signal Strength",
                                "icon": "mdi:signal-cellular-2"
                            },
                            {
                                "entity": f"sensor.stealthcam_{slug}_sd_free",
                                "name": "SD Card Free",
                                "icon": "mdi:sd"
                            },
                            {
                                "entity": f"sensor.stealthcam_{slug}_last_checkin",
                                "name": "Cellular Sync Time",
                                "icon": "mdi:sync"
                            }
                        ]
                    }
                ]
            }
        ]
    }

def build_trail_cams_view():
    cards = []

    # 1. Hunting Intelligence Summary Card (Responsive markdown)
    cards.append({
        "type": "markdown",
        "title": "🎯 Stand Hunting Intelligence & Wind Matrix",
        "content": (
            "### 🏆 Recommended Stand: **HOMER / MAGGIE RUN**\n"
            "- 🦌 **Recent Antlered Activity:** 2 Verified Buck Hits at Homer Stand\n"
            "- ⏰ **Peak Movement:** Dawn Transitions (04:45 - 07:15 AM)\n"
            "- 🌔 **Moon:** Waxing Crescent | 🌡️ **Field Temp:** ~58°F\n\n"
            "---\n\n"
            "### 🧭 Stand Scent & Wind Direction (Live: 5.0 mph SSW)\n"
            "- 🟢 **Homer (43° NE):** **Favorable** (Headwind • Scent Clear)\n"
            "- 🟢 **Santa's Helper (356° N):** **Favorable** (Headwind • Scent Clear)\n"
            "- 🟢 **Lisa (329° NNW):** **Favorable** (Headwind • Scent Clear)\n"
            "- 🟡 **Maggie (297° WNW):** **Marginal** (Crosswind Draft)\n"
            "- 🟡 **Marge (89° E):** **Marginal** (Crosswind Draft)\n"
            "- 🔴 **Bart (177° S):** **Unfavorable** (Tailwind • Downwind Risk)\n\n"
            "---\n\n"
            "### 📊 Property Movement Distribution (200 Captures)\n"
            "🌅 **Dawn (5-9 AM):** `12%` | ☀️ **Day (9 AM-4 PM):** `21%` | 🌇 **Eve (4-8 PM):** `14%` | 🌙 **Night:** `53%`"
        )
    })

    # 2. Camera Cards (One responsive card per camera)
    for cam in CAMERAS:
        cards.append(make_cam_card(cam))

    # 3. Property Map Card
    cards.append({
        "type": "map",
        "title": "🗺️ Property Camera Locations & Stand GPS",
        "default_zoom": 17,
        "hours_to_show": 1,
        "entities": [
            f"device_tracker.stealthcam_{cam['slug']}" for cam in CAMERAS
        ]
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
        
        # Replace trail-cams view
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
            print("Successfully updated Trail Cams dashboard with responsive desktop/mobile layout!")
        else:
            print("Failed to save lovelace config:", save_res)

if __name__ == "__main__":
    asyncio.run(update_dashboard())
