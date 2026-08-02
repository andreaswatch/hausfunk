#!/bin/bash
# Pi Zero 2W — PulseAudio capture → Opus → RTSP push to server go2rtc
# $1 = go2rtc {output} URL (127.0.0.1 → SERVER_IP)
export PULSE_SERVER=unix:/run/user/1000/pulse/native
export XDG_RUNTIME_DIR=/run/user/1000
URL="${1//127.0.0.1/192.168.178.99}"
exec ffmpeg -hide_banner -loglevel error -fflags nobuffer -flags low_delay \
  -f pulse -ac 1 -i default \
  -c:a libopus -b:a 32k -af volume=2.0 \
  -rtsp_transport tcp -f rtsp "$URL" 2>/dev/null
