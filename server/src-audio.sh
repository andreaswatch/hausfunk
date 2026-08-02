#!/bin/bash
# Server — launches Pulse → Opus → RTSP push on the Pi via SSH
# $1 = go2rtc {output} URL (server's RTSP endpoint)
exec sshpass -p 'PASSWORD' ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 \
  andreas@192.168.178.11 /opt/audio-push.sh "$@" 2>/dev/null
