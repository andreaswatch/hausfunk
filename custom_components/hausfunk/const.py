"""Constants for the Hausfunk integration."""

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

DOMAIN = "hausfunk"
NAME = "Hausfunk"

PLATFORMS = ["binary_sensor", "switch"]

# Defaults
DEFAULT_SSH_PORT = 22
DEFAULT_RTSP_PORT = 8554
DEFAULT_STREAM_NAME = "tuer"
DEFAULT_GO2RTC_URL = "http://localhost:1984"
DEFAULT_GO2RTC_VERSION = "v1.9.13"

# Camera defaults
DEFAULT_WIDTH = 320
DEFAULT_HEIGHT = 240
DEFAULT_FPS = 10
DEFAULT_AUDIO_GAIN = 2.0

# Pi-side paths
PI_INSTALL_DIR = "/opt/hausfunk"
PI_SERVICE_NAME = "hausfunk-pi"
PI_BINARY = "go2rtc"
PI_CONFIG = "go2rtc.yaml"

GO2RTC_RELEASE_URL = (
    "https://github.com/AlexxIT/go2rtc/releases/download/{version}/go2rtc_linux_{arch}"
)

# Config entry keys
CONF_PI_HOST = CONF_HOST
CONF_PI_PORT = CONF_PORT
CONF_PI_USERNAME = CONF_USERNAME
CONF_PI_PASSWORD = CONF_PASSWORD
CONF_SUDO_PASSWORD = "sudo_password"
CONF_SSH_KEY = "ssh_key"
CONF_RTSP_PORT = "rtsp_port"
CONF_STREAM_NAME = "stream_name"
CONF_WIDTH = "width"
CONF_HEIGHT = "height"
CONF_FPS = "fps"
CONF_AUDIO_GAIN = "audio_gain"
CONF_GO2RTC_URL = "go2rtc_url"
CONF_GO2RTC_USERNAME = "go2rtc_username"
CONF_GO2RTC_PASSWORD = "go2rtc_password"
CONF_GO2RTC_VERSION = "go2rtc_version"
CONF_INSTALL_NOW = "install_now"
