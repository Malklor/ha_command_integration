"""Sensor platform for Stealth Cam Command integration."""
import datetime
import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
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
    """Set up Stealth Cam sensors based on a config entry."""
    coordinator: StealthCamDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for name, data in coordinator.data.items():
        pdi = data.get("pdi", name)
        entities.append(StealthCamBatterySensor(coordinator, name, pdi))
        entities.append(StealthCamSignalSensor(coordinator, name, pdi))
        entities.append(StealthCamSDFreeSensor(coordinator, name, pdi))
        entities.append(StealthCamLastCheckinSensor(coordinator, name, pdi))

    async_add_entities(entities)


class StealthCamBaseEntity(CoordinatorEntity):
    """Base entity for Stealth Cam."""

    def __init__(
        self,
        coordinator: StealthCamDataUpdateCoordinator,
        camera_name: str,
        pdi: str,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self.camera_name = camera_name
        self.pdi = pdi

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


class StealthCamBatterySensor(StealthCamBaseEntity, SensorEntity):
    """Battery sensor for Stealth Cam."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, camera_name: str, pdi: str) -> None:
        super().__init__(coordinator, camera_name, pdi)
        self._attr_unique_id = f"{pdi}_battery"
        self._attr_name = f"{camera_name} Battery"

    @property
    def native_value(self) -> Optional[int]:
        return self.camera_data.get("battery_level")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return {
            "battery_volt": self.camera_data.get("battery_volt"),
            "latitude": self.camera_data.get("latitude"),
            "longitude": self.camera_data.get("longitude"),
        }


class StealthCamSignalSensor(StealthCamBaseEntity, SensorEntity):
    """Cellular signal sensor for Stealth Cam."""

    _attr_icon = "mdi:signal-cellular-3"

    def __init__(self, coordinator, camera_name: str, pdi: str) -> None:
        super().__init__(coordinator, camera_name, pdi)
        self._attr_unique_id = f"{pdi}_signal"
        self._attr_name = f"{camera_name} Cellular Signal"

    @property
    def native_value(self) -> Optional[str]:
        return self.camera_data.get("signal_strength")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return {
            "rssi": self.camera_data.get("rssi"),
            "carrier": self.camera_data.get("carrier"),
        }


class StealthCamSDFreeSensor(StealthCamBaseEntity, SensorEntity):
    """SD card free space sensor for Stealth Cam."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:sd"

    def __init__(self, coordinator, camera_name: str, pdi: str) -> None:
        super().__init__(coordinator, camera_name, pdi)
        self._attr_unique_id = f"{pdi}_sd_free"
        self._attr_name = f"{camera_name} SD Free Space"

    @property
    def native_value(self) -> Optional[int]:
        return self.camera_data.get("sd_card_free_space")


class StealthCamLastCheckinSensor(StealthCamBaseEntity, SensorEntity):
    """Last sync check-in sensor for Stealth Cam."""

    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, coordinator, camera_name: str, pdi: str) -> None:
        super().__init__(coordinator, camera_name, pdi)
        self._attr_unique_id = f"{pdi}_last_checkin"
        self._attr_name = f"{camera_name} Last Check-In"

    @property
    def native_value(self) -> Optional[str]:
        unix_ts = self.camera_data.get("last_sync_unix")
        if unix_ts:
            return datetime.datetime.fromtimestamp(
                unix_ts / 1000.0, tz=datetime.timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S UTC")
        return None
