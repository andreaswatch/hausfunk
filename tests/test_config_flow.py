import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import tests.hass_mock

# Mock base classes before importing config_flow
class DummyConfigFlow:
    def __init__(self):
        self.hass = MagicMock()
        self.hass.config_entries = MagicMock()

    @classmethod
    def __init_subclass__(cls, **kwargs):
        pass

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}

    async def async_set_unique_id(self, unique_id, *, raise_on_configured=False):
        return unique_id

    def _abort_if_unique_id_configured(self):
        pass


class DummySubentryFlow:
    """Stub for ConfigSubentryFlow (the Pi subentry flow base class)."""

    def __init__(self):
        self.hass = MagicMock()
        self.hass.config_entries = MagicMock()
        self.config_entry_id = "test_entry_id"

    @classmethod
    def __init_subclass__(cls, **kwargs):
        pass

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}


class DummyOptionsFlow:
    def __init__(self, entry):
        self.hass = MagicMock()
        self.hass.config_entries = MagicMock()
        self._entry = entry

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}


# Inject dummy bases into mocked config_entries module
tests.hass_mock.config_entries_mock.ConfigFlow = DummyConfigFlow
tests.hass_mock.config_entries_mock.ConfigSubentryFlow = DummySubentryFlow
tests.hass_mock.config_entries_mock.OptionsFlow = DummyOptionsFlow

from custom_components.hausfunk.config_flow import (
    HausfunkConfigFlow,
    HausfunkOptionsFlow,
    HausfunkPiSubentryFlow,
)
from custom_components.hausfunk.const import (
    CONF_GO2RTC_URL,
    CONF_PI_HOST,
    CONF_PI_PASSWORD,
    CONF_PI_PORT,
    CONF_PI_USERNAME,
)


class TestConfigFlow(unittest.IsolatedAsyncioTestCase):
    async def test_user_step_shows_go2rtc_form(self):
        """Main config flow always shows the go2rtc form (creates a new Sprechanlage)."""
        flow = HausfunkConfigFlow()
        flow.hass = MagicMock()

        with patch.object(flow, "_detect_go2rtc", AsyncMock(return_value=(MagicMock(), "detected"))):
            res = await flow.async_step_user(user_input=None)
        self.assertEqual(res["type"], "form")
        self.assertEqual(res["step_id"], "user")

    async def test_user_step_creates_sprechanlage(self):
        """Submitting the main flow always creates a 'Hausfunk Sprechanlage' hub entry."""
        flow = HausfunkConfigFlow()
        flow.hass = MagicMock()

        user_input = {CONF_GO2RTC_URL: "http://localhost:11984"}
        with patch.object(flow, "_detect_go2rtc", AsyncMock(return_value=(MagicMock(), "detected"))):
            res = await flow.async_step_user(user_input=user_input)

        self.assertEqual(res["type"], "create_entry")
        self.assertEqual(res["title"], "Hausfunk Sprechanlage")
        self.assertEqual(res["data"][CONF_GO2RTC_URL], "http://localhost:11984")

    async def test_user_step_creates_second_sprechanlage(self):
        """Main flow creates another Sprechanlage even if one already exists (multiple hubs)."""
        flow = HausfunkConfigFlow()
        flow.hass = MagicMock()
        # Even with existing entries the main flow still creates a new hub
        flow.hass.config_entries.async_entries = MagicMock(
            return_value=[MagicMock(data={CONF_GO2RTC_URL: "http://localhost:11984"})]
        )

        user_input = {CONF_GO2RTC_URL: "http://localhost:21984"}
        with patch.object(flow, "_detect_go2rtc", AsyncMock(return_value=(MagicMock(), "detected"))):
            res = await flow.async_step_user(user_input=user_input)

        self.assertEqual(res["type"], "create_entry")
        self.assertEqual(res["title"], "Hausfunk Sprechanlage")


class TestPiSubentryFlow(unittest.IsolatedAsyncioTestCase):
    async def test_pi_step_shows_form(self):
        """Pi subentry flow shows SSH form on first call."""
        flow = HausfunkPiSubentryFlow()
        res = await flow.async_step_user(user_input=None)
        self.assertEqual(res["type"], "form")
        self.assertEqual(res["step_id"], "user")

    async def test_pi_step_validates_and_advances(self):
        """Valid SSH input advances to install step."""
        flow = HausfunkPiSubentryFlow()
        flow._validate_pi = AsyncMock(return_value={})

        user_input = {
            CONF_PI_HOST: "192.168.178.50",
            CONF_PI_PORT: 22,
            CONF_PI_USERNAME: "pi",
            CONF_PI_PASSWORD: "test",
        }
        with patch.object(
            flow, "async_step_install",
            return_value={"type": "form", "step_id": "install"}
        ):
            res = await flow.async_step_user(user_input=user_input)

        self.assertEqual(res["type"], "form")
        self.assertEqual(res["step_id"], "install")
        self.assertEqual(flow._data[CONF_PI_HOST], "192.168.178.50")

    async def test_pi_step_shows_errors_on_bad_ssh(self):
        """SSH validation errors are returned to the form."""
        flow = HausfunkPiSubentryFlow()
        flow._validate_pi = AsyncMock(return_value={"base": "cannot_connect"})

        user_input = {
            CONF_PI_HOST: "10.0.0.1",
            CONF_PI_PORT: 22,
            CONF_PI_USERNAME: "pi",
            CONF_PI_PASSWORD: "wrong",
        }
        res = await flow.async_step_user(user_input=user_input)
        self.assertEqual(res["type"], "form")
        self.assertIn("cannot_connect", str(res.get("errors", {})))

    async def test_install_step_creates_subentry(self):
        """Skipping install creates a Pi subentry entry."""
        flow = HausfunkPiSubentryFlow()
        flow._data = {
            CONF_PI_HOST: "192.168.178.50",
            CONF_PI_USERNAME: "pi",
            CONF_PI_PASSWORD: "test",
        }
        res = await flow.async_step_install(user_input={"install_now": False})
        self.assertEqual(res["type"], "create_entry")
        self.assertEqual(res["title"], "Hausfunk Pi (192.168.178.50)")
        self.assertEqual(res["data"][CONF_PI_HOST], "192.168.178.50")


class TestOptionsFlow(unittest.IsolatedAsyncioTestCase):
    async def test_options_flow_shows_go2rtc_settings(self):
        """Options flow always shows go2rtc settings via init step."""
        entry = MagicMock()
        entry.data = {CONF_GO2RTC_URL: "http://localhost:11984"}

        flow = HausfunkOptionsFlow(entry)
        flow.hass = MagicMock()
        flow.hass.config_entries.async_entries = MagicMock(return_value=[entry])

        res = await flow.async_step_init(user_input=None)
        self.assertEqual(res["type"], "form")
        self.assertEqual(res["step_id"], "init")

    async def test_options_flow_saves_and_reloads(self):
        """Submitting the options flow saves the new go2rtc URL and reloads the entry."""
        entry = MagicMock()
        entry.data = {CONF_GO2RTC_URL: "http://localhost:11984"}
        entry.entry_id = "test_id"

        flow = HausfunkOptionsFlow(entry)
        flow.hass = MagicMock()
        flow.hass.config_entries.async_update_entry = MagicMock()
        flow.hass.config_entries.async_reload = AsyncMock()

        res = await flow.async_step_init(user_input={CONF_GO2RTC_URL: "http://localhost:21984"})
        self.assertEqual(res["type"], "create_entry")
        flow.hass.config_entries.async_reload.assert_awaited_once_with(entry.entry_id)
