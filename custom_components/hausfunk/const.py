"""Constants for the Hausfunk integration."""

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

DOMAIN = "hausfunk"
NAME = "Hausfunk"

# subentry type for Pi devices (provides the native "+ Add Pi" button)
PI_SUBENTRY_TYPE = "pi"

PLATFORMS = ["binary_sensor", "switch", "camera", "button", "select"]

# Defaults
DEFAULT_SSH_PORT = 22
DEFAULT_RTSP_PORT = 8554
DEFAULT_PI_GO2RTC_PORT = 1984
DEFAULT_PI_WEBRTC_PORT = 8555
DEFAULT_STREAM_NAME = "tuer"
DEFAULT_GO2RTC_URL = "http://localhost:11984"
DEFAULT_GO2RTC_VERSION = "v1.9.14"
# HA's built-in / add-on go2rtc prefixes ports with 1 by default
DEFAULT_GO2RTC_HOST = "127.0.0.1"
DEFAULT_GO2RTC_RTSP_PORT = 18554
DEFAULT_GO2RTC_WEBRTC_PORT = 8555
DEFAULT_GO2RTC_CANDIDATES = ""
DEFAULT_STREAM_MODE = "webrtc"

# Stream modes for the HA go2rtc source (how it pulls the Pi stream)
STREAM_MODE_WEBRTC = "webrtc"  # webrtc:ws://.../api/ws?src=... (two-way audio via relay)
STREAM_MODE_RTSP = "rtsp"  # rtsp://.../<name>#backchannel=1 (direct RTSP pull)
STREAM_MODE_BOTH = "both"  # both sources registered, WebRTC primary with RTSP fallback

# Camera defaults
DEFAULT_WIDTH = 320
DEFAULT_HEIGHT = 240
DEFAULT_FPS = 10
DEFAULT_AUDIO_GAIN = 2.0

# Pi-side paths
PI_SERVICE_NAME = "hausfunk-pi"
PI_BINARY = "go2rtc"
PI_CONFIG = "go2rtc.yaml"
PI_SUBDIR = "hausfunk"  # under user's home
PI_USER_SERVICE_DIR = ".config/systemd/user"  # under user's home

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
CONF_PI_GO2RTC_PORT = "pi_go2rtc_port"
CONF_STREAM_NAME = "stream_name"
CONF_WIDTH = "width"
CONF_HEIGHT = "height"
CONF_FPS = "fps"
CONF_AUDIO_GAIN = "audio_gain"
CONF_GO2RTC_URL = "go2rtc_url"
CONF_GO2RTC_USERNAME = "go2rtc_username"
CONF_GO2RTC_PASSWORD = "go2rtc_password"
CONF_GO2RTC_VERSION = "go2rtc_version"
CONF_GO2RTC_HOST = "go2rtc_host"
CONF_GO2RTC_RTSP_PORT = "go2rtc_rtsp_port"
CONF_GO2RTC_WEBRTC_PORT = "go2rtc_webrtc_port"
CONF_GO2RTC_CANDIDATES = "go2rtc_candidates"
CONF_STREAM_MODE = "stream_mode"
CONF_INSTALL_NOW = "install_now"
