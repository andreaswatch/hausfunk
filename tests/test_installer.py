import unittest
from unittest.mock import AsyncMock, MagicMock

import tests.hass_mock

from custom_components.hausfunk.const import (
    CONF_AUDIO_GAIN,
    CONF_FPS,
    CONF_GO2RTC_VERSION,
    CONF_HEIGHT,
    CONF_PI_GO2RTC_PORT,
    CONF_PI_HOST,
    CONF_PI_PASSWORD,
    CONF_PI_PORT,
    CONF_PI_USERNAME,
    CONF_RTSP_PORT,
    CONF_STREAM_MODE,
    CONF_STREAM_NAME,
    CONF_WIDTH,
    STREAM_MODE_RTSP,
    STREAM_MODE_WEBRTC,
)
from custom_components.hausfunk.pi.installer import HausfunkInstaller
from custom_components.hausfunk.pi.ssh import PiCommandError

CONFIG = {
    CONF_PI_HOST: "192.168.178.11",
    CONF_PI_PORT: 22,
    CONF_PI_USERNAME: "pi",
    CONF_PI_PASSWORD: "secret",
    CONF_PI_GO2RTC_PORT: 1984,
    CONF_RTSP_PORT: 8554,
    CONF_STREAM_NAME: "tuer",
    CONF_STREAM_MODE: STREAM_MODE_WEBRTC,
    CONF_WIDTH: 320,
    CONF_HEIGHT: 240,
    CONF_FPS: 10,
    CONF_AUDIO_GAIN: 2.0,
    CONF_GO2RTC_VERSION: "v1.9.14",
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


class TestInstallerConfig(unittest.IsolatedAsyncioTestCase):
    async def test_write_config_webrtc_mode_includes_webrtc_section(self):
        installer = _installer()
        installer.ssh.write_file = AsyncMock()
        installer.ssh.run = AsyncMock(return_value=(0, "", ""))
        await installer._write_config()

        content = installer.ssh.write_file.call_args.args[1]
        self.assertIn('api:\n  listen: ":1984"', content)
        self.assertIn('rtsp:\n  listen: ":8554"', content)
        self.assertIn('webrtc:\n  listen: ":8555"', content)
        self.assertIn("candidates:\n    - 192.168.178.11:8555", content)
        self.assertNotIn("{{", content)

    async def test_write_config_rtsp_mode_omits_webrtc_section(self):
        config = dict(CONFIG)
        config[CONF_STREAM_MODE] = STREAM_MODE_RTSP
        installer = _installer()
        installer.config = config
        installer.ssh.write_file = AsyncMock()
        installer.ssh.run = AsyncMock(return_value=(0, "", ""))
        await installer._write_config()

        content = installer.ssh.write_file.call_args.args[1]
        self.assertIn('rtsp:\n  listen: ":8554"', content)
        self.assertNotIn("webrtc:", content)
        self.assertNotIn("{{", content)


if __name__ == "__main__":
    unittest.main()
