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
tests.hass_mock.config_entries_mock.OptionsFlow = DummyOptionsFlow

from custom_components.hausfunk.config_flow import HausfunkConfigFlow, HausfunkOptionsFlow
from custom_components.hausfunk.const import (
    CONF_GO2RTC_URL,
    CONF_PI_HOST,
    CONF_PI_PASSWORD,
    CONF_PI_USERNAME,
)

class TestConfigFlow(unittest.IsolatedAsyncioTestCase):
    async def test_user_step_no_existing_entries(self):
        """Initial config flow run when no entries exist should prompt for go2rtc settings."""
        flow = HausfunkConfigFlow()
        flow.hass = MagicMock()
        flow.hass.config_entries.async_entries = MagicMock(return_value=[])

        # Show initial form
        with patch.object(flow, "_detect_go2rtc", AsyncMock(return_value=(MagicMock(), "detected"))):
            res = await flow.async_step_user(user_input=None)
            self.assertEqual(res["type"], "form")
            self.assertEqual(res["step_id"], "user")

        # Submit settings
        user_input = {CONF_GO2RTC_URL: "http://localhost:11984"}
        with patch.object(flow, "_detect_go2rtc", AsyncMock(return_value=(MagicMock(), "detected"))):
            res = await flow.async_step_user(user_input=user_input)
            self.assertEqual(res["type"], "create_entry")
            self.assertEqual(res["title"], "Hausfunk Sprechanlage")
            self.assertEqual(res["data"][CONF_GO2RTC_URL], "http://localhost:11984")

    async def test_user_step_with_existing_main_entry(self):
        """If main entry exists, user step should redirect to Pi step."""
        main_entry = MagicMock()
        main_entry.data = {CONF_GO2RTC_URL: "http://localhost:11984"}

        flow = HausfunkConfigFlow()
        flow.hass = MagicMock()
        flow.hass.config_entries.async_entries = MagicMock(return_value=[main_entry])

        with patch.object(flow, "async_step_pi", return_value={"type": "form", "step_id": "pi"}) as mock_pi:
            res = await flow.async_step_user(user_input=None)
            self.assertEqual(res["type"], "form")
            self.assertEqual(res["step_id"], "pi")
            mock_pi.assert_called_once()

    async def test_pi_step_flow(self):
        """Test configuring a Pi device entry."""
        flow = HausfunkConfigFlow()
        flow.hass = MagicMock()
        flow._validate_pi = AsyncMock(return_value={})

        user_input = {
            CONF_PI_HOST: "192.168.178.50",
            CONF_PI_PASSWORD: "test",
            CONF_PI_USERNAME: "pi",
        }
        with patch.object(flow, "async_step_install", return_value={"type": "form", "step_id": "install"}) as mock_install:
            res = await flow.async_step_pi(user_input=user_input)
            self.assertEqual(res["type"], "form")
            self.assertEqual(res["step_id"], "install")
            mock_install.assert_called_once()
            self.assertEqual(flow._data[CONF_PI_HOST], "192.168.178.50")


class TestOptionsFlow(unittest.IsolatedAsyncioTestCase):
    async def test_options_flow_main_entry(self):
        """Options flow for main entry should show go2rtc settings."""
        entry = MagicMock()
        entry.data = {CONF_GO2RTC_URL: "http://localhost:11984"}
        
        flow = HausfunkOptionsFlow(entry)
        flow.hass = MagicMock()
        flow.hass.config_entries.async_entries = MagicMock(return_value=[entry])

        res = await flow.async_step_init(user_input=None)
        self.assertEqual(res["type"], "form")
        self.assertEqual(res["step_id"], "go2rtc")

    async def test_options_flow_pi_entry(self):
        """Options flow for Pi entry should show Pi settings."""
        entry = MagicMock()
        entry.data = {CONF_PI_HOST: "192.168.178.11", CONF_PI_PASSWORD: "test"}
        
        flow = HausfunkOptionsFlow(entry)
        flow.hass = MagicMock()

        res = await flow.async_step_init(user_input=None)
        self.assertEqual(res["type"], "form")
        self.assertEqual(res["step_id"], "init")
