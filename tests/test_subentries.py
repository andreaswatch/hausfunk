import unittest
from unittest.mock import AsyncMock, MagicMock

import tests.hass_mock

from custom_components.hausfunk.__init__ import DOMAIN, _async_subentry_listener


class TestSubentryListener(unittest.IsolatedAsyncioTestCase):
    """HA has no lifecycle hook for runtime subentry changes; it only fires
    the config entry update listeners. Verify the listener reloads the hub
    entry only when the Pi subentry set actually changed."""

    def _make(self, stored, current):
        hass = MagicMock()
        hass.data = {DOMAIN: {"entry_id": {"subentry_ids": set(stored)}}}
        hass.config_entries = MagicMock()
        hass.config_entries.async_reload = AsyncMock()
        entry = MagicMock()
        entry.entry_id = "entry_id"
        entry.subentries = {sid: object() for sid in current}
        return hass, entry

    async def test_reloads_when_subentry_added(self):
        hass, entry = self._make(stored=["a"], current=["a", "b"])
        await _async_subentry_listener(hass, entry)
        hass.config_entries.async_reload.assert_awaited_once_with("entry_id")

    async def test_reloads_when_subentry_removed(self):
        hass, entry = self._make(stored=["a", "b"], current=["a"])
        await _async_subentry_listener(hass, entry)
        hass.config_entries.async_reload.assert_awaited_once_with("entry_id")

    async def test_no_reload_when_subentries_unchanged(self):
        hass, entry = self._make(stored=["a", "b"], current=["a", "b"])
        await _async_subentry_listener(hass, entry)
        hass.config_entries.async_reload.assert_not_awaited()

    async def test_reloads_only_once_for_a_given_change(self):
        hass, entry = self._make(stored=["a"], current=["a", "b"])
        await _async_subentry_listener(hass, entry)
        await _async_subentry_listener(hass, entry)
        hass.config_entries.async_reload.assert_awaited_once_with("entry_id")

    async def test_noop_when_entry_not_loaded(self):
        hass = MagicMock()
        hass.data = {DOMAIN: {}}
        hass.config_entries = MagicMock()
        hass.config_entries.async_reload = AsyncMock()
        entry = MagicMock()
        entry.entry_id = "other"
        entry.subentries = {"a": object()}
        await _async_subentry_listener(hass, entry)
        hass.config_entries.async_reload.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
