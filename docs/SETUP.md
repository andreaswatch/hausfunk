# Hausfunk Pi - Vollständige Wiederherstellung

Diese Anleitung beschreibt die komplette Einrichtung eines Hausfunk Pi Zero 2W von einem blanken Raspberry Pi OS Image.

## Übersicht

**Hardware:**
- Raspberry Pi Zero 2W
- Pi Camera Module
- Google VoiceHAT Soundcard (INMP441 Mikrofon + MAX98357A Verstärker)

**Software:**
- Raspberry Pi OS Lite (Bookworm, 64-bit)
- go2rtc (RTSP Server)
- PulseAudio
- ffmpeg
- I2S Audio Treiber

---

## 1. Betriebssystem installieren

### 1.1 Raspberry Pi OS flashen

1. [Raspberry Pi Imager](https://www.raspberrypi.com/software/) herunterladen
2. Raspberry Pi OS Lite (64-bit, Bookworm) auswählen
3. SD-Karte flashen

### 1.2 Erster Boot

Nach dem ersten Boot:
```bash
sudo raspi-config
```
- **System Options → S1 Expand App** (Dateisystem erweitern)
- **Interface Options → P1 Camera** (Kamera aktivieren)
- **Interface Options → P4 I2C** (I2C aktivieren)
- **Advanced Options → A1 Memory Split** (mindestens 128MB für GPU)
- Reboot

### 1.3 System aktualisieren

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y git build-essential cmake screen pulseaudio ffmpeg
```

---

## 2. I2S Audio konfigurieren

### 2.1 config.txt bearbeiten

```bash
sudo nano /boot/firmware/config.txt
```

**Änderungen:**
```diff
- dtoverlay=vc4-kms-v3d
- max_framebuffers=2
- dtparam=audio=on
+ dtoverlay=i2s-mmap
+ dtoverlay=googlevoicehat-soundcard
```

**Wichtig:** Die Zeilen `dtoverlay=vc4-kms-v3d`, `max_framebuffers=2` und `dtparam=audio=on` müssen **auskommentiert** oder entfernt werden!

### 2.2 Audio-Treiber laden

**Option 1: Über Cronjob (empfohlen)**

Der Cronjob lädt den Treiber spät im Bootprozess, damit PulseAudio Clicks/Pops reduzieren kann.

```bash
mkdir -p ~/autostart
nano ~/autostart/i2s_audio.sh
```

Inhalt:
```bash
#!/bin/bash
sudo dtoverlay googlevoicehat-soundcard
```

Rechte setzen:
```bash
chmod +x ~/autostart/i2s_audio.sh
```

Crontab bearbeiten:
```bash
crontab -e
```

Zeile hinzufügen:
```
@reboot /home/andreas/autostart/i2s_audio.sh
```

**Option 2: Direkt in config.txt**

Falls Option 1 nicht funktioniert, kann der Treiber auch direkt in `/boot/firmware/config.txt` geladen werden:
```
dtoverlay=googlevoicehat-soundcard
```

### 2.3 Audio testen

Nach einem Reboot:
```bash
# Audio-Geräte anzeigen
pactl list short sinks
pactl list short sources

# Testton abspielen
speaker-test -t sine -f 440 -c 1 -l 1

# Mikrofon testen
arecord -d 5 test.wav
aplay test.wav
```

**Troubleshooting:**
- Falls Audio mit halber Geschwindigkeit abgespielt wird: `pigpiod` deinstallieren!
- Logs prüfen: `sudo vcdbg log msg |& grep -v googlevoicehat-soundcard`

---

## 3. Kamera konfigurieren

### 3.1 Kamera aktivieren

```bash
sudo raspi-config
```
- **Interface Options → P1 Camera** → Enable

### 3.2 Kamera testen

```bash
# Kamera-Informationen anzeigen
rpicam-hello

# Testbild aufnehmen
rpicam-jpeg -o test.jpg

# Testvideo aufnehmen (5 Sekunden)
rpicam-vid -t 5000 -o test.h264
```

---

## 4. go2rtc installieren und konfigurieren

### 4.1 Verzeichnis erstellen

```bash
mkdir -p ~/hausfunk
cd ~/hausfunk
```

### 4.2 go2rtc Binary herunterladen

```bash
# Architektur prüfen
uname -m

# go2rtc herunterladen (Beispiel für arm64)
curl -fsSL -o go2rtc https://github.com/AlexxIT/go2rtc/releases/download/v1.9.4/go2rtc_linux_arm64
chmod +x go2rtc
```

**Verfügbare Architekturen:**
- `aarch64` → `arm64`
- `armv7l` → `arm`
- `armv6l` → `armv6`
- `x86_64` → `amd64`

### 4.3 Konfiguration erstellen

```bash
nano ~/hausfunk/go2rtc.yaml
```

**Minimale Konfiguration:**
```yaml
rtsp:
  listen: ":8554"

streams:
  sprechanlage:
    - exec:rpicam-vid -t 0 --inline --width 1280 --height 720 --framerate 25 --profile baseline -o -#video=h264#exec=always
    - exec:ffmpeg -hide_banner -loglevel error -fflags nobuffer -flags low_delay -f pulse -ac 1 -i default -c:a libopus -b:a 32k -af volume=2.0 -rtsp_transport tcp -f rtsp {output}#exec=always
    - exec:ffmpeg -hide_banner -loglevel error -fflags nobuffer -probesize 32 -analyzeduration 0 -f alaw -ar 8000 -ac 1 -i pipe:0 -f pulse default#backchannel=1#audio=alaw/8000

preload:
  sprechanlage: "video&audio"
```

**Parameter anpassen:**
- `width`: 1280 (oder 640)
- `height`: 720 (oder 480)
- `fps`: 25
- `volume`: 2.0 (Mikrofon-Verstärkung)
- `sprechanlage`: Stream-Name

### 4.4 go2rtc testen

```bash
./go2rtc -config go2rtc.yaml
```

RTSP-Stream sollte verfügbar sein unter:
```
rtsp://<pi-ip>:8554/sprechanlage
```

---

## 5. systemd Service einrichten

### 5.1 Service-Datei erstellen

```bash
mkdir -p ~/.config/systemd/user
nano ~/.config/systemd/user/hausfunk-pi.service
```

**Inhalt:**
```ini
[Unit]
Description=Hausfunk Pi (go2rtc)
After=network.target

[Service]
Type=simple
ExecStart=/home/andreas/hausfunk/go2rtc -config /home/andreas/hausfunk/go2rtc.yaml
Restart=always
RestartSec=3
Environment=PULSE_SERVER=unix:/run/user/1000/pulse/native
Environment=XDG_RUNTIME_DIR=/run/user/1000

[Install]
WantedBy=default.target
```

**Wichtig:** 
- Pfade anpassen (`/home/andreas/hausfunk/...`)
- UID anpassen (`1000` ist Standard für ersten Benutzer, prüfen mit `id -u`)

### 5.2 Service aktivieren

```bash
systemctl --user daemon-reload
systemctl --user enable --now hausfunk-pi.service
systemctl --user status hausfunk-pi.service
```

### 5.3 Service bei Boot starten

Damit der User-Service automatisch beim Boot startet (auch ohne Login):
```bash
sudo loginctl enable-linger $USER
```

---

## 6. Home Assistant Integration

### 6.1 Integration installieren

**Via HACS:**
1. HACS → 3 dots → Custom repositories
2. Repository URL hinzufügen, Kategorie: Integration
3. "Hausfunk" installieren
4. Home Assistant neu starten

**Manuell:**
1. `custom_components/hausfunk` nach `config/custom_components/` kopieren
2. Home Assistant neu starten

### 6.2 Integration konfigurieren

1. **Settings → Devices & Services → Add Integration → "Hausfunk"**
2. **Pi verbinden:**
   - IP-Adresse
   - SSH-Port (22)
   - Username
   - Passwort
   - Sudo-Passwort (falls abweichend)
3. **Kamera/Stream:**
   - Stream-Name (z.B. `sprechanlage`)
   - RTSP-Port (8554)
   - Breite (1280)
   - Höhe (720)
   - FPS (25)
   - Audio-Gain (2.0)
4. **go2rtc:**
   - URL der HA go2rtc-Instanz (z.B. `http://localhost:1984`)
   - Optional: Credentials
   - go2rtc-Version für Pi

### 6.3 Pi einrichten

Integration bietet Services:
- `hausfunk.setup_pi`: Installiert/aktualisiert den Pi
- `hausfunk.update_pi`: Aktualisiert go2rtc Binary
- `hausfunk.register_stream`: Registriert Stream in HA go2rtc
- `hausfunk.remove_stream`: Entfernt Stream aus HA go2rtc

---

## 7. Baresip (optional, legacy)

Falls baresip statt go2rtc verwendet werden soll:

### 7.1 Abhängigkeiten installieren

```bash
sudo apt install libasound2 libasound2-dev pulseaudio libpulse-dev \
  libwebrtc-audio-processing-dev ffmpeg libavcodec-dev libavformat-dev \
  libavfilter-dev libavdevice-dev libopus-dev \
  libgstreamer-plugins-base1.0-dev libgstreamer-plugins-bad1.0-dev \
  cmake zlib1g-dev libssl-dev libmosquitto-dev mosquitto-dev
```

### 7.2 re bauen

```bash
git clone https://github.com/baresip/re
cd re
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 1
sudo cmake --install build
sudo ldconfig
cd ..
```

### 7.3 baresip bauen

```bash
git clone https://github.com/baresip/baresip
cd baresip
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 1
sudo cmake --install build
cd ..
```

### 7.4 baresip konfigurieren

```bash
baresip  # Einmal ausführen, um ~/.baresip/ zu erstellen
```

Konfigurationsdateien aus `docs/setup/baresip/` nach `~/.baresip/` kopieren:
```bash
cp docs/setup/baresip/config ~/.baresip/
cp docs/setup/baresip/accounts ~/.baresip/
```

**Wichtige Parameter in `~/.baresip/config`:**
- `audio_player pulse`
- `audio_source pulse`
- `ausrc_srate 48000` (INMP441)
- `ausrc_channels 1` (INMP441)
- `auplay_channels 1` (MAX89357A)
- `ausrc_format s32` (INMP441)
- `video_source avformat,http://192.168.178.11:8081/0/stream`
- `mqtt_broker_host 192.168.178.10`
- `mqtt_basetopic baresip/sprechanlage`

**Wichtige Parameter in `~/.baresip/accounts`:**
```
<sip:101@192.168.178.21>;auth_pass=Vergessen2020;auth_user=101;sip_autoanswer=yes;sip_autoanswer_beep=on;answermode=early-video;mediaenc=dtls_srtp
```

---

## 8. Netzwerk-Konfiguration

### 8.1 Statische IP (optional)

```bash
sudo nano /etc/dhcpcd.conf
```

Beispiel:
```
interface wlan0
static ip_address=192.168.178.100/24
static routers=192.168.178.1
static domain_name_servers=192.168.178.1
```

### 8.2 Firewall (optional)

Falls UFW installiert:
```bash
sudo ufw allow 8554/tcp  # RTSP
sudo ufw allow 22/tcp    # SSH
```

---

## 9. Troubleshooting

### Audio-Probleme

**Kein Audio-Gerät:**
```bash
# Prüfen ob I2S-Treiber geladen
lsmod | grep googlevoicehat

# Manuel laden
sudo dtoverlay googlevoicehat-soundcard

# PulseAudio neu starten
systemctl --user restart pulseaudio
```

**Audio mit halber Geschwindigkeit:**
```bash
# pigpiod deinstallieren
sudo apt remove pigpiod
```

### Kamera-Probleme

**Kamera nicht erkannt:**
```bash
# Kamera-Interface prüfen
vcgencmd get_camera

# Kamera-Test
rpicam-hello
```

### go2rtc-Probleme

**Service startet nicht:**
```bash
# Logs prüfen
journalctl --user -u hausfunk-pi.service -f

# Manuell testen
cd ~/hausfunk
./go2rtc -config go2rtc.yaml
```

**PulseAudio-Verbindungsfehler:**
```bash
# UID prüfen
id -u

# PULSE_SERVER in Service-Datei anpassen
nano ~/.config/systemd/user/hausfunk-pi.service
```

---

## 10. Backup und Wiederherstellung

### 10.1 Backup erstellen

```bash
# Konfigurationsdateien sichern
tar -czvf hausfunk-backup-$(date +%Y%m%d).tar.gz \
  ~/hausfunk/ \
  ~/.config/systemd/user/hausfunk-pi.service \
  ~/.baresip/ \
  /boot/firmware/config.txt
```

### 10.2 Schnelle Wiederherstellung

Nach Flashen eines neuen Images:
1. Backup entpacken
2. `config.txt` nach `/boot/firmware/` kopieren
3. `hausfunk/` nach `~/` kopieren
4. Service-Datei nach `~/.config/systemd/user/` kopieren
5. Service aktivieren: `systemctl --user enable --now hausfunk-pi.service`
6. Reboot

---

## 11. Referenzen

- [go2rtc Documentation](https://github.com/AlexxIT/go2rtc)
- [Raspberry Pi Camera Documentation](https://www.raspberrypi.com/documentation/computers/camera_software.html)
- [Google VoiceHAT Soundcard](https://aiyprojects.withgoogle.com/voice/)
- [Baresip Documentation](https://github.com/baresip/baresip)

---

## Changelog

- **2024-03**: Initiale Dokumentation basierend auf bestehendem Setup
- **2024-08**: Migration zu go2rtc-basierter Architektur
