#!/usr/bin/env python3
"""Sync Stealth Cam Command trail cameras to Home Assistant."""

import argparse
import datetime
import json
import logging
import os
import sys
import time
from typing import Dict, Any
import requests

from stealthcam_api.client import StealthCamClient, StealthCamAuthError, StealthCamAPIError

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
    """Orchestrates syncing Stealth Cam cloud data to Home Assistant."""

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
        _LOGGER.info("Fetching camera data from Stealth Cam Command...")
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

            common_attrs = {
                "friendly_name": f"{name} Trail Camera",
                "camera_name": name,
                "pdi": cam.get("pdi"),
                "device_id": cam.get("id"),
                "model": model,
                "carrier": cam.get("carrier"),
                "latitude": lat,
                "longitude": lon,
                "last_synced_to_ha": now_iso,
            }

            # 1. Battery Sensor
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

            # 2. Cellular Signal Sensor
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

            # 3. SD Card Free Space
            sd_attrs = {
                **common_attrs,
                "friendly_name": f"{name} SD Free Space",
                "unit_of_measurement": "%",
                "icon": "mdi:sd",
            }
            self.post_state(
                f"sensor.stealthcam_{slug}_sd_free",
                cam.get("sd_card_free_space", 0),
                sd_attrs,
            )

            # 4. Last Sync / Check-in
            last_sync_unix = cam.get("last_sync_unix")
            last_sync_str = "Unknown"
            if last_sync_unix:
                last_sync_str = datetime.datetime.fromtimestamp(
                    last_sync_unix / 1000.0, tz=datetime.timezone.utc
                ).strftime("%Y-%m-%d %H:%M:%S UTC")

            sync_attrs = {
                **common_attrs,
                "friendly_name": f"{name} Last Check-In",
                "icon": "mdi:clock-check-outline",
            }
            self.post_state(
                f"sensor.stealthcam_{slug}_last_checkin",
                last_sync_str,
                sync_attrs,
            )

            # 5. Camera / Latest Photo Entity
            img_url = cam.get("latest_image_url")
            thumb_url = cam.get("latest_thumb_url")
            cam_attrs = {
                **common_attrs,
                "friendly_name": f"{name} Trail Cam",
                "entity_picture": thumb_url or img_url,
                "image_url": img_url,
                "thumbnail_url": thumb_url,
                "image_guid": cam.get("latest_image_guid"),
                "temperature": cam.get("latest_image_temperature"),
                "pressure": cam.get("latest_image_pressure"),
                "wind": cam.get("latest_image_wind"),
                "battery_level": cam.get("battery_level"),
                "signal": cam.get("signal_strength"),
            }
            self.post_state(
                f"camera.stealthcam_{slug}",
                "idle" if img_url else "unavailable",
                cam_attrs,
            )

            updated_count += 1

        _LOGGER.info("Successfully synced %d trail cameras to Home Assistant.", updated_count)
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
