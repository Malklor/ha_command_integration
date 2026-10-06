"""DataUpdateCoordinator for Stealth Cam Command."""
import datetime
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from stealthcam_api.client import StealthCamClient, StealthCamAuthError, StealthCamAPIError
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class StealthCamDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Stealth Cam data from cloud."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.entry = entry
        email = entry.data[CONF_EMAIL]
        password = entry.data[CONF_PASSWORD]
        self.client = StealthCamClient(email=email, password=password)
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=datetime.timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self):
        """Fetch data from Stealth Cam Command API."""
        try:
            return await self.hass.async_add_executor_job(
                self.client.get_full_camera_data
            )
        except (StealthCamAuthError, StealthCamAPIError) as err:
            raise UpdateFailed(f"Error communicating with Stealth Cam API: {err}") from err
