"""Config flow for Stealth Cam Command integration."""
import logging
from typing import Any, Dict, Optional
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

try:
    from .stealthcam_api.client import StealthCamClient, StealthCamAuthError
except ImportError:
    from stealthcam_api.client import StealthCamClient, StealthCamAuthError
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class StealthCamConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Stealth Cam Command."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            client = StealthCamClient(email=email, password=password)

            try:
                await self.hass.async_add_executor_job(client.login)
            except StealthCamAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during Stealth Cam login")
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(email.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"Stealth Cam ({email})", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
