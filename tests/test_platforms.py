import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import tests.hass_mock

from custom_components.hausfunk.binary_sensor import HausfunkBinarySensor
from custom_components.hausfunk.button import BUTTONS, HausfunkButton
from custom_components.hausfunk.camera import HausfunkCamera
from custom_components.hausfunk.select import HausfunkStreamModeSelect
from custom_components.hausfunk.switch import HausfunkStreamSwitch
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

HOST_CONFIG = {
    CONF_GO2RTC_URL: DEFAULT_GO2RTC_URL,
    CONF_GO2RTC_HOST: DEFAULT_GO2RTC_HOST,
    CONF_GO2RTC_RTSP_PORT: DEFAULT_GO2RTC_RTSP_PORT,
    CONF_GO2RTC_WEBRTC_PORT: DEFAULT_GO2RTC_WEBRTC_PORT,
    CONF_GO2RTC_CANDIDATES: DEFAULT_GO2RTC_CANDIDATES,
}

PI_CONFIG = {
    CONF_PI_HOST: "192.168.178.11",
    CONF_PI_PORT: 22,
    CONF_PI_USERNAME: "pi",
    CONF_PI_PASSWORD: "secret",
    CONF_RTSP_PORT: 8554,
    CONF_STREAM_NAME: "tuer",
}


def _coordinator(data=None):
    entry = MagicMock()
    entry.data = {**HOST_CONFIG, **PI_CONFIG}
    coordinator = HausfunkCoordinator(
        hass=MagicMock(),
        entry=entry,
        host_config=dict(HOST_CONFIG),
        pi_config=dict(PI_CONFIG),
        pi_id="192.168.178.11",
    )
    coordinator.data = data or {"pi_reachable": True, "stream_active": True}
    return coordinator


class TestEntities(unittest.TestCase):
    def test_binary_sensor_device_info(self):
        sensor = HausfunkBinarySensor(
            _coordinator(), "pi_reachable", "Erreichbar", "mdi:raspberry-pi"
        )
        self.assertEqual(
            sensor.device_info["identifiers"], {(DOMAIN, "192.168.178.11")}
        )
        self.assertTrue(sensor.is_on)

    def test_binary_sensor_has_entity_name(self):
        sensor = HausfunkBinarySensor(
            _coordinator(), "stream_active", "Stream aktiv", "mdi:cast-connected"
        )
        self.assertTrue(sensor.has_entity_name)
        self.assertEqual(sensor.name, "Stream aktiv")

    def test_switch_device_info(self):
        switch = HausfunkStreamSwitch(_coordinator())
        self.assertEqual(
            switch.device_info["identifiers"], {(DOMAIN, "192.168.178.11")}
        )
        self.assertTrue(switch.is_on)

    def test_camera_device_info(self):
        camera = HausfunkCamera(_coordinator())
        self.assertEqual(
            camera.device_info["identifiers"], {(DOMAIN, "192.168.178.11")}
        )
        self.assertTrue(camera.use_stream_for_stills)

    def test_buttons_defined(self):
        keys = [b[0] for b in BUTTONS]
        self.assertEqual(
            keys,
            ["install_pi", "uninstall_pi", "restart_pi_go2rtc", "install_ha", "uninstall_ha"],
        )

    def test_button_device_info(self):
        button = HausfunkButton(
            _coordinator(), "install_pi", "Pi einrichten", "mdi:raspberry-pi", "install_pi"
        )
        self.assertEqual(
            button.device_info["identifiers"], {(DOMAIN, "192.168.178.11")}
        )
        self.assertEqual(button.unique_id, "hausfunk_button_192.168.178.11_install_pi")

    def test_button_has_entity_name(self):
        button = HausfunkButton(
            _coordinator(), "restart_pi_go2rtc", "go2rtc auf Pi neu starten", "mdi:restart", "restart_pi_go2rtc"
        )
        self.assertTrue(button.has_entity_name)
        self.assertEqual(button.name, "go2rtc auf Pi neu starten")


class TestCameraAsync(unittest.IsolatedAsyncioTestCase):
    async def test_camera_stream_source_default_port(self):
        camera = HausfunkCamera(_coordinator())
        self.assertEqual(
            await camera.stream_source(), "rtsp://127.0.0.1:18554/tuer"
        )
        self.assertTrue(camera.available)

    async def test_camera_unavailable_when_pi_down(self):
        coordinator = _coordinator({"pi_reachable": False, "stream_active": False})
        camera = HausfunkCamera(coordinator)
        self.assertFalse(camera.available)
        self.assertIsNone(await camera.stream_source())

    async def test_camera_custom_host_port(self):
        host = dict(HOST_CONFIG)
        host[CONF_GO2RTC_HOST] = "10.0.0.5"
        host[CONF_GO2RTC_RTSP_PORT] = 8554
        entry = MagicMock()
        entry.data = {**host, **PI_CONFIG}
        coordinator = HausfunkCoordinator(
            hass=None, entry=entry, host_config=host, pi_config=dict(PI_CONFIG), pi_id="192.168.178.11"
        )
        coordinator.data = {"pi_reachable": True, "stream_active": True}
        camera = HausfunkCamera(coordinator)
        self.assertEqual(await camera.stream_source(), "rtsp://10.0.0.5:8554/tuer")


class TestButtonActions(unittest.IsolatedAsyncioTestCase):
    def _button(self, action):
        coordinator = _coordinator()
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

    async def test_restart_pi_go2rtc_uses_installer(self):
        button = self._button("restart_pi_go2rtc")
        with patch(
            "custom_components.hausfunk.button.HausfunkInstaller"
        ) as mock_installer:
            installer = mock_installer.return_value
            installer.restart_service = AsyncMock(return_value="ok")
            await button.async_press()
            installer.restart_service.assert_awaited_once()


class TestSelectEntity(unittest.IsolatedAsyncioTestCase):
    async def test_select_mode(self):
        coordinator = _coordinator()
        coordinator.async_update_setting = AsyncMock()
        select = HausfunkStreamModeSelect(coordinator)
        
        self.assertEqual(select.current_option, "rtsp")
        self.assertEqual(select.options, ["webrtc", "rtsp", "both", "rtsp_webrtc"])
        self.assertEqual(select.device_info["identifiers"], {(DOMAIN, "192.168.178.11")})
        
        await select.async_select_option("rtsp_webrtc")
        coordinator.async_update_setting.assert_awaited_once_with("stream_mode", "rtsp_webrtc")


class TestCoordinatorUpdateSetting(unittest.IsolatedAsyncioTestCase):
    async def test_update_setting_stream_mode(self):
        coordinator = _coordinator()
        coordinator.register_stream = AsyncMock()
        coordinator._update_pi_config = AsyncMock()

        await coordinator.async_update_setting("stream_mode", "rtsp")
        self.assertEqual(coordinator.config["stream_mode"], "rtsp")
        coordinator._update_pi_config.assert_awaited_once()
        coordinator.register_stream.assert_awaited_once_with(persist=True, restart=True)


if __name__ == "__main__":
    unittest.main()
