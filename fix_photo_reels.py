#!/usr/bin/env python3
"""Fix and update all Stealth Cam subviews in Home Assistant with dynamic photo reels."""

import asyncio
import json
import re
import websockets

HA_WS = "ws://192.168.131.17:8123/api/websocket"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJmMWUzMzA5ODZkYzQ0YWJiYWM4NmU5OGIxMTJiZDNiNSIsImlhdCI6MTc5MDk3MTMwMiwiZXhwIjoyMTA2MzMxMzAyfQ.wkyHRjBsBKiaEMbXmz_nyGreKnLtwiTTCGuxADaVeqs"

CAMERAS = [
    {
        "slug": "homer",
        "name": "HOMER",
        "emoji": "🍩",
        "heading": "43° NE",
        "icon": "mdi:donut",
    },
    {
        "slug": "maggie",
        "name": "MAGGIE",
        "emoji": "👶",
        "heading": "297° WNW",
        "icon": "mdi:pacifier",
    },
    {
        "slug": "santas_helper",
        "name": "SANTA'S HELPER",
        "emoji": "🐕",
        "heading": "356° N",
        "icon": "mdi:dog-side",
    },
    {
        "slug": "lisa",
        "name": "LISA",
        "emoji": "🎷",
        "heading": "329° NNW",
        "icon": "mdi:saxophone",
    },
    {
        "slug": "marge",
        "name": "MARGE",
        "emoji": "📿",
        "heading": "89° E",
        "icon": "mdi:necklace",
    },
    {
        "slug": "bart",
        "name": "BART",
        "emoji": "🛹",
        "heading": "177° S",
        "icon": "mdi:skateboard",
    },
]


def make_filter_bar():
    filter_options = [
        {"name": "All", "val": "All", "sub": "All"},
        {"name": "🦌 Bucks", "val": "Bucks", "sub": "Gold"},
        {"name": "🐾 Does", "val": "Does", "sub": "Blue"},
        {"name": "👤 Person", "val": "Person", "sub": "Alert"},
        {"name": "🌅 Dawn", "val": "Dawn", "sub": "5–9 AM"},
        {"name": "☀️ Midday", "val": "Midday", "sub": "9 AM–4 PM"},
        {"name": "🌇 Evening", "val": "Evening", "sub": "4–8 PM"},
        {"name": "🌙 Night", "val": "Night", "sub": "8 PM–5 AM"},
    ]
    buttons = []
    for opt in filter_options:
        val = opt["val"]
        btn = {
            "type": "custom:button-card",
            "entity": "input_select.stealthcam_photo_filter",
            "name": opt["name"],
            "label": opt["sub"],
            "show_name": True,
            "show_label": True,
            "show_icon": False,
            "tap_action": {
                "action": "call-service",
                "service": "input_select.select_option",
                "service_data": {
                    "entity_id": "input_select.stealthcam_photo_filter",
                    "option": val,
                },
            },
            "styles": {
                "card": [
                    {"border-radius": "8px"},
                    {"padding": "8px 2px"},
                    {
                        "background": f"[[[ return (states['input_select.stealthcam_photo_filter'] && states['input_select.stealthcam_photo_filter'].state === '{val}') ? 'rgba(82, 148, 226, 0.35)' : 'rgba(255, 255, 255, 0.05)'; ]]]"
                    },
                    {
                        "border": f"[[[ return (states['input_select.stealthcam_photo_filter'] && states['input_select.stealthcam_photo_filter'].state === '{val}') ? '2px solid var(--primary-color, #5294e2)' : '1px solid rgba(255, 255, 255, 0.1)'; ]]]"
                    },
                    {"cursor": "pointer"},
                    {"transition": "all 0.2s ease"},
                ],
                "name": [
                    {"font-size": "11px"},
                    {"font-weight": "700"},
                    {
                        "color": f"[[[ return (states['input_select.stealthcam_photo_filter'] && states['input_select.stealthcam_photo_filter'].state === '{val}') ? '#ffffff' : 'rgba(255, 255, 255, 0.85)'; ]]]"
                    },
                    {"text-align": "center"},
                ],
                "label": [
                    {"font-size": "9px"},
                    {"font-weight": "500"},
                    {
                        "color": f"[[[ return (states['input_select.stealthcam_photo_filter'] && states['input_select.stealthcam_photo_filter'].state === '{val}') ? '#70a5eb' : 'rgba(255, 255, 255, 0.45)'; ]]]"
                    },
                    {"text-align": "center"},
                    {"margin-top": "2px"},
                ],
            },
        }
        buttons.append(btn)

    return {
        "type": "custom:layout-card",
        "layout_type": "custom:grid-layout",
        "layout": {
            "grid-template-columns": "repeat(8, 1fr)",
            "grid-gap": "4px",
            "margin": "0px",
            "mediaquery": {
                "(max-width: 950px)": {
                    "grid-template-columns": "repeat(4, 1fr)",
                    "grid-gap": "6px",
                }
            },
        },
        "cards": buttons,
    }


def build_dynamic_photo_card(slug: str, idx: int):
    photo_entity = f"camera.stealth_cam_{slug}_{slug}_photo_{idx + 1}"
    cam_entity = f"camera.stealth_cam_{slug}_{slug}_trail_cam"
    buck_entity = f"sensor.stealth_cam_{slug}_{slug}_positive_buck_hits"

    filter_js = f"var e = states['{photo_entity}']; if (!e || !e.attributes || (!e.attributes.image_url && !e.attributes.thumbnail_url)) return 'none'; var f = states['input_select.stealthcam_photo_filter'] ? states['input_select.stealthcam_photo_filter'].state : 'All'; var t = e.attributes.tag || ''; var b = e.attributes.is_buck; var d = e.attributes.is_doe; var p = e.attributes.is_person; var h = e.attributes.hour || 0; if (f === 'Bucks' && !(b || t === 'buck')) return 'none'; if (f === 'Does' && !(d || t === 'doe')) return 'none'; if (f === 'Person' && !(p || t === 'person')) return 'none'; if (f === 'Dawn' && !(h >= 5 && h < 9)) return 'none'; if (f === 'Midday' && !(h >= 9 && h < 17)) return 'none'; if (f === 'Evening' && !(h >= 17 && h < 21)) return 'none'; if (f === 'Night' && !(h >= 21 || h < 5)) return 'none'; return 'block';"

    return {
        "type": "custom:vertical-stack-in-card",
        "card_mod": {
            "style": f"""
                :host, ha-card {{
                  border-radius: 12px !important;
                  overflow: hidden !important;
                  {{% set e = '{photo_entity}' %}}
                  {{% set tag = state_attr(e, 'tag') | default('') %}}
                  {{% set is_buck = state_attr(e, 'is_buck') | default(false) %}}
                  {{% set is_doe = state_attr(e, 'is_doe') | default(false) %}}
                  {{% set is_person = state_attr(e, 'is_person') | default(false) %}}
                  {{% if is_buck or tag == 'buck' %}}
                    border: 3px solid #f39c12 !important;
                    box-shadow: 0 0 16px rgba(243, 156, 18, 0.6) !important;
                  {{% elif is_doe or tag == 'doe' %}}
                    border: 3px solid #3498db !important;
                    box-shadow: 0 0 16px rgba(52, 152, 219, 0.6) !important;
                  {{% elif is_person or tag == 'person' %}}
                    border: 3px solid #e74c3c !important;
                    box-shadow: 0 0 16px rgba(231, 76, 60, 0.7) !important;
                  {{% else %}}
                    border: 1.5px solid rgba(82, 148, 226, 0.3) !important;
                  {{% endif %}}
                }}
            """
        },
        "cards": [
            {
                "type": "custom:button-card",
                "entity": photo_entity,
                "triggers_update": [photo_entity, cam_entity, buck_entity, "input_select.stealthcam_photo_filter"],
                "show_entity_picture": True,
                "show_name": True,
                "show_label": True,
                "entity_picture": f"[[[ return states['{photo_entity}'] ? (states['{photo_entity}'].attributes.entity_picture || states['{photo_entity}'].attributes.thumbnail_url || states['{photo_entity}'].attributes.image_url) : ''; ]]]",
                "name": f"[[[ var e = states['{photo_entity}']; if (!e || !e.attributes) return 'Photo {idx + 1}'; var t = e.attributes.time_str || e.attributes.friendly_name || 'Photo {idx + 1}'; return t + (e.attributes.is_hd ? ' 💎' : ''); ]]]",
                "label": f"""[[[
                  var e = states['{photo_entity}'];
                  if (!e || !e.attributes) return '';
                  var tag = e.attributes.tag || '';
                  var score = e.attributes.buck_score ? (' (' + e.attributes.buck_score + (String(e.attributes.buck_score).includes('PT') ? '' : '\"') + ')') : '';
                  var hd = e.attributes.is_hd ? ' 💎 HD' : '';
                  if (e.attributes.is_buck || tag === 'buck') return '✨ VERIFIED BUCK' + score + hd;
                  if (e.attributes.is_doe || tag === 'doe') return '🦌 VERIFIED DOE' + hd;
                  if (e.attributes.is_person || tag === 'person') return '🚨 👤 HUMAN ACTIVITY' + hd;
                  return (e.attributes.is_hd ? '💎 HD Photo • Tap to View' : '🔍 Tap for Photo');
                ]]]""",
                "tap_action": {"action": "more-info"},
                "hold_action": {
                    "action": "call-service",
                    "service": "stealthcam_command.request_hd",
                    "service_data": {
                        "guid": f"[[[ var e = states['{photo_entity}']; return (e && e.attributes.guid) ? e.attributes.guid : ''; ]]]"
                    },
                },
                "styles": {
                    "card": [
                        {"border-radius": "10px 10px 0 0"},
                        {"overflow": "hidden"},
                        {"padding": "0"},
                        {"border": "none"},
                        {"background": "var(--card-background-color, #1c1c1e)"},
                        {"cursor": "pointer"},
                        {"display": f"[[[ {filter_js} ]]]"},
                    ],
                    "entity_picture": [
                        {"width": "100%"},
                        {"height": "160px"},
                        {"object-fit": "cover"},
                        {"background": "#000"},
                        {"cursor": "pointer"},
                    ],
                    "name": [
                        {"font-size": "13px"},
                        {"font-weight": "700"},
                        {"color": "#fff"},
                        {"padding": "6px 8px 0px 8px"},
                        {"text-align": "left"},
                    ],
                    "label": [
                        {"font-size": "11px"},
                        {"font-weight": "700"},
                        {
                            "color": f"""[[[
                              var e = states['{photo_entity}'];
                              if (!e || !e.attributes) return '#70a5eb';
                              var tag = e.attributes.tag || '';
                              if (e.attributes.is_buck || tag === 'buck') return '#f39c12';
                              if (e.attributes.is_doe || tag === 'doe') return '#3498db';
                              if (e.attributes.is_person || tag === 'person') return '#e74c3c';
                              return '#70a5eb';
                            ]]]"""
                        },
                        {"padding": "2px 8px 6px 8px"},
                        {"text-align": "left"},
                    ],
                },
            },
            {
                "type": "grid",
                "columns": 4,
                "square": False,
                "cards": [
                    # 1. Buck Tag
                    {
                        "type": "custom:button-card",
                        "entity": photo_entity,
                        "triggers_update": [photo_entity, "input_select.stealthcam_photo_filter"],
                        "name": "🦌",
                        "tooltip": "Tag as Verified Buck (Gold)",
                        "show_name": True,
                        "show_icon": False,
                        "tap_action": {
                            "action": "call-service",
                            "service": "stealthcam_command.tag_buck",
                            "service_data": {
                                "guid": f"[[[ var e = states['{photo_entity}']; return (e && e.attributes.guid) ? e.attributes.guid : ''; ]]]"
                            },
                        },
                        "styles": {
                            "card": [
                                {"border-radius": "0 0 0 10px"},
                                {"padding": "6px 0"},
                                {"height": "34px"},
                                {
                                    "background": f"[[[ var e = states['{photo_entity}']; var tag = (e && e.attributes.tag) ? e.attributes.tag : ''; return (e && (e.attributes.is_buck || tag === 'buck')) ? 'rgba(243, 156, 18, 0.35)' : 'rgba(255, 255, 255, 0.05)'; ]]]"
                                },
                                {
                                    "border": f"[[[ var e = states['{photo_entity}']; var tag = (e && e.attributes.tag) ? e.attributes.tag : ''; return (e && (e.attributes.is_buck || tag === 'buck')) ? '1.5px solid #f39c12' : '1px solid rgba(255, 255, 255, 0.1)'; ]]]"
                                },
                                {"border-top": "none"},
                                {"cursor": "pointer"},
                                {"display": f"[[[ {filter_js} ]]]"},
                            ],
                            "name": [{"font-size": "15px"}, {"line-height": "1"}, {"text-align": "center"}],
                        },
                    },
                    # 2. Doe Tag
                    {
                        "type": "custom:button-card",
                        "entity": photo_entity,
                        "triggers_update": [photo_entity, "input_select.stealthcam_photo_filter"],
                        "name": "🐾",
                        "tooltip": "Tag as Verified Doe (Blue)",
                        "show_name": True,
                        "show_icon": False,
                        "tap_action": {
                            "action": "call-service",
                            "service": "stealthcam_command.tag_doe",
                            "service_data": {
                                "guid": f"[[[ var e = states['{photo_entity}']; return (e && e.attributes.guid) ? e.attributes.guid : ''; ]]]"
                            },
                        },
                        "styles": {
                            "card": [
                                {"border-radius": "0"},
                                {"padding": "6px 0"},
                                {"height": "34px"},
                                {
                                    "background": f"[[[ var e = states['{photo_entity}']; var tag = (e && e.attributes.tag) ? e.attributes.tag : ''; return (e && (e.attributes.is_doe || tag === 'doe')) ? 'rgba(52, 152, 219, 0.35)' : 'rgba(255, 255, 255, 0.05)'; ]]]"
                                },
                                {
                                    "border": f"[[[ var e = states['{photo_entity}']; var tag = (e && e.attributes.tag) ? e.attributes.tag : ''; return (e && (e.attributes.is_doe || tag === 'doe')) ? '1.5px solid #3498db' : '1px solid rgba(255, 255, 255, 0.1)'; ]]]"
                                },
                                {"border-top": "none"},
                                {"cursor": "pointer"},
                                {"display": f"[[[ {filter_js} ]]]"},
                            ],
                            "name": [{"font-size": "15px"}, {"line-height": "1"}, {"text-align": "center"}],
                        },
                    },
                    # 3. Person Tag
                    {
                        "type": "custom:button-card",
                        "entity": photo_entity,
                        "triggers_update": [photo_entity, "input_select.stealthcam_photo_filter"],
                        "name": "👤",
                        "tooltip": "Flag Human Activity (Red Alert)",
                        "show_name": True,
                        "show_icon": False,
                        "tap_action": {
                            "action": "call-service",
                            "service": "stealthcam_command.tag_person",
                            "service_data": {
                                "guid": f"[[[ var e = states['{photo_entity}']; return (e && e.attributes.guid) ? e.attributes.guid : ''; ]]]"
                            },
                        },
                        "styles": {
                            "card": [
                                {"border-radius": "0"},
                                {"padding": "6px 0"},
                                {"height": "34px"},
                                {
                                    "background": f"[[[ var e = states['{photo_entity}']; var tag = (e && e.attributes.tag) ? e.attributes.tag : ''; return (e && (e.attributes.is_person || tag === 'person')) ? 'rgba(231, 76, 60, 0.35)' : 'rgba(255, 255, 255, 0.05)'; ]]]"
                                },
                                {
                                    "border": f"[[[ var e = states['{photo_entity}']; var tag = (e && e.attributes.tag) ? e.attributes.tag : ''; return (e && (e.attributes.is_person || tag === 'person')) ? '1.5px solid #e74c3c' : '1px solid rgba(255, 255, 255, 0.1)'; ]]]"
                                },
                                {"border-top": "none"},
                                {"cursor": "pointer"},
                                {"display": f"[[[ {filter_js} ]]]"},
                            ],
                            "name": [{"font-size": "15px"}, {"line-height": "1"}, {"text-align": "center"}],
                        },
                    },
                    # 4. Request HD
                    {
                        "type": "custom:button-card",
                        "entity": photo_entity,
                        "triggers_update": [photo_entity, "input_select.stealthcam_photo_filter"],
                        "name": "💎",
                        "tooltip": "💎 Request Full-Res HD Photo from Camera",
                        "show_name": True,
                        "show_icon": False,
                        "tap_action": {
                            "action": "call-service",
                            "service": "stealthcam_command.request_hd",
                            "service_data": {
                                "guid": f"[[[ var e = states['{photo_entity}']; return (e && e.attributes.guid) ? e.attributes.guid : ''; ]]]"
                            },
                        },
                        "styles": {
                            "card": [
                                {"border-radius": "0 0 10px 0"},
                                {"padding": "6px 0"},
                                {"height": "34px"},
                                {
                                    "background": f"[[[ var e = states['{photo_entity}']; return (e && e.attributes && e.attributes.is_hd) ? 'rgba(0, 210, 255, 0.35)' : 'rgba(255, 255, 255, 0.05)'; ]]]"
                                },
                                {
                                    "border": f"[[[ var e = states['{photo_entity}']; return (e && e.attributes && e.attributes.is_hd) ? '1.5px solid #00d2ff' : '1px solid rgba(255, 255, 255, 0.1)'; ]]]"
                                },
                                {"border-top": "none"},
                                {"cursor": "pointer"},
                                {"display": f"[[[ {filter_js} ]]]"},
                            ],
                            "name": [{"font-size": "15px"}, {"line-height": "1"}, {"text-align": "center"}],
                        },
                    },
                ],
            },
        ],
    }


def build_stand_subview(cam: dict):
    slug = cam["slug"]
    name = cam["name"]
    heading = cam["heading"]

    cam_entity = f"camera.stealth_cam_{slug}_{slug}_trail_cam"
    battery_entity = f"sensor.stealth_cam_{slug}_{slug}_battery"
    signal_entity = f"sensor.stealth_cam_{slug}_{slug}_cellular_signal"
    last_hit_entity = f"sensor.stealth_cam_{slug}_{slug}_last_animal_hit"
    buck_entity = f"sensor.stealth_cam_{slug}_{slug}_positive_buck_hits"
    doe_entity = f"sensor.stealth_cam_{slug}_{slug}_verified_doe_hits"
    person_entity = f"sensor.stealth_cam_{slug}_{slug}_human_activity_detections"
    peak_entity = f"sensor.stealth_cam_{slug}_{slug}_peak_movement_window"
    location_entity = f"sensor.stealth_cam_{slug}_{slug}_stand_location"
    temp_entity = f"sensor.stealth_cam_{slug}_{slug}_field_temperature"
    pressure_entity = f"sensor.stealth_cam_{slug}_{slug}_barometric_pressure"
    wind_entity = f"sensor.stealth_cam_{slug}_{slug}_field_wind"
    moon_entity = f"sensor.stealth_cam_{slug}_{slug}_moon_phase"

    # 1. Navigation Header
    header_card = {
        "type": "markdown",
        "content": (
            f"## {cam.get('emoji', '🦌')} {name} Camera\n"
            f"**Position:** {{{{ states('{location_entity}') }}}}  •  **Heading:** {heading}\n\n"
            f"🔄 **HA Cloud Sync:** `{{{{ states('sensor.stealthcam_last_cloud_sync') }}}}` (Auto-syncs every 5m)  •  [⬅️ Return to Trail Cams](/lovelace-basement/trail-cams)"
        ),
    }

    # 2. Activity & Trends
    analytics_card = {
        "type": "markdown",
        "title": "📊 Activity & Trends",
        "content": (
            f"### 🦌 Deer & Wildlife Intelligence\n"
            f"- 🦌 <b style=\"color: #f39c12;\">Verified Bucks:</b> `{{{{ states('{buck_entity}') | int(state_attr('{last_hit_entity}', 'buck_hits_count') | default(0, true)) }}}} hits`\n"
            f"- 🐾 <b style=\"color: #3498db;\">Verified Does:</b> `{{{{ states('{doe_entity}') | int(state_attr('{last_hit_entity}', 'doe_hits_count') | default(0, true)) }}}} hits`\n"
            f"- 🚨 <b style=\"color: #e74c3c;\">Human Activity:</b> `{{{{ states('{person_entity}') | int(state_attr('{last_hit_entity}', 'person_hits_count') | default(0, true)) }}}} detections`\n"
            f"- 🎯 **Last Hit:** `{{{{ states('{last_hit_entity}') }}}}`\n"
            f"- ⏰ **Peak Window:** `{{{{ states('{peak_entity}') }}}}`\n\n"
            f"---\n\n"
            f"### ⏱️ 24-Hour Movement ({{{{ state_attr('{last_hit_entity}', 'captures_24h') | int(0) }}}} Captures • {{{{ state_attr('{last_hit_entity}', 'buck_hits_24h') | int(0) }}}} Bucks • {{{{ state_attr('{last_hit_entity}', 'doe_hits_24h') | int(0) }}}} Does)\n"
            f"- 🌅 **Dawn (5–9 AM):** `{{{{ state_attr('{last_hit_entity}', 'morning_24h') | int(0) }}}} hits`\n"
            f"- ☀️ **Midday (9 AM–4 PM):** `{{{{ state_attr('{last_hit_entity}', 'midday_24h') | int(0) }}}} hits`\n"
            f"- 🌇 **Evening (4–8 PM):** `{{{{ state_attr('{last_hit_entity}', 'evening_24h') | int(0) }}}} hits`\n"
            f"- 🌙 **Night (8 PM–5 AM):** `{{{{ state_attr('{last_hit_entity}', 'night_24h') | int(0) }}}} hits`\n\n"
            f"---\n\n"
            f"### 📊 All-Time Movement ({{{{ state_attr('{last_hit_entity}', 'total_analyzed_captures') | default(0) }}}} Captures)\n"
            f"- 🌅 **Dawn (5–9 AM):** `{{{{ state_attr('{last_hit_entity}', 'morning_hits') | default(0) }}}} hits`\n"
            f"- ☀️ **Midday (9 AM–4 PM):** `{{{{ state_attr('{last_hit_entity}', 'midday_hits') | default(0) }}}} hits`\n"
            f"- 🌇 **Evening (4–8 PM):** `{{{{ state_attr('{last_hit_entity}', 'evening_hits') | default(0) }}}} hits`\n"
            f"- 🌙 **Night (8 PM–5 AM):** `{{{{ state_attr('{last_hit_entity}', 'night_hits') | default(0) }}}} hits`\n\n"
            f"---\n\n"
            f"### 🌤️ Weather & Status\n"
            f"- 🌡️ **Temp:** `{{{{ states('{temp_entity}') }}}}°F`  •  **Baro:** `{{{{ states('{pressure_entity}') }}}} inHg` ({{{{ state_attr('{pressure_entity}', 'pressure_tendency') | default('Steady') }}}})\n"
            f"- 💨 **Wind:** `{{{{ states('{wind_entity}') }}}}`  •  **Moon:** `{{{{ states('{moon_entity}') }}}}`\n"
            f"- 🔋 **Battery:** `{{{{ states('{battery_entity}') }}}}%` ({{{{ state_attr('{battery_entity}', 'battery_volt') }}}}V)  •  **Signal:** `{{{{ states('{signal_entity}') }}}}`"
        ),
    }

    # 3. Visual Photo Gallery (Full 36 Dynamic Cards)
    gallery_cards = [build_dynamic_photo_card(slug, i) for i in range(36)]

    # 4. Zoomed Camera GPS Map
    camera_map = {
        "type": "map",
        "title": f"🗺️ {name} Camera Position",
        "default_zoom": 18,
        "hours_to_show": 1,
        "entities": [location_entity],
    }

    # Left Column
    left_column = {
        "type": "vertical-stack",
        "cards": [header_card, analytics_card, camera_map],
    }

    # Right Column
    right_column = {
        "type": "vertical-stack",
        "cards": [
            {
                "type": "markdown",
                "content": f"### 📸 Photo Reel (Latest 36 Captures)\n*Live feed directly connected to {name} camera stream*",
            },
            make_filter_bar(),
            {
                "type": "custom:layout-card",
                "layout_type": "custom:grid-layout",
                "layout": {
                    "grid-template-columns": "repeat(3, 1fr)",
                    "grid-gap": "12px",
                    "margin": "0px",
                    "mediaquery": {
                        "(max-width: 950px)": {
                            "grid-template-columns": "repeat(2, 1fr)",
                            "grid-gap": "8px",
                        }
                    },
                },
                "cards": gallery_cards,
            },
        ],
    }

    return {
        "title": f"{name} Camera",
        "path": f"stand-{slug}",
        "icon": cam.get("icon", "mdi:cctv"),
        "subview": True,
        "type": "custom:grid-layout",
        "layout": {
            "grid-template-columns": "380px 1fr",
            "grid-gap": "16px",
            "mediaquery": {"(max-width: 950px)": {"grid-template-columns": "100%"}},
        },
        "cards": [left_column, right_column],
    }


async def main():
    print("Connecting to Home Assistant WebSocket...")
    async with websockets.connect(HA_WS, max_size=25 * 1024 * 1024) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": TOKEN}))
        auth_res = json.loads(await ws.recv())
        if auth_res.get("type") != "auth_ok":
            print("Authentication failed:", auth_res)
            return

        # Fetch current dashboard config
        await ws.send(
            json.dumps(
                {"id": 1, "type": "lovelace/config", "url_path": "lovelace-basement"}
            )
        )
        resp = json.loads(await ws.recv())
        if not resp.get("success"):
            print("Failed fetching lovelace-basement config:", resp)
            return

        config = resp["result"]
        views = config.get("views", [])

        # Map stand subviews by path
        subview_map = {cam["slug"]: build_stand_subview(cam) for cam in CAMERAS}

        # Update or add stand subviews
        updated_views = []
        replaced_slugs = set()

        for v in views:
            path = v.get("path", "")
            if path == "trail-cams":
                for card in v.get("cards", []):
                    if card.get("type") == "custom:vertical-stack-in-card":
                        subcards = card.get("cards", [])
                        if subcards and subcards[0].get("type") == "custom:button-card":
                            first_card = subcards[0]
                            if "camera.stealth_cam_" in first_card.get("entity", ""):
                                first_card["entity_picture"] = "[[[ return entity.attributes.entity_picture || entity.attributes.thumbnail_url || entity.attributes.image_url; ]]]"
            if path.startswith("stand-"):
                slug = path.replace("stand-", "")
                if slug in subview_map:
                    print(f"Replacing subview for stand-{slug} with dynamic 36-photo reel...")
                    updated_views.append(subview_map[slug])
                    replaced_slugs.add(slug)
                    continue
            updated_views.append(v)

        for slug, subview in subview_map.items():
            if slug not in replaced_slugs:
                print(f"Appending new subview for stand-{slug}...")
                updated_views.append(subview)

        config["views"] = updated_views

        # Save dashboard back to HA
        await ws.send(
            json.dumps(
                {
                    "id": 2,
                    "type": "lovelace/config/save",
                    "url_path": "lovelace-basement",
                    "config": config,
                }
            )
        )
        save_res = json.loads(await ws.recv())
        print("Save result:", save_res)


if __name__ == "__main__":
    asyncio.run(main())
