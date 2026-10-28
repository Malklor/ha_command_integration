"""Camera platform for Stealth Cam Command integration."""
from collections import OrderedDict
import logging
import os
from typing import Any, Dict, Optional
import requests

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import StealthCamDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Global in-memory LRU image cache for ultra-fast local proxy serving
MAX_CACHE_SIZE = 300
_IMAGE_CACHE: "OrderedDict[str, bytes]" = OrderedDict()


def fetch_and_cache_image(
    url: Optional[str], guid: Optional[str] = None, timeout: int = 10
) -> Optional[bytes]:
    """Fetch image bytes with in-memory caching."""
    if not url:
        return None
    cache_key = guid or url
    if cache_key in _IMAGE_CACHE:
        _IMAGE_CACHE.move_to_end(cache_key)
        return _IMAGE_CACHE[cache_key]
    try:
        res = requests.get(url, timeout=timeout)
        if res.status_code == 200 and res.content:
            _IMAGE_CACHE[cache_key] = res.content
            if len(_IMAGE_CACHE) > MAX_CACHE_SIZE:
                _IMAGE_CACHE.popitem(last=False)
            return res.content
        _LOGGER.warning("HTTP %s when fetching photo from %s", res.status_code, url[:60])
    except Exception as ex:
        _LOGGER.error("Failed fetching photo bytes from %s: %s", url[:60], ex)
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Stealth Cam camera entities based on a config entry."""
    coordinator: StealthCamDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for name, data in coordinator.data.items():
        pdi = data.get("pdi", name)
        entities.append(StealthCamLatestPhotoCamera(coordinator, name, pdi))
        for idx in range(36):
            entities.append(StealthCamCapturePhotoCamera(coordinator, name, pdi, idx))

    # Create 8 Target Buck Profile Camera slots + 20 per-buck gallery photo entities served from /media/stealthcam_bucks/
    for idx in range(8):
        entities.append(StealthCamProfiledBuckCamera(coordinator, idx))
        for p_idx in range(20):
            entities.append(StealthCamBuckGalleryPhotoCamera(coordinator, idx, p_idx))

    async_add_entities(entities)


SIMPSON_ICONS = {
    "homer": "mdi:donut",
    "bart": "mdi:skateboard",
    "lisa": "mdi:saxophone",
    "maggie": "mdi:pacifier",
    "marge": "mdi:necklace",
    "santas_helper": "mdi:dog-side",
}


class StealthCamLatestPhotoCamera(CoordinatorEntity, Camera):
    """Camera entity representing the latest photo captured by Stealth Cam."""

    def __init__(
        self,
        coordinator: StealthCamDataUpdateCoordinator,
        camera_name: str,
        pdi: str,
    ) -> None:
        """Initialize camera entity."""
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self.camera_name = camera_name
        self.pdi = pdi
        self._attr_unique_id = f"{pdi}_camera"
        self._attr_name = f"{camera_name} Trail Cam"

    @property
    def icon(self) -> str:
        """Return custom character icon for the camera."""
        slug = slugify(self.camera_name).replace("-", "_")
        return SIMPSON_ICONS.get(slug, "mdi:cctv")

    @property
    def is_on(self) -> bool:
        """Return True if camera has images."""
        return bool(self.camera_data.get("latest_image_url") or self.camera_data.get("latest_thumb_url"))

    @property
    def camera_data(self) -> Dict[str, Any]:
        """Get current camera data from coordinator."""
        return self.coordinator.data.get(self.camera_name, {})

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.pdi)},
            name=f"Stealth Cam {self.camera_name}",
            manufacturer=self.camera_data.get("manufacturer", "Stealth Cam"),
            model=self.camera_data.get("model", "Connect Max 2"),
            sw_version=self.camera_data.get("firmware_version"),
        )

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes."""
        return {
            "image_url": self.camera_data.get("latest_image_url"),
            "thumbnail_url": self.camera_data.get("latest_thumb_url"),
            "image_guid": self.camera_data.get("latest_image_guid"),
            "guid": self.camera_data.get("latest_image_guid"),
            "temperature": self.camera_data.get("temperature"),
            "pressure": self.camera_data.get("pressure"),
            "pressure_tendency": self.camera_data.get("pressure_tendency", "Steady"),
            "wind_speed": self.camera_data.get("wind_speed"),
            "wind_direction": self.camera_data.get("wind_direction"),
            "moon_phase": self.camera_data.get("moon_phase"),
            "latitude": self.camera_data.get("latitude"),
            "longitude": self.camera_data.get("longitude"),
            "heading": self.camera_data.get("heading"),
            "battery_level": self.camera_data.get("battery_level"),
            "signal": self.camera_data.get("signal_strength"),
            "last_positive_hit": self.camera_data.get("last_positive_hit"),
            "total_analyzed_captures": self.camera_data.get("total_analyzed_captures", 0),
            "buck_hits_count": self.camera_data.get("buck_hits_count", 0),
            "doe_hits_count": self.camera_data.get("doe_hits_count", 0),
            "person_hits_count": self.camera_data.get("person_hits_count", 0),
            "latest_buck_score": self.camera_data.get("latest_buck_score"),
            "buck_score": self.camera_data.get("latest_buck_score"),
            "is_hd": self.camera_data.get("latest_is_hd", False),
            "hd_image_url": self.camera_data.get("latest_hd_image_url"),
            "peak_window": self.camera_data.get("peak_window", "Variable"),
            "recent_photos": self.camera_data.get("recent_photos", []),
            "buck_photos": self.camera_data.get("buck_photos", []),
            "doe_photos": self.camera_data.get("doe_photos", []),
            "person_photos": self.camera_data.get("person_photos", []),
        }

    def camera_image(
        self, width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[bytes]:
        """Return bytes of latest photo."""
        url = self.camera_data.get("latest_thumb_url") or self.camera_data.get("latest_image_url")
        guid = self.camera_data.get("latest_image_guid")
        return fetch_and_cache_image(url, guid=guid)


class StealthCamCapturePhotoCamera(CoordinatorEntity, Camera):
    """Camera entity representing a specific historical photo capture."""

    def __init__(
        self,
        coordinator: StealthCamDataUpdateCoordinator,
        camera_name: str,
        pdi: str,
        index: int,
    ) -> None:
        """Initialize capture photo camera entity."""
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self.camera_name = camera_name
        self.pdi = pdi
        self.index = index
        self._attr_unique_id = f"{pdi}_photo_{index + 1}"
        self._attr_name = f"{camera_name} Photo {index + 1}"

    @property
    def is_on(self) -> bool:
        """Return True if photo capture exists."""
        return bool(self.photo_data.get("image_url") or self.photo_data.get("thumb_url"))

    @property
    def photo_data(self) -> Dict[str, Any]:
        """Get photo capture data at specific index."""
        cam_data = self.coordinator.data.get(self.camera_name, {})
        photos = cam_data.get("recent_photos", [])
        if self.index < len(photos):
            return photos[self.index]
        return {}

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.pdi)},
            name=f"Stealth Cam {self.camera_name}",
        )

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes."""
        p = self.photo_data
        guid = p.get("guid")
        tag = p.get("tag", "")
        is_buck = p.get("is_buck", (tag == "buck"))
        is_doe = p.get("is_doe", (tag == "doe"))
        is_person = p.get("is_person", (tag == "person"))
        return {
            "image_url": p.get("image_url"),
            "thumbnail_url": p.get("thumb_url"),
            "hd_image_url": p.get("hd_image_url"),
            "image_guid": guid,
            "guid": guid,
            "time_str": p.get("time_str", "Recent"),
            "tag": tag,
            "is_buck": is_buck,
            "is_doe": is_doe,
            "is_person": is_person,
            "buck_score": p.get("buck_score"),
            "buck_id": p.get("buck_id"),
            "buck_name": p.get("buck_name"),
            "buck_points": p.get("buck_points"),
            "buck_age": p.get("buck_age"),
            "sighting_id": p.get("sighting_id"),
            "hq_photo_status": p.get("hq_photo_status", "NotRequested"),
            "is_hd": p.get("is_hd", False),
            "hour": p.get("hour", 0),
            "index": self.index + 1,
            "stand": self.camera_name,
        }

    def camera_image(
        self, width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[bytes]:
        """Return bytes of this specific capture."""
        guid = self.photo_data.get("guid")
        if guid:
            media_dir = getattr(self.coordinator.buck_tracker, "media_dir", "/media/stealthcam_bucks")
            for candidate in (f"{guid}_hd.jpg", f"{guid}.jpg"):
                local_file = os.path.join(media_dir, candidate)
                if os.path.exists(local_file):
                    try:
                        with open(local_file, "rb") as f:
                            return f.read()
                    except Exception:
                        pass
        url = self.photo_data.get("thumb_url") or self.photo_data.get("image_url")
        return fetch_and_cache_image(url, guid=guid)


class StealthCamProfiledBuckCamera(CoordinatorEntity, Camera):
    """Camera entity serving the permanent `/media/stealthcam_bucks/` hero portrait and analytics for a profiled buck."""

    _attr_icon = "mdi:deer"

    def __init__(
        self,
        coordinator: StealthCamDataUpdateCoordinator,
        index: int,
    ) -> None:
        """Initialize profiled buck camera slot."""
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self.index = index
        self._attr_unique_id = f"stealthcam_buck_profile_{index + 1}"
        self._attr_name = f"StealthCam Buck Profile {index + 1}"

    @property
    def buck_data(self) -> Dict[str, Any]:
        """Return buck profile dictionary for this slot."""
        reg = getattr(self.coordinator, "buck_registry_data", {}) or {}
        bucks = reg.get("bucks", [])
        if self.index < len(bucks):
            return bucks[self.index]
        return {}

    @property
    def is_on(self) -> bool:
        """Return True if this buck profile slot is populated."""
        return bool(self.buck_data.get("buck_id"))

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return full buck dossier and movement telemetry."""
        b = self.buck_data
        if not b:
            return {"active": False, "slot": self.index + 1}
        return {
            "active": True,
            "slot": self.index + 1,
            "buck_id": b.get("buck_id"),
            "buck_name": b.get("name"),
            "points": b.get("points"),
            "left_points": b.get("left_points"),
            "right_points": b.get("right_points"),
            "beam_spread": b.get("beam_spread"),
            "age_estimate": b.get("age_estimate"),
            "antler_notes": b.get("antler_notes"),
            "max_confidence": b.get("max_confidence", 90),
            "avg_confidence": b.get("avg_confidence", 88),
            "sightings_count": b.get("sightings_count", 0),
            "total_photos_count": b.get("total_photos_count", 0),
            "avg_burst_photos": b.get("avg_burst_photos", 1.0),
            "stands_visited_count": b.get("stands_visited_count", 1),
            "total_stands_count": b.get("total_stands_count", 6),
            "total_distance_yards": b.get("total_distance_yards", 0),
            "last_seen_formatted": b.get("last_seen_formatted"),
            "last_seen_stand": b.get("last_seen_stand"),
            "latitude": b.get("latitude"),
            "longitude": b.get("longitude"),
            "heading": b.get("heading"),
            "last_seen_temp": b.get("last_seen_temp"),
            "last_seen_pressure": b.get("last_seen_pressure"),
            "last_seen_pressure_tendency": b.get("last_seen_pressure_tendency"),
            "last_seen_wind": b.get("last_seen_wind"),
            "last_seen_moon": b.get("last_seen_moon"),
            "first_seen_formatted": b.get("first_seen_formatted"),
            "favorite_stand": b.get("favorite_stand"),
            "stand_breakdown": b.get("stand_breakdown", {}),
            "stand_analytics": b.get("stand_analytics", []),
            "preferred_window": b.get("preferred_window"),
            "window_breakdown": b.get("window_breakdown", {}),
            "hourly_histogram": b.get("hourly_histogram", {}),
            "daylight_sightings": b.get("daylight_sightings", 0),
            "night_sightings": b.get("night_sightings", 0),
            "daylight_pct": b.get("daylight_pct", 0),
            "avg_temp": b.get("avg_temp"),
            "min_temp": b.get("min_temp"),
            "max_temp": b.get("max_temp"),
            "temp_bands": b.get("temp_bands", {}),
            "avg_pressure": b.get("avg_pressure"),
            "min_pressure": b.get("min_pressure"),
            "max_pressure": b.get("max_pressure"),
            "pressure_trends": b.get("pressure_trends", {}),
            "avg_wind_speed": b.get("avg_wind_speed"),
            "preferred_wind": b.get("preferred_wind"),
            "wind_breakdown": b.get("wind_breakdown", {}),
            "moon_breakdown": b.get("moon_breakdown", {}),
            "hunt_prescription": b.get("hunt_prescription", {}),
            "travel_corridors": b.get("travel_corridors", []),
            "movement_waypoints": b.get("movement_waypoints", []),
            "movement_vectors": b.get("movement_vectors", []),
            "stands_gps": b.get("stands_gps", {}),
            "hero_guid": b.get("hero_guid"),
            "hero_local_path": b.get("hero_local_path"),
            "hero_media_source": b.get("hero_media_source"),
            "hero_is_hd": b.get("hero_is_hd", False),
            "movement_log": b.get("movement_log", []),
            "gallery": b.get("gallery", []),
        }

    def camera_image(
        self, width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[bytes]:
        """Return bytes of the buck's hero photo from `/media/stealthcam_bucks/` or fallback cloud URL."""
        b = self.buck_data
        if not b:
            return None
        local_path = b.get("hero_local_path")
        if local_path and os.path.exists(local_path):
            try:
                with open(local_path, "rb") as f:
                    return f.read()
            except Exception as ex:
                _LOGGER.warning("Failed reading local buck hero image %s: %s", local_path, ex)
        return fetch_and_cache_image(b.get("hero_cloud_url"), guid=b.get("hero_guid"))


class StealthCamBuckGalleryPhotoCamera(CoordinatorEntity, Camera):
    """Camera entity serving an individual historical capture in a profiled buck's photo gallery."""

    _attr_icon = "mdi:camera-burst"

    def __init__(
        self,
        coordinator: StealthCamDataUpdateCoordinator,
        buck_index: int,
        photo_index: int,
    ) -> None:
        """Initialize per-buck gallery photo camera slot."""
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self.buck_index = buck_index
        self.photo_index = photo_index
        self._attr_unique_id = f"stealthcam_buck_{buck_index + 1}_photo_{photo_index + 1}"
        self._attr_name = f"StealthCam Buck {buck_index + 1} Photo {photo_index + 1}"

    @property
    def buck_data(self) -> Dict[str, Any]:
        """Return buck profile dictionary for this buck index."""
        reg = getattr(self.coordinator, "buck_registry_data", {}) or {}
        bucks = reg.get("bucks", [])
        if self.buck_index < len(bucks):
            return bucks[self.buck_index]
        return {}

    @property
    def photo_data(self) -> Dict[str, Any]:
        """Return the specific gallery photo dictionary for this slot."""
        gallery = self.buck_data.get("gallery", [])
        if self.photo_index < len(gallery):
            return gallery[self.photo_index]
        return {}

    @property
    def is_on(self) -> bool:
        """Return True if this gallery photo slot is populated."""
        return bool(self.photo_data.get("guid"))

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return full metadata for this specific buck photo."""
        b = self.buck_data
        p = self.photo_data
        if not p:
            return {
                "active": False,
                "buck_slot": self.buck_index + 1,
                "photo_slot": self.photo_index + 1,
            }
        return {
            "active": True,
            "buck_slot": self.buck_index + 1,
            "photo_slot": self.photo_index + 1,
            "buck_id": b.get("buck_id"),
            "buck_name": b.get("name"),
            "points": b.get("points"),
            "guid": p.get("guid"),
            "stand": p.get("stand"),
            "latitude": p.get("latitude"),
            "longitude": p.get("longitude"),
            "heading": p.get("heading"),
            "time_str": p.get("time_formatted") or "Recent",
            "created_at": p.get("created_at"),
            "is_hd": p.get("is_hd", False),
            "hq_photo_status": p.get("hq_photo_status", "NotRequested"),
            "temperature": p.get("temperature"),
            "wind_cardinal": p.get("wind_cardinal"),
            "moon_phase": p.get("moon_phase"),
            "local_path": p.get("local_path"),
            "media_source_id": p.get("media_source_id"),
            "image_url": p.get("cloud_image_url"),
            "thumbnail_url": p.get("cloud_thumb_url") or p.get("cloud_image_url"),
        }

    def camera_image(
        self, width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[bytes]:
        """Return bytes of this buck gallery photo from `/media/stealthcam_bucks/` or fallback cloud URL."""
        p = self.photo_data
        if not p:
            return None
        local_path = p.get("local_path")
        if local_path and os.path.exists(local_path):
            try:
                with open(local_path, "rb") as f:
                    return f.read()
            except Exception as ex:
                _LOGGER.warning("Failed reading local buck gallery photo %s: %s", local_path, ex)
        url = p.get("cloud_image_url") or p.get("cloud_thumb_url")
        return fetch_and_cache_image(url, guid=p.get("guid"))


