## RPI OS x64
Used the lite version, but I had to install a lot of lib/dev packages (see other md's). Eventually the desktop version is better...

Edit `/boot/firmware/config.txt`  
(after flashing or after 1st boot or later)

```
- dtoverlay=vc4-kms-v3d
- max_framebuffers=2
- dtparam=audio=on
+ dtoverlay=i2s-mmap
+ dtoverlay=googlevoicehat-soundcard
```

# Default packages
```
sudo apt update
sudo apt install git build-essential cmake screen
```

# Pulse audio
````
sudo apt install pulseaudio
```

# Devel packages for baresip etc
```
 sudo apt install libpulse-dev libasound2 libasound2-dev libwebrtc-audio-processing-dev ffmpeg libavcodec-dev libavformat-dev libavfilter-dev libavdevice-dev libopus-dev libgstreamer-plugins-base1.0-dev libgstreamer-plugins-bad1.0-dev zlib1g-dev libssl-dev libmosquitto-dev mosquitto-dev
```

# Troubleshooting audio
# Playback on half speed only:
unintstall pigpiod!

# general
https://forums.raspberrypi.com/viewtopic.php?t=186438
## read logs
*original command: "sudo vcdbg log msg |& grep -v HDMI"*
*not tested:*
`sudo vcdbg log msg |& grep -v googlevoicehat-soundcard`

*not tested:*
udevadm monitor -p -k -u &
sudo dtoverlay googlevoicehat-soundcard