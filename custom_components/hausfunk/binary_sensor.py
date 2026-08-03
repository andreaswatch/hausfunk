"""Binary sensors for Hausfunk: Pi reachability and stream state."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PI_HOST, DOMAIN, NAME
from .coordinator import HausfunkCoordinator

SENSORS = (
    ("pi_reachable", "Erreichbar", "mdi:raspberry-pi"),
    ("stream_active", "Stream aktiv", "mdi:cast-connected"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up binary sensors for all current Pi subentries and register a callback for new ones."""
    entry_data = hass.data[DOMAIN][entry.entry_id]

    # Add entities for already-loaded coordinators
    for subentry_id, coordinator in entry_data["coordinators"].items():
        async_add_entities(
            [HausfunkBinarySensor(coordinator, key, name, icon) for key, name, icon in SENSORS],
            config_subentry_id=subentry_id,
        )

    # Register a callback so _async_setup_pi can add entities for new Pis
    @callback
    def _add_pi(coordinator: HausfunkCoordinator, subentry_id: str):
        async_add_entities(
            [HausfunkBinarySensor(coordinator, key, name, icon) for key, name, icon in SENSORS],
            config_subentry_id=subentry_id,
        )

    entry_data["pi_add_callbacks"].append(_add_pi)
    entry.async_on_unload(lambda: entry_data["pi_add_callbacks"].remove(_add_pi))


class HausfunkBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor backed by the coordinator."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator: HausfunkCoordinator, key: str, name: str, icon: str):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"hausfunk_{coordinator.pi_id}_{key}"
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
        return self.coordinator.data.get(self._key) if self.coordinator.data else None
