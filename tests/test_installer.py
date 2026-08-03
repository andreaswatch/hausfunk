import unittest
from unittest.mock import AsyncMock, MagicMock

import tests.hass_mock

from custom_components.hausfunk.pi.installer import HausfunkInstaller
from custom_components.hausfunk.pi.ssh import PiCommandError

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

    async def test_restart_service_restarts_go2rtc_only(self):
        installer = _installer()
        # is-active check must report "active" for a successful restart
        calls = []

        async def fake_run(cmd, input_data=None, timeout=None):
            calls.append(cmd)
            if "is-active" in cmd:
                return (0, "active", "")
            return (0, "", "")
        installer.ssh.run = fake_run
        message = await installer.restart_service()
        self.assertIn("go2rtc", message)
        joined = "\n".join(calls)
        self.assertIn("systemctl --user restart hausfunk-pi", joined)
        self.assertNotIn("sudo", joined)
        self.assertNotIn("reboot", joined)

    async def test_restart_service_fails_when_inactive(self):
        installer = _installer()
        async def fake_run(cmd, input_data=None, timeout=None):
            return (0, "inactive", "")
        installer.ssh.run = fake_run
        with self.assertRaises(PiCommandError):
            await installer.restart_service()


class TestInstallerDownload(unittest.IsolatedAsyncioTestCase):
    async def test_download_adds_v_prefix_to_version(self):
        config = dict(CONFIG)
        config["go2rtc_version"] = "1.9.14"  # stored without "v" prefix
        installer = HausfunkInstaller(hass=MagicMock(), ssh=MagicMock(), config=config)
        installer.ssh.run = AsyncMock(return_value=(0, "", ""))
        installer.ssh.connect = AsyncMock()
        installer._ensure_dir = AsyncMock()
        installer._binary_path = "/home/pi/hausfunk/go2rtc"

        # Capture the download URL used in the curl command
        async def fake_run(cmd, input_data=None, timeout=None):
            calls.append(cmd)
            if cmd.startswith("test -s"):
                return (0, "", "")
            return (0, "", "")
        calls = []
        installer.ssh.run = fake_run
        await installer._download_binary("arm")

        joined = "\n".join(calls)
        self.assertIn(
            "https://github.com/AlexxIT/go2rtc/releases/download/v1.9.14/go2rtc_linux_arm",
            joined,
        )

    async def test_download_keeps_existing_v_prefix(self):
        installer = _installer()  # CONFIG already has "v1.9.14"
        installer._ensure_dir = AsyncMock()
        calls = []

        async def fake_run(cmd, input_data=None, timeout=None):
            calls.append(cmd)
            if cmd.startswith("test -s"):
                return (0, "", "")
            return (0, "", "")
        installer.ssh.run = fake_run
        await installer._download_binary("arm")

        joined = "\n".join(calls)
        self.assertIn(
            "https://github.com/AlexxIT/go2rtc/releases/download/v1.9.14/go2rtc_linux_arm",
            joined,
        )


if __name__ == "__main__":
    unittest.main()
