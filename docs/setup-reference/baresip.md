# Install
## Packages
Today (03/2024) debian's packages are very outdated. Some features like wss are missing.

## Build

Changed re & baresip `- j` in the original instructions to `cmake --build build -j 1`. Otherwise the cmake command consumes too much resources and seems to crash the filesystem on a Pi Zero 2 with a black Intenso 16GB sdcard.

### Audio
Pulse is required for volume control with an INMP441 and MAX98357A.
```
sudo apt update
sudo apt install libasound2 libasound2-dev pulseaudio libpulse-dev libwebrtc-audio-processing-dev ffmpeg libavcodec-dev libavformat-dev libavfilter-dev libavdevice-dev libopus-dev

### Video (using mmjpeg stream)
sudo apt install libgstreamer-plugins-base1.0-dev libgstreamer-plugins-bad1.0-dev
```  

### Required packages
```
sudo apt install cmake zlib1g-dev libssl-dev libmosquitto-dev mosquitto-dev
```

### build **re**
Can take a few minutes.
```
git clone https://github.com/baresip/re
cd re
cmake -B build -DCMAKE_BUILD_TYPE=Release 
cmake --build build -j 1
sudo cmake --install build
sudo ldconfig
cd ..
```
### build **baresip**
Added `sudo` to `cmake --install build`.
Can take a few minutes.
```
git clone https://github.com/baresip/baresip
cd baresip
cmake -B build -DCMAKE_BUILD_TYPE=Release 
cmake --build build -j 1
sudo cmake --install build
cd ..

```  
---

## Configuration 
Execute baresip a single time to generate default configuration files.
```
baresip
```
quit with CTRL+C.
### .baresip/config
copy config files from the baresip directory here into ~/.baresip/
```
cp $PATH_TO_WIKI/baresip ~/.baresip/
```

#### ~/.baresip/config:
This is a typical contact:
```
<sip:101@192.168.178.21>;auth_pass=Vergessen2020;auth_user=101;sip_autoanswer=yes;sip_autoanswer_beep=on;answermode=auto
```
- `101`: Username, can often be a readable name like 'Sprechanlage'.
- `192.168.178.21`: IP address of the SIP server (e.g. asterisk).  
*The Fritz!Box is not suitable, because it has no WebRtc support which is required for HomeAssistant's WebUI*
- `auth_user`: Login name, often a number
- `mediaenc=dtls_srtp`: needed for webrtc -> baresip calls. The other way works out of the box.


#### ~/.baresip/config:
Modified for Pulse Audio. Not sure if the Hardware-related settings are really needed (commented with INMP441 and MAX89357A).

