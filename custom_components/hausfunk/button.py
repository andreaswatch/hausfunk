"""Buttons for Hausfunk: Pi install/uninstall/reboot and HA go2rtc config."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import notify_restart_needed
from .const import (
    CONF_PI_HOST,
    CONF_PI_PASSWORD,
    CONF_PI_PORT,
    CONF_PI_USERNAME,
    CONF_SUDO_PASSWORD,
    DOMAIN,
    NAME,
)
from .coordinator import HausfunkCoordinator
from .pi.installer import HausfunkInstaller
from .pi.ssh import PiCommandError, PiSSH

_LOGGER = logging.getLogger(__name__)

BUTTONS = (
    ("install_pi", "Pi einrichten", "mdi:raspberry-pi", "install_pi"),
    ("uninstall_pi", "Pi deinstallieren", "mdi:raspberry-pi", "uninstall_pi"),
    ("restart_pi_go2rtc", "go2rtc auf Pi neu starten", "mdi:restart", "restart_pi_go2rtc"),
    ("install_ha", "HA go2rtc einrichten", "mdi:cog", "install_ha"),
    ("uninstall_ha", "HA go2rtc entfernen", "mdi:cog-off", "uninstall_ha"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up buttons for all current Pi subentries and register a callback for new ones."""
    entry_data = hass.data[DOMAIN][entry.entry_id]

    for coordinator in entry_data["coordinators"].values():
        async_add_entities(
            HausfunkButton(coordinator, key, name, icon, action)
            for key, name, icon, action in BUTTONS
        )

    @callback
    def _add_pi(coordinator: HausfunkCoordinator, subentry_id: str):
        async_add_entities(
            HausfunkButton(coordinator, key, name, icon, action)
            for key, name, icon, action in BUTTONS
        )

    entry_data["pi_add_callbacks"].append(_add_pi)
    entry.async_on_unload(lambda: entry_data["pi_add_callbacks"].remove(_add_pi))


class HausfunkButton(CoordinatorEntity, ButtonEntity):
    """A one-shot action button backed by the coordinator."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = True

    def __init__(
        self, coordinator: HausfunkCoordinator, key: str, name: str, icon: str, action: str
    ):
        super().__init__(coordinator)
        self._action = action
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"hausfunk_button_{coordinator.pi_id}_{key}"
        device_info = {
            "identifiers": {(DOMAIN, coordinator.config[CONF_PI_HOST])},
            "manufacturer": NAME,
            "model": "Pi + go2rtc",
            "name": f"Hausfunk Pi ({coordinator.config[CONF_PI_HOST]})",
        }
        if getattr(coordinator, "subentry_id", None):
            device_info["subentry_id"] = coordinator.subentry_id
        self._attr_device_info = DeviceInfo(**device_info)

    @property
    def available(self) -> bool:
        return True

    async def async_press(self):
        """Execute the button action."""
        config = self.coordinator.config
        pi_config = self.coordinator.pi_config
        hass = self.coordinator.hass
        if self._action == "install_ha":
            ok = await self.coordinator.register_stream(persist=True, restart=True)
            await self.coordinator.async_request_refresh()
            if not ok:
                notify_restart_needed(hass)
        elif self._action == "uninstall_ha":
            await self.coordinator.remove_stream()
            await self.coordinator.async_request_refresh()
        else:
            ssh = PiSSH(
                pi_config[CONF_PI_HOST],
                pi_config[CONF_PI_PORT],
                pi_config[CONF_PI_USERNAME],
                pi_config[CONF_PI_PASSWORD],
            )
            installer = HausfunkInstaller(hass, ssh, config)
            try:
                if self._action == "install_pi":
                    await installer.install(pi_config.get(CONF_SUDO_PASSWORD))
                elif self._action == "uninstall_pi":
                    await installer.uninstall(pi_config.get(CONF_SUDO_PASSWORD))
                elif self._action == "restart_pi_go2rtc":
                    await installer.restart_service()
            except PiCommandError as err:
                _LOGGER.exception("Pi-Aktion fehlgeschlagen: %s", self._action)
                raise
