# Vergleich: Baresip vs go2rtc

Diese Datei vergleicht die alte Baresip-basierte Architektur mit der neuen go2rtc-basierten Architektur.

## Architektur-Vergleich

### Baresip (Legacy)

```
Pi Zero 2W ──(baresip, SIP)──▶ SIP Server (Asterisk/Fritz!Box) ──▶ Home Assistant
  ├─ Pulse Audio (INMP441 Mic)
  ├─ Pulse Audio (MAX98357A Amp)
  ├─ HTTP MJPEG Stream (Video)
  └─ MQTT (Steuerung)
```

**Vorteile:**
- SIP-Standard, kompatibel mit vielen Telefonanlagen
- WebRTC-Unterstützung für Browser-Calls
- Bewährt für VoIP-Anwendungen

**Nachteile:**
- Komplexer Build-Prozess (re + baresip aus Quelle)
- Viele Abhängigkeiten (PulseAudio, MQTT, etc.)
- Höherer Ressourcenverbrauch
- Fritz!Box nicht geeignet (kein WebRTC)

### go2rtc (Aktuell)

```
Pi Zero 2W ──(go2rtc, RTSP)──▶ HA go2rtc ──(WebRTC)──▶ Browser / Lovelace
  ├─ rpicam-vid (H264 video, hardware)
  ├─ ffmpeg pulse → Opus (mic)
  └─ ffmpeg alaw ← pipe (speaker)
```

**Vorteile:**
- Minimaler Ressourcenverbrauch (ein Binary)
- Keine SIP-Infrastruktur nötig
- Einfache Installation (ein Binary, eine Config)
- Native Home Assistant Integration
- Geringe Latenz
- Two-way audio über RTSP backchannel

**Nachteile:**
- Kein SIP-Support (nicht für Telefonie geeignet)
- Benötigt Home Assistant mit go2rtc

---

## Konfigurations-Vergleich

### Audio-Konfiguration

| Aspekt | Baresip | go2rtc |
|--------|---------|--------|
| **Audio-Treiber** | PulseAudio | PulseAudio |
| **Mikrofon** | INMP441 (I2S, 48kHz, s32, mono) | INMP441 (via PulseAudio) |
| **Lautsprecher** | MAX98357A (I2S, s16, mono) | MAX98357A (via PulseAudio) |
| **Codec** | Opus, G.711 | Opus (mic), A-Law (speaker) |
| **Sample Rate** | 48000 Hz (mic), 48000 Hz (speaker) | 48000 Hz (mic), 8000 Hz (speaker) |
| **Echo-Cancellation** | webrtc_aec.so | (nicht aktiv) |
| **Lautstärke** | PulseAudio-Steuerung | ffmpeg `volume`-Filter |

### Video-Konfiguration

| Aspekt | Baresip | go2rtc |
|--------|---------|--------|
| **Quelle** | HTTP MJPEG Stream | rpicam-vid (Hardware-Encoder) |
| **Codec** | H.264 (via avcodec) | H.264 (Hardware) |
| **Auflösung** | 640x480 (config) | 1280x720 (anpassbar) |
| **FPS** | 30 (config) | 25 (anpassbar) |
| **Transport** | SIP/RTP | RTSP |

### Netzwerk

| Aspekt | Baresip | go2rtc |
|--------|---------|--------|
| **Protokoll** | SIP (UDP/TCP/TLS/WSS) | RTSP (TCP) |
| **Port** | 5060 (SIP), 8000 (HTTP) | 8554 (RTSP) |
| **Verschlüsselung** | DTLS-SRTP | (optional, via HA go2rtc) |
| **MQTT** | Ja (Steuerung) | Nein |

---

## Migration von Baresip zu go2rtc

### Was bleibt gleich

1. **Hardware:** Pi Zero 2W, Kamera, Google VoiceHAT
2. **Audio-Treiber:** I2S mit googlevoicehat-soundcard Overlay
3. **PulseAudio:** Wird weiterhin für Mic/Speaker verwendet
4. **config.txt:** Gleiche I2S-Konfiguration

### Was sich ändert

1. **Software-Stack:**
   - ❌ baresip, re, MQTT
   - ✅ go2rtc, ffmpeg

2. **Integration:**
   - ❌ SIP-Server (Asterisk/Fritz!Box)
   - ✅ Home Assistant go2rtc

3. **Konfiguration:**
   - ❌ `~/.baresip/config`, `~/.baresip/accounts`
   - ✅ `~/hausfunk/go2rtc.yaml`, systemd service

4. **Steuerung:**
   - ❌ MQTT (`baresip/sprechanlage`)
   - ✅ Home Assistant Services

### Migrationsschritte

1. **Backup erstellen:**
   ```bash
   tar -czvf baresip-backup.tar.gz ~/.baresip/
   ```

2. **go2rtc installieren:**
   Siehe [SETUP.md](SETUP.md) Abschnitt 4

3. **Service einrichten:**
   Siehe [SETUP.md](SETUP.md) Abschnitt 5

4. **Home Assistant Integration:**
   Siehe [SETUP.md](SETUP.md) Abschnitt 6

5. **Baresip deinstallieren (optional):**
   ```bash
   # Binary entfernen
   sudo rm /usr/local/bin/baresip
   sudo rm /usr/local/lib/libre.*
   
   # Config behalten (als Backup)
   # rm -rf ~/.baresip/
   ```

---

## Entscheidungshilfe

**Verwende Baresip, wenn:**
- Du eine bestehende SIP-Telefonanlage hast
- Du die Sprechanlage in ein bestehendes VoIP-System integrieren willst
- Du WebRTC-Calls direkt im Browser ohne Home Assistant brauchst

**Verwende go2rtc, wenn:**
- Du Home Assistant als zentrale Plattform nutzt
- Du eine einfache, wartungsarme Lösung willst
- Du minimale Hardware-Ressourcen hast (Pi Zero 2W)
- Du niedrige Latenz brauchst

---

## Fazit

Die Migration zu go2rtc vereinfacht das System erheblich:
- Weniger Komponenten (ein Binary statt baresip + re + MQTT)
- Bessere Home Assistant Integration
- Geringerer Ressourcenverbrauch
- Einfachere Wartung

Die Audio-Qualität bleibt gleich, da beide Systeme PulseAudio und die gleiche Hardware verwenden.
