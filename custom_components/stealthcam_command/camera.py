"""Camera platform for Stealth Cam Command integration."""
import logging
from typing import Any, Dict, Optional
import requests

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StealthCamDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


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

    async_add_entities(entities)


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
    def entity_picture(self) -> Optional[str]:
        """Return entity picture thumbnail."""
        return self.camera_data.get("latest_thumb_url") or self.camera_data.get("latest_image_url")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes."""
        return {
            "image_url": self.camera_data.get("latest_image_url"),
            "thumbnail_url": self.camera_data.get("latest_thumb_url"),
            "image_guid": self.camera_data.get("latest_image_guid"),
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
            "peak_window": self.camera_data.get("peak_window", "Variable"),
            "recent_photos": self.camera_data.get("recent_photos", []),
            "buck_photos": self.camera_data.get("buck_photos", []),
        }

    def camera_image(
        self, width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[bytes]:
        """Return bytes of latest photo."""
        url = self.camera_data.get("latest_image_url") or self.camera_data.get("latest_thumb_url")
        if not url:
            return None
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                return res.content
        except Exception as ex:
            _LOGGER.error("Failed fetching photo bytes for %s: %s", self.camera_name, ex)
        return None
