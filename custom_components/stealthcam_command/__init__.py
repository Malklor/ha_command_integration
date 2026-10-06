"""The Stealth Cam Command integration."""
import json
import logging
import os
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, Event
from homeassistant.const import Platform, EVENT_STATE_CHANGED

from .const import DOMAIN
from .coordinator import StealthCamDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CAMERA]
TAGGED_FILE = "/config/stealthcam_tagged_bucks.json"


def _toggle_buck_tag(guid: str) -> bool:
    """Read, toggle, and save buck tag in HA storage."""
    if not guid or guid in ["", "none", "idle", "test_guid_123", "unknown"]:
        return False
    data = {}
    if os.path.exists(TAGGED_FILE):
        try:
            with open(TAGGED_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            pass
    curr = data.get(guid, False)
    new_state = not curr
    if new_state:
        data[guid] = True
    else:
        data.pop(guid, None)
    try:
        with open(TAGGED_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as ex:
        _LOGGER.error("Failed saving tagged bucks to %s: %s", TAGGED_FILE, ex)
    return new_state


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Stealth Cam Command from a config entry."""
    coordinator = StealthCamDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_tag_buck(call: ServiceCall):
        guid = call.data.get("guid")
        if guid:
            await hass.async_add_executor_job(_toggle_buck_tag, guid)
            await coordinator.async_request_refresh()

    async def handle_sync_now(call: ServiceCall):
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "tag_buck", handle_tag_buck)
    hass.services.async_register(DOMAIN, "toggle_buck", handle_tag_buck)
    hass.services.async_register(DOMAIN, "sync_now", handle_sync_now)

    async def async_state_change_listener(event: Event):
        entity_id = event.data.get("entity_id")
        if entity_id == "input_text.stealthcam_tag_action":
            new_state = event.data.get("new_state")
            if new_state and new_state.state and new_state.state not in ["", "none", "idle", "unknown"]:
                guid = new_state.state
                await hass.async_add_executor_job(_toggle_buck_tag, guid)
                # Reset helper
                await hass.services.async_call("input_text", "set_value", {"entity_id": "input_text.stealthcam_tag_action", "value": ""})
                await coordinator.async_request_refresh()

    entry.async_on_unload(hass.bus.async_listen(EVENT_STATE_CHANGED, async_state_change_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
