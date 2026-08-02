# Gegensprechanlage — Pi Zero 2W + go2rtc auf Server

**Architektur:** Der Pi Zero 2W (192.168.178.11) macht nur Kamera+Audio-Capture.  
go2rtc läuft auf dem stärkeren Server (192.168.178.99) und macht WebRTC+Backchannel.

```
Browser (WebRTC) ────▶ FRITZBox ──▶ NPM ──▶ Server go2rtc (:1984/:8555)
                                                 │
                    ┌────────────────────────────┤
                    │ raw H264 pipe              │ RTSP push (opus)
                    │ backchannel (alaw TCP:5555)│
                    ▼                            ▼
                 ┌─────────────────────────────────┐
                 │  Pi Zero 2W (192.168.178.11)    │
                 │  rpicam + PulseAudio             │
                 └─────────────────────────────────┘
```

## Voraussetzungen

- **Pi Zero 2W** mit Pi-Kamera, Google VoiceHAT (Mikrofon+Lautsprecher), Debian Bookworm
- **Server** mit Fedora 39+ x86_64 (oder Docker), go2rtc läuft nativ
- **Nginx Proxy Manager** für HTTPS (auf dem Server, Port 80/443)
- **FRITZBox** Port-Freigabe 8555 UDP für WebRTC
- **sshpass** auf dem Server für SSH-zum-Pi (`dnf install -y sshpass`, Pi hat es via `apt`)
- **socat** auf dem Pi für den Backchannel-Empfänger (`apt install -y socat`)

## Schritt 1 — Pi Zero 2W einrichten

```bash
# === 1.1 Software installieren ===
sudo apt update && sudo apt install -y socat

# === 1.2 Pi-Scripts nach /opt kopieren ===
sudo cp pi/rpicam-stream.sh /opt/ && sudo chmod +x /opt/rpicam-stream.sh
sudo cp pi/audio-push.sh    /opt/ && sudo chmod +x /opt/audio-push.sh
sudo cp pi/bc-play.sh       /opt/ && sudo chmod +x /opt/bc-play.sh

# === 1.3 Backchannel-Empfänger (TCP:5555 → ffmpeg → Lautsprecher) ===
sudo cp pi/bc-receiver.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bc-receiver

# === 1.4 PulseAudio-Lautstärken ===
mkdir -p ~/.config/pulse
cp pi/default.pa ~/.config/pulse/default.pa
systemctl --user restart pulseaudio
```

**Prüfen:** `systemctl is-active bc-receiver` → `active`  
**Prüfen:** `ss -tlnp | grep 5555` → `LISTEN`

## Schritt 2 — Server einrichten

```bash
# === 2.1 go2rtc herunterladen (aktuelle Version) ===
sudo curl -sL -o /opt/go2rtc \
  https://github.com/AlexxIT/go2rtc/releases/download/v1.9.14/go2rtc_linux_amd64
sudo chmod +x /opt/go2rtc

# === 2.2 go2rtc-Konfiguration ===
sudo cp server/go2rtc.yaml /opt/go2rtc.yaml
```

Passe die Server-IP in `go2rtc.yaml` an (Zeile `192.168.178.99` → deine Server-IP).

```bash
# === 2.3 Server-Scripts (SSH-Wrapper zum Pi) ===
sudo cp server/src-video.sh       /opt/ && sudo chmod +x /opt/src-video.sh
sudo cp server/src-audio.sh       /opt/ && sudo chmod +x /opt/src-audio.sh
sudo cp server/src-backchannel.sh /opt/ && sudo chmod +x /opt/src-backchannel.sh
```

**WICHTIG:** Passe das Pi-Passwort in allen drei `src-*.sh`-Dateien an:
```
exec sshpass -p 'DEIN_PI_PASSWORT' ssh ...
```

```bash
# === 2.4 go2rtc systemd Service ===
sudo cp server/go2rtc.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now go2rtc

# === 2.5 Firewall (falls aktiv) ===
sudo firewall-cmd --add-port=1984/tcp --add-port=8554/tcp \
  --add-port=8555/tcp --add-port=8555/udp --permanent
sudo firewall-cmd --reload
```

**Prüfen:** `systemctl is-active go2rtc` → `active`  
**Prüfen:** `curl -s http://localhost:1984/api/streams | python3 -m json.tool | grep tuerkamera` → sollte den Stream zeigen

## Schritt 3 — Netzwerk

### 3.1 Nginx Proxy Manager (http://server:81)

Proxy Host für `sprechanlage.moers.webredirect.org`:
- **Forward:** `http://192.168.178.99:1984`  *(vorher: 192.168.178.11:1984)*
- ✅ SSL erzwungen (Let's Encrypt)
- ✅ WebSocket Support
- ✅ HTTP/2
- HSTS, buffering off wie bisher

### 3.2 FRITZBox (http://fritz.box)

Port-Freigabe `go2rtc-webrtc`:
- **Interner Host:** `192.168.178.99` *(vorher: 192.168.178.11)*
- Protokoll: TCP + UDP, Port 8555

## Schritt 4 — Testen

URL im Browser öffnen:

```
https://sprechanlage.moers.webredirect.org/webrtc.html?src=tuerkamera&media=video+audio+microphone
```

## Troubleshooting

| Problem | Prüfen |
|---------|--------|
| Kein Bild/kein Ton | `ssh andreas@192.168.178.11 'ps aux \| grep rpicam'` — läuft rpicam-vid? |
| Kein Ton Pi→Browser | `sudo journalctl -u go2rtc -f` auf Server — Fehler bei audio-push.sh? |
| Kein Ton Browser→Pi | `ss -tn \| grep 5555` auf Pi — TCP-Verbindung vom Server? |
| Backchannel kehrt stumm | `sudo journalctl -u bc-receiver -f` auf Pi — socat/ffmpeg-Fehler? |
| PULSE_SERVER-Fehler | `sudo journalctl -u bc-receiver` — Environment-Variablen gesetzt? |

## Datenfluss

```
Video:  rpicam ──raw h264──▶ SSH ──▶ Server go2rtc ──WebRTC──▶ Browser
Audio:  Pulse ──ffmpeg/opus──▶ RTSP-push ──▶ Server go2rtc ──WebRTC──▶ Browser
Talk:   Browser ──WebRTC──▶ Server go2rtc ──SSH/socat──▶ TCP:5555 ──▶ ffmpeg ──▶ Pulse ▶ Lautsprecher
```
