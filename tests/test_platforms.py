import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import tests.hass_mock

from custom_components.hausfunk.binary_sensor import HausfunkBinarySensor
from custom_components.hausfunk.button import BUTTONS, HausfunkButton
from custom_components.hausfunk.camera import HausfunkCamera
from custom_components.hausfunk.const import (
    CONF_GO2RTC_CANDIDATES,
    CONF_GO2RTC_HOST,
    CONF_GO2RTC_RTSP_PORT,
    CONF_GO2RTC_URL,
    CONF_GO2RTC_WEBRTC_PORT,
    CONF_PI_HOST,
    CONF_PI_PASSWORD,
    CONF_PI_PORT,
    CONF_PI_USERNAME,
    CONF_RTSP_PORT,
    CONF_STREAM_NAME,
    DEFAULT_GO2RTC_CANDIDATES,
    DEFAULT_GO2RTC_HOST,
    DEFAULT_GO2RTC_RTSP_PORT,
    DEFAULT_GO2RTC_WEBRTC_PORT,
    DEFAULT_GO2RTC_URL,
    DEFAULT_PI_GO2RTC_PORT,
    DOMAIN,
)
from custom_components.hausfunk.coordinator import HausfunkCoordinator
from custom_components.hausfunk.switch import HausfunkStreamSwitch

CONFIG = {
    CONF_PI_HOST: "192.168.178.11",
    CONF_PI_PORT: 22,
    CONF_PI_USERNAME: "pi",
    CONF_PI_PASSWORD: "secret",
    CONF_RTSP_PORT: 8554,
    CONF_STREAM_NAME: "tuer",
    CONF_GO2RTC_URL: DEFAULT_GO2RTC_URL,
    CONF_GO2RTC_HOST: DEFAULT_GO2RTC_HOST,
    CONF_GO2RTC_RTSP_PORT: DEFAULT_GO2RTC_RTSP_PORT,
    CONF_GO2RTC_WEBRTC_PORT: DEFAULT_GO2RTC_WEBRTC_PORT,
    CONF_GO2RTC_CANDIDATES: DEFAULT_GO2RTC_CANDIDATES,
}


class TestEntities(unittest.TestCase):
    def _coordinator(self):
        coordinator = HausfunkCoordinator(hass=None, config=CONFIG)
        coordinator.data = {"pi_reachable": True, "stream_active": True}
        return coordinator

    def test_binary_sensor_device_info(self):
        sensor = HausfunkBinarySensor(
            self._coordinator(), "pi_reachable", "Erreichbar", "mdi:raspberry-pi"
        )
        self.assertEqual(
            sensor.device_info,
            {"identifiers": {(DOMAIN, "192.168.178.11")}},
        )
        self.assertTrue(sensor.is_on)

    def test_binary_sensor_has_entity_name(self):
        sensor = HausfunkBinarySensor(
            self._coordinator(), "stream_active", "Stream aktiv", "mdi:cast-connected"
        )
        self.assertTrue(sensor.has_entity_name)
        self.assertEqual(sensor.name, "Stream aktiv")

    def test_switch_device_info(self):
        switch = HausfunkStreamSwitch(self._coordinator())
        self.assertEqual(
            switch.device_info,
            {"identifiers": {(DOMAIN, "192.168.178.11")}},
        )
        self.assertTrue(switch.is_on)

    def test_camera_device_info(self):
        camera = HausfunkCamera(self._coordinator())
        self.assertEqual(
            camera.device_info,
            {"identifiers": {(DOMAIN, "192.168.178.11")}},
        )
        self.assertTrue(camera.use_stream_for_stills)

    def test_buttons_defined(self):
        keys = [b[0] for b in BUTTONS]
        self.assertEqual(
            keys,
            ["install_pi", "uninstall_pi", "reboot_pi", "install_ha", "uninstall_ha"],
        )

    def test_button_device_info(self):
        button = HausfunkButton(
            self._coordinator(), "install_pi", "Pi einrichten", "mdi:raspberry-pi", "install_pi"
        )
        self.assertEqual(
            button.device_info,
            {"identifiers": {(DOMAIN, "192.168.178.11")}},
        )
        self.assertEqual(button.unique_id, "hausfunk_button_install_pi")

    def test_button_has_entity_name(self):
        button = HausfunkButton(
            self._coordinator(), "reboot_pi", "Pi neu starten", "mdi:restart", "reboot_pi"
        )
        self.assertTrue(button.has_entity_name)
        self.assertEqual(button.name, "Pi neu starten")


class TestCameraAsync(unittest.IsolatedAsyncioTestCase):
    def _coordinator(self):
        coordinator = HausfunkCoordinator(hass=None, config=CONFIG)
        coordinator.data = {"pi_reachable": True, "stream_active": True}
        return coordinator

    async def test_camera_stream_source_default_port(self):
        camera = HausfunkCamera(self._coordinator())
        self.assertEqual(
            await camera.stream_source(), "rtsp://127.0.0.1:18554/tuer"
        )
        self.assertTrue(camera.available)

    async def test_camera_unavailable_when_pi_down(self):
        coordinator = self._coordinator()
        coordinator.data = {"pi_reachable": False, "stream_active": False}
        camera = HausfunkCamera(coordinator)
        self.assertFalse(camera.available)
        self.assertIsNone(await camera.stream_source())

    async def test_camera_custom_host_port(self):
        config = dict(CONFIG)
        config[CONF_GO2RTC_HOST] = "10.0.0.5"
        config[CONF_GO2RTC_RTSP_PORT] = 8554
        coordinator = HausfunkCoordinator(hass=None, config=config)
        coordinator.data = {"pi_reachable": True, "stream_active": True}
        camera = HausfunkCamera(coordinator)
        self.assertEqual(await camera.stream_source(), "rtsp://10.0.0.5:8554/tuer")


class TestButtonActions(unittest.IsolatedAsyncioTestCase):
    def _button(self, action):
        coordinator = HausfunkCoordinator(hass=MagicMock(), config=CONFIG)
        coordinator.data = {"pi_reachable": True, "stream_active": True}
        coordinator.register_stream = AsyncMock(return_value=True)
        coordinator.remove_stream = AsyncMock(return_value=True)
        coordinator.async_request_refresh = AsyncMock()
        button = HausfunkButton(
            coordinator, action, "x", "mdi:cog", action
        )
        return button

    async def test_install_ha_calls_register_stream_with_restart(self):
        button = self._button("install_ha")
        await button.async_press()
        button.coordinator.register_stream.assert_awaited_once_with(
            persist=True, restart=True
        )

    async def test_uninstall_ha_calls_remove_stream(self):
        button = self._button("uninstall_ha")
        await button.async_press()
        button.coordinator.remove_stream.assert_awaited_once()

    async def test_install_pi_uses_installer(self):
        button = self._button("install_pi")
        with patch(
            "custom_components.hausfunk.button.HausfunkInstaller"
        ) as mock_installer:
            installer = mock_installer.return_value
            installer.install = AsyncMock(return_value="ok")
            await button.async_press()
            installer.install.assert_awaited_once()

    async def test_uninstall_pi_uses_installer(self):
        button = self._button("uninstall_pi")
        with patch(
            "custom_components.hausfunk.button.HausfunkInstaller"
        ) as mock_installer:
            installer = mock_installer.return_value
            installer.uninstall = AsyncMock(return_value="ok")
            await button.async_press()
            installer.uninstall.assert_awaited_once()

    async def test_reboot_pi_uses_installer(self):
        button = self._button("reboot_pi")
        with patch(
            "custom_components.hausfunk.button.HausfunkInstaller"
        ) as mock_installer:
            installer = mock_installer.return_value
            installer.reboot = AsyncMock(return_value="ok")
            await button.async_press()
            installer.reboot.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
