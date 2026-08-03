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

### 1. Add the integration (host-level, once)

Go to **Settings → Devices & Services** → **Add Integration**, search for
"Hausfunk". The config flow only asks for **go2rtc (Home Assistant)** settings
and does **not** create a device. Only **one** hub entry is allowed (like
ESPHome); Pis are added as devices inside it.

- The integration tries to **auto-detect** the HA go2rtc instance (known local
  endpoints) and the HA host's LAN IP. Detected values are pre-filled; adjust
  if needed: go2rtc URL, optional credentials, go2rtc version, **HA go2rtc LAN
  host** (used for the WebRTC candidate), RTSP port, WebRTC port.

  The **HA go2rtc RTSP host** is also used to derive the WebRTC candidate:
  set it to the LAN address of the go2rtc instance (e.g. `192.168.178.21`)
  so the browser can open the media connection. If go2rtc runs inside a VM,
  this must be the VM's IP, **not** the hypervisor's. You can override the
  candidates manually via **WebRTC candidates** (comma-separated, e.g.
  `mydomain:8555, 192.168.178.21:8555, STUN:stun.l.google.com:19302`).

  If you run a standalone go2rtc without the `1` prefix, set the RTSP port
  to `8554` instead.

### 2. Add Pi device(s) (per device)

Only the Pis appear as devices; the HA go2rtc host itself is not a device.
Use the **"Add Pi device"** button on the Hausfunk integration row to add one
or more Pis (like ESPHome / BrowserMod / Landroid Cloud: one hub entry with
multiple devices). The flow asks for the **Pi-specific** settings:

| Setting | Description |
|---------|-------------|
| Pi IP / SSH access | Pi IP, SSH port, username, password, sudo password |
| Stream name | Name of the stream in go2rtc (default `tuer`) |
| Pi RTSP port | RTSP server port on the Pi (default `8554`) |
| Pi go2rtc API port | go2rtc API port on the Pi (default `1984`) |
| Stream mode | `webrtc` (relay, recommended) or `rtsp` (direct pull) |
| Width / Height / FPS | Camera resolution and frame rate |
| Microphone gain | Mic amplification on the Pi |
| Set up the Pi now | Install/configure go2rtc on the Pi right away |

Afterwards the `camera.<stream_name>` entity appears on the Hausfunk Pi device
and the stream `<stream_name>` is registered in HA go2rtc (including the
`preload` entry and the WebRTC section so the two-way audio relay works).
You can add multiple Pis to one go2rtc host.

### Edit settings

- **Host (go2rtc):** Integration → Options (URL, version, LAN host, ports,
  candidates).
- **Pi device:** the pencil icon on the Pi (stream name, ports, mode,
  resolution, fps, mic gain); Remove via the trash icon.

## Services

| Service | Description |
|---------|-------------|
| `hausfunk.setup_pi` | (Re)installs or updates the Pi side over SSH |
| `hausfunk.update_pi` | Updates the go2rtc binary to the configured version |
| `hausfunk.uninstall_pi` | Stops/disables the Pi service, removes config + binary |
| `hausfunk.restart_pi_go2rtc` | Restarts only the go2rtc service on the Pi (no device reboot) |
| `hausfunk.register_stream` | (Re)registers the stream in HA go2rtc (streams + preload + WebRTC) |
| `hausfunk.remove_stream` | Removes the stream from the HA go2rtc instance |

## Entities

| Entity | Description |
|--------|-------------|
| `camera.<stream_name>` | Camera stream proxied through HA go2rtc (WebRTC, backchannel) |
| `binary_sensor.<pi>_erreichbar` | Pi reachable (RTSP port probe) |
| `binary_sensor.<pi>_stream_aktiv` | Stream registered in go2rtc |
| `switch.<pi>_stream_registriert` | Toggle stream registration |
| `button.<pi>_pi_einrichten` | Install / update the Pi over SSH |
| `button.<pi>_pi_deinstallieren` | Stop + remove the Pi service, config and binary |
| `button.<pi>_go2rtc_auf_pi_neu_starten` | Restart the go2rtc service on the Pi |
| `button.<pi>_ha_go2rtc_einrichten` | Register stream + write HA go2rtc config |
| `button.<pi>_ha_go2rtc_entfernen` | Remove the stream from HA go2rtc |

## Development

```bash
npm test            # run unit tests
npm run release     # bump patch, tag, push, create GitHub release
npm run release:minor
npm run release:major
```

## License

Provided "as is". Feel free to fork, adapt, and use it in your own setup.
