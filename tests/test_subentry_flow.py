import unittest

import tests.hass_mock

from custom_components.hausfunk.const import PI_SUBENTRY_TYPE


class TestSubentryFlow(unittest.TestCase):
    def test_pi_subentry_type_constant(self):
        self.assertEqual(PI_SUBENTRY_TYPE, "pi")


if __name__ == "__main__":
    unittest.main()
