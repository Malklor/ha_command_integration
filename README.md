# 🦌 Stealth Cam Command Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/Malklor/ha_command_integration?style=for-the-badge&color=blue)](https://github.com/Malklor/ha_command_integration/releases)
[![Validate](https://img.shields.io/github/actions/workflow/status/Malklor/ha_command_integration/hassfest.yml?label=Hassfest&style=for-the-badge)](https://github.com/Malklor/ha_command_integration/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Malklor&repository=ha_command_integration&category=integration)

A native, feature-rich Home Assistant custom integration for **Stealth Cam / GSM Outdoors Command** cellular trail cameras.

Provides real-time hardware telemetry, cellular connectivity monitoring, field weather analytics, GPS tracking, high-resolution photo reels, live wind matrix calculations, and 1-tap verified buck tagging.

---

## 🌟 Key Features

- 🔋 **Hardware & Battery Telemetry**: Real-time battery percentage (`%`), voltage (`V`), SD card health & free space (`%`), and cellular sync timestamps.
- 📶 **Cellular Connectivity**: Signal strength ratings, RSSI dBm values, and carrier network status.
- 📸 **High-Resolution Photo Feeds**: Native camera entities with high-resolution image proxies, thumbnail galleries, and full-screen inspection.
- 🌤️ **Field Environmental Sensors**: Ambient field temperature (`°F`), barometric pressure (`inHg`), pressure trend, wind speed & compass direction, and moon phase.
- 🧭 **Stand Scent & Wind Direction Matrix**: Evaluates current field wind against each camera stand's physical heading to compute favorable, marginal, or unfavorable hunting conditions.
- 🦌 **Multi-Classification Photo Tagging**: 1-tap tagging for **Bucks (Gold ✨)**, **Does (Blue 🦌)**, and **Human Activity (Red Alert 🚨)** with automatic visual borders and glow badges.
- ⏱️ **Dual 24-Hour & All-Time Movement Distribution**: Classifies both rolling 24-hour activity and historical trends across Dawn Transitions (5–9 AM), Daylight Movement (9 AM–4 PM), Evening Feeding (4–8 PM), and Night Roaming (8 PM–5 AM).
- 🚨 **Human Activity & Intruder Detection**: Flags cameras with human presence to immediately alert landowners of field activity.
- 🗺️ **GPS Mapping & Stand Tracking**: Tracks camera positions on Home Assistant maps with custom stand character pins and compass headings.

---

## 📦 Installation via HACS (Recommended)

1. Ensure [HACS (Home Assistant Community Store)](https://hacs.xyz/) is installed.
2. Open Home Assistant and navigate to **HACS ➔ Integrations**.
3. Click the **3 dots** in the top right corner and select **Custom repositories**.
4. Enter the Repository URL:
   ```
   https://github.com/Malklor/ha_command_integration
   ```
5. Select **Integration** as the Category and click **Add**.
6. Find **Stealth Cam Command** in the integration list and click **Download**.
7. Restart Home Assistant.

---

## ⚙️ Configuration

1. In Home Assistant, go to **Settings ➔ Devices & Services ➔ Add Integration**.
2. Search for **Stealth Cam Command**.
3. Enter your **Stealth Cam Command account email and password**.
4. Click **Submit**. Home Assistant will automatically discover all registered cellular trail cameras and generate camera, sensor, and tracker entities.

---

## 📊 Entities Created Per Camera

| Entity Type | Entity ID Example | Description |
| :--- | :--- | :--- |
| **Camera (Latest Photo)** | `camera.stealth_cam_north_ridge_north_ridge_trail_cam` | Latest high-res photo capture with full image proxy |
| **Capture Cameras (1–36)** | `camera.stealth_cam_north_ridge_north_ridge_photo_1` | Individual historical photo capture camera entities |
| **Battery Sensor** | `sensor.stealth_cam_north_ridge_north_ridge_battery` | Battery percentage (`%`) and voltage |
| **Signal Sensor** | `sensor.stealth_cam_north_ridge_north_ridge_cellular_signal` | Cellular signal strength and carrier |
| **SD Card Sensor** | `sensor.stealth_cam_north_ridge_north_ridge_sd_free_space` | SD card free storage percentage (`%`) |
| **Check-in Sensor** | `sensor.stealth_cam_north_ridge_north_ridge_last_check_in` | Timestamp of last cellular check-in |
| **Last Hit Sensor** | `sensor.stealth_cam_north_ridge_north_ridge_last_animal_hit` | Timestamp of most recent animal detection |
| **Buck Hits Sensor** | `sensor.stealth_cam_north_ridge_north_ridge_positive_buck_hits` | Verified buck hit count |
| **Peak Window Sensor** | `sensor.stealth_cam_north_ridge_north_ridge_peak_movement_window` | Stand's peak movement window |
| **Location Sensor** | `sensor.stealth_cam_north_ridge_north_ridge_stand_location` | GPS coordinates and stand compass bearing |

---

## 🛠️ Services

The integration registers native services for dashboard interactions and automations:

### `stealthcam_command.tag_buck`
Tags or scores a photo capture as a verified antlered buck (Gold badge):
```yaml
service: stealthcam_command.tag_buck
data:
  guid: "01a1109a-f850-73a7-9fb2-8b1be1024262"
```

### `stealthcam_command.tag_doe`
Tags a photo capture as a verified doe (Blue badge):
```yaml
service: stealthcam_command.tag_doe
data:
  guid: "01a1109a-f850-73a7-9fb2-8b1be1024262"
```

### `stealthcam_command.tag_person`
Flags a photo capture for human activity (Red Alert badge):
```yaml
service: stealthcam_command.tag_person
data:
  guid: "01a1109a-f850-73a7-9fb2-8b1be1024262"
```

### `stealthcam_command.sync_now`
Triggers an immediate cloud refresh of camera telemetry and latest captures:
```yaml
service: stealthcam_command.sync_now
```

- 🔮 **5-Day Solunar & Weather Predictive Forecast Engine**: Correlates future multi-day weather forecasts (`temperature`, `templow`, `wind_bearing`, `wind_speed`), upcoming moon phases, and cold snaps against historical stand baselines to recommend optimal stands and tactics for **Dawn (5:30–8:30 AM)** vs. **Dusk (4:30–7:30 PM)** hunting windows.
- 🌡️ **Deep Wildlife Environmental Matrix**: Correlates buck/doe activity across temperature bands (`<40°F`, `40–50°F`, `50–60°F`, `60–70°F`, `>70°F`), 8 lunar rut phases, and a 24-hour chronogram.
- 📱 **Mobile-Optimized Photo Reel**: Responsive 2-column photo reel layout on phones with 8-option Quick Filter bar (`Bucks`, `Does`, `Person`, `Dawn`, `Midday`, `Evening`, `Night`).

---

## 📱 Drop-in Lovelace Dashboards & Auto-Discovery

Pre-built dashboard templates are provided in the [`dashboards/`](dashboards/) directory:

### 🌟 Zero-Config Auto-Discovery Hub ([`dashboards/auto_entities_hub.yaml`](dashboards/auto_entities_hub.yaml))
Automatically discovers and displays all cameras on your account in a responsive grid with weather, battery, and 24-hour movement intelligence.

### 🧭 Deep Wildlife Analytics & 5-Day Forecast View ([`dashboards/hunting_analytics_view.yaml`](dashboards/hunting_analytics_view.yaml))
Dedicated full dashboard view featuring 5-day predictive forecast tables, temperature movement matrix, moon phase correlation, 24-hour movement chronogram, and stand habitat scorecards.

### 📸 Stand Deep-Dive & 36-Photo Reel ([`dashboards/camera_subview_template.yaml`](dashboards/camera_subview_template.yaml))
Provides individual stand telemetry, 24-hr time-of-day movement distribution, verified buck/doe hit badges, responsive mobile 2-column photo reel, and auto-populates all 36 capture entities.

---

## 🎨 Customizing Camera Icons & Map Pin Avatars

You can customize camera icons and map pins directly in Home Assistant without touching YAML:

### Option A: Home Assistant UI
1. Go to **Settings ➔ Devices & Services ➔ Entities**.
2. Click on your camera's location entity (e.g. `North Ridge Camera Location`).
3. Click the ⚙️ icon to set any custom icon (e.g. `mdi:tree`, `mdi:deer`, `mdi:target`).

### Option B: Custom Face Avatars on Map Pins (`customize.yaml`)
To show custom circular character photos or stand badges on Home Assistant maps:
1. Place your PNG icons in `/config/www/avatars/`.
2. Add to `/config/customize.yaml`:
   ```yaml
   sensor.stealth_cam_north_ridge_north_ridge_stand_location:
     entity_picture: /local/avatars/stand_1.png
   ```

---

## 📄 License

Distributed under the [MIT License](LICENSE).
