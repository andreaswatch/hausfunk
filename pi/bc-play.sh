#!/bin/bash
# Pi Zero 2W — alaw pipe → PulseAudio speaker (backchannel audio receiver)
export PULSE_SERVER=unix:/run/user/1000/pulse/native
export XDG_RUNTIME_DIR=/run/user/1000
exec ffmpeg -hide_banner -loglevel error -fflags nobuffer -probesize 32 -analyzeduration 0 \
  -f alaw -ar 8000 -ac 1 -i pipe:0 -f pulse default 2>/dev/null
