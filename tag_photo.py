#!/usr/bin/env python3
"""
Toggles or sets the Buck tag on a trail camera capture by Image GUID.
Updates tagged_bucks.json, syncs with Home Assistant, and refreshes dashboard views.
"""

import argparse
import json
import os
import subprocess
import sys

TAGGED_FILE = "/home/tgoetz/Projects/ha_command_integration/tagged_bucks.json"

def load_tagged() -> dict:
    if os.path.exists(TAGGED_FILE):
        try:
            with open(TAGGED_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_tagged(data: dict):
    with open(TAGGED_FILE, "w") as f:
        json.dump(data, f, indent=2)

def toggle_tag(guid: str, force_state=None) -> bool:
    data = load_tagged()
    curr = data.get(guid, False)
    new_state = (not curr) if force_state is None else bool(force_state)
    
    if new_state:
        data[guid] = True
    else:
        data.pop(guid, None)
        
    save_tagged(data)
    print(f"Photo {guid} buck tag set to: {new_state}")
    
    # Run sync and update dashboard
    subprocess.run(["python3", "/home/tgoetz/Projects/ha_command_integration/sync_to_ha.py"], check=False)
    subprocess.run(["python3", "/home/tgoetz/Projects/ha_command_integration/update_dashboard.py"], check=False)
    return new_state

def main():
    parser = argparse.ArgumentParser(description="Tag a photo as a verified buck hit")
    parser.add_argument("--guid", required=True, help="Image GUID")
    parser.add_argument("--untag", action="store_true", help="Remove buck tag")
    args = parser.parse_args()

    toggle_tag(args.guid, force_state=False if args.untag else None)

if __name__ == "__main__":
    main()
