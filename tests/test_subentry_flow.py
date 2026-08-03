import unittest
from unittest.mock import MagicMock

import tests.hass_mock

from custom_components.hausfunk.config_flow import _has_pi_subentry
from custom_components.hausfunk.const import PI_SUBENTRY_TYPE


def _make_subentry(pi_host="192.168.178.11"):
    subentry = MagicMock()
    subentry.subentry_type = PI_SUBENTRY_TYPE
    subentry.data = {"host": pi_host}
    return subentry


class TestPiSubentryAbort(unittest.TestCase):
    def _entry_with(self, subentries):
        return MagicMock(subentries=subentries)

    def test_abort_when_pi_already_exists(self):
        self.assertTrue(_has_pi_subentry(self._entry_with({"sub1": _make_subentry()})))

    def test_proceeds_when_no_pi(self):
        self.assertFalse(_has_pi_subentry(self._entry_with({})))

    def test_ignores_other_subentry_types(self):
        other = MagicMock()
        other.subentry_type = "other"
        self.assertFalse(_has_pi_subentry(self._entry_with({"sub1": other})))


if __name__ == "__main__":
    unittest.main()

