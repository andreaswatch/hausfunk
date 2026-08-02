# i2s audio 
Tested with INMP441 and MAX98357a.

## Install audio driver
### Option1: Cronjob
This option is recommended as it runs later than the other option. This is prefered, because we want audio to be initialized >after< boot, so that pulse audio can reduce/disable clicks and pops.
#### Create autostart script
`nano /home/andreas/autostart/i2s_audio.sh`
```
sudo dtoverlay googlevoicehat-soundcard
```
#### Add the following to your crontab to load the i2saudio overlay
`crontab -e`
```
@reboot sudo /home/andreas/autostart/i2s_audio.sh
```
### Option2: config.txt
`sudo nano /boot/firmware/config.txt`
```
dtoverlay=googlevoicehat-soundcard
```
