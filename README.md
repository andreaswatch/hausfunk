# Hausfunk

![Hausfunk Icon](icon.png)

A Home Assistant integration for a **door intercom (Türsprechanlage)** built around
a Raspberry Pi Zero 2W (camera + microphone + speaker) and the go2rtc instance
that Home Assistant already runs.

The integration provisions the Pi once over SSH and then talks to it exclusively
over standard protocols (RTSP + go2rtc). No SSH in steady state.

> **Status:** Early development. Tested by the author against his own door
> intercom setup. Use at your own risk.

## Architecture

```
Pi Zero 2W ──(go2rtc, WebRTC)──▶ HA go2rtc ──(WebRTC)──▶ Browser / Lovelace
  ├─ rpicam-vid … -o -                     # H264 video (hardware)
  ├─ ffmpeg pulse → Opus → {output}        # microphone
  └─ ffmpeg alaw ← pipe:0 #backchannel=1   # speaker (talk)
```

- The Pi runs a **minimal go2rtc** — an RTSP server (`:8554`), plus go2rtc's
  default API (`:1984`) and WebRTC (`:8555`) endpoints used for signaling and
  the two-way audio relay. It stays lightweight (no WebRTC config tuning).
- Home Assistant's go2rtc pulls the stream via a **go2rtc-to-go2rtc WebRTC
  client link** (`webrtc:ws://<pi>:1984/api/ws?src=<name>`). Unlike a plain
  RTSP pull, this reliably exposes the Pi's RTSP backchannel to WebRTC
  clients (browser microphone → speaker) in both directions. The integration
  registers and persists this source in the HA go2rtc instance via its API.
- **Camera entity:** the integration exposes its own `camera.<stream_name>`
  entity whose `stream_source` points at the HA-local go2rtc RTSP server
  (`rtsp://127.0.0.1:18554/<name>`), so the browser reaches the Pi only via
  the HA go2rtc WebRTC proxy — never directly. No Generic Camera needed.
- **Two-way audio** works end to end: browser → HA go2rtc (WebRTC) → Pi
  go2rtc (WebRTC) → `exec` stdin → ffmpeg → speaker, and the mic in the
  opposite direction. For the talk-back button use the
  [advanced-camera-card](https://github.com/dermotduffy/advanced-camera-card)
  with the registered stream name and `backchannel`.

## Features

- **One-time SSH setup** through the integration: installs go2rtc, writes config +
  systemd unit, enables the service. Afterwards no SSH is used.
- **Everything configurable** via the config/options flow: Pi IP, username,
  password, sudo password, ports, stream name, resolution, fps, mic gain,
  go2rtc URL and version.
- **Self-contained Pi**: the Pi brings its own dependencies (go2rtc binary,
  `ffmpeg` if missing). One binary, one config, one systemd unit, one port.
- **Stream auto-registration**: the integration registers the stream in the
  HA go2rtc instance via its API and persists it to go2rtc's config.
- **Services** to re-run setup, update go2rtc, register/remove the stream.

## Prerequisites

- **Pi Zero 2W** (or similar) with Pi Camera, Google VoiceHAT (mic + speaker),
  Debian/Raspberry Pi OS (Bookworm), SSH enabled, user with sudo rights.
- **Home Assistant** (2024.11+) with a running **go2rtc** instance reachable at
  `http://localhost:1984` (e.g. the [go2rtc add-on](https://github.com/AlexxIT/go2rtc)
  or the HA go2rtc integration).
- go2rtc on the Pi must support the RTSP server backchannel and the go2rtc
  WebRTC signaling (`webrtc:ws://.../api/ws`) — **≥ v1.9.x**.

## Installation

### Method 1: HACS

1. Open Home Assistant and go to **HACS**.
2. Click the 3 dots in the top right and select **Custom repositories**.
3. Add the URL of this GitHub repository and select the category `Integration`.
4. Click **Install** on the `Hausfunk` integration.
5. Restart Home Assistant.

### Method 2: Manual

1. Download the latest release.
2. Copy the `custom_components/hausfunk` folder into your HA
   `config/custom_components` directory.
3. Restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & Services** and click **Add Integration**, search
   for "Hausfunk".
2. **Connect Pi:** Pi IP address, SSH port, SSH username, SSH password
   (and sudo password if different from the SSH password).
3. **Camera and stream:** stream name, RTSP port, Pi go2rtc API port
   (default `1984`, used for the `webrtc:ws://` relay), **stream mode**
   (`webrtc` = go2rtc-to-go2rtc WebRTC relay, recommended for reliable
   two-way audio; `rtsp` = direct RTSP pull), width, height, fps, mic gain.
4. **go2rtc:** URL of the HA go2rtc instance (e.g. `http://localhost:11984`
   with the HA add-on / built-in go2rtc), optional credentials, go2rtc
   version to install on the Pi, the HA go2rtc RTSP host and port
   (defaults `127.0.0.1` / `18554` — the add-on prefixes ports with `1`),
   plus the HA go2rtc **WebRTC port** (default `8555`) and optional WebRTC
   **candidates** (comma-separated, e.g. `mydomain:8555, STUN:stun.l.google.com:19302`).

   If you run a standalone go2rtc without the `1` prefix, set the RTSP port
   to `8554` instead.
5. **Install:** optionally set up the Pi right away (downloads go2rtc, writes
   config + service, enables it).

Afterwards the `camera.<stream_name>` entity appears on the Hausfunk Pi device
and the stream `<stream_name>` is registered in HA go2rtc (including the
`preload` entry and the WebRTC section so the two-way audio relay works).

## Services

| Service | Description |
|---------|-------------|
| `hausfunk.setup_pi` | (Re)installs or updates the Pi side over SSH |
| `hausfunk.update_pi` | Updates the go2rtc binary to the configured version |
| `hausfunk.uninstall_pi` | Stops/disables the Pi service, removes config + binary |
| `hausfunk.reboot_pi` | Reboots the Pi over SSH |
| `hausfunk.register_stream` | (Re)registers the stream in HA go2rtc (streams + preload + WebRTC) |
| `hausfunk.remove_stream` | Removes the stream from the HA go2rtc instance |

## Entities

| Entity | Description |
|--------|-------------|
| `camera.<stream_name>` | Camera stream proxied through HA go2rtc (WebRTC, backchannel) |
| `binary_sensor.hausfunk_pi_erreichbar` | Pi reachable (RTSP port probe) |
| `binary_sensor.hausfunk_stream_aktiv` | Stream registered in go2rtc |
| `switch.hausfunk_stream_registriert` | Toggle stream registration |
| `button.hausfunk_pi_einrichten` | Install / update the Pi over SSH |
| `button.hausfunk_pi_deinstallieren` | Stop + remove the Pi service, config and binary |
| `button.hausfunk_pi_neu_starten` | Reboot the Pi |
| `button.hausfunk_ha_go2rtc_einrichten` | Register stream + write HA go2rtc config |
| `button.hausfunk_ha_go2rtc_entfernen` | Remove the stream from HA go2rtc |

## Development

```bash
npm test            # run unit tests
npm run release     # bump patch, tag, push, create GitHub release
npm run release:minor
npm run release:major
```

## License

Provided "as is". Feel free to fork, adapt, and use it in your own setup.
