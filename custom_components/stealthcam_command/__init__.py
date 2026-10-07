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


def _toggle_tag(guid: str, tag_type: str = "buck") -> str:
    """Read, toggle, and save photo tag in HA storage."""
    if not guid or guid in ["", "none", "idle", "test_guid_123", "unknown"]:
        return ""
    data = {}
    if os.path.exists(TAGGED_FILE):
        try:
            with open(TAGGED_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            pass
    curr = data.get(guid)
    if curr is True:
        curr = "buck"

    if curr == tag_type:
        data.pop(guid, None)
        new_tag = ""
    else:
        data[guid] = tag_type
        new_tag = tag_type

    try:
        with open(TAGGED_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as ex:
        _LOGGER.error("Failed saving tagged photos to %s: %s", TAGGED_FILE, ex)
    return new_tag


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Stealth Cam Command from a config entry."""
    coordinator = StealthCamDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_tag_buck(call: ServiceCall):
        guid = call.data.get("guid")
        if guid:
            await hass.async_add_executor_job(_toggle_tag, guid, "buck")
            await coordinator.async_request_refresh()

    async def handle_tag_doe(call: ServiceCall):
        guid = call.data.get("guid")
        if guid:
            await hass.async_add_executor_job(_toggle_tag, guid, "doe")
            await coordinator.async_request_refresh()

    async def handle_tag_person(call: ServiceCall):
        guid = call.data.get("guid")
        if guid:
            await hass.async_add_executor_job(_toggle_tag, guid, "person")
            await coordinator.async_request_refresh()

    async def handle_tag_photo(call: ServiceCall):
        guid = call.data.get("guid")
        tag_type = call.data.get("type", "buck")
        if guid:
            await hass.async_add_executor_job(_toggle_tag, guid, tag_type)
            await coordinator.async_request_refresh()

    async def handle_request_hd(call: ServiceCall):
        guid = call.data.get("guid")
        if guid:
            await hass.async_add_executor_job(coordinator.client.request_hd_photo, guid)
            await coordinator.async_request_refresh()

    async def handle_sync_now(call: ServiceCall):
        await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "tag_buck", handle_tag_buck)
    hass.services.async_register(DOMAIN, "tag_doe", handle_tag_doe)
    hass.services.async_register(DOMAIN, "tag_person", handle_tag_person)
    hass.services.async_register(DOMAIN, "tag_photo", handle_tag_photo)
    hass.services.async_register(DOMAIN, "toggle_buck", handle_tag_buck)
    hass.services.async_register(DOMAIN, "request_hd", handle_request_hd)
    hass.services.async_register(DOMAIN, "sync_now", handle_sync_now)

    async def async_state_change_listener(event: Event):
        entity_id = event.data.get("entity_id")
        if entity_id == "input_text.stealthcam_tag_action":
            new_state = event.data.get("new_state")
            if new_state and new_state.state and new_state.state not in ["", "none", "idle", "unknown"]:
                parts = new_state.state.split(":", 1)
                guid = parts[0].strip()
                tag_type = parts[1].strip().lower() if len(parts) > 1 else "buck"
                await hass.async_add_executor_job(_toggle_tag, guid, tag_type)
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
