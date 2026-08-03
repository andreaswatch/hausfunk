"""Hausfunk integration setup and services.

Architecture (HA 2024.12+):
- Each 'Hausfunk Sprechanlage' is a hub ConfigEntry holding the go2rtc settings.
- Each Pi device is a ConfigSubentry (type 'pi') of its parent hub entry.
- 'Gerät hinzufügen' creates a new hub entry.
- 'Pi hinzufügen' (shown on the hub device page) creates a Pi subentry.

hass.data[DOMAIN][entry_id] = {
    "go2rtc": Go2rtcClient,
    "coordinators": {subentry_id: HausfunkCoordinator},
    "pi_add_callbacks": list[callable],
}
"""

import logging

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr

from .const import (
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
from .go2rtc.client import Go2rtcClient
from .pi.installer import HausfunkInstaller
from .pi.ssh import PiCommandError, PiSSH

_LOGGER = logging.getLogger(__name__)

_NOTIFICATION_ID = "hausfunk_install"


# ---------------------------------------------------------------------------
# Entry setup / teardown
# ---------------------------------------------------------------------------


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Hausfunk Sprechanlage hub entry."""
    # Build the go2rtc client for this hub
    from .go2rtc.client import Go2rtcClient
    go2rtc_client = Go2rtcClient(
        url=entry.data.get("go2rtc_url", "http://localhost:11984"),
        username=entry.data.get("go2rtc_username"),
        password=entry.data.get("go2rtc_password"),
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "go2rtc": go2rtc_client,
        "coordinators": {},      # subentry_id -> HausfunkCoordinator
        "pi_add_callbacks": [],  # registered by each platform
        "subentry_ids": set(entry.subentries),
    }

    # HA has no lifecycle hook for runtime subentry changes. It only fires the
    # config entry update listeners, so reload the hub entry whenever its Pi
    # subentries are added or removed and the new device/entities show up
    # without a manual reload.
    entry.async_on_unload(entry.add_update_listener(_async_subentry_listener))

    # Bootstrap existing Pi subentries (those already stored in config_entries)
    for subentry in entry.subentries.values():
        await _async_setup_pi(hass, entry, subentry)

    # Forward platform setups so each platform can register its entity-add callback
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Hausfunk Sprechanlage hub entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, {})
        for coordinator in entry_data.get("coordinators", {}).values():
            await coordinator.async_close()
        client = entry_data.get("go2rtc")
        if client:
            await client.close()

        # Remove services only when there are no more hub entries
        if not hass.data.get(DOMAIN):
            for service in _SERVICE_NAMES:
                if hass.services.has_service(DOMAIN, service):
                    hass.services.async_remove(DOMAIN, service)
    return unload_ok


async def _async_subentry_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the hub entry when its Pi subentries change.

    Fired on every config entry update (options, data, subentries). Only reload
    when the set of Pi subentries actually changed, so unrelated updates such
    as option changes or stream-mode toggles do not restart the entry.
    """
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if entry_data is None:
        return
    current_ids = set(entry.subentries)
    if current_ids != entry_data.get("subentry_ids"):
        entry_data["subentry_ids"] = current_ids
        await hass.config_entries.async_reload(entry.entry_id)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _async_setup_pi(
    hass: HomeAssistant, entry: ConfigEntry, subentry
) -> None:
    """Create a coordinator for a Pi subentry and notify platforms."""
    go2rtc_config = dict(entry.data)
    pi_config = dict(subentry.data)
    pi_id = pi_config.get(CONF_PI_HOST)

    # Merge go2rtc config into pi_config so the coordinator has everything
    merged_config = {**go2rtc_config, **pi_config}

    subentry_id = getattr(subentry, "subentry_id", None)

    # Register/update the Pi device in device_registry linked to this subentry
    if subentry_id:
        dev_reg = dr.async_get(hass)
        dev_reg.async_get_or_create(
            config_entry_id=entry.entry_id,
            config_subentry_id=subentry_id,
            identifiers={(DOMAIN, pi_id)},
            manufacturer=NAME,
            model="Pi + go2rtc",
            name=f"Hausfunk Pi ({pi_id})",
        )

    coordinator = HausfunkCoordinator(
        hass, entry, go2rtc_config, pi_config, pi_id=pi_id, subentry_id=subentry_id
    )
    await coordinator.register_stream()
    await coordinator.async_config_entry_first_refresh()

    entry_data = hass.data.setdefault(DOMAIN, {}).setdefault(entry.entry_id, {
        "go2rtc": None,
        "coordinators": {},
        "pi_add_callbacks": [],
        "subentry_ids": set(entry.subentries),
    })
    entry_data["coordinators"][subentry.subentry_id] = coordinator

    # Notify any platform that has already registered a callback
    for callback in entry_data["pi_add_callbacks"]:
        callback(coordinator, subentry.subentry_id)


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

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


def _get_all_coordinators(hass: HomeAssistant) -> list[HausfunkCoordinator]:
    """Return all coordinators across all hub entries."""
    coordinators = []
    for entry_data in hass.data.get(DOMAIN, {}).values():
        if isinstance(entry_data, dict):
            coordinators.extend(entry_data.get("coordinators", {}).values())
    return coordinators


def _get_coordinator(
    hass: HomeAssistant, pi_id: str | None
) -> HausfunkCoordinator | None:
    coordinators = _get_all_coordinators(hass)
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
