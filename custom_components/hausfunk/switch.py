"""Switch for Hausfunk: toggles the go2rtc stream registration."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PI_HOST, DOMAIN, NAME
from .coordinator import HausfunkCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up switches for all current Pi subentries and register a callback for new ones."""
    entry_data = hass.data[DOMAIN][entry.entry_id]

    for subentry_id, coordinator in entry_data["coordinators"].items():
        async_add_entities([HausfunkStreamSwitch(coordinator)], config_subentry_id=subentry_id)

    @callback
    def _add_pi(coordinator: HausfunkCoordinator, subentry_id: str):
        async_add_entities([HausfunkStreamSwitch(coordinator)], config_subentry_id=subentry_id)

    entry_data["pi_add_callbacks"].append(_add_pi)
    entry.async_on_unload(lambda: entry_data["pi_add_callbacks"].remove(_add_pi))


class HausfunkStreamSwitch(CoordinatorEntity, SwitchEntity):
    """Toggles the stream registration in go2rtc."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator: HausfunkCoordinator):
        super().__init__(coordinator)
        self._attr_name = "Stream registriert"
        self._attr_icon = "mdi:cast"
        self._attr_unique_id = f"hausfunk_stream_switch_{coordinator.pi_id}"
        device_info = {
            "identifiers": {(DOMAIN, coordinator.config[CONF_PI_HOST])},
            "manufacturer": NAME,
            "model": "Pi + go2rtc",
            "name": f"Hausfunk Pi ({coordinator.config[CONF_PI_HOST]})",
        }
        if getattr(coordinator, "subentry_id", None):
            device_info["subentry_id"] = coordinator.subentry_id
            device_info["config_subentry_id"] = coordinator.subentry_id
        self._attr_device_info = DeviceInfo(**device_info)

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get("stream_active") if self.coordinator.data else None

    async def async_turn_on(self, **kwargs):
        await self.coordinator.register_stream()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        await self.coordinator.remove_stream()
        await self.coordinator.async_request_refresh()
