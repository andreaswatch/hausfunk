import unittest
from unittest.mock import AsyncMock, MagicMock

import tests.hass_mock

from custom_components.hausfunk.pi.installer import HausfunkInstaller

CONFIG = {
    "pi_host": "192.168.178.11",
    "pi_port": 22,
    "pi_username": "pi",
    "pi_password": "secret",
    "rtsp_port": 8554,
    "stream_name": "tuer",
    "width": 320,
    "height": 240,
    "fps": 10,
    "audio_gain": 2.0,
    "go2rtc_version": "v1.9.14",
}


def _installer():
    installer = HausfunkInstaller(hass=MagicMock(), ssh=MagicMock(), config=CONFIG)
    installer.ssh.run = AsyncMock(return_value=(0, "", ""))
    installer.ssh.connect = AsyncMock()
    installer.ssh.close = AsyncMock()
    installer._detect_home = AsyncMock()
    installer._home_dir = "/home/pi"
    installer._config_path = "/home/pi/hausfunk/go2rtc.yaml"
    installer._binary_path = "/home/pi/hausfunk/go2rtc"
    return installer


class TestInstallerUninstall(unittest.IsolatedAsyncioTestCase):
    async def test_uninstall_removes_service_config_binary(self):
        installer = _installer()
        message = await installer.uninstall("sudo-pass")
        self.assertIn("deinstalliert", message)
        commands = [c.args[0] for c in installer.ssh.run.await_args_list]
        joined = "\n".join(commands)
        self.assertIn("systemctl --user disable --now hausfunk-pi", joined)
        self.assertIn("go2rtc.yaml", joined)
        self.assertIn("/home/pi/hausfunk/go2rtc", joined)
        self.assertIn(".service", joined)

    async def test_reboot_uses_sudo(self):
        installer = _installer()
        installer._sudo = AsyncMock(return_value=(0, "", ""))
        message = await installer.reboot("sudo-pass")
        self.assertIn("Reboot", message)
        installer._sudo.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
