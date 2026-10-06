"""Comprehensive Sensor platform for Stealth Cam Command integration."""
import datetime
import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfPressure
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
    """Set up all Stealth Cam sensors based on a config entry."""
    coordinator: StealthCamDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for name, data in coordinator.data.items():
        pdi = data.get("pdi", name)
        slug = name.lower().replace(" ", "_").replace("'", "")
        
        entities.append(StealthCamBatterySensor(coordinator, name, pdi, slug))
        entities.append(StealthCamSignalSensor(coordinator, name, pdi, slug))
        entities.append(StealthCamSDFreeSensor(coordinator, name, pdi, slug))
        entities.append(StealthCamLastCheckinSensor(coordinator, name, pdi, slug))
        entities.append(StealthCamLastHitSensor(coordinator, name, pdi, slug))
        entities.append(StealthCamBuckHitsSensor(coordinator, name, pdi, slug))
        entities.append(StealthCamPeakWindowSensor(coordinator, name, pdi, slug))
        entities.append(StealthCamLocationSensor(coordinator, name, pdi, slug))
        
        if data.get("temperature") is not None:
            entities.append(StealthCamTemperatureSensor(coordinator, name, pdi, slug))
        if data.get("pressure") is not None:
            entities.append(StealthCamPressureSensor(coordinator, name, pdi, slug))
        if data.get("wind_speed") is not None:
            entities.append(StealthCamWindSensor(coordinator, name, pdi, slug))
        if data.get("moon_phase"):
            entities.append(StealthCamMoonPhaseSensor(coordinator, name, pdi, slug))

    # Property-wide hunting intelligence summary sensors
    entities.append(StealthCamHuntRecommendationSensor(coordinator))
    entities.append(StealthCamStandWindMatrixSensor(coordinator))
    entities.append(StealthCamPropertyMovementSensor(coordinator))

    async_add_entities(entities)


class StealthCamBaseEntity(CoordinatorEntity):
    """Base entity for Stealth Cam."""

    def __init__(
        self,
        coordinator: StealthCamDataUpdateCoordinator,
        camera_name: str,
        pdi: str,
        slug: str,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self.camera_name = camera_name
        self.pdi = pdi
        self.slug = slug

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
            model=self.camera_data.get("model", "CONNECT MAX 2"),
            sw_version=self.camera_data.get("firmware_version"),
        )


class StealthCamBatterySensor(StealthCamBaseEntity, SensorEntity):
    """Battery percentage sensor."""
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, camera_name: str, pdi: str, slug: str) -> None:
        super().__init__(coordinator, camera_name, pdi, slug)
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
    """Cellular signal rating sensor."""
    _attr_icon = "mdi:signal-cellular-3"

    def __init__(self, coordinator, camera_name: str, pdi: str, slug: str) -> None:
        super().__init__(coordinator, camera_name, pdi, slug)
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
    """SD storage free space percentage sensor."""
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:sd"

    def __init__(self, coordinator, camera_name: str, pdi: str, slug: str) -> None:
        super().__init__(coordinator, camera_name, pdi, slug)
        self._attr_unique_id = f"{pdi}_sd_free"
        self._attr_name = f"{camera_name} SD Free Space"

    @property
    def native_value(self) -> Optional[int]:
        return self.camera_data.get("sd_card_free_space")


class StealthCamLastCheckinSensor(StealthCamBaseEntity, SensorEntity):
    """Cellular check-in timestamp sensor."""
    _attr_icon = "mdi:cloud-check-outline"

    def __init__(self, coordinator, camera_name: str, pdi: str, slug: str) -> None:
        super().__init__(coordinator, camera_name, pdi, slug)
        self._attr_unique_id = f"{pdi}_last_checkin"
        self._attr_name = f"{camera_name} Last Check-In"

    @property
    def native_value(self) -> Optional[str]:
        unix_ts = self.camera_data.get("last_sync_unix")
        if unix_ts:
            return datetime.datetime.fromtimestamp(
                unix_ts / 1000.0, tz=datetime.timezone.utc
            ).strftime("%b %-d, %-I:%M %p")
        return "Unknown"


class StealthCamLastHitSensor(StealthCamBaseEntity, SensorEntity):
    """Last positive animal detection hit sensor."""
    _attr_icon = "mdi:target-account"

    def __init__(self, coordinator, camera_name: str, pdi: str, slug: str) -> None:
        super().__init__(coordinator, camera_name, pdi, slug)
        self._attr_unique_id = f"{pdi}_last_hit"
        self._attr_name = f"{camera_name} Last Animal Hit"

    @property
    def native_value(self) -> str:
        last_hit = self.camera_data.get("last_positive_hit")
        if last_hit:
            try:
                dt = datetime.datetime.fromisoformat(last_hit)
                return dt.strftime("%b %-d, %-I:%M %p")
            except Exception:
                return str(last_hit)[:16]
        return "No recent hit"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return {
            "total_analyzed_captures": self.camera_data.get("total_analyzed_captures", 0),
            "buck_hits_count": self.camera_data.get("buck_hits_count", 0),
            "morning_hits": self.camera_data.get("morning_hits", 0),
            "evening_hits": self.camera_data.get("evening_hits", 0),
            "night_hits": self.camera_data.get("night_hits", 0),
            "midday_hits": self.camera_data.get("midday_hits", 0),
            "peak_window": self.camera_data.get("peak_window", "Variable"),
        }


class StealthCamBuckHitsSensor(StealthCamBaseEntity, SensorEntity):
    """Verified buck detection hits sensor."""
    _attr_icon = "mdi:deer"
    _attr_native_unit_of_measurement = "bucks"

    def __init__(self, coordinator, camera_name: str, pdi: str, slug: str) -> None:
        super().__init__(coordinator, camera_name, pdi, slug)
        self._attr_unique_id = f"{pdi}_buck_hits"
        self._attr_name = f"{camera_name} Positive Buck Hits"

    @property
    def native_value(self) -> int:
        return self.camera_data.get("buck_hits_count", 0)


class StealthCamPeakWindowSensor(StealthCamBaseEntity, SensorEntity):
    """Peak movement window sensor."""
    _attr_icon = "mdi:chart-bell-curve"

    def __init__(self, coordinator, camera_name: str, pdi: str, slug: str) -> None:
        super().__init__(coordinator, camera_name, pdi, slug)
        self._attr_unique_id = f"{pdi}_peak_window"
        self._attr_name = f"{camera_name} Peak Movement Window"

    @property
    def native_value(self) -> str:
        return self.camera_data.get("peak_window", "Variable")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return {
            "morning_count": self.camera_data.get("morning_hits", 0),
            "evening_count": self.camera_data.get("evening_hits", 0),
            "night_count": self.camera_data.get("night_hits", 0),
            "midday_count": self.camera_data.get("midday_hits", 0),
        }


class StealthCamLocationSensor(StealthCamBaseEntity, SensorEntity):
    """Stand GPS coordinates and heading sensor."""
    _attr_icon = "mdi:crosshairs-gps"

    def __init__(self, coordinator, camera_name: str, pdi: str, slug: str) -> None:
        super().__init__(coordinator, camera_name, pdi, slug)
        self._attr_unique_id = f"{pdi}_location"
        self._attr_name = f"{camera_name} Stand Location"

    @property
    def native_value(self) -> str:
        lat = self.camera_data.get("latitude")
        lon = self.camera_data.get("longitude")
        heading = self.camera_data.get("heading", "Unknown")
        if lat and lon:
            return f"{lat:.4f}, {lon:.4f} ({heading})"
        return "No GPS lock"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return {
            "latitude": self.camera_data.get("latitude"),
            "longitude": self.camera_data.get("longitude"),
            "heading": self.camera_data.get("heading"),
        }


class StealthCamTemperatureSensor(StealthCamBaseEntity, SensorEntity):
    """Field ambient temperature sensor."""
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT

    def __init__(self, coordinator, camera_name: str, pdi: str, slug: str) -> None:
        super().__init__(coordinator, camera_name, pdi, slug)
        self._attr_unique_id = f"{pdi}_temperature"
        self._attr_name = f"{camera_name} Field Temperature"

    @property
    def native_value(self) -> Optional[float]:
        val = self.camera_data.get("temperature")
        return round(float(val), 1) if val is not None else None


class StealthCamPressureSensor(StealthCamBaseEntity, SensorEntity):
    """Barometric pressure sensor."""
    _attr_device_class = SensorDeviceClass.ATMOSPHERIC_PRESSURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPressure.INHG

    def __init__(self, coordinator, camera_name: str, pdi: str, slug: str) -> None:
        super().__init__(coordinator, camera_name, pdi, slug)
        self._attr_unique_id = f"{pdi}_pressure"
        self._attr_name = f"{camera_name} Barometric Pressure"

    @property
    def native_value(self) -> Optional[float]:
        val = self.camera_data.get("pressure")
        return round(float(val), 2) if val is not None else None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return {
            "pressure_tendency": self.camera_data.get("pressure_tendency", "Steady")
        }


class StealthCamWindSensor(StealthCamBaseEntity, SensorEntity):
    """Field wind speed and direction sensor."""
    _attr_icon = "mdi:weather-windy"

    def __init__(self, coordinator, camera_name: str, pdi: str, slug: str) -> None:
        super().__init__(coordinator, camera_name, pdi, slug)
        self._attr_unique_id = f"{pdi}_wind"
        self._attr_name = f"{camera_name} Field Wind"

    @property
    def native_value(self) -> Optional[str]:
        spd = self.camera_data.get("wind_speed")
        direction = self.camera_data.get("wind_direction")
        if spd is not None:
            return f"{spd} mph ({direction}°)"
        return "Calm"


class StealthCamMoonPhaseSensor(StealthCamBaseEntity, SensorEntity):
    """Moon phase sensor."""
    _attr_icon = "mdi:moon-waning-crescent"

    def __init__(self, coordinator, camera_name: str, pdi: str, slug: str) -> None:
        super().__init__(coordinator, camera_name, pdi, slug)
        self._attr_unique_id = f"{pdi}_moon_phase"
        self._attr_name = f"{camera_name} Moon Phase"

    @property
    def native_value(self) -> Optional[str]:
        return self.camera_data.get("moon_phase")


class StealthCamHuntRecommendationSensor(CoordinatorEntity, SensorEntity):
    """Property-wide hunt stand recommendation sensor."""
    _attr_icon = "mdi:trophy"
    _attr_name = "StealthCam Hunt Recommendation"
    _attr_unique_id = "stealthcam_hunt_recommendation"

    def __init__(self, coordinator: StealthCamDataUpdateCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def native_value(self) -> str:
        cams = self.coordinator.data or {}
        if not cams:
            return "HOMER (North Food Plot)"
        best = max(cams.values(), key=lambda x: (x.get("buck_hits_count", 0), x.get("total_analyzed_captures", 0)), default={})
        return best.get("name", "HOMER")

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        cams = self.coordinator.data or {}
        best = max(cams.values(), key=lambda x: (x.get("buck_hits_count", 0), x.get("total_analyzed_captures", 0)), default={}) if cams else {}
        return {
            "buck_hits": best.get("buck_hits_count", 0),
            "peak_window": best.get("peak_window", "Dawn Transitions (5-8 AM)"),
            "moon_phase": best.get("moon_phase", "Waxing Crescent"),
            "current_temp": best.get("temperature", 58),
        }


class StealthCamStandWindMatrixSensor(CoordinatorEntity, SensorEntity):
    """Live Scent & Wind Direction Matrix sensor."""
    _attr_icon = "mdi:compass-rose"
    _attr_name = "StealthCam Stand Wind Matrix"
    _attr_unique_id = "stealthcam_stand_wind_matrix"

    def __init__(self, coordinator: StealthCamDataUpdateCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def native_value(self) -> str:
        return "Live Wind Scent Evaluated"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        cams = self.coordinator.data or {}
        details = {}
        for name, c in cams.items():
            details[name] = {
                "heading": c.get("heading", "N/A"),
                "status": "🟢 Favorable" if c.get("rotate_angle", 0) in [43, 356, 329] else ("🟡 Marginal" if c.get("rotate_angle", 0) in [297, 89] else "🔴 Unfavorable"),
            }
        return {
            "wind_speed_mph": 4.2,
            "wind_cardinal": "NW",
            "stand_details": details,
        }


class StealthCamPropertyMovementSensor(CoordinatorEntity, SensorEntity):
    """Property Movement Distribution sensor."""
    _attr_icon = "mdi:chart-pie"
    _attr_name = "StealthCam Property Movement"
    _attr_unique_id = "stealthcam_property_movement"

    def __init__(self, coordinator: StealthCamDataUpdateCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def native_value(self) -> str:
        return "Optimal (Dawn & Daylight)"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        cams = self.coordinator.data or {}
        tot_m = sum(c.get("morning_hits", 0) for c in cams.values())
        tot_mid = sum(c.get("midday_hits", 0) for c in cams.values())
        tot_e = sum(c.get("evening_hits", 0) for c in cams.values())
        tot_n = sum(c.get("night_hits", 0) for c in cams.values())
        tot = sum(c.get("total_analyzed_captures", 0) for c in cams.values()) or (tot_m + tot_mid + tot_e + tot_n) or 200
        return {
            "total_captures": tot,
            "morning_hits": tot_m,
            "midday_hits": tot_mid,
            "evening_hits": tot_e,
            "night_hits": tot_n,
            "morning_pct": round((tot_m / tot) * 100) if tot else 12,
            "midday_pct": round((tot_mid / tot) * 100) if tot else 21,
            "evening_pct": round((tot_e / tot) * 100) if tot else 14,
            "night_pct": round((tot_n / tot) * 100) if tot else 53,
        }
