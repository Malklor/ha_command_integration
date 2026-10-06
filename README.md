# 🦌 Stealth Cam Command Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/Malklor/ha_command_integration?style=for-the-badge&color=blue)](https://github.com/Malklor/ha_command_integration/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

A native, feature-rich Home Assistant custom integration for **Stealth Cam / GSM Outdoors Command** cellular trail cameras.

Provides real-time hardware telemetry, cellular connectivity monitoring, field weather analytics, GPS tracking, high-resolution photo reels, live wind matrix calculations, and 1-tap verified buck tagging.

---

## 🌟 Key Features

- 🔋 **Hardware & Battery Telemetry**: Real-time battery percentage (`%`), voltage (`V`), SD card health & free space (`%`), and cellular sync timestamps.
- 📶 **Cellular Connectivity**: Signal strength ratings, RSSI dBm values, and carrier network status.
- 📸 **High-Resolution Photo Feeds**: Native camera entities with high-resolution image proxies, thumbnail galleries, and full-screen inspection.
- 🌤️ **Field Environmental Sensors**: Ambient field temperature (`°F`), barometric pressure (`inHg`), pressure trend, wind speed & compass direction, and moon phase.
- 🧭 **Stand Scent & Wind Direction Matrix**: Evaluates current field wind against each camera stand's physical heading to compute favorable, marginal, or unfavorable hunting conditions.
- 🦌 **1-Tap Buck Tagging & Score Tracking**: Tag captures as verified antlered bucks with real-time gold badge highlights and stand analytics.
- 📊 **24-Hour Time-of-Day Movement Distribution**: Classifies property-wide and stand-specific deer movement into Dawn Transitions (5-8 AM), Daylight Movement (9 AM-4 PM), Evening Feeding (4-8 PM), and Night Roaming (8 PM-5 AM).
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
| **Camera** | `camera.stealthcam_homer` | Latest high-res photo capture with full image proxy |
| **Battery Sensor** | `sensor.stealthcam_homer_battery` | Battery percentage (`%`) and voltage |
| **Signal Sensor** | `sensor.stealthcam_homer_signal` | Cellular signal strength and carrier |
| **SD Card Sensor** | `sensor.stealthcam_homer_sd_free` | SD card free storage percentage (`%`) |
| **Check-in Sensor** | `sensor.stealthcam_homer_last_checkin` | Timestamp of last cellular check-in |
| **Last Hit Sensor** | `sensor.stealthcam_homer_last_hit` | Timestamp of most recent animal detection |
| **Buck Hits Sensor** | `sensor.stealthcam_homer_buck_hits` | Verified buck hit count |
| **Peak Window Sensor** | `sensor.stealthcam_homer_peak_window` | Stand's peak movement window |
| **Device Tracker** | `device_tracker.stealthcam_homer` | GPS coordinates and stand compass bearing |

---

## 🛠️ Services

The integration registers native services for dashboard interactions and automations:

### `stealthcam_command.toggle_buck`
Toggles or sets the verified antlered buck state for a capture GUID:
```yaml
service: stealthcam_command.toggle_buck
data:
  guid: "01a1109a-f850-73a7-9fb2-8b1be1024262"
```

### `stealthcam_command.sync_now`
Triggers an immediate cloud refresh of camera telemetry and latest captures:
```yaml
service: stealthcam_command.sync_now
```

---

## 📱 Lovelace Dashboard Example

```yaml
type: custom:vertical-stack-in-card
cards:
  - type: custom:button-card
    entity: camera.stealthcam_homer
    show_entity_picture: true
    show_name: true
    show_label: true
    name: HOMER STAND
    tap_action:
      action: more-info
    styles:
      entity_picture:
        - width: 100%
        - height: 220px
        - object-fit: cover
```

---

## 📄 License

Distributed under the [MIT License](LICENSE).
