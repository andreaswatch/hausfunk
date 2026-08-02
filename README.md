# Intercom — Pi Zero 2W + go2rtc on Server

**Architecture:** Pi Zero 2W (192.168.178.11) handles only camera+audio capture.
go2rtc runs on the faster server (192.168.178.99) and provides WebRTC+backchannel.

```
Browser (WebRTC) ────▶ FRITZBox ──▶ NPM ──▶ Server go2rtc (:1984/:8555)
                                                 │
                    ┌────────────────────────────┤
                    │ raw H264 pipe              │ RTSP push (opus)
                    │ backchannel (alaw TCP:5555)│
                    ▼                            ▼
                 ┌─────────────────────────────────┐
                 │  Pi Zero 2W (192.168.178.11)    │
                 │  rpicam + PulseAudio            │
                 └─────────────────────────────────┘
```

## Prerequisites

- **Pi Zero 2W** with Pi Camera, Google VoiceHAT (mic+speaker), Debian Bookworm
- **Server** running Fedora 39+ x86_64 (or Docker), go2rtc runs natively
- **Nginx Proxy Manager** for HTTPS (on the server, ports 80/443)
- **FRITZBox** port-forward 8555 UDP for WebRTC
- **sshpass** on the server for SSH to Pi (`dnf install -y sshpass`, Pi has it via `apt`)
- **socat** on the Pi for the backchannel receiver (`apt install -y socat`)

## Step 1 — Set up the Pi Zero 2W

```bash
# === 1.1 Install dependencies ===
sudo apt update && sudo apt install -y socat

# === 1.2 Copy Pi scripts to /opt ===
sudo cp pi/rpicam-stream.sh /opt/ && sudo chmod +x /opt/rpicam-stream.sh
sudo cp pi/audio-push.sh    /opt/ && sudo chmod +x /opt/audio-push.sh
sudo cp pi/bc-play.sh       /opt/ && sudo chmod +x /opt/bc-play.sh

# === 1.3 Backchannel receiver (TCP:5555 -> ffmpeg -> speaker) ===
sudo cp pi/bc-receiver.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bc-receiver

# === 1.4 PulseAudio volumes ===
mkdir -p ~/.config/pulse
cp pi/default.pa ~/.config/pulse/default.pa
systemctl --user restart pulseaudio
```

**Verify:** `systemctl is-active bc-receiver` → `active`  
**Verify:** `ss -tlnp | grep 5555` → `LISTEN`

## Step 2 — Set up the Server

```bash
# === 2.1 Download go2rtc (latest release) ===
sudo curl -sL -o /opt/go2rtc \
  https://github.com/AlexxIT/go2rtc/releases/download/v1.9.14/go2rtc_linux_amd64
sudo chmod +x /opt/go2rtc

# === 2.2 go2rtc configuration ===
sudo cp server/go2rtc.yaml /opt/go2rtc.yaml
```

Edit the server IP in `go2rtc.yaml` if needed (line `192.168.178.99` → your server IP).

```bash
# === 2.3 Server scripts (SSH wrappers to Pi) ===
sudo cp server/src-video.sh       /opt/ && sudo chmod +x /opt/src-video.sh
sudo cp server/src-audio.sh       /opt/ && sudo chmod +x /opt/src-audio.sh
sudo cp server/src-backchannel.sh /opt/ && sudo chmod +x /opt/src-backchannel.sh
```

**IMPORTANT:** Replace `PASSWORD` in all three `src-*.sh` scripts with your Pi password:
```
exec sshpass -p 'YOUR_PI_PASSWORD' ssh ...
```

```bash
# === 2.4 go2rtc systemd service ===
sudo cp server/go2rtc.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now go2rtc

# === 2.5 Firewall (if active) ===
sudo firewall-cmd --add-port=1984/tcp --add-port=8554/tcp \
  --add-port=8555/tcp --add-port=8555/udp --permanent
sudo firewall-cmd --reload
```

**Verify:** `systemctl is-active go2rtc` → `active`  
**Verify:** `curl -s http://localhost:1984/api/streams | python3 -m json.tool | grep tuerkamera` → should show the stream

## Step 3 — Network

### 3.1 Nginx Proxy Manager (http://server:81)

Proxy Host for `sprechanlage.moers.webredirect.org`:
- **Forward:** `http://192.168.178.99:1984`  *(was: 192.168.178.11:1984)*
- ✅ SSL enforced (Let's Encrypt)
- ✅ WebSocket support
- ✅ HTTP/2
- HSTS enabled, `proxy_buffering off`, etc.

### 3.2 FRITZBox (http://fritz.box)

Port-forwarding `go2rtc-webrtc`:
- **Internal host:** `192.168.178.99` *(was: 192.168.178.11)*
- Protocol: TCP + UDP, port 8555

## Step 4 — Test

Open in browser:

```
https://sprechanlage.moers.webredirect.org/webrtc.html?src=tuerkamera&media=video+audio+microphone
```

## Data Flow

```
Video:  rpicam ──raw h264──▶ SSH ──▶ Server go2rtc ──WebRTC──▶ Browser
Audio:  Pulse ──ffmpeg/opus──▶ RTSP push ──▶ Server go2rtc ──WebRTC──▶ Browser
Talk:   Browser ──WebRTC──▶ Server go2rtc ──SSH/socat──▶ TCP:5555 ──▶ ffmpeg ──▶ Pulse ▶ Speaker
```

## Troubleshooting

| Problem | Check |
|---------|-------|
| No video/audio | `ssh andreas@192.168.178.11 'ps aux \| grep rpicam'` — is rpicam-vid running? |
| No audio Pi→Browser | `sudo journalctl -u go2rtc -f` on server — errors from audio-push.sh? |
| No audio Browser→Pi | `ss -tn \| grep 5555` on Pi — TCP connection from server? |
| Backchannel silent | `sudo journalctl -u bc-receiver -f` on Pi — socat/ffmpeg errors? |
| PULSE_SERVER errors | `sudo journalctl -u bc-receiver` — environment variables set? |
