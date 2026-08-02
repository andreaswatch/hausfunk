import unittest

import tests.hass_mock

from custom_components.hausfunk.binary_sensor import HausfunkBinarySensor
from custom_components.hausfunk.const import (
    CONF_GO2RTC_URL,
    CONF_PI_HOST,
    CONF_RTSP_PORT,
    CONF_STREAM_NAME,
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


if __name__ == "__main__":
    unittest.main()
