# i2s audio 
i2saudio is a linux kernel overlay that allows you to use generic i2s components as microphones and speakers.
Tested with INMP441 and MAX98357a.

This functionality is provided by a overlay derivered from googlevoicehat-soundcard.
The main difference is that the overlay is not using GPIO16 anymore. 
The reason for this overlay is that I needed to make use of GPIO16 for another task. This caused a problem with the googlevoicehat-soundcard overlay's audio output (loud cracks and pops).

## Convert dtbs to dtb
```
cd /home/andreas/iterative-way-to-i2s-inmp441-max98357a/assets/i2s-audio
dtc -I dts -O dtb -f i2saudio.dtbs -o i2saudio.dtb
dtc -@ -I dts -O dtb -o i2saudio.dtbo i2saudio.dtbs
```
## Install overlay
```
sudo cp i2saudio.dtbo /boot/overlays/
sudo reboot
```
## make sure no other overlays are loaded: 
```
sudo dtoverlay -l 
```
## Test the overlay
```
sudo dtoverlay i2saudio
sudo dtoverlay -l 
```
