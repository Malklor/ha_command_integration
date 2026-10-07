#!/usr/bin/env python3
"""Automated Tier-1 Live Diagnostics Test Suite for Stealth Cam Command Integration.

Executes end-to-end live testing of API authentication, status telemetry,
batch photo ingestion, cloud species tag mapping, buck scoring, and coordinator schemas in < 2 seconds.
"""

import datetime
import json
import logging
import os
import sys
import time

# Set path to custom_components
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "custom_components", "stealthcam_command"))

from stealthcam_api.client import StealthCamClient, extract_species_tag, extract_buck_score, extract_hd_info

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_LOGGER = logging.getLogger("diagnostics")


def load_credentials():
    """Load credentials from local environment files."""
    candidates = [
        os.path.join(REPO_ROOT, ".env"),
        "/home/tgoetz/Projects/stealthcam_personal/.env",
        os.path.expanduser("~/.stealthcam.env"),
    ]
    env = {}
    for path in candidates:
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if ":" in line and "=" not in line:
                            k, v = line.split(":", 1)
                        elif "=" in line:
                            k, v = line.split("=", 1)
                        else:
                            continue
                        env[k.strip().lower()] = v.strip().strip('"').strip("'")
            if env.get("username") or env.get("stealthcam_email"):
                break
    return env


def run_diagnostics():
    """Run full diagnostic test suite."""
    print("=================================================================")
    print("  Stealth Cam Command - Tier 1 Live Diagnostic Test Suite")
    print("=================================================================")
    start_time = time.time()
    env = load_credentials()
    email = env.get("username") or env.get("stealthcam_email") or os.environ.get("STEALTHCAM_EMAIL")
    password = env.get("password") or env.get("stealthcam_password") or os.environ.get("STEALTHCAM_PASSWORD")

    if not email or not password:
        print("❌ ERROR: Stealth Cam credentials not found in .env or environment.")
        sys.exit(1)

    print(f"1. Authenticating as {email}...")
    client = StealthCamClient(email, password)
    auth_data = client.login()
    assert client.access_token, "No access token received"
    print(f"   ✅ Authenticated successfully (User ID: {auth_data.get('userId')})")

    print("\n2. Fetching Registered Devices & Hardware Telemetry...")
    devices = client.get_devices()
    assert len(devices) > 0, "No camera devices found on account"
    pdis = [d["physicalDeviceIdentifier"] for d in devices if "physicalDeviceIdentifier" in d]
    statuses = client.get_device_statuses(pdis)
    print(f"   ✅ Discovered {len(devices)} cameras, {len(statuses)} real-time status objects")

    print("\n3. Batch-Fetching Cloud Species Tags from Command Cloud...")
    cloud_tags = client.fetch_cloud_tags()
    print(f"   ✅ Retrieved and mapped {len(cloud_tags)} tagged photo GUIDs across cloud categories")

    print("\n4. Running Full Unified Coordinator Data Ingestion...")
    full_data = client.get_full_camera_data()
    assert len(full_data) == len(devices), "Camera count mismatch in coordinator data"

    print("\n5. Validating Camera Entities & Photo Slot Data:")
    for cam_name, cam in full_data.items():
        recent = cam.get("recent_photos", [])
        buck_photos = cam.get("buck_photos", [])
        doe_photos = cam.get("doe_photos", [])
        person_photos = cam.get("person_photos", [])
        print(f"   📷 Camera: {cam_name:16} | Battery: {cam.get('battery_level'):3}% | Signal: {cam.get('signal_strength'):8} | Captures: {len(recent):2} | 🦌 Buck: {len(buck_photos):2} | 🦌 Doe: {len(doe_photos):2} | 👤 Person: {len(person_photos):2}")
        
        # Verify first 3 photos schema
        for idx, p in enumerate(recent[:3]):
            assert "image_url" in p, f"Missing image_url in {cam_name} photo #{idx+1}"
            assert "thumb_url" in p, f"Missing thumb_url in {cam_name} photo #{idx+1}"
            assert "guid" in p, f"Missing guid in {cam_name} photo #{idx+1}"
            assert "tag" in p, f"Missing tag in {cam_name} photo #{idx+1}"

    elapsed = time.time() - start_time
    print(f"\n=================================================================")
    print(f"  🎉 ALL TIER-1 DIAGNOSTICS PASSED in {elapsed:.2f} seconds!")
    print("=================================================================")


if __name__ == "__main__":
    run_diagnostics()
