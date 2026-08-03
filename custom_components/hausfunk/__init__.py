"""Hausfunk integration setup and services."""

import logging

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    CONF_PI_HOST,
    CONF_PI_PASSWORD,
    CONF_PI_PORT,
    CONF_PI_USERNAME,
    CONF_SUDO_PASSWORD,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import HausfunkCoordinator
from .pi.installer import HausfunkInstaller
from .pi.ssh import PiCommandError, PiSSH

_LOGGER = logging.getLogger(__name__)

_NOTIFICATION_ID = "hausfunk_install"


def get_main_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Return the main go2rtc config entry if it exists."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if CONF_PI_HOST not in entry.data:
            return entry
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hausfunk from a config entry."""
    # Main entry setup (HA-side go2rtc config)
    if CONF_PI_HOST not in entry.data:
        await _async_register_services(hass)
        return True

    # Pi entry setup
    main_entry = get_main_entry(hass)
    if not main_entry:
        _LOGGER.error("Main Hausfunk Sprechanlage config entry not found.")
        return False

    pi_config = dict(entry.data)
    go2rtc_config = dict(main_entry.data)
    pi_id = pi_config.get(CONF_PI_HOST)
    
    coordinator = HausfunkCoordinator(
        hass, entry, go2rtc_config, pi_config, pi_id=pi_id
    )
    await coordinator.register_stream()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await _async_register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if CONF_PI_HOST not in entry.data:
        # Main entry unloading
        if len(hass.config_entries.async_entries(DOMAIN)) <= 1:
            for service in _SERVICE_NAMES:
                if hass.services.has_service(DOMAIN, service):
                    hass.services.async_remove(DOMAIN, service)
        return True

    # Pi entry unloading
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
        if coordinator:
            await coordinator.async_close()
        
        # Only remove services if no entries left
        if not hass.data.get(DOMAIN):
            for service in _SERVICE_NAMES:
                if hass.services.has_service(DOMAIN, service):
                    hass.services.async_remove(DOMAIN, service)
    return unload_ok


_SERVICE_NAMES = (
    "setup_pi",
    "update_pi",
    "uninstall_pi",
    "restart_pi_go2rtc",
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


def _get_coordinators(hass: HomeAssistant) -> list[HausfunkCoordinator]:
    """Return all coordinators."""
    return list(hass.data.get(DOMAIN, {}).values())


def _get_coordinator(
    hass: HomeAssistant, pi_id: str | None
) -> HausfunkCoordinator | None:
    coordinators = _get_coordinators(hass)
    if not coordinators:
        return None
    if pi_id is None:
        if len(coordinators) == 1:
            return coordinators[0]
        return None
    for coordinator in coordinators:
        if coordinator.pi_id == pi_id:
            return coordinator
    return None


def _make_ssh(pi_config: dict) -> PiSSH:
    return PiSSH(
        pi_config[CONF_PI_HOST], pi_config[CONF_PI_PORT],
        pi_config[CONF_PI_USERNAME], pi_config[CONF_PI_PASSWORD],
    )


async def _async_register_services(hass: HomeAssistant):
    """Register services that operate on a specific Pi (device)."""
    if hass.services.has_service(DOMAIN, _SERVICE_NAMES[0]):
        return

    async def _setup_pi(call: ServiceCall):
        pi_id = call.data.get("pi_id")
        coordinator = _get_coordinator(hass, pi_id)
        if not coordinator:
            _notify(hass, "Fehler", "Gerät nicht gefunden oder pi_id fehlt bei mehreren Geräten.")
            return
        try:
            installer = HausfunkInstaller(hass, _make_ssh(coordinator.pi_config), coordinator.config)
            message = await installer.install(coordinator.pi_config.get(CONF_SUDO_PASSWORD))
            _LOGGER.info(message)
            await coordinator.register_stream()
            _clear_notification(hass)
        except (PiCommandError, OSError) as err:
            _LOGGER.exception("Pi-Setup fehlgeschlagen")
            _notify(hass, "Pi-Setup fehlgeschlagen", str(err), error=True)

    async def _update_pi(call: ServiceCall):
        pi_id = call.data.get("pi_id")
        coordinator = _get_coordinator(hass, pi_id)
        if not coordinator:
            _notify(hass, "Fehler", "Gerät nicht gefunden oder pi_id fehlt bei mehreren Geräten.")
            return
        try:
            installer = HausfunkInstaller(hass, _make_ssh(coordinator.pi_config), coordinator.config)
            message = await installer.update(coordinator.pi_config.get(CONF_SUDO_PASSWORD))
            _LOGGER.info(message)
            _clear_notification(hass)
        except (PiCommandError, OSError) as err:
            _LOGGER.exception("Pi-Update fehlgeschlagen")
            _notify(hass, "Pi-Update fehlgeschlagen", str(err), error=True)

    async def _uninstall_pi(call: ServiceCall):
        pi_id = call.data.get("pi_id")
        coordinator = _get_coordinator(hass, pi_id)
        if not coordinator:
            _notify(hass, "Fehler", "Gerät nicht gefunden oder pi_id fehlt bei mehreren Geräten.")
            return
        try:
            installer = HausfunkInstaller(hass, _make_ssh(coordinator.pi_config), coordinator.config)
            message = await installer.uninstall(coordinator.pi_config.get(CONF_SUDO_PASSWORD))
            _LOGGER.info(message)
            _clear_notification(hass)
        except (PiCommandError, OSError) as err:
            _LOGGER.exception("Pi-Deinstallation fehlgeschlagen")
            _notify(hass, "Pi-Deinstallation fehlgeschlagen", str(err), error=True)

    async def _restart_pi_go2rtc(call: ServiceCall):
        pi_id = call.data.get("pi_id")
        coordinator = _get_coordinator(hass, pi_id)
        if not coordinator:
            _notify(hass, "Fehler", "Gerät nicht gefunden oder pi_id fehlt bei mehreren Geräten.")
            return
        try:
            installer = HausfunkInstaller(hass, _make_ssh(coordinator.pi_config), coordinator.config)
            message = await installer.restart_service()
            _LOGGER.info(message)
        except PiCommandError as err:
            _LOGGER.exception("go2rtc-Neustart auf Pi fehlgeschlagen")
            _notify(hass, "go2rtc-Neustart auf Pi fehlgeschlagen", str(err), error=True)

    async def _register_stream(call: ServiceCall):
        pi_id = call.data.get("pi_id")
        coordinator = _get_coordinator(hass, pi_id)
        if not coordinator:
            _notify(hass, "Fehler", "Gerät nicht gefunden oder pi_id fehlt bei mehreren Geräten.")
            return
        ok = await coordinator.register_stream(persist=True, restart=True)
        await coordinator.async_request_refresh()
        if not ok:
            notify_restart_needed(hass)

    async def _remove_stream(call: ServiceCall):
        pi_id = call.data.get("pi_id")
        coordinator = _get_coordinator(hass, pi_id)
        if not coordinator:
            _notify(hass, "Fehler", "Gerät nicht gefunden oder pi_id fehlt bei mehreren Geräten.")
            return
        ok = await coordinator.remove_stream()
        await coordinator.async_request_refresh()
        if ok:
            _clear_notification(hass)

    handlers = {
        "setup_pi": _setup_pi,
        "update_pi": _update_pi,
        "uninstall_pi": _uninstall_pi,
        "restart_pi_go2rtc": _restart_pi_go2rtc,
        "register_stream": _register_stream,
        "remove_stream": _remove_stream,
    }
    for name, handler in handlers.items():
        hass.services.async_register(DOMAIN, name, handler)
