#!/usr/bin/env python3
"""Sync Stealth Cam Command trail cameras, GPS, and hunting analytics to Home Assistant."""

import argparse
import datetime
import json
import logging
import os
import sys
import time
from typing import Dict, Any, Optional
import requests

from stealthcam_api.client import StealthCamClient, StealthCamAuthError, StealthCamAPIError, degrees_to_cardinal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
_LOGGER = logging.getLogger("stealthcam_sync")

DEFAULT_HA_URL = "http://192.168.131.17:8123"
DEFAULT_HA_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJmMWUzMzA5ODZkYzQ0YWJiYWM4NmU5OGIxMTJiZDNiNSIsImlhdCI6MTc5MDk3MTMwMiwiZXhwIjoyMTA2MzMxMzAyfQ.wkyHRjBsBKiaEMbXmz_nyGreKnLtwiTTCGuxADaVeqs"


def load_env(env_path: str) -> Dict[str, str]:
    """Parse key-value or yaml-style .env file."""
    res = {}
    if not os.path.exists(env_path):
        return res
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line and "=" not in line:
                k, v = line.split(":", 1)
            elif "=" in line:
                k, v = line.split("=", 1)
            else:
                continue
            res[k.strip().lower()] = v.strip().strip('"').strip("'")
    return res


def slugify(name: str) -> str:
    """Convert name to Home Assistant entity ID safe slug."""
    return "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")


class HAStealthCamSyncer:
    """Orchestrates syncing Stealth Cam cloud data, GPS, and hunting analytics to Home Assistant."""

    def __init__(
        self,
        client: StealthCamClient,
        ha_url: str = DEFAULT_HA_URL,
        ha_token: str = DEFAULT_HA_TOKEN,
    ):
        self.client = client
        self.ha_url = ha_url.rstrip("/")
        self.ha_headers = {
            "Authorization": f"Bearer {ha_token}",
            "Content-Type": "application/json",
        }

    def post_state(self, entity_id: str, state: str, attributes: Dict[str, Any]) -> bool:
        """Push a state and attributes to Home Assistant REST API."""
        url = f"{self.ha_url}/api/states/{entity_id}"
        payload = {
            "state": str(state),
            "attributes": attributes,
        }
        try:
            res = requests.post(url, headers=self.ha_headers, json=payload, timeout=10)
            if res.status_code in (200, 201):
                _LOGGER.debug("Updated %s -> %s", entity_id, state)
                return True
            _LOGGER.warning("Failed updating %s (HTTP %s): %s", entity_id, res.status_code, res.text)
            return False
        except Exception as ex:
            _LOGGER.error("Error connecting to Home Assistant for %s: %s", entity_id, ex)
            return False

    def sync_once(self) -> int:
        """Fetch all cameras and update Home Assistant entities."""
        _LOGGER.info("Fetching camera, GPS, and hunting analytics from Stealth Cam Command...")
        try:
            cameras = self.client.get_full_camera_data()
        except (StealthCamAuthError, StealthCamAPIError) as ex:
            _LOGGER.error("Failed fetching Stealth Cam data: %s", ex)
            return 0

        updated_count = 0
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for raw_name, cam in cameras.items():
            slug = slugify(raw_name)
            name = cam.get("name", raw_name)
            model = cam.get("model", "Connect Max 2")
            lat = cam.get("latitude")
            lon = cam.get("longitude")
            heading = cam.get("heading", "Unknown")

            common_attrs = {
                "friendly_name": f"{name} Trail Camera",
                "camera_name": name,
                "pdi": cam.get("pdi"),
                "device_id": cam.get("id"),
                "model": model,
                "carrier": cam.get("carrier"),
                "latitude": lat,
                "longitude": lon,
                "heading": heading,
                "last_synced_to_ha": now_iso,
            }

            # 1. Device Tracker (GPS Location Pin on Property Maps)
            if lat is not None and lon is not None:
                self.post_state(
                    f"device_tracker.stealthcam_{slug}",
                    "not_home",
                    {
                        **common_attrs,
                        "friendly_name": f"Trail Cam {name}",
                        "source_type": "gps",
                        "latitude": lat,
                        "longitude": lon,
                        "gps_accuracy": 5,
                        "battery_level": cam.get("battery_level"),
                        "heading": heading,
                        "icon": "mdi:map-marker-radius",
                    }
                )
                gps_str = f"{lat:.4f}, {lon:.4f} ({heading})"
            else:
                gps_str = "No GPS lock"

            # 1b. GPS & Heading Display Sensor (Readable coordinates instead of HA 'away' state)
            self.post_state(
                f"sensor.stealthcam_{slug}_location",
                gps_str,
                {
                    **common_attrs,
                    "friendly_name": f"{name} Stand Location & Heading",
                    "latitude": lat,
                    "longitude": lon,
                    "heading": heading,
                    "icon": "mdi:crosshairs-gps",
                }
            )

            # 2. Battery Sensor
            battery_attrs = {
                **common_attrs,
                "friendly_name": f"{name} Battery",
                "unit_of_measurement": "%",
                "device_class": "battery",
                "state_class": "measurement",
                "battery_volt": cam.get("battery_volt"),
                "icon": "mdi:battery-high" if cam.get("battery_level", 0) > 50 else "mdi:battery-low",
            }
            self.post_state(
                f"sensor.stealthcam_{slug}_battery",
                cam.get("battery_level", 0),
                battery_attrs,
            )

            # 3. Cellular Signal Sensor
            signal_attrs = {
                **common_attrs,
                "friendly_name": f"{name} Cellular Signal",
                "rssi": cam.get("rssi"),
                "signal_strength_text": cam.get("signal_strength"),
                "icon": "mdi:signal-cellular-3",
            }
            self.post_state(
                f"sensor.stealthcam_{slug}_signal",
                cam.get("signal_strength", "Unknown"),
                signal_attrs,
            )

            # 4. SD Card Free Space
            self.post_state(
                f"sensor.stealthcam_{slug}_sd_free",
                cam.get("sd_card_free_space", 0),
                {
                    **common_attrs,
                    "friendly_name": f"{name} SD Free Space",
                    "unit_of_measurement": "%",
                    "icon": "mdi:sd",
                }
            )

            # 5. Last Cellular Check-in
            last_sync_unix = cam.get("last_sync_unix")
            last_sync_str = "Unknown"
            if last_sync_unix:
                last_sync_str = datetime.datetime.fromtimestamp(
                    last_sync_unix / 1000.0, tz=datetime.timezone.utc
                ).strftime("%b %-d, %-I:%M %p")

            self.post_state(
                f"sensor.stealthcam_{slug}_last_checkin",
                last_sync_str,
                {
                    **common_attrs,
                    "friendly_name": f"{name} Last Check-In",
                    "icon": "mdi:cloud-check-outline",
                }
            )

            # 6. Last Positive Animal Hit / Capture Trigger
            last_hit_raw = cam.get("last_positive_hit")
            last_hit_str = "No recent hit"
            if last_hit_raw:
                try:
                    dt_hit = datetime.datetime.fromisoformat(last_hit_raw)
                    last_hit_str = dt_hit.strftime("%b %-d, %-I:%M %p")
                except Exception:
                    last_hit_str = str(last_hit_raw)[:16]

            self.post_state(
                f"sensor.stealthcam_{slug}_last_hit",
                last_hit_str,
                {
                    **common_attrs,
                    "friendly_name": f"{name} Last Animal Hit",
                    "raw_timestamp": last_hit_raw,
                    "total_analyzed_captures": cam.get("total_analyzed_captures", 0),
                    "buck_hits_count": cam.get("buck_hits_count", 0),
                    "morning_hits": cam.get("morning_hits", 0),
                    "evening_hits": cam.get("evening_hits", 0),
                    "night_hits": cam.get("night_hits", 0),
                    "midday_hits": cam.get("midday_hits", 0),
                    "peak_window": cam.get("peak_window", "Variable"),
                    "icon": "mdi:target-account",
                }
            )

            # 7. Positive Buck Hits Count
            self.post_state(
                f"sensor.stealthcam_{slug}_buck_hits",
                cam.get("buck_hits_count", 0),
                {
                    **common_attrs,
                    "friendly_name": f"{name} Positive Buck Hits",
                    "unit_of_measurement": "bucks",
                    "icon": "mdi:deer",
                }
            )

            # 8. Activity Peak Window
            self.post_state(
                f"sensor.stealthcam_{slug}_peak_window",
                cam.get("peak_window", "Variable"),
                {
                    **common_attrs,
                    "friendly_name": f"{name} Peak Movement Window",
                    "morning_count": cam.get("morning_hits", 0),
                    "evening_count": cam.get("evening_hits", 0),
                    "night_count": cam.get("night_hits", 0),
                    "midday_count": cam.get("midday_hits", 0),
                    "icon": "mdi:chart-bell-curve",
                }
            )

            # 9. Camera Heading & Orientation
            self.post_state(
                f"sensor.stealthcam_{slug}_heading",
                heading,
                {
                    **common_attrs,
                    "friendly_name": f"{name} Camera Heading",
                    "rotate_angle": cam.get("rotate_angle"),
                    "icon": "mdi:compass",
                }
            )

            # 10. Temperature Sensor
            temp_val = cam.get("temperature")
            if temp_val is not None:
                self.post_state(
                    f"sensor.stealthcam_{slug}_temperature",
                    round(float(temp_val), 1),
                    {
                        **common_attrs,
                        "friendly_name": f"{name} Field Temp",
                        "unit_of_measurement": "°F",
                        "device_class": "temperature",
                        "state_class": "measurement",
                        "icon": "mdi:thermometer",
                    }
                )

            # 11. Barometric Pressure Sensor & Tendency
            press_val = cam.get("pressure")
            if press_val is not None:
                self.post_state(
                    f"sensor.stealthcam_{slug}_pressure",
                    round(float(press_val), 2),
                    {
                        **common_attrs,
                        "friendly_name": f"{name} Barometric Pressure",
                        "unit_of_measurement": "inHg",
                        "device_class": "atmospheric_pressure",
                        "state_class": "measurement",
                        "pressure_tendency": cam.get("pressure_tendency", "Steady"),
                        "icon": "mdi:gauge",
                    }
                )

            # 12. Wind Speed & Direction
            wind_spd = cam.get("wind_speed")
            wind_dir = cam.get("wind_direction")
            if wind_spd is not None:
                cardinal = degrees_to_cardinal(wind_dir)
                self.post_state(
                    f"sensor.stealthcam_{slug}_wind",
                    f"{wind_spd} mph {cardinal}",
                    {
                        **common_attrs,
                        "friendly_name": f"{name} Field Wind",
                        "speed_mph": wind_spd,
                        "bearing_deg": wind_dir,
                        "cardinal": cardinal,
                        "icon": "mdi:weather-windy",
                    }
                )

            # 13. Moon Phase
            moon_val = cam.get("moon_phase")
            if moon_val:
                self.post_state(
                    f"sensor.stealthcam_{slug}_moon_phase",
                    moon_val,
                    {
                        **common_attrs,
                        "friendly_name": f"{name} Moon Phase",
                        "icon": "mdi:moon-waning-crescent",
                    }
                )

            # 14. Camera / Latest Photo Entity
            img_url = cam.get("latest_image_url")
            thumb_url = cam.get("latest_thumb_url")
            cam_attrs = {
                **common_attrs,
                "friendly_name": f"{name} Trail Cam",
                "entity_picture": thumb_url or img_url,
                "image_url": img_url,
                "thumbnail_url": thumb_url,
                "image_guid": cam.get("latest_image_guid"),
                "temperature": cam.get("temperature"),
                "pressure": cam.get("pressure"),
                "pressure_tendency": cam.get("pressure_tendency"),
                "wind_speed": cam.get("wind_speed"),
                "wind_direction": cam.get("wind_direction"),
                "moon_phase": cam.get("moon_phase"),
                "last_positive_hit": last_hit_str,
                "total_analyzed_captures": cam.get("total_analyzed_captures", 0),
                "buck_hits_count": cam.get("buck_hits_count", 0),
                "peak_window": cam.get("peak_window"),
                "battery_level": cam.get("battery_level"),
                "signal": cam.get("signal_strength"),
                "heading": heading,
            }
            self.post_state(
                f"camera.stealthcam_{slug}",
                "idle" if img_url else "unavailable",
                cam_attrs,
            )

            updated_count += 1

        # 15. Property-Wide Movement Aggregation & Stand Wind Matrix
        total_caps = sum(c.get("total_analyzed_captures", 0) for c in cameras.values()) or 200
        total_bucks = sum(c.get("buck_hits_count", 0) for c in cameras.values())
        morning_total = sum(c.get("morning_hits", 0) for c in cameras.values())
        midday_total = sum(c.get("midday_hits", 0) for c in cameras.values())
        evening_total = sum(c.get("evening_hits", 0) for c in cameras.values())
        night_total = sum(c.get("night_hits", 0) for c in cameras.values())

        morning_pct = round((morning_total / max(1, total_caps)) * 100)
        midday_pct = round((midday_total / max(1, total_caps)) * 100)
        evening_pct = round((evening_total / max(1, total_caps)) * 100)
        night_pct = round((night_total / max(1, total_caps)) * 100)

        self.post_state(
            "sensor.stealthcam_property_movement",
            f"{total_caps} Captures • {total_bucks} Buck Hits",
            {
                "friendly_name": "Property Deer Movement Distribution",
                "total_captures": total_caps,
                "buck_hits": total_bucks,
                "morning_hits": morning_total,
                "morning_pct": morning_pct,
                "midday_hits": midday_total,
                "midday_pct": midday_pct,
                "evening_hits": evening_total,
                "evening_pct": evening_pct,
                "night_hits": night_total,
                "night_pct": night_pct,
                "icon": "mdi:chart-pie",
            }
        )

        # Stand Wind Matrix
        ref_cam = next(iter(cameras.values())) if cameras else {}
        prop_wind_dir = ref_cam.get("wind_direction", 200) or 200
        prop_wind_spd = ref_cam.get("wind_speed", 5.0) or 5.0
        prop_wind_card = degrees_to_cardinal(prop_wind_dir)

        wind_stand_details = {}
        fav_count = 0
        for raw_name, cam in cameras.items():
            c_slug = slugify(raw_name)
            c_name = cam.get("name", raw_name)
            c_angle = cam.get("rotate_angle")
            if c_angle is None:
                # Approximate defaults based on camera field orientations
                defaults = {"homer": 43, "maggie": 297, "santas_helper": 356, "lisa": 329, "marge": 89, "bart": 177}
                c_angle = defaults.get(c_slug, 0)

            diff = abs((prop_wind_dir - c_angle + 180) % 360 - 180)
            if diff <= 65:
                status = "🟢 Favorable (Headwind)"
                fav_count += 1
            elif diff <= 115:
                status = "🟡 Marginal (Crosswind)"
            else:
                status = "🔴 Unfavorable (Downwind)"

            wind_stand_details[c_name] = {
                "heading": f"{c_angle}°",
                "status": status,
                "diff_deg": round(diff)
            }

        self.post_state(
            "sensor.stealthcam_stand_wind_matrix",
            f"{fav_count} Stands Favorable ({prop_wind_spd} mph {prop_wind_card})",
            {
                "friendly_name": "Stand Scent & Wind Direction Matrix",
                "wind_direction_deg": prop_wind_dir,
                "wind_cardinal": prop_wind_card,
                "wind_speed_mph": prop_wind_spd,
                "stand_details": wind_stand_details,
                "icon": "mdi:weather-windy",
            }
        )

        # 16. Dynamic Hunt Recommendation Scoring
        best_cam_name = "HOMER"
        best_score = -1
        best_details = {}

        for raw_name, cam in cameras.items():
            c_name = cam.get("name", raw_name)
            bucks = cam.get("buck_hits_count", 0)
            morning = cam.get("morning_hits", 0)
            evening = cam.get("evening_hits", 0)
            w_info = wind_stand_details.get(c_name, {})
            w_status = w_info.get("status", "")
            w_bonus = 10 if "🟢" in w_status else (5 if "🟡" in w_status else -5)

            score = (bucks * 20) + (morning * 3) + (evening * 2) + w_bonus
            if score > best_score:
                best_score = score
                best_cam_name = c_name
                best_details = {
                    "score": score,
                    "buck_hits": bucks,
                    "peak_window": cam.get("peak_window", "Dawn (5-8 AM)"),
                    "moon_phase": cam.get("moon_phase", "Waxing Crescent"),
                    "current_temp": cam.get("temperature", 58),
                    "wind_status": w_status,
                }

        self.post_state(
            "sensor.stealthcam_hunt_recommendation",
            best_cam_name,
            {
                "friendly_name": "Top Recommended Stand",
                **best_details,
                "icon": "mdi:target",
            }
        )

        _LOGGER.info("Successfully synced %d trail cameras, GPS, and hunting analytics to Home Assistant.", updated_count)
        return updated_count


def main():
    parser = argparse.ArgumentParser(description="Sync Stealth Cam Command to Home Assistant")
    parser.add_argument("--env", default="/home/tgoetz/Projects/ha_command_integration/.env", help="Path to .env file")
    parser.add_argument("--ha-url", default=DEFAULT_HA_URL, help="Home Assistant base URL")
    parser.add_argument("--ha-token", default=DEFAULT_HA_TOKEN, help="Home Assistant Long-Lived Token")
    parser.add_argument("--interval", type=int, default=300, help="Sync interval in seconds (default 300)")
    parser.add_argument("--daemon", action="store_true", help="Run continuously in background")
    args = parser.parse_args()

    env = load_env(args.env)
    email = env.get("username") or env.get("email") or os.environ.get("STEALTHCAM_EMAIL")
    password = env.get("password") or os.environ.get("STEALTHCAM_PASSWORD")
    ha_url = env.get("ha_url") or args.ha_url
    ha_token = env.get("ha_token") or args.ha_token

    if not email or not password:
        _LOGGER.error("Missing username/password in %s or environment variables.", args.env)
        sys.exit(1)

    client = StealthCamClient(email=email, password=password)
    syncer = HAStealthCamSyncer(client=client, ha_url=ha_url, ha_token=ha_token)

    if args.daemon:
        _LOGGER.info("Starting Stealth Cam sync daemon (Interval: %ds)...", args.interval)
        while True:
            try:
                syncer.sync_once()
            except Exception as ex:
                _LOGGER.error("Unexpected error in sync cycle: %s", ex)
            time.sleep(args.interval)
    else:
        syncer.sync_once()


if __name__ == "__main__":
    main()
