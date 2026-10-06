# Stealth Cam Command Integration for Home Assistant

A Home Assistant integration and sync service for **Stealth Cam / GSM Outdoors Command** cellular trail cameras.

---

## 🌟 Features

- 🔋 **Battery Monitoring**: Real-time battery percentage (`sensor.stealthcam_<name>_battery`) and voltage.
- 📶 **Cellular Signal Strength**: Signal strength rating and RSSI level (`sensor.stealthcam_<name>_signal`).
- 💾 **SD Card Health**: Free space percentage (`sensor.stealthcam_<name>_sd_free`).
- 🕒 **Last Check-in**: Exact timestamp of last cellular sync (`sensor.stealthcam_<name>_last_checkin`).
- 📸 **Latest Photo Feeds**: Full high-resolution captured photos & thumbnails with environmental sensor data (temperature, barometric pressure, wind speed, GPS coordinates).
- 🗺️ **GPS Mapping**: Automatically tracks camera field locations with built-in latitude and longitude coordinates.

---

## 📁 Repository Structure

```
ha_command_integration/
├── stealthcam_api/                # Python client library for Command Cloud API
│   ├── __init__.py
│   └── client.py
├── custom_components/             # HACS-compatible Home Assistant Integration
│   └── stealthcam_command/
│       ├── __init__.py
│       ├── camera.py
│       ├── config_flow.py
│       ├── const.py
│       ├── coordinator.py
│       ├── manifest.json
│       └── sensor.py
├── sync_to_ha.py                  # Standalone sync daemon & script
├── .gitignore
└── README.md
```

---

## 🚀 Quick Start & Usage

### Method A: Automated Sync Daemon (Ready Immediately)

1. Create or verify your `.env` file:
   ```yaml
   username: your_email@domain.com
   password: your_command_password
   ```

2. Run a one-time sync:
   ```bash
   ./sync_to_ha.py
   ```

3. Run continuously as a background daemon:
   ```bash
   ./sync_to_ha.py --daemon --interval 300
   ```

4. Or set up as a standard cron job (every 15 minutes):
   ```crontab
   */15 * * * * /home/tgoetz/Projects/ha_command_integration/sync_to_ha.py > /tmp/stealthcam_sync.log 2>&1
   ```

---

### Method B: Native Home Assistant Custom Integration (HACS)

1. Copy the `custom_components/stealthcam_command` directory into your Home Assistant `/config/custom_components/` directory:
   ```bash
   cp -r /home/tgoetz/Projects/ha_command_integration/custom_components/stealthcam_command /config/custom_components/
   ```
2. Restart Home Assistant.
3. Go to **Settings ➔ Devices & Services ➔ Add Integration**.
4. Search for **Stealth Cam Command** and enter your Command app email and password.

---

## 📊 Lovelace Dashboard Examples

### 1. Trail Cam Photo Gallery Card
```yaml
type: grid
columns: 3
square: false
cards:
  - type: picture-entity
    entity: camera.stealthcam_homer
    name: Homer
    show_state: false
  - type: picture-entity
    entity: camera.stealthcam_lisa
    name: Lisa
    show_state: false
  - type: picture-entity
    entity: camera.stealthcam_maggie
    name: Maggie
    show_state: false
  - type: picture-entity
    entity: camera.stealthcam_santas_helper
    name: Santa's Helper
    show_state: false
  - type: picture-entity
    entity: camera.stealthcam_bart
    name: Bart
    show_state: false
  - type: picture-entity
    entity: camera.stealthcam_marge
    name: Marge
    show_state: false
```

### 2. Trail Cam Status & Battery Glance Card
```yaml
type: glance
title: 🦌 Trail Cameras Status
entities:
  - entity: sensor.stealthcam_homer_battery
    name: Homer
  - entity: sensor.stealthcam_lisa_battery
    name: Lisa
  - entity: sensor.stealthcam_maggie_battery
    name: Maggie
  - entity: sensor.stealthcam_santas_helper_battery
    name: Santa's Helper
  - entity: sensor.stealthcam_bart_battery
    name: Bart
  - entity: sensor.stealthcam_marge_battery
    name: Marge
```

---

## 🔒 Security
- All sensitive credentials, tokens, and `.env` files are strictly excluded via `.gitignore`.
