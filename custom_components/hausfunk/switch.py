"""Switch for Hausfunk: toggles the go2rtc stream registration."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PI_HOST, DOMAIN
from .coordinator import HausfunkCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    coordinators: dict[str, HausfunkCoordinator] = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        HausfunkStreamSwitch(coordinator) for coordinator in coordinators.values()
    )


class HausfunkStreamSwitch(CoordinatorEntity, SwitchEntity):
    """Toggles the stream registration in go2rtc."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HausfunkCoordinator):
        super().__init__(coordinator)
        self._attr_name = "Stream registriert"
        self._attr_icon = "mdi:cast"
        self._attr_unique_id = f"hausfunk_stream_switch_{coordinator.subentry_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config[CONF_PI_HOST])},
        )

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get("stream_active") if self.coordinator.data else None

    async def async_turn_on(self, **kwargs):
        await self.coordinator.register_stream()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        await self.coordinator.remove_stream()
        await self.coordinator.async_request_refresh()
