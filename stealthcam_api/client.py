"""Stealth Cam Command API Client."""

import datetime
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
import requests

_LOGGER = logging.getLogger(__name__)

BASE_URL_US = "https://app.stealthcamcommand.com"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class StealthCamAuthError(Exception):
    """Exception raised when authentication fails."""


class StealthCamAPIError(Exception):
    """Exception raised when an API call fails."""


def degrees_to_cardinal(deg: Optional[float]) -> str:
    """Convert degree bearing to 16-point cardinal compass direction."""
    if deg is None:
        return "N/A"
    val = int((deg / 22.5) + 0.5)
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[(val % 16)]


class StealthCamClient:
    """Client for interacting with the Stealth Cam Command Cloud REST API."""

    def __init__(
        self,
        email: str,
        password: str,
        base_url: str = BASE_URL_US,
        timeout: int = 20,
    ):
        """Initialize the Stealth Cam client."""
        self.email = email
        self.password = password
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.access_token: Optional[str] = None
        self.token_expiry_unix: Optional[int] = None
        self.user_id: Optional[int] = None
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Content-Type": "application/json",
        })

    def login(self) -> Dict[str, Any]:
        """Authenticate and retrieve bearer token."""
        url = f"{self.base_url}/api/v1/login"
        payload = {
            "email": self.email,
            "password": self.password,
            "useAuthCookie": False,
        }
        try:
            res = self.session.post(url, json=payload, timeout=self.timeout)
            if res.status_code != 200:
                raise StealthCamAuthError(
                    f"Login failed (HTTP {res.status_code}): {res.text}"
                )
            data = res.json()
            self.access_token = data.get("accessToken")
            self.token_expiry_unix = data.get("expiredUnixTime")
            self.user_id = data.get("userId")
            if not self.access_token:
                raise StealthCamAuthError("No accessToken returned in login response")

            self.session.headers.update({
                "Authorization": f"Bearer {self.access_token}"
            })
            _LOGGER.debug("Successfully authenticated as %s", self.email)
            return data
        except requests.RequestException as ex:
            raise StealthCamAuthError(f"Network error during login: {ex}") from ex

    def ensure_auth(self) -> None:
        """Ensure token is valid or re-login if expired."""
        now_unix = int(time.time())
        if (
            not self.access_token
            or (self.token_expiry_unix and now_unix >= (self.token_expiry_unix - 60))
        ):
            self.login()

    def get_devices(self) -> List[Dict[str, Any]]:
        """Retrieve list of registered camera devices."""
        self.ensure_auth()
        url = f"{self.base_url}/api/v1/device-management/devices"
        try:
            res = self.session.get(url, timeout=self.timeout)
            if res.status_code != 200:
                raise StealthCamAPIError(
                    f"Failed to fetch devices (HTTP {res.status_code}): {res.text}"
                )
            return res.json()
        except requests.RequestException as ex:
            raise StealthCamAPIError(f"Network error fetching devices: {ex}") from ex

    def get_device_statuses(
        self, physical_device_identifiers: List[str]
    ) -> List[Dict[str, Any]]:
        """Retrieve real-time status (battery, signal, SD space) for given camera PDIs."""
        if not physical_device_identifiers:
            return []
        self.ensure_auth()
        query_str = "&".join(
            [f"physicalDeviceIdentifier[]={pdi}" for pdi in physical_device_identifiers]
        )
        url = f"{self.base_url}/api/v4/device-management/devices/status?{query_str}"
        try:
            res = self.session.get(url, timeout=self.timeout)
            if res.status_code != 200:
                raise StealthCamAPIError(
                    f"Failed to fetch device statuses (HTTP {res.status_code}): {res.text}"
                )
            data = res.json()
            return data.get("cameraStatuses", [])
        except requests.RequestException as ex:
            raise StealthCamAPIError(f"Network error fetching statuses: {ex}") from ex

    def get_latest_images(self) -> List[Dict[str, Any]]:
        """Retrieve latest captured photos with environmental data for all cameras."""
        self.ensure_auth()
        url = f"{self.base_url}/api/v3/file-manager/images/latest"
        try:
            res = self.session.get(url, timeout=self.timeout)
            if res.status_code != 200:
                raise StealthCamAPIError(
                    f"Failed to fetch latest images (HTTP {res.status_code}): {res.text}"
                )
            data = res.json()
            return data if isinstance(data, list) else []
        except requests.RequestException as ex:
            raise StealthCamAPIError(f"Network error fetching latest images: {ex}") from ex

    def get_recent_captures(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Fetch historical batch of photo captures across all cameras for statistical modeling."""
        self.ensure_auth()
        url = f"{self.base_url}/api/v6/file-manager/images"
        payload = {"takeCount": limit, "skipCount": 0}
        try:
            res = self.session.post(url, json=payload, timeout=self.timeout)
            if res.status_code == 200:
                data = res.json()
                return data.get("images", [])
            return []
        except Exception as ex:
            _LOGGER.warning("Failed fetching recent captures: %s", ex)
            return []

    def get_full_camera_data(self, tagged_bucks: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
        """Fetch unified dictionary of all cameras with status, latest photo, weather, GPS, and stats."""
        devices = self.get_devices()
        pdis = [d["physicalDeviceIdentifier"] for d in devices if "physicalDeviceIdentifier" in d]
        statuses = self.get_device_statuses(pdis)
        latest_images = self.get_latest_images()
        recent_captures = self.get_recent_captures(limit=200)

        status_map = {s["physicalDeviceIdentifier"]: s for s in statuses}
        image_map = {img["deviceName"]: img for img in latest_images if "deviceName" in img}

        # Index captures by deviceId
        captures_by_dev: Dict[int, List[Dict[str, Any]]] = {}
        for cap in recent_captures:
            dev_id = cap.get("deviceId")
            if dev_id:
                captures_by_dev.setdefault(dev_id, []).append(cap)

        result = {}
        for dev in devices:
            pdi = dev.get("physicalDeviceIdentifier")
            name = dev.get("name", "Unknown")
            dev_id = dev.get("deviceId")
            status = status_map.get(pdi, {})
            latest_img = image_map.get(name, {})
            dev_captures = captures_by_dev.get(dev_id, [])

            # Determine last positive hit / detection timestamp
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            total_hits = len(dev_captures)
            buck_hits_count = 0
            doe_hits_count = 0
            person_hits_count = 0
            morning_hits = 0
            evening_hits = 0
            midday_hits = 0
            night_hits = 0

            captures_24h_count = 0
            buck_hits_24h = 0
            doe_hits_24h = 0
            person_hits_24h = 0
            morning_24h = 0
            evening_24h = 0
            midday_24h = 0
            night_24h = 0

            if dev_captures:
                last_hit_dt = dev_captures[0].get("createdDateTime") or dev_captures[0].get("uploadedTime")

            active_tags = dict(tagged_bucks) if tagged_bucks is not None else {}
            if tagged_bucks is None:
                tagged_file = "/config/stealthcam_tagged_bucks.json"
                if not os.path.exists(tagged_file):
                    tagged_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tagged_bucks.json")
                if not os.path.exists(tagged_file):
                    tagged_file = "/home/tgoetz/Projects/ha_command_integration/tagged_bucks.json"
                if os.path.exists(tagged_file):
                    try:
                        with open(tagged_file) as tf:
                            active_tags = json.load(tf)
                    except Exception:
                        pass

            for c in dev_captures:
                guid = c.get("imageGuid")
                raw_tag = active_tags.get(guid)
                if raw_tag is True:
                    tag = "buck"
                elif isinstance(raw_tag, str):
                    tag = raw_tag.lower()
                elif c.get("isBuckScored"):
                    tag = "buck"
                elif c.get("isDoeScored") or c.get("isDoe"):
                    tag = "doe"
                elif c.get("isPerson") or c.get("isHuman"):
                    tag = "person"
                else:
                    tag = ""

                is_buck = (tag == "buck")
                is_doe = (tag == "doe")
                is_person = (tag == "person")

                if is_buck:
                    buck_hits_count += 1
                elif is_doe:
                    doe_hits_count += 1
                elif is_person:
                    person_hits_count += 1

                cdt = c.get("createdDateTime") or c.get("uploadedTime")
                dt_obj = None
                if cdt:
                    try:
                        dt_obj = datetime.datetime.fromisoformat(cdt)
                        if dt_obj.tzinfo is None:
                            dt_obj = dt_obj.replace(tzinfo=datetime.timezone.utc)
                    except Exception:
                        dt_obj = None

                is_within_24h = False
                if dt_obj:
                    diff_sec = (now_utc - dt_obj).total_seconds()
                    if 0 <= diff_sec <= 86400:
                        is_within_24h = True

                hour = dt_obj.hour if dt_obj else None
                if hour is None and cdt and "T" in str(cdt):
                    try:
                        hour = int(str(cdt).split("T")[1].split(":")[0])
                    except Exception:
                        hour = None

                if hour is not None:
                    if 5 <= hour < 9:
                        morning_hits += 1
                        if is_within_24h:
                            morning_24h += 1
                    elif 9 <= hour < 17:
                        midday_hits += 1
                        if is_within_24h:
                            midday_24h += 1
                    elif 17 <= hour < 21:
                        evening_hits += 1
                        if is_within_24h:
                            evening_24h += 1
                    else:
                        night_hits += 1
                        if is_within_24h:
                            night_24h += 1

                if is_within_24h:
                    captures_24h_count += 1
                    if is_buck:
                        buck_hits_24h += 1
                    elif is_doe:
                        doe_hits_24h += 1
                    elif is_person:
                        person_hits_24h += 1

            peak_window = "Variable"
            if total_hits > 0:
                windows = [
                    ("Dawn (5–9 AM)", morning_hits),
                    ("Midday (9 AM–5 PM)", midday_hits),
                    ("Evening (5–9 PM)", evening_hits),
                    ("Night (9 PM–5 AM)", night_hits),
                ]
                max_w = max(windows, key=lambda x: x[1])
                if max_w[1] > 0:
                    peak_window = f"{max_w[0]} ({round((max_w[1] / total_hits) * 100)}%)"

            peak_window_24h = "Variable"
            if captures_24h_count > 0:
                windows_24h = [
                    ("Dawn (5–9 AM)", morning_24h),
                    ("Midday (9 AM–5 PM)", midday_24h),
                    ("Evening (5–9 PM)", evening_24h),
                    ("Night (9 PM–5 AM)", night_24h),
                ]
                max_w24 = max(windows_24h, key=lambda x: x[1])
                if max_w24[1] > 0:
                    peak_window_24h = f"{max_w24[0]} ({round((max_w24[1] / captures_24h_count) * 100)}%)"

            recent_photos = []
            buck_photos = []
            doe_photos = []
            person_photos = []
            for c in dev_captures[:36]:
                img_urls = c.get("imageUrls") or []
                thumb_urls = c.get("thumbnailUrls") or []
                cdt = c.get("createdDateTime") or c.get("uploadedTime")
                guid = c.get("imageGuid")
                raw_tag = active_tags.get(guid)
                if raw_tag is True:
                    tag = "buck"
                elif isinstance(raw_tag, str):
                    tag = raw_tag.lower()
                elif c.get("isBuckScored") or c.get("isBuck"):
                    tag = "buck"
                elif c.get("isDoeScored") or c.get("isDoe"):
                    tag = "doe"
                elif c.get("isPerson") or c.get("isHuman") or c.get("humanDetected"):
                    tag = "person"
                else:
                    tag = ""
                is_buck = (tag == "buck")
                is_doe = (tag == "doe")
                is_person = (tag == "person")

                time_str = "Recent"
                hour = 0
                if cdt:
                    try:
                        dt_obj = datetime.datetime.fromisoformat(cdt)
                        time_str = dt_obj.strftime("%b %-d, %-I:%M %p")
                        hour = dt_obj.hour
                    except Exception:
                        time_str = str(cdt)[:16]
                p_data = {
                    "image_url": img_urls[0] if img_urls else None,
                    "thumb_url": thumb_urls[0] if thumb_urls else (img_urls[0] if img_urls else None),
                    "time_str": time_str,
                    "tag": tag,
                    "is_buck": is_buck,
                    "is_doe": is_doe,
                    "is_person": is_person,
                    "guid": guid,
                    "hour": hour,
                }
                recent_photos.append(p_data)
                if is_buck:
                    buck_photos.append(p_data)
                elif is_doe:
                    doe_photos.append(p_data)
                elif is_person:
                    person_photos.append(p_data)

            rotate_angle = dev.get("rotateAngle")
            heading_cardinal = degrees_to_cardinal(rotate_angle) if rotate_angle is not None else "N/A"

            result[name] = {
                "id": dev_id,
                "name": name,
                "pdi": pdi,
                "model": dev.get("deviceType", {}).get("deviceTypeName", dev.get("deviceModel")),
                "manufacturer": dev.get("manufacturer"),
                "carrier": dev.get("carrier"),
                # GPS & Position Intelligence
                "latitude": dev.get("latitude"),
                "longitude": dev.get("longitude"),
                "rotate_angle": rotate_angle,
                "heading": f"{heading_cardinal} ({rotate_angle}°)" if rotate_angle is not None else "Unknown",
                "is_active": dev.get("isActive", True),
                # Hardware Telemetry
                "battery_level": status.get("batteryLevel", 0),
                "battery_volt": status.get("batteryVolt", 0.0),
                "signal_strength": status.get("signalStrength", "Unknown"),
                "rssi": status.get("rssi", 0),
                "sd_card_free_space": status.get("sdCardFreeSpace", 0),
                "last_sync_unix": status.get("lastSyncDateUnixTime"),
                "firmware_version": status.get("firmwareVersion", "Unknown"),
                # Photo & Environmental Telemetry
                "latest_image_url": latest_img.get("imageUrl"),
                "latest_thumb_url": latest_img.get("thumbnailUrl"),
                "latest_image_guid": latest_img.get("imageGuid"),
                "temperature": latest_img.get("temperature"),
                "pressure": latest_img.get("pressure"),
                "pressure_tendency": latest_img.get("pressureTendency", "Steady"),
                "wind_speed": latest_img.get("wind"),
                "wind_direction": latest_img.get("windDirection"),
                "moon_phase": latest_img.get("moonPhase"),
                # Hunting & Stand Breakdown - All-Time & 24-Hour
                "last_positive_hit": last_hit_dt,
                "total_analyzed_captures": total_hits,
                "buck_hits_count": buck_hits_count,
                "doe_hits_count": doe_hits_count,
                "person_hits_count": person_hits_count,
                "morning_hits": morning_hits,
                "evening_hits": evening_hits,
                "night_hits": night_hits,
                "midday_hits": midday_hits,
                "peak_window": peak_window,
                "captures_24h_count": captures_24h_count,
                "buck_hits_24h": buck_hits_24h,
                "doe_hits_24h": doe_hits_24h,
                "person_hits_24h": person_hits_24h,
                "morning_24h": morning_24h,
                "evening_24h": evening_24h,
                "night_24h": night_24h,
                "midday_24h": midday_24h,
                "peak_window_24h": peak_window_24h,
                "recent_photos": recent_photos,
                "buck_photos": buck_photos,
                "doe_photos": doe_photos,
                "person_photos": person_photos,
            }
        return result
