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
    PI_SUBENTRY_TYPE,
    PLATFORMS,
)
from .coordinator import HausfunkCoordinator
from .pi.installer import HausfunkInstaller
from .pi.ssh import PiCommandError, PiSSH

_LOGGER = logging.getLogger(__name__)

_NOTIFICATION_ID = "hausfunk_install"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hausfunk from a config entry.

    The entry is a hub for the HA go2rtc instance. Each Pi is a subentry; its
    coordinator provides the entities, which create the device entries via
    device_info (Landroid Cloud pattern — no subentry link on devices).
    """
    host_config = dict(entry.data)

    coordinators: dict[str, HausfunkCoordinator] = {}
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != PI_SUBENTRY_TYPE:
            continue
        pi_config = dict(subentry.data)
        pi_id = pi_config.get(CONF_PI_HOST)
        coordinator = HausfunkCoordinator(
            hass, host_config, pi_config, pi_id=pi_id
        )
        await coordinator.register_stream()
        await coordinator.async_config_entry_first_refresh()
        coordinators[pi_id] = coordinator

        # Register the device manually so it's linked to the subentry.
        # When entities are created later, they will attach to this device.
        from homeassistant.helpers import device_registry as dr
        from .const import NAME
        
        device_registry = dr.async_get(hass)
        device = device_registry.async_get_device(identifiers={(DOMAIN, pi_id)})
        if device and device.config_subentry_id != subentry_id:
            device_registry.async_update_device(
                device.id,
                new_config_subentry_id=subentry_id,
            )
        else:
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                config_subentry_id=subentry_id,
                identifiers={(DOMAIN, pi_id)},
                manufacturer=NAME,
                model="Pi + go2rtc",
                name=f"Hausfunk Pi ({pi_id})",
            )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await _async_register_services(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinators = hass.data[DOMAIN].pop(entry.entry_id)
        for coordinator in coordinators.values():
            await coordinator.async_close()
        for service in _SERVICE_NAMES:
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


def _get_coordinators(hass: HomeAssistant) -> dict[str, HausfunkCoordinator]:
    """Return all coordinators across entries."""
    result: dict[str, HausfunkCoordinator] = {}
    for coordinators in hass.data.get(DOMAIN, {}).values():
        result.update(coordinators)
    return result


def _get_coordinator(
    hass: HomeAssistant, entry: ConfigEntry, pi_id: str
) -> HausfunkCoordinator:
    coordinators = hass.data[DOMAIN][entry.entry_id]
    return coordinators[pi_id]


def _make_ssh(pi_config: dict) -> PiSSH:
    return PiSSH(
        pi_config[CONF_PI_HOST], pi_config[CONF_PI_PORT],
        pi_config[CONF_PI_USERNAME], pi_config[CONF_PI_PASSWORD],
    )


async def _async_register_services(hass: HomeAssistant, entry: ConfigEntry):
    """Register services that operate on a specific Pi (device)."""

    def _resolve_pi_id(call: ServiceCall) -> str | None:
        coordinators = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
        if call.data.get("pi_id") in coordinators:
            return call.data["pi_id"]
        if len(coordinators) == 1:
            return next(iter(coordinators))
        return None

    async def _setup_pi(call: ServiceCall):
        pi_id = _resolve_pi_id(call)
        if pi_id is None:
            _notify(hass, "Mehrere Geräte", "Bitte pi_id angeben.")
            return
        coordinator = _get_coordinator(hass, entry, pi_id)
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
        pi_id = _resolve_pi_id(call)
        if pi_id is None:
            _notify(hass, "Mehrere Geräte", "Bitte pi_id angeben.")
            return
        coordinator = _get_coordinator(hass, entry, pi_id)
        try:
            installer = HausfunkInstaller(hass, _make_ssh(coordinator.pi_config), coordinator.config)
            message = await installer.update(coordinator.pi_config.get(CONF_SUDO_PASSWORD))
            _LOGGER.info(message)
            _clear_notification(hass)
        except (PiCommandError, OSError) as err:
            _LOGGER.exception("Pi-Update fehlgeschlagen")
            _notify(hass, "Pi-Update fehlgeschlagen", str(err), error=True)

    async def _uninstall_pi(call: ServiceCall):
        pi_id = _resolve_pi_id(call)
        if pi_id is None:
            _notify(hass, "Mehrere Geräte", "Bitte pi_id angeben.")
            return
        coordinator = _get_coordinator(hass, entry, pi_id)
        try:
            installer = HausfunkInstaller(hass, _make_ssh(coordinator.pi_config), coordinator.config)
            message = await installer.uninstall(coordinator.pi_config.get(CONF_SUDO_PASSWORD))
            _LOGGER.info(message)
            _clear_notification(hass)
        except (PiCommandError, OSError) as err:
            _LOGGER.exception("Pi-Deinstallation fehlgeschlagen")
            _notify(hass, "Pi-Deinstallation fehlgeschlagen", str(err), error=True)

    async def _restart_pi_go2rtc(call: ServiceCall):
        pi_id = _resolve_pi_id(call)
        if pi_id is None:
            _notify(hass, "Mehrere Geräte", "Bitte pi_id angeben.")
            return
        coordinator = _get_coordinator(hass, entry, pi_id)
        try:
            installer = HausfunkInstaller(hass, _make_ssh(coordinator.pi_config), coordinator.config)
            message = await installer.restart_service()
            _LOGGER.info(message)
        except PiCommandError as err:
            _LOGGER.exception("go2rtc-Neustart auf Pi fehlgeschlagen")
            _notify(hass, "go2rtc-Neustart auf Pi fehlgeschlagen", str(err), error=True)

    async def _register_stream(call: ServiceCall):
        pi_id = _resolve_pi_id(call)
        if pi_id is None:
            _notify(hass, "Mehrere Geräte", "Bitte pi_id angeben.")
            return
        coordinator = _get_coordinator(hass, entry, pi_id)
        ok = await coordinator.register_stream(persist=True, restart=True)
        await coordinator.async_request_refresh()
        if not ok:
            notify_restart_needed(hass)

    async def _remove_stream(call: ServiceCall):
        pi_id = _resolve_pi_id(call)
        if pi_id is None:
            _notify(hass, "Mehrere Geräte", "Bitte pi_id angeben.")
            return
        coordinator = _get_coordinator(hass, entry, pi_id)
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
