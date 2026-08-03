"""Hausfunk integration setup and services."""

import logging

from homeassistant.components import persistent_notification
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

_NOTIFICATION_ID = "hausfunk_install"


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


_SERVICE_NAMES = (
    "setup_pi",
    "update_pi",
    "uninstall_pi",
    "reboot_pi",
    "register_stream",
    "remove_stream",
)


def _notify(hass: HomeAssistant, title: str, message: str, error: bool = False):
    """Show a persistent notification (dismissed on the next success)."""
    persistent_notification.async_create(
        hass, message, title=f"Hausfunk: {title}", notification_id=_NOTIFICATION_ID
    )


def notify_restart_needed(hass: HomeAssistant):
    """Notify the user that go2rtc should be restarted."""
    _notify(
        hass,
        "go2rtc neu starten",
        "Die go2rtc-Konfiguration wurde geändert. Starte go2rtc neu, "
        "damit die Änderungen wirksam werden.",
    )


def _clear_notification(hass: HomeAssistant):
    persistent_notification.async_dismiss(hass, _NOTIFICATION_ID)


def _make_ssh(config: dict) -> PiSSH:
    return PiSSH(
        config[CONF_PI_HOST], config[CONF_PI_PORT],
        config[CONF_PI_USERNAME], config[CONF_PI_PASSWORD],
    )


def get_coordinator(hass: HomeAssistant) -> HausfunkCoordinator:
    return next(iter(hass.data[DOMAIN].values()))


async def _async_register_services(hass: HomeAssistant, config: dict):
    async def _setup_pi(call: ServiceCall):
        try:
            installer = HausfunkInstaller(hass, _make_ssh(config), config)
            message = await installer.install(config.get(CONF_SUDO_PASSWORD))
            _LOGGER.info(message)
            coordinator = get_coordinator(hass)
            await coordinator.register_stream()
            _clear_notification(hass)
        except (PiCommandError, OSError) as err:
            _LOGGER.exception("Pi-Setup fehlgeschlagen")
            _notify(hass, "Pi-Setup fehlgeschlagen", str(err), error=True)

    async def _update_pi(call: ServiceCall):
        try:
            installer = HausfunkInstaller(hass, _make_ssh(config), config)
            message = await installer.update(config.get(CONF_SUDO_PASSWORD))
            _LOGGER.info(message)
            _clear_notification(hass)
        except (PiCommandError, OSError) as err:
            _LOGGER.exception("Pi-Update fehlgeschlagen")
            _notify(hass, "Pi-Update fehlgeschlagen", str(err), error=True)

    async def _uninstall_pi(call: ServiceCall):
        try:
            installer = HausfunkInstaller(hass, _make_ssh(config), config)
            message = await installer.uninstall(config.get(CONF_SUDO_PASSWORD))
            _LOGGER.info(message)
            _clear_notification(hass)
        except (PiCommandError, OSError) as err:
            _LOGGER.exception("Pi-Deinstallation fehlgeschlagen")
            _notify(hass, "Pi-Deinstallation fehlgeschlagen", str(err), error=True)

    async def _reboot_pi(call: ServiceCall):
        try:
            installer = HausfunkInstaller(hass, _make_ssh(config), config)
            message = await installer.reboot(config.get(CONF_SUDO_PASSWORD))
            _LOGGER.info(message)
        except (PiCommandError, OSError) as err:
            _LOGGER.exception("Pi-Reboot fehlgeschlagen")
            _notify(hass, "Pi-Reboot fehlgeschlagen", str(err), error=True)

    async def _register_stream(call: ServiceCall):
        coordinator = get_coordinator(hass)
        ok = await coordinator.register_stream(persist=True, restart=True)
        await coordinator.async_request_refresh()
        if not ok:
            notify_restart_needed(hass)

    async def _remove_stream(call: ServiceCall):
        coordinator = get_coordinator(hass)
        ok = await coordinator.remove_stream()
        await coordinator.async_request_refresh()
        if ok:
            _clear_notification(hass)

    handlers = {
        "setup_pi": _setup_pi,
        "update_pi": _update_pi,
        "uninstall_pi": _uninstall_pi,
        "reboot_pi": _reboot_pi,
        "register_stream": _register_stream,
        "remove_stream": _remove_stream,
    }
    for name, handler in handlers.items():
        hass.services.async_register(DOMAIN, name, handler)
