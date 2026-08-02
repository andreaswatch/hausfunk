#!/bin/bash
# Pi Zero 2W — raw H264 video output (via stdout pipe, accessed over SSH)
exec rpicam-vid -t 0 --inline --width 320 --height 240 --framerate 10 --profile baseline -o - 2>/dev/null
