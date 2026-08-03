# Multi-Entry Device Architecture for Hausfunk

This document outlines the architectural changes to restructure the Hausfunk Home Assistant integration. The goal is to separate the server-side configuration (Home Assistant-local `go2rtc` proxy settings) from the individual client-side Pi devices.

## 1. Goal & Context

Currently, the integration assumes a 1:1 mapping where each Config Entry contains both the Pi SSH credentials and the HA-side `go2rtc` settings. When adding multiple entries, the user is prompted for duplicate `go2rtc` settings, which are then synchronized across entries.

In the new architecture:
- **Main Config Entry:** Named **Hausfunk Sprechanlage**. It holds the HA-side `go2rtc` server configuration. Only one should exist.
- **Device Config Entries:** Named **Hausfunk Pi (<IP>)**. Each represents a single physical Raspberry Pi device. These can be added dynamically.

This aligns the integration with Home Assistant's standard hub/device pattern, simplifying the UI and settings management.

## 2. Component Design & Changes

### A. Config Flow (`config_flow.py`)

1. **`async_step_user` (Entry Point):**
   - Query if a main entry (no `CONF_PI_HOST`) already exists.
   - **If no main entry exists:**
     - Prompt for the `go2rtc` settings (HA-side proxy).
     - Create the Config Entry titled `Hausfunk Sprechanlage`.
   - **If a main entry already exists:**
     - Call/redirect to `async_step_pi`.

2. **`async_step_pi` (Device Creation):**
   - Prompt the user for Pi SSH credentials and stream settings (`PI_SCHEMA`).
   - Validate Pi connection.
   - Forward to `async_step_install` (optional setup/installation).
   - Create a separate Config Entry with title `Hausfunk Pi (<IP>)`.

3. **`HausfunkOptionsFlow` (Options / Configuration):**
   - Check if the entry being configured is the main entry.
     - **Main entry:** Show only the `go2rtc` settings form. When saved, reload all Hausfunk config entries so the Pis pick up the new server configuration.
     - **Pi entry:** Show only the Pi connection options (RTSP ports, FPS, width, height, audio gain). When saved, reload only this Pi's entry.

### B. Integration Setup & Services (`__init__.py`)

1. **`get_main_entry(hass)` Helper:**
   - Iterate over `hass.config_entries.async_entries(DOMAIN)` and return the first entry that does not contain `CONF_PI_HOST` in its data.

2. **`async_setup_entry`:**
   - **Main Entry Setup:**
     - Register the global custom services (`setup_pi`, `update_pi`, `uninstall_pi`, `restart_pi_go2rtc`, `register_stream`, `remove_stream`).
     - Return `True`. Do not load platforms or initialize a coordinator.
   - **Pi Entry Setup:**
     - Retrieve the main entry. If it is missing, log an error and abort setup.
     - Merge `go2rtc_config` (from main entry) and `pi_config` (from this Pi entry) into a single configuration dictionary.
     - Initialize the `HausfunkCoordinator` with the merged configuration.
     - Execute `register_stream()` and the first coordinator refresh.
     - Forward entry setups to platforms (`PLATFORMS`).

3. **`async_unload_entry`:**
   - **Main Entry Unload:**
     - If no other Hausfunk entries remain, unregister all services.
   - **Pi Entry Unload:**
     - Unload platforms.
     - Close coordinator.
     - If no other entries remain, unregister services.

### C. Translations (`strings.json` & translation files)

- Swap translations for the `user` step under `config.step` with the `go2rtc` step, since `user` is the initial step for the main entry.
- Create a new step `pi` containing the connection credentials translation strings for setting up a Pi device.

## 3. Data Flow & Security

- There is no change to how SSH keys or passwords are handled.
- High-level `go2rtc` settings are stored globally in the main `Hausfunk Sprechanlage` entry.
- Device-specific SSH and camera settings are stored in their respective `Hausfunk Pi` entries.

## 4. Verification & Testing

### Automated Tests
- Run `pytest` to verify the existing unit tests pass or update them to align with the new structure.

### Manual Verification
1. Add the integration for the first time. Verify it only prompts for `go2rtc` settings and creates "Hausfunk Sprechanlage".
2. Click "Gerät hinzufügen" on the integration card. Verify it prompts for Pi SSH credentials.
3. Verify all 10 entities (binary sensors, camera, buttons, switches) are successfully registered under a device named `Hausfunk Pi (<IP>)`.
4. Run options flows for both the main entry and the Pi entry, checking that options are saved correctly.
