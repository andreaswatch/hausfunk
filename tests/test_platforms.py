import unittest

import tests.hass_mock

from custom_components.hausfunk.binary_sensor import HausfunkBinarySensor
from custom_components.hausfunk.camera import HausfunkCamera
from custom_components.hausfunk.const import (
    CONF_GO2RTC_HOST,
    CONF_GO2RTC_RTSP_PORT,
    CONF_GO2RTC_URL,
    CONF_PI_HOST,
    CONF_RTSP_PORT,
    CONF_STREAM_NAME,
    DEFAULT_GO2RTC_HOST,
    DEFAULT_GO2RTC_RTSP_PORT,
    DOMAIN,
    DEFAULT_GO2RTC_URL,
)
from custom_components.hausfunk.coordinator import HausfunkCoordinator
from custom_components.hausfunk.switch import HausfunkStreamSwitch

CONFIG = {
    CONF_PI_HOST: "192.168.178.11",
    CONF_RTSP_PORT: 8554,
    CONF_STREAM_NAME: "tuer",
    CONF_GO2RTC_URL: DEFAULT_GO2RTC_URL,
    CONF_GO2RTC_HOST: DEFAULT_GO2RTC_HOST,
    CONF_GO2RTC_RTSP_PORT: DEFAULT_GO2RTC_RTSP_PORT,
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

    def test_camera_stream_source_default_port(self):
        camera = HausfunkCamera(self._coordinator())
        self.assertEqual(
            camera.stream_source, "rtsp://127.0.0.1:18554/tuer"
        )
        self.assertTrue(camera.available)

    def test_camera_unavailable_when_pi_down(self):
        coordinator = self._coordinator()
        coordinator.data = {"pi_reachable": False, "stream_active": False}
        camera = HausfunkCamera(coordinator)
        self.assertFalse(camera.available)
        self.assertIsNone(camera.stream_source)

    def test_camera_custom_host_port(self):
        config = dict(CONFIG)
        config[CONF_GO2RTC_HOST] = "10.0.0.5"
        config[CONF_GO2RTC_RTSP_PORT] = 8554
        coordinator = HausfunkCoordinator(hass=None, config=config)
        coordinator.data = {"pi_reachable": True, "stream_active": True}
        camera = HausfunkCamera(coordinator)
        self.assertEqual(camera.stream_source, "rtsp://10.0.0.5:8554/tuer")

    def test_camera_device_info(self):
        camera = HausfunkCamera(self._coordinator())
        self.assertEqual(
            camera.device_info,
            {"identifiers": {(DOMAIN, "192.168.178.11")}},
        )


if __name__ == "__main__":
    unittest.main()
