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
from buck_tracker import StealthCamBuckTracker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_LOGGER = logging.getLogger("diagnostics")


def load_credentials():
    """Load credentials from local environment files."""
    candidates = [
        os.path.join(REPO_ROOT, ".env"),
        os.path.join(os.path.dirname(REPO_ROOT), "stealthcam_personal", ".env"),
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


def test_consecutive_photo_deduplication():
    """Unit test verifying that consecutive buck or doe photos deduplicate to 1 sighting."""
    print("0. Running Unit Tests for Consecutive Buck/Doe Photo Deduplication...")
    client = StealthCamClient("test@example.com", "secret")
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Mock API methods so we can test get_full_camera_data deterministically
    client.get_devices = lambda: [
        {
            "physicalDeviceIdentifier": "PDI_TEST_1",
            "name": "NORTH RIDGE",
            "deviceId": 101,
        }
    ]
    client.get_device_statuses = lambda pdis: [
        {"physicalDeviceIdentifier": "PDI_TEST_1", "batteryLevel": 100, "signalStrength": "Good"}
    ]
    client.get_latest_images = lambda: [{"deviceName": "NORTH RIDGE"}]
    client.fetch_cloud_tags = lambda: {}

    # 5 consecutive buck photos, followed by 5 consecutive doe photos, followed by 1 untagged photo,
    # followed by 3 more consecutive buck photos -> should equal 2 buck hits (8 raw) and 1 doe hit (5 raw)
    captures = []
    for i in range(5):
        captures.append({"deviceId": 101, "imageGuid": f"buck_run1_{i}", "isBuck": True, "createdDateTime": now_iso})
    for i in range(5):
        captures.append({"deviceId": 101, "imageGuid": f"doe_run1_{i}", "isDoe": True, "createdDateTime": now_iso})
    captures.append({"deviceId": 101, "imageGuid": "empty_1", "createdDateTime": now_iso})
    for i in range(3):
        captures.append({"deviceId": 101, "imageGuid": f"buck_run2_{i}", "isBuck": True, "createdDateTime": now_iso})

    client.get_recent_captures = lambda limit=600: captures

    data = client.get_full_camera_data(tagged_bucks={})
    cam = data["NORTH RIDGE"]
    assert cam["buck_hits_count"] == 2, f"Expected 2 deduplicated buck hits, got {cam['buck_hits_count']}"
    assert cam["buck_hits_24h"] == 2, f"Expected 2 deduplicated 24h buck hits, got {cam['buck_hits_24h']}"
    assert cam["raw_buck_photos_count"] == 8, f"Expected 8 raw buck photos, got {cam['raw_buck_photos_count']}"
    assert cam["doe_hits_count"] == 1, f"Expected 1 deduplicated doe hit, got {cam['doe_hits_count']}"
    assert cam["doe_hits_24h"] == 1, f"Expected 1 deduplicated 24h doe hit, got {cam['doe_hits_24h']}"
    assert cam["raw_doe_photos_count"] == 5, f"Expected 5 raw doe photos, got {cam['raw_doe_photos_count']}"
    assert len(cam["buck_sightings"]) == 2, f"Expected 2 buck_sightings objects, got {len(cam['buck_sightings'])}"
    print("   ✅ Consecutive photo deduplication unit tests passed (5 consecutive bucks -> 1 hit, 5 consecutive does -> 1 hit)!\n")


def test_buck_tracker_and_iterative_hd():
    """Unit test for StealthCamBuckTracker, /media archiving, iterative HD escalation, and buck renaming."""
    import tempfile
    import shutil

    print("0b. Running Unit Tests for Buck Tracker & Iterative HD Escalation...")
    tmp_dir = tempfile.mkdtemp(prefix="stealthcam_test_")
    try:
        client = StealthCamClient("test@example.com", "secret")
        requested_hd = []
        client.request_hd_photo = lambda guid, dev_id=None, cancel=False: (requested_hd.append((guid, dev_id)) or True)
        client.get_image_details = lambda guid, dev_id=None: {
            "createdDateTime": "2026-10-27T00:27:14-05:00",
            "temperature": 48.0,
            "pressure": 30.05,
            "pressureTendency": "Rising",
            "wind": 5.0,
            "windDirection": 225.0,
            "moonPhase": "FullMoon",
            "hqPhotoStatus": "NotRequested",
        }

        tracker = StealthCamBuckTracker(
            client=client,
            media_dir=os.path.join(tmp_dir, "media_bucks"),
            profiles_file=os.path.join(tmp_dir, "profiles.json"),
        )
        tracker._download_to_media = lambda url, fname, force=False: os.path.join(tmp_dir, "media_bucks", fname)

        # Simulate a 3-photo consecutive buck burst with low-confidence initial frame
        mock_cam_data = {
            "SOUTH PLOT": {
                "buck_sightings": [
                    {
                        "sighting_id": "101_guid_frame_1",
                        "camera_name": "SOUTH PLOT",
                        "device_id": 101,
                        "pdi": "PDI_101",
                        "hero_guid": "guid_frame_1",
                        "created_at": "2026-10-27T00:27:14-05:00",
                        "guids": ["guid_frame_1", "guid_frame_2", "guid_frame_3"],
                        "captures": [
                            {"imageGuid": "guid_frame_1", "hqPhotoStatus": "NotRequested", "imageUrls": ["http://example/1.jpg"]},
                            {"imageGuid": "guid_frame_2", "hqPhotoStatus": "NotRequested", "imageUrls": ["http://example/2.jpg"]},
                            {"imageGuid": "guid_frame_3", "hqPhotoStatus": "NotRequested", "imageUrls": ["http://example/3.jpg"]},
                        ],
                    }
                ],
                "recent_photos": [{"guid": "guid_frame_1"}],
            }
        }

        # Step 1: Initial ingestion requests HD only for Frame #1 (guid_frame_1)
        summary = tracker.process_camera_data(mock_cam_data)
        assert len(requested_hd) == 1 and requested_hd[0][0] == "guid_frame_1", f"Expected HD request only on frame 1, got {requested_hd}"
        assert summary["unique_bucks_count"] == 1

        # Step 2: Simulate Frame #1 HD failing (or low confidence after HD) -> should automatically escalate to Frame #2!
        mock_cam_data["SOUTH PLOT"]["buck_sightings"][0]["captures"][0]["hqPhotoStatus"] = "Failed"
        summary2 = tracker.process_camera_data(mock_cam_data)
        assert len(requested_hd) == 2 and requested_hd[1][0] == "guid_frame_2", f"Expected iterative escalation to frame 2, got {requested_hd}"

        # Step 3: Test renaming the buck profile
        buck_id = summary2["bucks"][0]["buck_id"]
        assert tracker.rename_buck(buck_id, "Goliath 10", points="10-PT (5x5)", antler_notes="Tall G2s")
        summary3 = tracker.get_summary_payload()
        assert summary3["bucks"][0]["name"] == "Goliath 10"
        assert summary3["bucks"][0]["points"] == "10-PT (5x5)"
        print("   ✅ Buck Tracker & Iterative HD Escalation unit tests passed (Frame #1 -> Frame #2 escalation + Buck Renaming)!\n")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def run_diagnostics():
    """Run full diagnostic test suite."""
    print("=================================================================")
    print("  Stealth Cam Command - Tier 1 Live Diagnostic Test Suite")
    print("=================================================================")
    test_consecutive_photo_deduplication()
    test_buck_tracker_and_iterative_hd()
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
        print(
            f"   📷 Camera: {cam_name:16} | Battery: {cam.get('battery_level'):3}% | Signal: {cam.get('signal_strength'):8} "
            f"| Captures: {len(recent):2} | 🦌 Buck Hits: {cam.get('buck_hits_count', 0):2} (Raw: {cam.get('raw_buck_photos_count', 0):2}) "
            f"| 🦌 Doe Hits: {cam.get('doe_hits_count', 0):2} (Raw: {cam.get('raw_doe_photos_count', 0):2}) "
            f"| 👤 Person: {cam.get('person_hits_count', 0):2}"
        )
        
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
