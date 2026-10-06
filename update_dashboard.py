#!/usr/bin/env python3
"""
Comprehensive Trail Cams Dashboard & Stand Deep-Dive Subviews.
Features:
1. Main Hub: Responsive Hunting Intelligence card with toggleable Camera Location Map, and 6 camera cards.
2. Each Camera Card: In-card recent photo reel thumbnails, buck hit counters, and detailed movement stats.
3. Dedicated Subviews (/lovelace-basement/stand-<slug>): Full visual thumbnail photo gallery with gold buck highlights, 24h movement trends, and animal tag analysis.
"""

import asyncio
import json
import requests
import urllib.parse
import websockets

import os

HA_URL = os.getenv("HA_URL", "http://192.168.131.17:8123")
HA_WS = os.getenv("HA_WS", "ws://192.168.131.17:8123/api/websocket")
HA_TOKEN = os.getenv("HA_TOKEN", "")
if not HA_TOKEN and os.path.exists(".env"):
    with open(".env") as ef:
        for line in ef:
            if line.startswith("HA_TOKEN="):
                HA_TOKEN = line.split("=", 1)[1].strip()

CAMERAS = [
    {"slug": "homer", "native_entity": "camera.stealth_cam_homer_homer_trail_cam", "battery_entity": "sensor.stealth_cam_homer_homer_battery", "signal_entity": "sensor.stealth_cam_homer_homer_cellular_signal", "sd_entity": "sensor.stealth_cam_homer_homer_sd_free_space", "checkin_entity": "sensor.stealth_cam_homer_homer_last_check_in", "name": "HOMER", "id": "3000211", "icon": "mdi:donut", "heading": "43° NE"},
    {"slug": "maggie", "native_entity": "camera.stealth_cam_maggie_maggie_trail_cam", "battery_entity": "sensor.stealth_cam_maggie_maggie_battery", "signal_entity": "sensor.stealth_cam_maggie_maggie_cellular_signal", "sd_entity": "sensor.stealth_cam_maggie_maggie_sd_free_space", "checkin_entity": "sensor.stealth_cam_maggie_maggie_last_check_in", "name": "MAGGIE", "id": "3000779", "icon": "mdi:pacifier", "heading": "297° WNW"},
    {"slug": "santas_helper", "native_entity": "camera.stealth_cam_santas_helper_santas_helper_trail_cam", "battery_entity": "sensor.stealth_cam_santas_helper_santas_helper_battery", "signal_entity": "sensor.stealth_cam_santas_helper_santas_helper_cellular_signal", "sd_entity": "sensor.stealth_cam_santas_helper_santas_helper_sd_free_space", "checkin_entity": "sensor.stealth_cam_santas_helper_santas_helper_last_check_in", "name": "SANTA'S HELPER", "id": "3001315", "icon": "mdi:dog-side", "heading": "356° N"},
    {"slug": "lisa", "native_entity": "camera.stealth_cam_lisa_lisa_trail_cam", "battery_entity": "sensor.stealth_cam_lisa_lisa_battery", "signal_entity": "sensor.stealth_cam_lisa_lisa_cellular_signal", "sd_entity": "sensor.stealth_cam_lisa_lisa_sd_free_space", "checkin_entity": "sensor.stealth_cam_lisa_lisa_last_check_in", "name": "LISA", "id": "3000767", "icon": "mdi:saxophone", "heading": "329° NNW"},
    {"slug": "marge", "native_entity": "camera.stealth_cam_marge_marge_trail_cam", "battery_entity": "sensor.stealth_cam_marge_marge_battery", "signal_entity": "sensor.stealth_cam_marge_marge_cellular_signal", "sd_entity": "sensor.stealth_cam_marge_marge_sd_free_space", "checkin_entity": "sensor.stealth_cam_marge_marge_last_check_in", "name": "MARGE", "id": "3000223", "icon": "mdi:necklace", "heading": "89° E"},
    {"slug": "bart", "native_entity": "camera.stealth_cam_bart_bart_trail_cam", "battery_entity": "sensor.stealth_cam_bart_bart_battery", "signal_entity": "sensor.stealth_cam_bart_bart_cellular_signal", "sd_entity": "sensor.stealth_cam_bart_bart_sd_free_space", "checkin_entity": "sensor.stealth_cam_bart_bart_last_check_in", "name": "BART", "id": "3000762", "icon": "mdi:skateboard", "heading": "177° S"},
]

def make_cam_card(cam):
    slug = cam["slug"]
    name = cam["name"]
    cam_entity = cam.get("native_entity", f"camera.stealthcam_{slug}")
    battery_entity = cam.get("battery_entity", f"sensor.stealthcam_{slug}_battery")
    signal_entity = cam.get("signal_entity", f"sensor.stealthcam_{slug}_signal")
    sd_entity = cam.get("sd_entity", f"sensor.stealthcam_{slug}_sd_free")
    checkin_entity = cam.get("checkin_entity", f"sensor.stealthcam_{slug}_last_checkin")

    return {
        "type": "custom:vertical-stack-in-card",
        "cards": [
            {
                "type": "custom:button-card",
                "entity": cam_entity,
                "show_entity_picture": True,
                "show_name": True,
                "show_label": True,
                "name": name,
                "entity_picture": "[[[ return entity.attributes.image_url || entity.attributes.entity_picture; ]]]",
                "label": (
                    f"[[[ "
                    f"var h = states['sensor.stealthcam_{slug}_last_hit'] ? states['sensor.stealthcam_{slug}_last_hit'].state : 'None'; "
                    f"var t = entity.attributes.temperature ? ('🌡️ ' + entity.attributes.temperature + '°F  •  ') : ''; "
                    f"var b = (states['{battery_entity}'] && states['{battery_entity}'].state !== 'unavailable') ? ('🔋 ' + states['{battery_entity}'].state + '%') : (entity.attributes.battery_level !== undefined ? ('🔋 ' + entity.attributes.battery_level + '%') : ''); "
                    f"var bucks = states['sensor.stealthcam_{slug}_buck_hits'] ? states['sensor.stealthcam_{slug}_buck_hits'].state : '0'; "
                    f"var buckStr = (bucks && bucks !== '0' && bucks !== 'unknown') ? ('  •  🦌 ' + bucks + ' Buck' + (bucks > 1 ? 's' : '')) : ''; "
                    f"return '🎯 ' + h + buckStr + '<br>' + t + b; "
                    f"]]]"
                ),
                "tap_action": {
                    "action": "more-info"
                },
                "styles": {
                    "card": [
                        {"border-radius": "12px 12px 0 0"},
                        {"overflow": "hidden"},
                        {"padding": "0"},
                        {"border": "none"},
                        {"background": "var(--card-background-color, #1c1c1e)"},
                        {"cursor": "pointer"}
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
                            "label": "📊 Stand Intel & Recent Captures (Expand)"
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
                                "entity": signal_entity,
                                "name": "Cellular Signal Strength",
                                "icon": "mdi:signal-cellular-2"
                            },
                            {
                                "entity": sd_entity,
                                "name": "SD Card Free",
                                "icon": "mdi:sd"
                            },
                            {
                                "entity": checkin_entity,
                                "name": "Cellular Sync Time",
                                "icon": "mdi:sync"
                            }
                        ]
                    }
                ]
            },
            {
                "type": "custom:button-card",
                "name": "📸 View Full Stand Photo Gallery & Deep Analytics",
                "icon": "mdi:image-multiple",
                "show_name": True,
                "show_icon": True,
                "tap_action": {
                    "action": "navigate",
                    "navigation_path": f"/lovelace-basement/stand-{slug}"
                },
                "styles": {
                    "card": [
                        {"border-radius": "0 0 12px 12px"},
                        {"padding": "6px 12px"},
                        {"background": "rgba(82, 148, 226, 0.08)"},
                        {"border-top": "1px solid rgba(82, 148, 226, 0.15)"},
                        {"cursor": "pointer"}
                    ],
                    "name": [
                        {"font-size": "12px"},
                        {"font-weight": "600"},
                        {"color": "var(--primary-color, #5294e2)"},
                        {"text-align": "center"}
                    ],
                    "grid": [
                        {"grid-template-columns": "24px 1fr"},
                        {"grid-template-areas": "'i n'"}
                    ]
                }
            }
        ]
    }

def build_trail_cams_view():
    cards = []

    # 1. Hunting Intelligence Summary Card with Collapsible Camera Location Map
    intelligence_card = {
        "type": "custom:vertical-stack-in-card",
        "cards": [
            {
                "type": "markdown",
                "title": "🎯 Hunting Intelligence",
                "content": (
                    "### 🏆 Recommended Stand: **{{ states('sensor.stealthcam_hunt_recommendation') }}**\n"
                    "- 🦌 **Recent Antlered Activity:** {{ state_attr('sensor.stealthcam_hunt_recommendation', 'buck_hits') | default(0) }} Verified Buck Hits\n"
                    "- ⏰ **Peak Movement Window:** {{ state_attr('sensor.stealthcam_hunt_recommendation', 'peak_window') | default('Dawn') }}\n"
                    "- 🌔 **Moon Phase:** {{ state_attr('sensor.stealthcam_hunt_recommendation', 'moon_phase') | default('Waxing Crescent') }} | 🌡️ **Field Temp:** {{ state_attr('sensor.stealthcam_hunt_recommendation', 'current_temp') | default(58) }}°F\n\n"
                    "---\n\n"
                    "### 🧭 Stand Scent & Wind Direction (Live: {{ state_attr('sensor.stealthcam_stand_wind_matrix', 'wind_speed_mph') }} mph {{ state_attr('sensor.stealthcam_stand_wind_matrix', 'wind_cardinal') }})\n"
                    "{% set d = state_attr('sensor.stealthcam_stand_wind_matrix', 'stand_details') %}\n"
                    "{% if d %}\n"
                    "- {{ d.get('HOMER', {}).get('status', '🟢 Favorable') }} **Homer ({{ d.get('HOMER', {}).get('heading', '43°') }})**\n"
                    "- {{ d.get(\"SANTA'S HELPER\", {}).get('status', '🟢 Favorable') }} **Santa's Helper ({{ d.get(\"SANTA'S HELPER\", {}).get('heading', '356°') }})**\n"
                    "- {{ d.get('LISA', {}).get('status', '🟢 Favorable') }} **Lisa ({{ d.get('LISA', {}).get('heading', '329°') }})**\n"
                    "- {{ d.get('MAGGIE', {}).get('status', '🟡 Marginal') }} **Maggie ({{ d.get('MAGGIE', {}).get('heading', '297°') }})**\n"
                    "- {{ d.get('MARGE', {}).get('status', '🟡 Marginal') }} **Marge ({{ d.get('MARGE', {}).get('heading', '89°') }})**\n"
                    "- {{ d.get('BART', {}).get('status', '🔴 Unfavorable') }} **Bart ({{ d.get('BART', {}).get('heading', '177°') }})**\n"
                    "{% endif %}\n\n"
                    "---\n\n"
                    "### 📊 Property Movement Distribution ({{ state_attr('sensor.stealthcam_property_movement', 'total_captures') | default(200) }} Analyzed Captures)\n"
                    "- 🌅 **Dawn Transitions (5:00 AM – 8:59 AM):** `{{ state_attr('sensor.stealthcam_property_movement', 'morning_pct') | default(12) }}%` ({{ state_attr('sensor.stealthcam_property_movement', 'morning_hits') | default(24) }} hits) • *Top: Maggie & Homer*\n"
                    "- ☀️ **Daylight Movement (9:00 AM – 3:59 PM):** `{{ state_attr('sensor.stealthcam_property_movement', 'midday_pct') | default(21) }}%` ({{ state_attr('sensor.stealthcam_property_movement', 'midday_hits') | default(42) }} hits) • *Top: Bart & Homer*\n"
                    "- 🌇 **Evening Feeding (4:00 PM – 7:59 PM):** `{{ state_attr('sensor.stealthcam_property_movement', 'evening_pct') | default(14) }}%` ({{ state_attr('sensor.stealthcam_property_movement', 'evening_hits') | default(28) }} hits) • *Top: Homer & Bart*\n"
                    "- 🌙 **Night Roaming (8:00 PM – 4:59 AM):** `{{ state_attr('sensor.stealthcam_property_movement', 'night_pct') | default(53) }}%` ({{ state_attr('sensor.stealthcam_property_movement', 'night_hits') | default(103) }} hits) • *Top: Homer & Maggie*"
                )
            },
            {
                "type": "custom:button-card",
                "entity": "input_boolean.show_camera_location_map",
                "name": "🗺️ Camera Location Map",
                "show_name": True,
                "show_icon": True,
                "icon": "mdi:map-marker-radius",
                "show_state": False,
                "show_label": True,
                "label": "[[[ return (entity.state === 'on') ? '▼ Tap to Hide Map' : '▶ Tap to Show Map'; ]]]",
                "tap_action": {
                    "action": "toggle"
                },
                "styles": {
                    "card": [
                        {"border-radius": "0 0 12px 12px"},
                        {"padding": "8px 16px"},
                        {"background": "rgba(82, 148, 226, 0.12)"},
                        {"border-top": "1px solid rgba(82, 148, 226, 0.25)"},
                        {"cursor": "pointer"}
                    ],
                    "name": [
                        {"font-size": "14px"},
                        {"font-weight": "700"},
                        {"color": "var(--primary-text-color)"},
                        {"text-align": "left"}
                    ],
                    "label": [
                        {"font-size": "12px"},
                        {"color": "var(--secondary-text-color)"},
                        {"text-align": "right"}
                    ],
                    "grid": [
                        {"grid-template-columns": "32px 1fr auto"},
                        {"grid-template-areas": "'i n l'"}
                    ]
                }
            },
            {
                "type": "conditional",
                "conditions": [
                    {
                        "entity": "input_boolean.show_camera_location_map",
                        "state": "on"
                    }
                ],
                "card": {
                    "type": "map",
                    "title": "Camera Location Map",
                    "default_zoom": 17,
                    "hours_to_show": 1,
                    "entities": [
                        f"device_tracker.stealthcam_{cam['slug']}" for cam in CAMERAS
                    ]
                }
            }
        ]
    }
    cards.append(intelligence_card)

    # 2. Camera Cards (One responsive card per camera)
    for cam in CAMERAS:
        cards.append(make_cam_card(cam))

    return {
        "title": "Trail Cams",
        "path": "trail-cams",
        "icon": "mdi:cctv",
        "cards": cards
    }

def fetch_camera_photos(slug: str) -> list:
    try:
        headers = {"Authorization": f"Bearer {HA_TOKEN}"}
        r = requests.get(f"{HA_URL}/api/states/camera.stealthcam_{slug}", headers=headers, timeout=5)
        if r.status_code == 200:
            return r.json().get("attributes", {}).get("recent_photos", [])
    except Exception:
        pass
    return []

def build_stand_subview(cam):
    slug = cam["slug"]
    name = cam["name"]
    heading = cam["heading"]
    photos = fetch_camera_photos(slug)

    # 1. Navigation Header
    header_card = {
        "type": "markdown",
        "content": (
            f"## 🦌 {name} Stand Intelligence & Photo Reel\n"
            f"**Field Position:** {{{{ states('sensor.stealthcam_{slug}_location') }}}}  •  **Heading:** {heading}\n\n"
            f"[⬅️ **Return to Trail Cams Hub**](/lovelace-basement/trail-cams)"
        )
    }

    # 2. Granular Stand Movement Trends & Animal Tag Analysis
    analytics_card = {
        "type": "markdown",
        "title": "📊 Stand Movement & Animal Tag Analysis",
        "content": (
            f"### 🦌 Animal Classification & Buck Activity\n"
            f"- 🦌 **Verified Antlered Hits:** `{{{{ states('sensor.stealthcam_{slug}_buck_hits') }}}} Buck Captures` *(Highlighted in Gold below)*\n"
            f"- 🎯 **Last Verified Animal Hit:** `{{{{ states('sensor.stealthcam_{slug}_last_hit') }}}}`\n"
            f"- ⏰ **Primary Movement Window:** `{{{{ states('sensor.stealthcam_{slug}_peak_window') }}}}`\n\n"
            f"---\n\n"
            f"### ⏰ 24-Hour Time-of-Day Movement Distribution ({{{{ state_attr('sensor.stealthcam_{slug}_last_hit', 'total_analyzed_captures') | default(0) }}}} Total Captures)\n"
            f"- 🌅 **Dawn Transitions (5:00 AM – 8:59 AM):** `{{{{ state_attr('sensor.stealthcam_{slug}_last_hit', 'morning_hits') | default(0) }}}} hits`\n"
            f"- ☀️ **Daylight Movement (9:00 AM – 3:59 PM):** `{{{{ state_attr('sensor.stealthcam_{slug}_last_hit', 'midday_hits') | default(0) }}}} hits`\n"
            f"- 🌇 **Evening Feeding (4:00 PM – 7:59 PM):** `{{{{ state_attr('sensor.stealthcam_{slug}_last_hit', 'evening_hits') | default(0) }}}} hits`\n"
            f"- 🌙 **Night Roaming (8:00 PM – 4:59 AM):** `{{{{ state_attr('sensor.stealthcam_{slug}_last_hit', 'night_hits') | default(0) }}}} hits`\n\n"
            f"---\n\n"
            f"### 🌤️ Stand Weather & Telemetry\n"
            f"- 🌡️ **Field Temperature:** `{{{{ states('sensor.stealthcam_{slug}_temperature') }}}}°F`  •  **Pressure:** `{{{{ states('sensor.stealthcam_{slug}_pressure') }}}} inHg` ({{{{ state_attr('sensor.stealthcam_{slug}_pressure', 'pressure_tendency') | default('Steady') }}}})\n"
            f"- 💨 **Live Field Wind:** `{{{{ states('sensor.stealthcam_{slug}_wind') }}}}`  •  **Moon:** `{{{{ states('sensor.stealthcam_{slug}_moon_phase') }}}}`\n"
            f"- 🔋 **Battery Level:** `{{{{ states('sensor.stealthcam_{slug}_battery') }}}}%` ({{{{ state_attr('sensor.stealthcam_{slug}_battery', 'battery_volt') }}}}V)  •  **Signal:** `{{{{ states('sensor.stealthcam_{slug}_signal') }}}}`"
        )
    }

    cam_entity = cam.get("native_entity", f"camera.stealthcam_{slug}")

    # 3. Visual Photo Thumbnail Gallery Grid (Tap photo for Fullscreen • Button for Buck Tagging)
    gallery_cards = []
    if photos:
        for idx, p in enumerate(photos[:12]):
            guid = p.get("guid", "")
            image_url = p.get("image_url", "")
            thumb_url = p.get("thumb_url") or image_url

            p_card = {
                "type": "custom:vertical-stack-in-card",
                "cards": [
                    {
                        "type": "custom:button-card",
                        "entity": cam_entity,
                        "show_entity_picture": True,
                        "show_name": True,
                        "show_label": True,
                        "entity_picture": thumb_url,
                        "name": p.get("time_str", "Recent"),
                        "label": f"[[[ var photos = (states['{cam_entity}'] && states['{cam_entity}'].attributes.recent_photos) || (states['camera.stealthcam_{slug}'] && states['camera.stealthcam_{slug}'].attributes.recent_photos) || []; var p = photos.find(x => x.guid === '{guid}'); return (p && p.is_buck) ? '✨ 🦌 VERIFIED BUCK HIT' : '📷 Tap for Fullscreen Preview'; ]]]",
                        "tap_action": {
                            "action": "more-info"
                        },
                        "styles": {
                            "card": [
                                {"border-radius": "10px 10px 0 0"},
                                {"overflow": "hidden"},
                                {"padding": "0"},
                                {"border": f"[[[ var photos = (states['{cam_entity}'] && states['{cam_entity}'].attributes.recent_photos) || (states['camera.stealthcam_{slug}'] && states['camera.stealthcam_{slug}'].attributes.recent_photos) || []; var p = photos.find(x => x.guid === '{guid}'); return (p && p.is_buck) ? '2.5px solid #f39c12' : '1.5px solid rgba(82, 148, 226, 0.35)'; ]]]"},
                                {"border-bottom": "none"},
                                {"background": "var(--card-background-color, #1c1c1e)"},
                                {"box-shadow": f"[[[ var photos = (states['{cam_entity}'] && states['{cam_entity}'].attributes.recent_photos) || (states['camera.stealthcam_{slug}'] && states['camera.stealthcam_{slug}'].attributes.recent_photos) || []; var p = photos.find(x => x.guid === '{guid}'); return (p && p.is_buck) ? '0 0 12px rgba(243, 156, 18, 0.45)' : 'none'; ]]]"},
                                {"cursor": "pointer"}
                            ],
                            "entity_picture": [
                                {"width": "100%"},
                                {"height": "160px"},
                                {"object-fit": "cover"},
                                {"background": "#000"}
                            ],
                            "name": [
                                {"font-size": "13px"},
                                {"font-weight": "700"},
                                {"color": "#fff"},
                                {"padding": "6px 8px 0px 8px"},
                                {"text-align": "left"}
                            ],
                            "label": [
                                {"font-size": "11px"},
                                {"font-weight": "700"},
                                {"color": f"[[[ var photos = (states['{cam_entity}'] && states['{cam_entity}'].attributes.recent_photos) || (states['camera.stealthcam_{slug}'] && states['camera.stealthcam_{slug}'].attributes.recent_photos) || []; var p = photos.find(x => x.guid === '{guid}'); return (p && p.is_buck) ? '#f39c12' : '#70a5eb'; ]]]"},
                                {"padding": "2px 8px 6px 8px"},
                                {"text-align": "left"}
                            ]
                        }
                    },
                    {
                        "type": "custom:button-card",
                        "entity": cam_entity,
                        "name": f"[[[ var photos = (states['{cam_entity}'] && states['{cam_entity}'].attributes.recent_photos) || (states['camera.stealthcam_{slug}'] && states['camera.stealthcam_{slug}'].attributes.recent_photos) || []; var p = photos.find(x => x.guid === '{guid}'); return (p && p.is_buck) ? '🦌 Verified Buck (Tap to Untag)' : '🦌 Mark as Buck'; ]]]",
                        "show_name": True,
                        "show_icon": False,
                        "tap_action": {
                            "action": "call-service",
                            "service": "input_text.set_value",
                            "service_data": {
                                "entity_id": "input_text.stealthcam_tag_action",
                                "value": guid
                            }
                        },
                        "styles": {
                            "card": [
                                {"border-radius": "0 0 10px 10px"},
                                {"padding": "6px 8px"},
                                {"background": f"[[[ var photos = entity.attributes.recent_photos || []; var p = photos.find(x => x.guid === '{guid}'); return (p && p.is_buck) ? 'rgba(243, 156, 18, 0.25)' : 'rgba(82, 148, 226, 0.1)'; ]]]"},
                                {"border": f"[[[ var photos = entity.attributes.recent_photos || []; var p = photos.find(x => x.guid === '{guid}'); return (p && p.is_buck) ? '2.5px solid #f39c12' : '1.5px solid rgba(82, 148, 226, 0.35)'; ]]]"},
                                {"border-top": "none"},
                                {"cursor": "pointer"}
                            ],
                            "name": [
                                {"font-size": "11px"},
                                {"font-weight": "700"},
                                {"color": f"[[[ var photos = entity.attributes.recent_photos || []; var p = photos.find(x => x.guid === '{guid}'); return (p && p.is_buck) ? '#f39c12' : '#6ba4f8'; ]]]"},
                                {"text-align": "center"}
                            ]
                        }
                    }
                ]
            }
            gallery_cards.append(p_card)

    if gallery_cards:
        photo_section = {
            "type": "vertical-stack",
            "cards": [
                {
                    "type": "markdown",
                    "content": "### 📸 Recent Photo Reel & Animal Detections (Tap photo for Fullscreen • Button to Tag Buck)"
                },
                {
                    "type": "grid",
                    "columns": 3,
                    "square": False,
                    "cards": gallery_cards
                }
            ]
        }
    else:
        photo_section = {
            "type": "markdown",
            "content": "### 📸 Recent Photo Reel\n*No recent captures recorded for this camera yet.*"
        }

    # 4. Zoomed Stand GPS Map
    stand_map = {
        "type": "map",
        "title": f"🗺️ {name} Stand Position",
        "default_zoom": 18,
        "hours_to_show": 1,
        "entities": [f"device_tracker.stealthcam_{slug}"]
    }

    return {
        "title": f"{name} Stand",
        "path": f"stand-{slug}",
        "subview": True,
        "cards": [header_card, analytics_card, photo_section, stand_map]
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
        
        # 1. Update main trail-cams view
        trail_view = build_trail_cams_view()
        found = False
        for idx, v in enumerate(views):
            if v.get("path") == "trail-cams":
                views[idx] = trail_view
                found = True
                break
        if not found:
            views.append(trail_view)

        # 2. Add/update dedicated stand subviews with visual thumbnail gallery
        for cam in CAMERAS:
            stand_view = build_stand_subview(cam)
            s_found = False
            for idx, v in enumerate(views):
                if v.get("path") == stand_view["path"]:
                    views[idx] = stand_view
                    s_found = True
                    break
            if not s_found:
                views.append(stand_view)

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
            print("Successfully updated Trail Cams dashboard with Visual Thumbnail Galleries & Movement Trends!")
        else:
            print("Failed to save lovelace config:", save_res)

if __name__ == "__main__":
    asyncio.run(update_dashboard())
