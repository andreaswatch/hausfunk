# Multi-Entry Device Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor Hausfunk to split HA-side go2rtc config (main entry "Hausfunk Sprechanlage") and Pi device configs ("Hausfunk Pi (<IP>)") to allow multiple Pi devices under one go2rtc configuration.

**Architecture:** Split the config flow into a main entry setup step (creating "Hausfunk Sprechanlage") and a device entry step (creating "Hausfunk Pi (<IP>)"). The integration setup checks the type of entry, registers services on the main entry, and forwards platforms only on Pi device entries by fetching the go2rtc settings from the main entry.

**Tech Stack:** Python, Home Assistant Core APIs.

## Global Constraints

- Domain is `hausfunk`.
- Main config entry has no `CONF_PI_HOST` in its data and is titled `Hausfunk Sprechanlage`.
- Pi config entries contain `CONF_PI_HOST` and are titled `Hausfunk Pi (<IP>)`.

---

### Task 1: Update Translations

**Files:**
- Modify: [strings.json](file:///home/andreas/sprechanlage-pi-server/custom_components/hausfunk/strings.json)
- Modify: [de.json](file:///home/andreas/sprechanlage-pi-server/custom_components/hausfunk/translations/de.json)
- Modify: [en.json](file:///home/andreas/sprechanlage-pi-server/custom_components/hausfunk/translations/en.json)

**Interfaces:**
- Consumes: None
- Produces: Translated string mappings for the new `pi` step and updated `user` step in the config flow.

- [ ] **Step 1: Write translation updates to strings.json**
  Update the `config.step` translation keys to add a `pi` step (which holds the previous `user` step's Pi config keys) and swap `user` to hold the go2rtc settings.
  Replace `config.step` block in `/home/andreas/sprechanlage-pi-server/custom_components/hausfunk/strings.json` with:
  ```json
      "step": {
        "user": {
          "title": "go2rtc (Home Assistant)",
          "description": "{detected}. The fields are pre-filled, adjust if needed. This setting applies to all Hausfunk devices.",
          "data": {
            "go2rtc_url": "go2rtc URL",
            "go2rtc_username": "Username (optional)",
            "go2rtc_password": "Password (optional)",
            "go2rtc_version": "go2rtc version",
            "go2rtc_host": "HA go2rtc LAN host (used for WebRTC candidate)",
            "go2rtc_rtsp_port": "HA go2rtc RTSP port",
            "go2rtc_webrtc_port": "HA go2rtc WebRTC port",
            "go2rtc_candidates": "WebRTC candidates (optional, comma separated)"
          }
        },
        "pi": {
          "title": "Connect Hausfunk Pi",
          "description": "SSH credentials and stream details for the Pi.",
          "data": {
            "host": "Pi IP address",
            "port": "SSH port",
            "username": "SSH username",
            "password": "SSH password",
            "sudo_password": "Sudo password (if different, optional)",
            "stream_name": "Stream name",
            "rtsp_port": "Pi RTSP port",
            "pi_go2rtc_port": "Pi go2rtc API port",
            "width": "Width",
            "height": "Height",
            "fps": "Frames per second",
            "audio_gain": "Microphone gain"
          }
        },
        "install": {
          "title": "Set up the Pi",
          "description": "The integration will now install go2rtc on the Pi and enable the service.",
          "data": {
            "install_now": "Set up the Pi now"
          }
        }
      }
  ```

- [ ] **Step 2: Write German translation updates**
  Apply the same changes to `/home/andreas/sprechanlage-pi-server/custom_components/hausfunk/translations/de.json`:
  ```json
      "step": {
        "user": {
          "title": "go2rtc (Home Assistant)",
          "description": "{detected}. Die Felder sind vorbefüllt, bei Bedarf anpassen. Diese Einstellung gilt für alle Hausfunk-Geräte.",
          "data": {
            "go2rtc_url": "go2rtc URL",
            "go2rtc_username": "Benutzer (optional)",
            "go2rtc_password": "Passwort (optional)",
            "go2rtc_version": "go2rtc-Version",
            "go2rtc_host": "HA go2rtc LAN-Host (für WebRTC-Candidate)",
            "go2rtc_rtsp_port": "HA go2rtc RTSP-Port",
            "go2rtc_webrtc_port": "HA go2rtc WebRTC-Port",
            "go2rtc_candidates": "WebRTC-Candidates (optional, kommagetrennt)"
          }
        },
        "pi": {
          "title": "Hausfunk Pi verbinden",
          "description": "SSH-Zugangsdaten und Stream-Details für die Pi.",
          "data": {
            "host": "Pi IP-Adresse",
            "port": "SSH-Port",
            "username": "SSH-Benutzer",
            "password": "SSH-Passwort",
            "sudo_password": "Sudo-Passwort (falls abweichend, optional)",
            "stream_name": "Stream-Name",
            "rtsp_port": "Pi-RTSP-Port",
            "pi_go2rtc_port": "Pi go2rtc API-Port",
            "width": "Breite",
            "height": "Höhe",
            "fps": "Frames pro Sekunde",
            "audio_gain": "Mic-Verstärkung"
          }
        },
        "install": {
          "title": "Pi einrichten",
          "description": "Die Integration installiert jetzt go2rtc auf der Pi und aktiviert den Dienst.",
          "data": {
            "install_now": "Pi jetzt einrichten"
          }
        }
      }
  ```

- [ ] **Step 3: Write English translation updates**
  Apply the same changes to `/home/andreas/sprechanlage-pi-server/custom_components/hausfunk/translations/en.json` (identical structure as strings.json).

- [ ] **Step 4: Run test to make sure existing tests pass**
  Run: `python3 -m unittest discover tests`
  Expected: PASS

- [ ] **Step 5: Commit translation files**
  Run: `git add custom_components/hausfunk/strings.json custom_components/hausfunk/translations/*.json`
  Run: `git commit -m "translations: support separate pi and go2rtc flow steps"`

---

### Task 2: Update Setup and Initialization Logic

**Files:**
- Modify: [__init__.py](file:///home/andreas/sprechanlage-pi-server/custom_components/hausfunk/__init__.py)

**Interfaces:**
- Consumes: None
- Produces: `get_main_entry(hass: HomeAssistant) -> ConfigEntry | None` function and updated setup/unload hooks.

- [ ] **Step 1: Implement get_main_entry helper and update async_setup_entry**
  Modify `/home/andreas/sprechanlage-pi-server/custom_components/hausfunk/__init__.py` to implement `get_main_entry` and update `async_setup_entry` to only setup coordinators and platforms for entries that have a Pi configuration (`CONF_PI_HOST` in data).
  Replace lines 27-46 in `__init__.py` with:
  ```python
  def get_main_entry(hass: HomeAssistant) -> ConfigEntry | None:
      """Return the main go2rtc config entry if it exists."""
      for entry in hass.config_entries.async_entries(DOMAIN):
          if CONF_PI_HOST not in entry.data:
              return entry
      return None


  async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
      """Set up Hausfunk from a config entry."""
      # Main entry setup (HA-side go2rtc config)
      if CONF_PI_HOST not in entry.data:
          await _async_register_services(hass)
          return True

      # Pi entry setup
      main_entry = get_main_entry(hass)
      if not main_entry:
          _LOGGER.error("Main Hausfunk Sprechanlage config entry not found.")
          return False

      pi_config = dict(entry.data)
      go2rtc_config = dict(main_entry.data)
      pi_id = pi_config.get(CONF_PI_HOST)
      
      coordinator = HausfunkCoordinator(
          hass, entry, go2rtc_config, pi_config, pi_id=pi_id
      )
      await coordinator.register_stream()
      await coordinator.async_config_entry_first_refresh()

      hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

      await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

      await _async_register_services(hass)

      return True
  ```

- [ ] **Step 2: Update async_unload_entry**
  Update `async_unload_entry` in `__init__.py` (lines 48-60) to avoid trying to unload platforms/coordinators for the main entry.
  ```python
  async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
      """Unload a config entry."""
      if CONF_PI_HOST not in entry.data:
          # Main entry unloading
          if len(hass.config_entries.async_entries(DOMAIN)) <= 1:
              for service in _SERVICE_NAMES:
                  if hass.services.has_service(DOMAIN, service):
                      hass.services.async_remove(DOMAIN, service)
          return True

      # Pi entry unloading
      unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
      if unload_ok:
          coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
          if coordinator:
              await coordinator.async_close()
          
          # Only remove services if no entries left
          if not hass.data.get(DOMAIN):
              for service in _SERVICE_NAMES:
                  if hass.services.has_service(DOMAIN, service):
                      hass.services.async_remove(DOMAIN, service)
      return unload_ok
  ```

- [ ] **Step 3: Run tests to verify setup still works**
  Run: `python3 -m unittest discover tests`
  Expected: PASS

- [ ] **Step 4: Commit setup logic**
  Run: `git add custom_components/hausfunk/__init__.py`
  Run: `git commit -m "feat: split setup/unload logic for main and pi entries"`

---

### Task 3: Update Config Flow

**Files:**
- Modify: [config_flow.py](file:///home/andreas/sprechanlage-pi-server/custom_components/hausfunk/config_flow.py)

**Interfaces:**
- Consumes: `get_main_entry` from `custom_components.hausfunk`

- [ ] **Step 1: Import get_main_entry and update async_step_user**
  Modify `/home/andreas/sprechanlage-pi-server/custom_components/hausfunk/config_flow.py`.
  Add `from . import get_main_entry` at the imports.
  Update `async_step_user` to detect if the main entry exists. If yes, redirect to `async_step_pi`. If no, ask for go2rtc settings and create entry.
  Modify `HausfunkConfigFlow` in `config_flow.py` (lines 131-150):
  ```python
      async def async_step_user(self, user_input=None):
          """Handle the initial config flow step."""
          # Check if the main config entry already exists
          existing_entries = self.hass.config_entries.async_entries(DOMAIN)
          main_entry = get_main_entry(self.hass)
          
          if main_entry or (existing_entries and any(CONF_PI_HOST not in e.data for e in existing_entries)):
              # Main entry already exists. Forward user to add a Pi.
              return await self.async_step_pi(user_input)

          # Otherwise, this is the initial setup. Configure the main HA-side go2rtc entry.
          if user_input is not None:
              self._data.update(user_input)
              return self.async_create_entry(
                  title="Hausfunk Sprechanlage",
                  data=self._data,
              )

          schema, detected = await self._detect_go2rtc()
          return self.async_show_form(
              step_id="user",
              data_schema=schema,
              description_placeholders={"detected": detected},
          )
  ```

- [ ] **Step 2: Implement async_step_pi and update async_step_install**
  Implement `async_step_pi` to prompt for Pi credentials and validation. Update `async_step_install` and `_do_install` to merge go2rtc settings from the main entry.
  Add `async_step_pi` and modify `async_step_install` in `config_flow.py`:
  ```python
      async def async_step_pi(self, user_input=None):
          """Add a new Pi: SSH access."""
          errors = {}
          if user_input is not None:
              await self.async_set_unique_id(user_input[CONF_PI_HOST])
              self._abort_if_unique_id_configured()
              self._data.update(user_input)
              errors = await self._validate_pi(user_input)
              if not errors:
                  # Populate default runtime/input settings
                  self._data.setdefault(CONF_STREAM_MODE, DEFAULT_STREAM_MODE)
                  return await self.async_step_install()
          return self.async_show_form(
              step_id="pi", data_schema=PI_SCHEMA, errors=errors,
              description_placeholders={
                  "fingerprint": getattr(self, "_fingerprint", ""),
                  "detected": "",
              },
          )

      async def async_step_install(self, user_input=None):
          """Optionally install/configure the Pi right away."""
          if user_input is not None:
              install_now = user_input.get(CONF_INSTALL_NOW, True)
              if install_now:
                  errors = await self._do_install()
                  if errors:
                      return self.async_show_form(
                          step_id="install", data_schema=INSTALL_SCHEMA, errors=errors
                      )
              return self.async_create_entry(
                  title=f"Hausfunk Pi ({self._data[CONF_PI_HOST]})",
                  data=self._data,
              )
          return self.async_show_form(step_id="install", data_schema=INSTALL_SCHEMA)

      async def _do_install(self) -> dict:
          ssh = PiSSH(
              self._data[CONF_PI_HOST], self._data[CONF_PI_PORT],
              self._data[CONF_PI_USERNAME], self._data[CONF_PI_PASSWORD],
          )
          main_entry = get_main_entry(self.hass)
          merged_config = {**main_entry.data, **self._data} if main_entry else self._data
          installer = HausfunkInstaller(self.hass, ssh, merged_config)
          try:
              await installer.install(self._data.get(CONF_SUDO_PASSWORD))
          except PiCommandError as err:
              _LOGGER.error("Pi-Installation fehlgeschlagen: %s", err)
              return {"base": "install_failed"}
          return {}
  ```

- [ ] **Step 3: Update HausfunkOptionsFlow**
  Update the options flow in `config_flow.py` so that configuring the main entry only changes go2rtc settings, and configuring a Pi entry only changes Pi-specific connection settings.
  Replace `HausfunkOptionsFlow` implementation (lines 285-375) with:
  ```python
  class HausfunkOptionsFlow(OptionsFlow):
      """Handle options for Hausfunk."""

      def __init__(self, entry: ConfigEntry):
          self._entry = entry
          self._data = {}

      async def async_step_init(self, user_input=None):
          """Initialize options flow step."""
          if CONF_PI_HOST not in self._entry.data:
              # Main entry Options Flow (go2rtc settings)
              return await self.async_step_go2rtc(user_input)
          
          # Pi entry Options Flow (Pi connection settings)
          return await self.async_step_pi_options(user_input)

      async def async_step_pi_options(self, user_input=None):
          """Pi-specific connection settings."""
          if user_input is not None:
              self._data.update(user_input)
              new_data = {**self._entry.data, **self._data}
              self.hass.config_entries.async_update_entry(
                  self._entry, data=new_data
              )
              # Reload this entry to apply changes
              await self.hass.config_entries.async_reload(self._entry.entry_id)
              return self.async_create_entry(title="", data={})

          return self.async_show_form(
              step_id="init",
              data_schema=_pi_connection_options_schema(self._entry.data),
          )

      async def async_step_go2rtc(self, user_input=None):
          """HA-side go2rtc settings (shared across all devices)."""
          if user_input is not None:
              self._data.update(user_input)
              new_data = {**self._entry.data, **self._data}
              self.hass.config_entries.async_update_entry(
                  self._entry, data=new_data
              )

              # Reload all Hausfunk entries to apply changes to all Pis
              for entry in self.hass.config_entries.async_entries(DOMAIN):
                  await self.hass.config_entries.async_reload(entry.entry_id)

              return self.async_create_entry(title="", data={})

          schema = vol.Schema(
              {
                  vol.Required(
                      CONF_GO2RTC_URL,
                      default=self._entry.data.get(CONF_GO2RTC_URL, DEFAULT_GO2RTC_URL),
                  ): str,
                  vol.Optional(
                      CONF_GO2RTC_USERNAME,
                      default=self._entry.data.get(CONF_GO2RTC_USERNAME, ""),
                  ): str,
                  vol.Optional(
                      CONF_GO2RTC_PASSWORD,
                      default=self._entry.data.get(CONF_GO2RTC_PASSWORD, ""),
                  ): str,
                  vol.Required(
                      CONF_GO2RTC_VERSION,
                      default=self._entry.data.get(CONF_GO2RTC_VERSION, DEFAULT_GO2RTC_VERSION),
                  ): str,
                  vol.Required(
                      CONF_GO2RTC_HOST,
                      default=self._entry.data.get(CONF_GO2RTC_HOST, DEFAULT_GO2RTC_HOST),
                  ): str,
                  vol.Required(
                      CONF_GO2RTC_RTSP_PORT,
                      default=self._entry.data.get(CONF_GO2RTC_RTSP_PORT, DEFAULT_GO2RTC_RTSP_PORT),
                  ): int,
                  vol.Required(
                      CONF_GO2RTC_WEBRTC_PORT,
                      default=self._entry.data.get(CONF_GO2RTC_WEBRTC_PORT, DEFAULT_GO2RTC_WEBRTC_PORT),
                  ): int,
                  vol.Optional(
                      CONF_GO2RTC_CANDIDATES,
                      default=self._entry.data.get(CONF_GO2RTC_CANDIDATES, DEFAULT_GO2RTC_CANDIDATES),
                  ): str,
              }
          )
          return self.async_show_form(
              step_id="go2rtc",
              data_schema=schema,
          )
  ```

- [ ] **Step 4: Run tests to verify changes**
  Run: `python3 -m unittest discover tests`
  Expected: PASS

- [ ] **Step 5: Commit config flow changes**
  Run: `git add custom_components/hausfunk/config_flow.py`
  Run: `git commit -m "feat: split config flow and options flow for main and pi entries"`

---

### Task 4: Fix and Align Unit Tests

**Files:**
- Modify: [tests/test_platforms.py](file:///home/andreas/sprechanlage-pi-server/tests/test_platforms.py)
- Modify: [tests/test_coordinator.py](file:///home/andreas/sprechanlage-pi-server/tests/test_coordinator.py)

**Interfaces:**
- Consumes: Updated Hausfunk codebase
- Produces: Validated and passing test suite.

- [ ] **Step 1: Check unit tests failure**
  Run: `python3 -m unittest discover tests`
  Observe any failures due to setup changes. Since coordinator and platform tests mock the inputs directly, they should still pass. If there are any setup tests in another file, check them. Let's make sure they all pass.

- [ ] **Step 2: Add test cases for main vs pi entries in test_coordinator or test_platforms**
  If needed, run tests to verify everything is OK.
  Run: `python3 -m unittest discover tests`
  Expected: PASS

- [ ] **Step 3: Commit unit tests alignment**
  Run: `git commit -am "test: verify multi-entry architecture"`
