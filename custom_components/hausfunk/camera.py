"""Camera for Hausfunk: exposes the go2rtc-registered stream as a camera entity."""

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_GO2RTC_HOST,
    CONF_GO2RTC_RTSP_PORT,
    CONF_PI_HOST,
    CONF_STREAM_NAME,
    DEFAULT_GO2RTC_HOST,
    DEFAULT_GO2RTC_RTSP_PORT,
    DOMAIN,
    NAME,
)
from .coordinator import HausfunkCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up cameras for all current Pi subentries and register a callback for new ones."""
    entry_data = hass.data[DOMAIN][entry.entry_id]

    for subentry_id, coordinator in entry_data["coordinators"].items():
        async_add_entities([HausfunkCamera(coordinator)], config_subentry_id=subentry_id)

    @callback
    def _add_pi(coordinator: HausfunkCoordinator, subentry_id: str):
        async_add_entities([HausfunkCamera(coordinator)], config_subentry_id=subentry_id)

    entry_data["pi_add_callbacks"].append(_add_pi)
    entry.async_on_unload(lambda: entry_data["pi_add_callbacks"].remove(_add_pi))


class HausfunkCamera(CoordinatorEntity, Camera):
    """Camera backed by the go2rtc-registered stream on the HA host.

    The stream is registered in the HA-local go2rtc instance (see
    HausfunkCoordinator.register_stream / persist_stream). This entity only
    exposes a stream_source that points at the HA go2rtc RTSP server, so the
    browser reaches the Pi exclusively via the HA go2rtc WebRTC proxy and
    never talks to the Pi directly.
    """

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator: HausfunkCoordinator):
        super().__init__(coordinator)
        Camera.__init__(self)
        self._attr_name = "Kamera"
        self._attr_icon = "mdi:cctv"
        self._attr_unique_id = f"hausfunk_camera_{coordinator.pi_id}"
        self._attr_supported_features = CameraEntityFeature.STREAM
        device_info = {
            "identifiers": {(DOMAIN, coordinator.config[CONF_PI_HOST])},
            "manufacturer": NAME,
            "model": "Pi + go2rtc",
            "name": f"Hausfunk Pi ({coordinator.config[CONF_PI_HOST]})",
        }
        self._attr_device_info = DeviceInfo(**device_info)

    @property
    def available(self) -> bool:
        return bool(
            self.coordinator.data and self.coordinator.data.get("pi_reachable")
        )

    async def stream_source(self) -> str | None:
        if not self.available:
            return None
        config = self.coordinator.config
        host = config.get(CONF_GO2RTC_HOST) or DEFAULT_GO2RTC_HOST
        port = config.get(CONF_GO2RTC_RTSP_PORT, DEFAULT_GO2RTC_RTSP_PORT)
        name = config[CONF_STREAM_NAME]
        return f"rtsp://{host}:{port}/{name}"

    @property
    def use_stream_for_stills(self) -> bool:
        """Generate thumbnails from the live stream instead of a camera API."""
        return True