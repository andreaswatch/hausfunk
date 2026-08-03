"""Select entities for Hausfunk."""

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_PI_HOST,
    CONF_STREAM_MODE,
    DEFAULT_STREAM_MODE,
    DOMAIN,
    NAME,
    STREAM_MODE_RTSP,
    STREAM_MODE_WEBRTC,
)
from .coordinator import HausfunkCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    coordinator: HausfunkCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HausfunkStreamModeSelect(coordinator)])


class HausfunkStreamModeSelect(CoordinatorEntity, SelectEntity):
    """Select entity for the stream mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "stream_mode"

    def __init__(self, coordinator: HausfunkCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"hausfunk_{coordinator.pi_id}_stream_mode"
        self._attr_options = [STREAM_MODE_WEBRTC, STREAM_MODE_RTSP]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config[CONF_PI_HOST])},
            manufacturer=NAME,
            model="Pi + go2rtc",
            name=f"Hausfunk Pi ({coordinator.config[CONF_PI_HOST]})",
        )

    @property
    def current_option(self) -> str | None:
        return self.coordinator.config.get(CONF_STREAM_MODE, DEFAULT_STREAM_MODE)

    async def async_select_option(self, option: str) -> None:
        """Change the stream mode."""
        await self.coordinator.async_update_setting(CONF_STREAM_MODE, option)
