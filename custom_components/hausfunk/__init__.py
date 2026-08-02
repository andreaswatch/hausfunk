"""Hausfunk integration setup and services."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_GO2RTC_VERSION,
    CONF_PI_HOST,
    CONF_PI_PASSWORD,
    CONF_PI_PORT,
    CONF_PI_USERNAME,
    CONF_SUDO_PASSWORD,
    DOMAIN,
    NAME,
    PLATFORMS,
)
from .coordinator import HausfunkCoordinator
from .pi.installer import HausfunkInstaller
from .pi.ssh import PiSSH

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hausfunk from a config entry."""
    config = {**entry.data, **entry.options}

    coordinator = HausfunkCoordinator(hass, config)
    await coordinator.register_stream()
    await coordinator.async_config_entry_first_refresh()

    await _register_device(hass, entry, config)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await _async_register_services(hass, config)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_close()
        for service in _SERVICE_NAMES:
            hass.services.async_remove(DOMAIN, service)
    return unload_ok


async def _register_device(hass: HomeAssistant, entry: ConfigEntry, config: dict):
    registry = dr.async_get(hass)
    registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, config[CONF_PI_HOST])},
        name="Hausfunk Pi",
        manufacturer=NAME,
        model="Pi Zero 2W + go2rtc",
        sw_version=config.get(CONF_GO2RTC_VERSION),
    )


_SERVICE_NAMES = ("setup_pi", "update_pi", "register_stream", "remove_stream")


async def _async_register_services(hass: HomeAssistant, config: dict):
    async def _setup_pi(_call: ServiceCall):
        ssh = PiSSH(
            config[CONF_PI_HOST], config[CONF_PI_PORT],
            config[CONF_PI_USERNAME], config[CONF_PI_PASSWORD],
        )
        installer = HausfunkInstaller(hass, ssh, config)
        await installer.install(config.get(CONF_SUDO_PASSWORD))
        coordinator: HausfunkCoordinator = next(iter(hass.data[DOMAIN].values()))
        await coordinator.register_stream()

    async def _update_pi(_call: ServiceCall):
        ssh = PiSSH(
            config[CONF_PI_HOST], config[CONF_PI_PORT],
            config[CONF_PI_USERNAME], config[CONF_PI_PASSWORD],
        )
        installer = HausfunkInstaller(hass, ssh, config)
        await installer.update(config.get(CONF_SUDO_PASSWORD))

    async def _register_stream(_call: ServiceCall):
        coordinator: HausfunkCoordinator = next(iter(hass.data[DOMAIN].values()))
        await coordinator.register_stream()
        await coordinator.async_request_refresh()

    async def _remove_stream(_call: ServiceCall):
        coordinator: HausfunkCoordinator = next(iter(hass.data[DOMAIN].values()))
        await coordinator.remove_stream()
        await coordinator.async_request_refresh()

    handlers = {
        "setup_pi": _setup_pi,
        "update_pi": _update_pi,
        "register_stream": _register_stream,
        "remove_stream": _remove_stream,
    }
    for name, handler in handlers.items():
        hass.services.async_register(DOMAIN, name, handler)
