"""Buck Registry, Iterative HD Photo Requester, and AI Vision Profiler for Stealth Cam Command."""

import base64
import datetime
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import requests

try:
    from .stealthcam_api.client import StealthCamClient, degrees_to_cardinal, extract_hd_info
except ImportError:
    from stealthcam_api.client import StealthCamClient, degrees_to_cardinal, extract_hd_info

_LOGGER = logging.getLogger(__name__)

DEFAULT_MEDIA_DIR = "/media/stealthcam_bucks"
FALLBACK_MEDIA_DIR = os.path.abspath("media_bucks")
DEFAULT_PROFILES_FILE = "/config/stealthcam_buck_profiles.json"
FALLBACK_PROFILES_FILE = os.path.abspath("stealthcam_buck_profiles.json")
DEFAULT_SEED_FILE = "/config/stealthcam_buck_seed.json"


def _load_optional_seed_sightings() -> Dict[str, Dict[str, Any]]:
    """Load optional local seed sightings from `/config/stealthcam_buck_seed.json` if present."""
    if os.path.exists(DEFAULT_SEED_FILE):
        try:
            with open(DEFAULT_SEED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


INITIAL_SEEDED_SIGHTINGS: Dict[str, Dict[str, Any]] = _load_optional_seed_sightings()


def slugify_buck_id(name: str) -> str:
    """Create a stable buck_id from a buck name."""
    cleaned = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not cleaned.startswith("buck_"):
        cleaned = f"buck_{cleaned}"
    return cleaned or "buck_unknown"


def get_time_window_label(hour: Optional[int]) -> str:
    """Classify hour into Dawn, Midday, Dusk, or Night."""
    if hour is None:
        return "Night"
    if 5 <= hour < 9:
        return "Dawn"
    if 9 <= hour < 17:
        return "Midday"
    if 17 <= hour < 21:
        return "Dusk"
    return "Night"


class StealthCamBuckTracker:
    """Manages persistent buck profiles, `/media/stealthcam_bucks` photo storage, iterative HD requests, and AI profiling."""

    def __init__(
        self,
        client: StealthCamClient,
        media_dir: Optional[str] = None,
        profiles_file: Optional[str] = None,
        ai_api_key: Optional[str] = None,
        ai_provider: str = "gemini",
    ) -> None:
        """Initialize the buck tracker."""
        self.client = client
        if media_dir:
            self.media_dir = media_dir
        elif os.path.exists("/media") and os.access("/media", os.W_OK):
            self.media_dir = DEFAULT_MEDIA_DIR
        else:
            self.media_dir = FALLBACK_MEDIA_DIR

        if profiles_file:
            self.profiles_file = profiles_file
        elif os.path.exists("/config") and os.access("/config", os.W_OK):
            self.profiles_file = DEFAULT_PROFILES_FILE
        else:
            self.profiles_file = FALLBACK_PROFILES_FILE

        self.ai_api_key = ai_api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.ai_provider = ai_provider
        os.makedirs(self.media_dir, exist_ok=True)
        self.db: Dict[str, Any] = self._load_db()

    def _load_db(self) -> Dict[str, Any]:
        """Load persistent buck profile database from disk."""
        if os.path.exists(self.profiles_file):
            try:
                with open(self.profiles_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "bucks" in data and "sightings" in data:
                        return data
            except Exception as ex:
                _LOGGER.warning("Failed reading buck profiles from %s: %s", self.profiles_file, ex)
        return {
            "bucks": {},
            "sightings": {},
            "guid_to_sighting": {},
            "config": {
                "ai_provider": self.ai_provider,
                "ai_api_key": self.ai_api_key or "",
                "auto_request_hd": True,
                "confidence_threshold": 0.78,
            },
        }

    def save_db(self) -> None:
        """Persist buck profile database to disk."""
        try:
            parent = os.path.dirname(self.profiles_file)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self.profiles_file, "w", encoding="utf-8") as f:
                json.dump(self.db, f, indent=2)
        except Exception as ex:
            _LOGGER.error("Failed saving buck profiles to %s: %s", self.profiles_file, ex)

    def set_ai_credentials(self, provider: str, api_key: str) -> None:
        """Update AI Vision provider and API key in persistent config."""
        self.ai_provider = provider.lower().strip()
        self.ai_api_key = api_key.strip()
        self.db.setdefault("config", {})["ai_provider"] = self.ai_provider
        self.db["config"]["ai_api_key"] = self.ai_api_key
        self.save_db()

    def _download_to_media(self, url: Optional[str], filename: str, force: bool = False) -> Optional[str]:
        """Download an image URL to `/media/stealthcam_bucks/<filename>` and return the absolute path."""
        if not url:
            return None
        dest = os.path.join(self.media_dir, filename)
        if os.path.exists(dest) and os.path.getsize(dest) > 1000 and not force:
            return dest
        try:
            res = requests.get(url, timeout=15)
            if res.status_code == 200 and res.content and len(res.content) > 1000:
                with open(dest, "wb") as f:
                    f.write(res.content)
                return dest
        except Exception as ex:
            _LOGGER.warning("Failed downloading buck image %s to %s: %s", url[:60], dest, ex)
        return dest if os.path.exists(dest) else None

    def _call_ai_vision_profiler(
        self,
        image_path: str,
        camera_name: str,
        created_at: str,
        existing_bucks: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Call Gemini or OpenAI Vision API to profile antlers and match against existing named bucks."""
        cfg = self.db.get("config", {})
        api_key = self.ai_api_key or cfg.get("ai_api_key")
        provider = (self.ai_provider or cfg.get("ai_provider") or "gemini").lower()
        if not api_key or not image_path or not os.path.exists(image_path):
            return None

        try:
            with open(image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            return None

        roster_summary = []
        for bid, binfo in existing_bucks.items():
            roster_summary.append(
                f"- ID `{bid}`: Name='{binfo.get('name')}', Points='{binfo.get('points')}', "
                f"Spread='{binfo.get('beam_spread')}', Age='{binfo.get('age_estimate')}', "
                f"Notes='{binfo.get('antler_notes')}'"
            )
        roster_text = "\n".join(roster_summary) if roster_summary else "None yet."

        prompt = (
            "You are an expert whitetail deer biologist and trail-camera buck profiler.\n"
            f"Analyze this trail camera photo captured at stand '{camera_name}' at '{created_at}'.\n"
            "Existing Known Bucks on this property:\n"
            f"{roster_text}\n\n"
            "Respond ONLY with a valid JSON object matching this exact schema:\n"
            "{\n"
            '  "antlers_clearly_visible": true/false,\n'
            '  "profile_confidence": 0.0 to 1.0,\n'
            '  "points": "e.g. 8-PT (4x4) or 6-PT (3x3) or 4-PT (Fork) or Unknown",\n'
            '  "left_points": integer,\n'
            '  "right_points": integer,\n'
            '  "beam_spread": "e.g. Wide (17\\" Outside Ears) or Inside Ears (14\\")",\n'
            '  "age_estimate": "e.g. 1.5 Years, 2.5 Years, or 3.5+ Years (Mature)",\n'
            '  "antler_notes": "Detailed description of main beams, G2/G3 tine height, brow tines, symmetry, and posture",\n'
            '  "matched_buck_id": "existing buck_id if this is the same buck, or null if a new unique buck",\n'
            '  "suggested_name": "descriptive name if new buck, e.g. Wide 8 or Split Brow 10"\n'
            "}"
        )

        try:
            if "openai" in provider:
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {
                    "model": "gpt-4o",
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                            ],
                        }
                    ],
                }
                res = requests.post(url, headers=headers, json=payload, timeout=25)
                if res.status_code == 200:
                    content = res.json()["choices"][0]["message"]["content"]
                    return json.loads(content)
            else:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": prompt},
                                {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
                            ]
                        }
                    ],
                    "generationConfig": {"responseMimeType": "application/json"},
                }
                res = requests.post(url, json=payload, timeout=25)
                if res.status_code == 200:
                    candidates = res.json().get("candidates", [])
                    if candidates:
                        text = candidates[0]["content"]["parts"][0]["text"]
                        return json.loads(text)
        except Exception as ex:
            _LOGGER.warning("AI Vision buck profiling call failed: %s", ex)
        return None

    def process_camera_data(self, camera_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Ingest deduplicated buck sightings across all cameras, archive to `/media`, manage iterative HD requests, and rebuild buck dossiers."""
        sightings_db = self.db.setdefault("sightings", {})
        guid_map = self.db.setdefault("guid_to_sighting", {})
        bucks_db = self.db.setdefault("bucks", {})
        cfg = self.db.setdefault("config", {})
        auto_hd = cfg.get("auto_request_hd", True)
        conf_threshold = float(cfg.get("confidence_threshold", 0.78))

        changed = False

        # Collect all buck sightings from all cameras
        all_sightings: List[Dict[str, Any]] = []
        cam_gps_map: Dict[str, Dict[str, Any]] = {}
        for cam_name, cdata in camera_data.items():
            cam_gps_map[cam_name] = {
                "latitude": cdata.get("latitude"),
                "longitude": cdata.get("longitude"),
                "heading": cdata.get("heading"),
            }
            for b_sighting in cdata.get("buck_sightings", []):
                all_sightings.append(b_sighting)

        for s in all_sightings:
            hero_guid = s["hero_guid"]
            if not hero_guid:
                continue
            sighting_id = s["sighting_id"]
            cam_name = s["camera_name"]
            dev_id = s["device_id"]
            captures = s.get("captures", [])
            guids = s.get("guids", [])
            gps_info = cam_gps_map.get(cam_name, {})
            lat = s.get("latitude") if s.get("latitude") is not None else gps_info.get("latitude")
            lon = s.get("longitude") if s.get("longitude") is not None else gps_info.get("longitude")
            heading = s.get("heading") or gps_info.get("heading") or "Unknown"

            for g in guids:
                guid_map[g] = sighting_id

            existing_s = sightings_db.get(sighting_id)

            # Archive every photo in this consecutive burst to /media/stealthcam_bucks/
            saved_photos: List[Dict[str, Any]] = []
            for idx, cap in enumerate(captures):
                c_guid = cap.get("imageGuid") or cap.get("guid") or f"{hero_guid}_{idx}"
                is_hd, hd_url = extract_hd_info(cap)
                std_url = (cap.get("imageUrls") or [None])[0] or cap.get("imageUrl")
                thumb_url = (cap.get("thumbnailUrls") or [None])[0] or cap.get("thumbnailUrl") or std_url
                hq_status = cap.get("hqPhotoStatus", "NotRequested")

                std_filename = f"{c_guid}.jpg"
                hd_filename = f"{c_guid}_hd.jpg"

                local_std = self._download_to_media(std_url, std_filename)
                local_hd = None
                if is_hd and hd_url:
                    local_hd = self._download_to_media(hd_url, hd_filename, force=True)

                best_local = local_hd or local_std
                best_filename = hd_filename if local_hd else std_filename

                saved_photos.append({
                    "guid": c_guid,
                    "index_in_burst": idx,
                    "created_at": cap.get("createdDateTime") or cap.get("uploadedTime"),
                    "latitude": lat,
                    "longitude": lon,
                    "heading": heading,
                    "is_hd": bool(local_hd or is_hd),
                    "hq_photo_status": hq_status,
                    "local_path": best_local,
                    "media_filename": best_filename,
                    "media_source_id": f"media-source://media_source/local/stealthcam_bucks/{best_filename}",
                    "cloud_image_url": hd_url if (is_hd and hd_url) else std_url,
                    "cloud_thumb_url": thumb_url,
                })

            if existing_s is None:
                # Fetch V3 image details for rich environmental telemetry (temp, wind, pressure, moon, bounding box)
                v3_details = self.client.get_image_details(hero_guid, dev_id)
                temp = v3_details.get("temperature")
                pressure = v3_details.get("pressure")
                pressure_tendency = v3_details.get("pressureTendency", "Steady")
                wind_spd = v3_details.get("wind")
                wind_dir = v3_details.get("windDirection")
                moon = v3_details.get("moonPhase")
                hq_status = v3_details.get("hqPhotoStatus") or (saved_photos[0]["hq_photo_status"] if saved_photos else "NotRequested")
                rec_results = v3_details.get("animalRecognitionResults") or []
                ai_precision = rec_results[0].get("precision") if rec_results else None

                created_iso = v3_details.get("createdDateTime") or s.get("created_at") or ""
                hour = None
                time_formatted = created_iso[:16]
                if created_iso:
                    try:
                        dt_obj = datetime.datetime.fromisoformat(created_iso)
                        hour = dt_obj.hour
                        time_formatted = dt_obj.strftime("%b %-d, %-I:%M %p")
                    except Exception:
                        pass

                # Check if this sighting is in our initial baseline or call AI Vision profiler
                seeded = INITIAL_SEEDED_SIGHTINGS.get(hero_guid)
                ai_profile = None
                if not seeded and saved_photos and saved_photos[0].get("local_path"):
                    ai_profile = self._call_ai_vision_profiler(
                        saved_photos[0]["local_path"],
                        cam_name,
                        created_iso,
                        bucks_db,
                    )

                profile_data = ai_profile or seeded or {}
                antlers_visible = bool(profile_data.get("antlers_clearly_visible", False))
                conf = float(profile_data.get("profile_confidence", 0.5))
                buck_name = (
                    profile_data.get("buck_name")
                    or profile_data.get("suggested_name")
                    or f"{cam_name.title()} Buck"
                )
                buck_id = (
                    profile_data.get("matched_buck_id")
                    or profile_data.get("buck_id")
                    or slugify_buck_id(buck_name)
                )

                # Iterative HD request logic:
                # 1. Always request HD for Candidate #0 (the hero photo) if NotRequested so we get the HD portrait
                #    OR to resolve low-confidence standard photos.
                hd_candidate_index = 0
                hd_requested_guids: List[str] = []
                if auto_hd and saved_photos:
                    cand_guid = saved_photos[0]["guid"]
                    if hq_status == "NotRequested":
                        if self.client.request_hd_photo(cand_guid, dev_id):
                            hq_status = "Pending"
                            saved_photos[0]["hq_photo_status"] = "Pending"
                            hd_requested_guids.append(cand_guid)
                    elif hq_status in ("Pending", "Completed"):
                        hd_requested_guids.append(cand_guid)

                existing_s = {
                    "sighting_id": sighting_id,
                    "hero_guid": hero_guid,
                    "camera_name": cam_name,
                    "device_id": dev_id,
                    "latitude": lat,
                    "longitude": lon,
                    "heading": heading,
                    "created_at": created_iso,
                    "time_formatted": time_formatted,
                    "hour": hour,
                    "time_window": get_time_window_label(hour),
                    "burst_count": len(saved_photos),
                    "guids": guids,
                    "photos": saved_photos,
                    "temperature": temp,
                    "pressure": pressure,
                    "pressure_tendency": pressure_tendency,
                    "wind_speed": wind_spd,
                    "wind_direction": wind_dir,
                    "wind_cardinal": degrees_to_cardinal(wind_dir) if wind_dir is not None else "N/A",
                    "moon_phase": moon,
                    "ai_precision": ai_precision,
                    "buck_id": buck_id,
                    "buck_name": buck_name,
                    "points": profile_data.get("points", "Unknown"),
                    "left_points": profile_data.get("left_points"),
                    "right_points": profile_data.get("right_points"),
                    "beam_spread": profile_data.get("beam_spread", "Unknown"),
                    "age_estimate": profile_data.get("age_estimate", "Unknown"),
                    "antler_notes": profile_data.get("antler_notes", "Awaiting HD photo or manual review."),
                    "profile_confidence": conf,
                    "antlers_clearly_visible": antlers_visible,
                    "manual_override": False,
                    # Iterative HD state machine
                    "hd_candidate_index": hd_candidate_index,
                    "hd_requested_guids": hd_requested_guids,
                    "hd_status": "Completed" if any(p["is_hd"] for p in saved_photos) else hq_status,
                    "profiled_on_hd": any(p["is_hd"] for p in saved_photos),
                }
                sightings_db[sighting_id] = existing_s
                changed = True
            else:
                # Sighting already exists: update photo statuses, GPS coordinates, and run Iterative HD State Machine!
                existing_s["photos"] = saved_photos
                existing_s["burst_count"] = len(saved_photos)
                if lat is not None and existing_s.get("latitude") != lat:
                    existing_s["latitude"] = lat
                    existing_s["longitude"] = lon
                    existing_s["heading"] = heading
                    changed = True
                cand_idx = int(existing_s.get("hd_candidate_index", 0))
                if cand_idx < len(saved_photos):
                    cand_photo = saved_photos[cand_idx]
                    # Check if HD photo just arrived for the current candidate!
                    if cand_photo["is_hd"] and not existing_s.get("profiled_on_hd"):
                        existing_s["hd_status"] = "Completed"
                        if not existing_s.get("manual_override") and cand_photo.get("local_path"):
                            hd_ai = self._call_ai_vision_profiler(
                                cand_photo["local_path"],
                                cam_name,
                                existing_s.get("created_at", ""),
                                bucks_db,
                            )
                            if hd_ai:
                                existing_s["profile_confidence"] = float(hd_ai.get("profile_confidence", existing_s["profile_confidence"]))
                                existing_s["antlers_clearly_visible"] = bool(hd_ai.get("antlers_clearly_visible", True))
                                existing_s["points"] = hd_ai.get("points") or existing_s["points"]
                                existing_s["beam_spread"] = hd_ai.get("beam_spread") or existing_s["beam_spread"]
                                existing_s["age_estimate"] = hd_ai.get("age_estimate") or existing_s["age_estimate"]
                                existing_s["antler_notes"] = hd_ai.get("antler_notes") or existing_s["antler_notes"]
                                if hd_ai.get("matched_buck_id"):
                                    existing_s["buck_id"] = hd_ai["matched_buck_id"]
                        existing_s["profiled_on_hd"] = True
                        changed = True

                    # Iterative Fallback Escalation:
                    # If Candidate #cand_idx failed HD upload OR was profiled with low confidence (< threshold / antlers not visible),
                    # automatically step to Candidate #(cand_idx + 1) in the burst and request its HD photo!
                    needs_escalation = (
                        cand_photo.get("hq_photo_status") == "Failed"
                        or (
                            existing_s.get("profiled_on_hd")
                            and not existing_s.get("antlers_clearly_visible")
                            and float(existing_s.get("profile_confidence", 0)) < conf_threshold
                        )
                    )
                    if auto_hd and needs_escalation and (cand_idx + 1) < len(saved_photos):
                        next_idx = cand_idx + 1
                        next_guid = saved_photos[next_idx]["guid"]
                        req_list = existing_s.setdefault("hd_requested_guids", [])
                        if next_guid not in req_list:
                            _LOGGER.info(
                                "Iterative HD Escalation for sighting %s: stepping from frame #%d to frame #%d (%s)",
                                sighting_id,
                                cand_idx + 1,
                                next_idx + 1,
                                next_guid,
                            )
                            if self.client.request_hd_photo(next_guid, dev_id):
                                req_list.append(next_guid)
                                existing_s["hd_candidate_index"] = next_idx
                                existing_s["hd_status"] = f"Pending (Frame #{next_idx + 1})"
                                existing_s["profiled_on_hd"] = False
                                changed = True

        # Backfill any older sightings in sightings_db that were recorded before GPS fields were added
        for sid, s_obj in sightings_db.items():
            cname = s_obj.get("camera_name")
            if cname in cam_gps_map:
                ginfo = cam_gps_map[cname]
                if s_obj.get("latitude") is None and ginfo.get("latitude") is not None:
                    s_obj["latitude"] = ginfo["latitude"]
                    s_obj["longitude"] = ginfo["longitude"]
                    s_obj["heading"] = ginfo.get("heading", "Unknown")
                    for p_obj in s_obj.get("photos", []):
                        p_obj["latitude"] = ginfo["latitude"]
                        p_obj["longitude"] = ginfo["longitude"]
                        p_obj["heading"] = ginfo.get("heading", "Unknown")
                    changed = True

        # Store camera stand GPS positions in db so _rebuild_buck_profiles can build full property map context
        if cam_gps_map:
            self.db["stands_gps"] = cam_gps_map

        # Rebuild aggregated Buck Profiles from all sightings
        self._rebuild_buck_profiles()
        if changed:
            self.save_db()

        # Enrich camera_data buck_photos with buck_id and buck_name so camera cards show the buck identity
        for cam_name, cdata in camera_data.items():
            for p in cdata.get("recent_photos", []):
                g = p.get("guid")
                sid = guid_map.get(g)
                if sid and sid in sightings_db:
                    s_obj = sightings_db[sid]
                    p["buck_id"] = s_obj.get("buck_id")
                    p["buck_name"] = s_obj.get("buck_name")
                    p["buck_points"] = s_obj.get("points")
                    p["buck_age"] = s_obj.get("age_estimate")
                    p["sighting_id"] = sid
                    if not p.get("buck_score") and s_obj.get("points") and s_obj.get("points") != "Unknown":
                        p["buck_score"] = s_obj.get("points")

        return self.get_summary_payload()

    def _rebuild_buck_profiles(self) -> None:
        """Aggregate all sightings by buck_id into rich per-buck dossiers with movement history & analytics."""
        sightings_db = self.db.get("sightings", {})
        bucks_db = self.db.setdefault("bucks", {})
        stands_gps = self.db.get("stands_gps", {})

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for sid, s in sightings_db.items():
            bid = s.get("buck_id") or "buck_unassigned"
            grouped.setdefault(bid, []).append(s)

        new_bucks_db: Dict[str, Any] = {}
        for bid, s_list in grouped.items():
            # Sort sightings newest-first
            s_list.sort(key=lambda x: x.get("created_at") or "", reverse=True)
            latest = s_list[0]
            oldest = s_list[-1]
            existing_b = bucks_db.get(bid, {})

            # Pick custom name if user renamed, else highest-confidence sighting name
            best_s = max(s_list, key=lambda x: float(x.get("profile_confidence", 0)))
            name = existing_b.get("custom_name") or best_s.get("buck_name") or latest.get("buck_name") or bid

            # Stand frequency & detailed breakdown
            stand_counts: Dict[str, int] = {}
            stand_photos: Dict[str, int] = {}
            stand_last_seen: Dict[str, str] = {}
            stand_windows: Dict[str, Dict[str, int]] = {}
            window_counts: Dict[str, int] = {"Dawn": 0, "Midday": 0, "Dusk": 0, "Night": 0}
            hourly_counts: Dict[str, int] = {f"{h:02d}": 0 for h in range(24)}
            temp_bands: Dict[str, int] = {"<45°F": 0, "45-55°F": 0, "55-65°F": 0, ">65°F": 0}
            pressure_trends: Dict[str, int] = {"Rising": 0, "Steady": 0, "Falling": 0}
            moon_counts: Dict[str, int] = {}
            wind_counts: Dict[str, int] = {}
            temps: List[float] = []
            pressures: List[float] = []
            winds: List[str] = []
            wind_speeds: List[float] = []
            confs: List[float] = []
            all_photos: List[Dict[str, Any]] = []
            movement_log: List[Dict[str, Any]] = []

            # Build chronological movement trail (oldest -> newest) for travel corridor & GPS vector analysis
            chronological = list(reversed(s_list))
            prev_stand = None
            prev_dt = None
            prev_lat = None
            prev_lon = None
            corridors: List[str] = []
            movement_vectors: List[Dict[str, Any]] = []
            movement_waypoints: List[Dict[str, Any]] = []
            total_distance_yards = 0

            for step_idx, item in enumerate(chronological, start=1):
                st = item.get("camera_name", "Unknown")
                gfallback = stands_gps.get(st, {})
                lat = item.get("latitude") if item.get("latitude") is not None else gfallback.get("latitude")
                lon = item.get("longitude") if item.get("longitude") is not None else gfallback.get("longitude")
                hdg = item.get("heading") or gfallback.get("heading") or "Unknown"

                stand_counts[st] = stand_counts.get(st, 0) + 1
                stand_photos[st] = stand_photos.get(st, 0) + int(item.get("burst_count", len(item.get("photos", [])) or 1))
                stand_last_seen[st] = item.get("time_formatted") or ""
                w_label = item.get("time_window", "Night")
                window_counts[w_label] = window_counts.get(w_label, 0) + 1
                sw = stand_windows.setdefault(st, {"Dawn": 0, "Midday": 0, "Dusk": 0, "Night": 0})
                sw[w_label] = sw.get(w_label, 0) + 1

                if item.get("hour") is not None:
                    hk = f"{int(item['hour']):02d}"
                    hourly_counts[hk] = hourly_counts.get(hk, 0) + 1

                if item.get("temperature") is not None:
                    tval = float(item["temperature"])
                    temps.append(tval)
                    if tval < 45:
                        temp_bands["<45°F"] += 1
                    elif tval < 55:
                        temp_bands["45-55°F"] += 1
                    elif tval <= 65:
                        temp_bands["55-65°F"] += 1
                    else:
                        temp_bands[">65°F"] += 1

                if item.get("pressure") is not None:
                    pressures.append(float(item["pressure"]))
                ptrend = item.get("pressure_tendency") or "Steady"
                pressure_trends[ptrend] = pressure_trends.get(ptrend, 0) + 1

                if item.get("wind_speed") is not None:
                    wind_speeds.append(float(item["wind_speed"]))
                if item.get("wind_cardinal") and item.get("wind_cardinal") != "N/A":
                    wc = item["wind_cardinal"]
                    winds.append(wc)
                    wind_counts[wc] = wind_counts.get(wc, 0) + 1

                if item.get("moon_phase"):
                    mp = str(item["moon_phase"])
                    moon_counts[mp] = moon_counts.get(mp, 0) + 1

                if item.get("profile_confidence") is not None:
                    confs.append(float(item["profile_confidence"]))

                dt_obj = None
                if item.get("created_at"):
                    try:
                        dt_obj = datetime.datetime.fromisoformat(item["created_at"])
                    except Exception:
                        dt_obj = None

                movement_waypoints.append({
                    "step": step_idx,
                    "stand": st,
                    "latitude": lat,
                    "longitude": lon,
                    "heading": hdg,
                    "time_formatted": item.get("time_formatted"),
                    "time_window": w_label,
                    "burst_count": item.get("burst_count", 1),
                    "temperature": item.get("temperature"),
                    "pressure": item.get("pressure"),
                    "pressure_tendency": ptrend,
                    "moon_phase": item.get("moon_phase"),
                    "wind": f"{item.get('wind_speed')} mph {item.get('wind_cardinal')}" if item.get("wind_speed") is not None else "Calm",
                })

                if prev_stand and prev_stand != st and prev_dt and dt_obj:
                    hours_diff = abs((dt_obj - prev_dt).total_seconds()) / 3600.0
                    elapsed_label = (
                        f"{round(hours_diff * 60)} mins"
                        if hours_diff < 2
                        else f"{hours_diff:.1f} hrs"
                    )
                    if hours_diff <= 12:
                        corridors.append(f"{prev_stand} → {st} ({elapsed_label} on {dt_obj.strftime('%b %-d')})")
                    if prev_lat is not None and prev_lon is not None and lat is not None and lon is not None:
                        import math
                        rad = math.pi / 180.0
                        dlat = (lat - prev_lat) * rad
                        dlon = (lon - prev_lon) * rad
                        a_val = math.sin(dlat / 2) ** 2 + math.cos(prev_lat * rad) * math.cos(lat * rad) * math.sin(dlon / 2) ** 2
                        dist_yd = round(2 * 6371000 * 1.09361 * math.atan2(math.sqrt(a_val), math.sqrt(1 - a_val)))
                        total_distance_yards += dist_yd
                        speed_yph = round(dist_yd / max(0.05, hours_diff))
                        movement_vectors.append({
                            "from_stand": prev_stand,
                            "to_stand": st,
                            "from_lat": prev_lat,
                            "from_lon": prev_lon,
                            "to_lat": lat,
                            "to_lon": lon,
                            "distance_yards": dist_yd,
                            "speed_yards_per_hr": speed_yph,
                            "elapsed_hours": round(hours_diff, 2),
                            "elapsed_label": elapsed_label,
                            "date_label": dt_obj.strftime("%b %-d"),
                            "time_window": w_label,
                        })
                prev_stand = st
                prev_dt = dt_obj
                prev_lat = lat
                prev_lon = lon

            for item in s_list:
                movement_log.append({
                    "sighting_id": item["sighting_id"],
                    "hero_guid": item["hero_guid"],
                    "stand": item["camera_name"],
                    "latitude": item.get("latitude"),
                    "longitude": item.get("longitude"),
                    "heading": item.get("heading"),
                    "time_formatted": item["time_formatted"],
                    "created_at": item["created_at"],
                    "time_window": item["time_window"],
                    "burst_count": item["burst_count"],
                    "temperature": item["temperature"],
                    "pressure": item["pressure"],
                    "pressure_tendency": item["pressure_tendency"],
                    "wind": f"{item['wind_speed']} mph {item['wind_cardinal']}" if item.get("wind_speed") is not None else "Calm",
                    "moon_phase": item["moon_phase"],
                    "hd_status": item["hd_status"],
                    "confidence": round(float(item.get("profile_confidence", 0)) * 100),
                })
                for p in item.get("photos", []):
                    all_photos.append({
                        **p,
                        "stand": item["camera_name"],
                        "latitude": p.get("latitude") if p.get("latitude") is not None else item.get("latitude"),
                        "longitude": p.get("longitude") if p.get("longitude") is not None else item.get("longitude"),
                        "heading": p.get("heading") or item.get("heading"),
                        "time_formatted": item["time_formatted"],
                        "temperature": item["temperature"],
                        "wind_cardinal": item["wind_cardinal"],
                        "moon_phase": item["moon_phase"],
                    })

            favorite_stand = max(stand_counts.items(), key=lambda x: x[1])[0] if stand_counts else "Unknown"
            preferred_window = max(window_counts.items(), key=lambda x: x[1])[0] if window_counts else "Night"
            daylight_sightings = window_counts.get("Dawn", 0) + window_counts.get("Midday", 0) + window_counts.get("Dusk", 0)
            daylight_pct = round((daylight_sightings / max(1, len(s_list))) * 100)

            # Build rich per-stand analytics table
            stand_analytics = []
            for st_name, st_cnt in sorted(stand_counts.items(), key=lambda x: x[1], reverse=True):
                ginfo = stands_gps.get(st_name, {})
                sw_map = stand_windows.get(st_name, {})
                top_w = max(sw_map.items(), key=lambda x: x[1])[0] if sw_map else "Night"
                stand_analytics.append({
                    "stand": st_name,
                    "sightings": st_cnt,
                    "pct": round((st_cnt / max(1, len(s_list))) * 100),
                    "photos": stand_photos.get(st_name, st_cnt),
                    "last_seen": stand_last_seen.get(st_name, ""),
                    "top_window": top_w,
                    "heading": ginfo.get("heading", "Unknown"),
                    "latitude": ginfo.get("latitude"),
                    "longitude": ginfo.get("longitude"),
                })

            # Build Tactical Hunt Prescription for this buck
            fav_hdg = stands_gps.get(favorite_stand, {}).get("heading", "Unknown")
            best_wind_dir = max(set(winds), key=winds.count) if winds else "Variable"
            best_temp = round(sum(temps) / len(temps), 1) if temps else 50.0
            best_baro = round(sum(pressures) / len(pressures), 2) if pressures else 30.00
            top_ptrend = max(pressure_trends.items(), key=lambda x: x[1])[0] if pressure_trends else "Steady"
            hunt_prescription = {
                "recommended_stand": favorite_stand,
                "stand_heading": fav_hdg,
                "best_time_window": "Dawn (5:30–8:30 AM)" if window_counts.get("Dawn", 0) >= window_counts.get("Dusk", 0) and daylight_sightings > 0 else ("Dusk (4:30–7:30 PM)" if window_counts.get("Dusk", 0) > 0 else f"Crepuscular Edge ({preferred_window} Transition)"),
                "optimal_temp_range": f"{round(min(temps))}°F – {round(max(temps))}°F (Avg {best_temp}°F)" if temps else "45°F – 55°F",
                "optimal_barometer": f"{best_baro} inHg ({top_ptrend})",
                "preferred_wind": best_wind_dir,
                "corridor_ambush": corridors[0] if corridors else f"Core staging area around {favorite_stand}",
                "tactical_summary": (
                    f"Target {name} at {favorite_stand} ({fav_hdg}) when temperatures drop near {best_temp}°F "
                    f"with a {best_wind_dir} wind and {top_ptrend.lower()} barometer (~{best_baro} inHg)."
                ),
            }

            # Hero photo: prefer HD photo from highest-confidence sighting, else latest sighting hero photo
            hero_photo = best_s["photos"][0] if best_s.get("photos") else (latest["photos"][0] if latest.get("photos") else {})
            for p in all_photos:
                if p.get("is_hd") and p.get("local_path"):
                    hero_photo = p
                    break

            pts_str = existing_b.get("custom_points") or best_s.get("points", "Unknown")
            l_pts = best_s.get("left_points")
            r_pts = best_s.get("right_points")
            if l_pts is None or r_pts is None:
                m_pts = re.search(r"(\d+)x(\d+)", str(pts_str))
                if m_pts:
                    l_pts, r_pts = int(m_pts.group(1)), int(m_pts.group(2))

            new_bucks_db[bid] = {
                "buck_id": bid,
                "name": name,
                "custom_name": existing_b.get("custom_name"),
                "points": pts_str,
                "left_points": l_pts,
                "right_points": r_pts,
                "beam_spread": existing_b.get("custom_spread") or best_s.get("beam_spread", "Unknown"),
                "age_estimate": existing_b.get("custom_age") or best_s.get("age_estimate", "Unknown"),
                "antler_notes": existing_b.get("custom_notes") or best_s.get("antler_notes", ""),
                "max_confidence": round(max(confs) * 100) if confs else 90,
                "avg_confidence": round((sum(confs) / len(confs)) * 100) if confs else 88,
                "sightings_count": len(s_list),
                "total_photos_count": len(all_photos),
                "avg_burst_photos": round(len(all_photos) / max(1, len(s_list)), 1),
                "stands_visited_count": len(stand_counts),
                "total_stands_count": max(len(stands_gps), len(stand_counts)),
                "total_distance_yards": total_distance_yards,
                "last_seen_at": latest.get("created_at"),
                "last_seen_formatted": latest.get("time_formatted"),
                "last_seen_stand": latest.get("camera_name"),
                "latitude": latest.get("latitude"),
                "longitude": latest.get("longitude"),
                "heading": latest.get("heading"),
                "last_seen_temp": latest.get("temperature"),
                "last_seen_pressure": latest.get("pressure"),
                "last_seen_pressure_tendency": latest.get("pressure_tendency"),
                "last_seen_wind": f"{latest.get('wind_speed')} mph {latest.get('wind_cardinal')}" if latest.get("wind_speed") is not None else "Calm",
                "last_seen_moon": latest.get("moon_phase"),
                "first_seen_formatted": oldest.get("time_formatted"),
                "favorite_stand": favorite_stand,
                "stand_breakdown": stand_counts,
                "stand_analytics": stand_analytics,
                "preferred_window": preferred_window,
                "window_breakdown": window_counts,
                "hourly_histogram": hourly_counts,
                "daylight_sightings": daylight_sightings,
                "night_sightings": window_counts.get("Night", 0),
                "daylight_pct": daylight_pct,
                "avg_temp": round(sum(temps) / len(temps), 1) if temps else None,
                "min_temp": round(min(temps), 1) if temps else None,
                "max_temp": round(max(temps), 1) if temps else None,
                "temp_bands": temp_bands,
                "avg_pressure": round(sum(pressures) / len(pressures), 2) if pressures else None,
                "min_pressure": round(min(pressures), 2) if pressures else None,
                "max_pressure": round(max(pressures), 2) if pressures else None,
                "pressure_trends": pressure_trends,
                "avg_wind_speed": round(sum(wind_speeds) / len(wind_speeds), 1) if wind_speeds else None,
                "preferred_wind": best_wind_dir,
                "wind_breakdown": wind_counts,
                "moon_breakdown": moon_counts,
                "hunt_prescription": hunt_prescription,
                "travel_corridors": corridors,
                "movement_waypoints": movement_waypoints,
                "movement_vectors": movement_vectors,
                "stands_gps": stands_gps,
                "hero_guid": hero_photo.get("guid"),
                "hero_local_path": hero_photo.get("local_path"),
                "hero_media_source": hero_photo.get("media_source_id"),
                "hero_cloud_url": hero_photo.get("cloud_image_url"),
                "hero_is_hd": hero_photo.get("is_hd", False),
                "movement_log": movement_log,
                "gallery": all_photos[:24],
            }

        self.db["bucks"] = new_bucks_db

    def rename_buck(
        self,
        buck_id: str,
        new_name: str,
        points: Optional[str] = None,
        antler_notes: Optional[str] = None,
    ) -> bool:
        """Rename a buck profile and optionally update its rack points or notes."""
        bucks = self.db.setdefault("bucks", {})
        sightings = self.db.setdefault("sightings", {})
        if buck_id not in bucks:
            # Try matching by current name
            for bid, b in bucks.items():
                if b.get("name", "").lower() == buck_id.lower():
                    buck_id = bid
                    break
        if buck_id not in bucks:
            return False

        bucks[buck_id]["custom_name"] = new_name.strip()
        bucks[buck_id]["name"] = new_name.strip()
        if points:
            bucks[buck_id]["custom_points"] = points.strip()
        if antler_notes:
            bucks[buck_id]["custom_notes"] = antler_notes.strip()

        for s in sightings.values():
            if s.get("buck_id") == buck_id:
                s["buck_name"] = new_name.strip()
                if points:
                    s["points"] = points.strip()
                if antler_notes:
                    s["antler_notes"] = antler_notes.strip()
                s["manual_override"] = True

        self._rebuild_buck_profiles()
        self.save_db()
        return True

    def assign_sighting_to_buck(
        self,
        guid_or_sighting_id: str,
        buck_name: str,
        points: Optional[str] = None,
        antler_notes: Optional[str] = None,
    ) -> bool:
        """Assign a buck sighting (by photo GUID or sighting_id) to a named buck profile."""
        sightings = self.db.setdefault("sightings", {})
        guid_map = self.db.setdefault("guid_to_sighting", {})
        sid = guid_map.get(guid_or_sighting_id, guid_or_sighting_id)
        if sid not in sightings:
            return False

        target_buck_id = slugify_buck_id(buck_name)
        # Check if an existing buck has this name
        for bid, b in self.db.get("bucks", {}).items():
            if b.get("name", "").lower() == buck_name.strip().lower() or bid == buck_name.strip():
                target_buck_id = bid
                buck_name = b.get("name", buck_name.strip())
                break

        s = sightings[sid]
        s["buck_id"] = target_buck_id
        s["buck_name"] = buck_name.strip()
        if points:
            s["points"] = points.strip()
        if antler_notes:
            s["antler_notes"] = antler_notes.strip()
        s["manual_override"] = True

        self._rebuild_buck_profiles()
        self.save_db()
        return True

    def escalate_hd_request(self, guid_or_sighting_id: str) -> bool:
        """Manually trigger the next iterative HD photo request for a buck sighting burst."""
        sightings = self.db.get("sightings", {})
        guid_map = self.db.get("guid_to_sighting", {})
        sid = guid_map.get(guid_or_sighting_id, guid_or_sighting_id)
        if sid not in sightings:
            return self.client.request_hd_photo(guid_or_sighting_id)

        s = sightings[sid]
        photos = s.get("photos", [])
        dev_id = s.get("device_id")
        req_list = s.setdefault("hd_requested_guids", [])
        for idx, p in enumerate(photos):
            g = p.get("guid")
            if g and g not in req_list:
                if self.client.request_hd_photo(g, dev_id):
                    req_list.append(g)
                    s["hd_candidate_index"] = idx
                    s["hd_status"] = f"Pending (Frame #{idx + 1})"
                    self.save_db()
                    return True
        # If all were already requested, force re-request on hero_guid
        return self.client.request_hd_photo(s.get("hero_guid", guid_or_sighting_id), dev_id)

    def get_summary_payload(self) -> Dict[str, Any]:
        """Return structured summary of all profiled bucks and sightings for sensors and cameras."""
        bucks = list(self.db.get("bucks", {}).values())
        bucks.sort(key=lambda x: (x.get("last_seen_at") or "", x.get("sightings_count", 0)), reverse=True)
        sightings = list(self.db.get("sightings", {}).values())
        sightings.sort(key=lambda x: x.get("created_at") or "", reverse=True)

        hd_pending = sum(1 for s in sightings if "Pending" in str(s.get("hd_status", "")))
        hd_completed = sum(1 for s in sightings if s.get("hd_status") == "Completed")

        return {
            "unique_bucks_count": len(bucks),
            "total_buck_sightings": len(sightings),
            "media_directory": self.media_dir,
            "hd_pending_count": hd_pending,
            "hd_completed_count": hd_completed,
            "bucks": bucks,
            "recent_sightings": sightings[:20],
        }
