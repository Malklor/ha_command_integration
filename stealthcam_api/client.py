"""Stealth Cam Command API Client."""

import logging
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
        """Retrieve latest captured photos for all cameras."""
        self.ensure_auth()
        url = f"{self.base_url}/api/v4/file-manager/images/latest"
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

    def download_image(self, image_url: str, target_path: str) -> bool:
        """Download high-res photo from S3 and save locally."""
        try:
            res = requests.get(image_url, timeout=self.timeout)
            if res.status_code == 200:
                with open(target_path, "wb") as f:
                    f.write(res.content)
                return True
            _LOGGER.warning("Failed to download image (HTTP %s)", res.status_code)
            return False
        except Exception as ex:
            _LOGGER.error("Error saving image to %s: %s", target_path, ex)
            return False

    def get_full_camera_data(self) -> Dict[str, Dict[str, Any]]:
        """Fetch unified dictionary of all cameras with status and latest photo."""
        devices = self.get_devices()
        pdis = [d["physicalDeviceIdentifier"] for d in devices if "physicalDeviceIdentifier" in d]
        statuses = self.get_device_statuses(pdis)
        latest_images = self.get_latest_images()

        status_map = {s["physicalDeviceIdentifier"]: s for s in statuses}
        image_map = {img["deviceName"]: img for img in latest_images if "deviceName" in img}

        result = {}
        for dev in devices:
            pdi = dev.get("physicalDeviceIdentifier")
            name = dev.get("name", "Unknown")
            status = status_map.get(pdi, {})
            latest_img = image_map.get(name, {})

            result[name] = {
                "id": dev.get("deviceId"),
                "name": name,
                "pdi": pdi,
                "model": dev.get("deviceType", {}).get("deviceTypeName", dev.get("deviceModel")),
                "manufacturer": dev.get("manufacturer"),
                "carrier": dev.get("carrier"),
                "latitude": dev.get("latitude"),
                "longitude": dev.get("longitude"),
                "is_active": dev.get("isActive", True),
                "battery_level": status.get("batteryLevel", 0),
                "battery_volt": status.get("batteryVolt", 0.0),
                "signal_strength": status.get("signalStrength", "Unknown"),
                "rssi": status.get("rssi", 0),
                "sd_card_free_space": status.get("sdCardFreeSpace", 0),
                "last_sync_unix": status.get("lastSyncDateUnixTime"),
                "firmware_version": status.get("firmwareVersion", "Unknown"),
                "latest_image_url": latest_img.get("imageUrl"),
                "latest_thumb_url": latest_img.get("thumbnailUrl"),
                "latest_image_guid": latest_img.get("imageGuid"),
                "latest_image_temperature": latest_img.get("temperature"),
                "latest_image_pressure": latest_img.get("pressure"),
                "latest_image_wind": latest_img.get("wind"),
            }
        return result
