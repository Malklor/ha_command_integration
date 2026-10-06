#!/usr/bin/env python3
"""
WebSocket listener for Home Assistant.
Listens for state changes on `input_text.stealthcam_tag_action` to instantly toggle
buck tagging on trail camera captures, re-sync HA, and refresh dashboards.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] tag_listener: %(message)s"
)
_LOGGER = logging.getLogger("tag_listener")

HA_WS = os.getenv("HA_WS", "ws://192.168.131.17:8123/api/websocket")
HA_TOKEN = os.getenv("HA_TOKEN", "")
if not HA_TOKEN and os.path.exists(".env"):
    with open(".env") as ef:
        for line in ef:
            if line.startswith("HA_TOKEN="):
                HA_TOKEN = line.split("=", 1)[1].strip()
TAGGED_FILE = "/home/tgoetz/Projects/ha_command_integration/tagged_bucks.json"

def toggle_buck(guid: str) -> bool:
    if not guid or guid == "none" or guid == "test_guid_123":
        return False
        
    data = {}
    if os.path.exists(TAGGED_FILE):
        try:
            with open(TAGGED_FILE) as f:
                data = json.load(f)
        except Exception:
            pass

    curr = data.get(guid, False)
    new_state = not curr
    if new_state:
        data[guid] = True
    else:
        data.pop(guid, None)

    with open(TAGGED_FILE, "w") as f:
        json.dump(data, f, indent=2)

    _LOGGER.info("Toggled buck status for GUID %s -> %s", guid, new_state)

    # Sync entities to HA (Lovelace custom:button-card updates reactively)
    subprocess.run(["python3", "/home/tgoetz/Projects/ha_command_integration/sync_to_ha.py"], check=False)
    return new_state

async def run_listener():
    _LOGGER.info("Starting StealthCam Tag Action WebSocket listener...")
    while True:
        try:
            async with websockets.connect(HA_WS) as ws:
                # Auth
                await ws.recv()
                await ws.send(json.dumps({"type": "auth", "access_token": HA_TOKEN}))
                auth_res = json.loads(await ws.recv())
                if auth_res.get("type") != "auth_ok":
                    _LOGGER.error("Auth failed: %s", auth_res)
                    await asyncio.sleep(5)
                    continue

                # Subscribe to state_changed events
                await ws.send(json.dumps({
                    "id": 1,
                    "type": "subscribe_events",
                    "event_type": "state_changed"
                }))
                sub_res = json.loads(await ws.recv())
                _LOGGER.info("Subscribed to state_changed events: %s", sub_res.get("success"))

                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("type") == "event":
                        event_data = msg.get("event", {}).get("data", {})
                        entity_id = event_data.get("entity_id")
                        if entity_id == "input_text.stealthcam_tag_action":
                            new_state = event_data.get("new_state", {}).get("state", "")
                            if new_state and new_state not in ["", "none", "idle", "test_guid_123"]:
                                _LOGGER.info("Received tag action for GUID: %s", new_state)
                                toggle_buck(new_state)
                                # Reset helper
                                await ws.send(json.dumps({
                                    "id": 2,
                                    "type": "call_service",
                                    "domain": "input_text",
                                    "service": "set_value",
                                    "service_data": {
                                        "entity_id": "input_text.stealthcam_tag_action",
                                        "value": ""
                                    }
                                }))
                                await ws.recv()

        except Exception as ex:
            _LOGGER.error("WebSocket connection error: %s, reconnecting in 5s...", ex)
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run_listener())
