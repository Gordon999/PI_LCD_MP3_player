#!/usr/bin/env python3


"""Copyright (c) 2026
Permission is hereby granted,free of charge,to any person obtaining a copy of this 
software and associated documentation files (the "Software"),to dealin the Software
without restriction,including without limitation the rightsto use,copy,modify,
merge,publish,distribute,sublicense,and/or sell copies of the Software,and to permit
persons to whom the Software is furnished to do so,subject to the following conditions:
The above copyright notice and this permission notice shall be included in allcopies
or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS",WITHOUT WARRANTY OF ANY KIND,EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,FITNESS FOR A 
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM,DAMAGES OR OTHER LIABILITY,WHETHER IN AN ACTION OF
CONTRACT,TORT OR OTHERWISE,ARISING FROM,OUT OF OR IN CONNECTION WITH THE SOFTWARE 
OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."""

# imports 
import glob
import subprocess
import os,sys
import time
import datetime
from datetime import timedelta
from random import shuffle
from mutagen.mp3 import MP3
import alsaaudio
from signal import signal,SIGTERM,SIGHUP,pause

# code version
version = 3.6

# set starting variables
lcd_type     = 0    # 0 = 16x2 or 20x4 LCD, 1 = OLED SSD1306
lcd_lines    = 2    # dependent on i2c lcd display used
boot_mode    = 0    # Action at BOOT, 0 = STOPPED, 1 = MP3 PLAY, 2 = RADIO PLAY *
album_mode   = 0    # set to 1 for Album Mode,will play an album then stop *
randomed     = 0    # 0 = SORTED, 1 = RANDOMED (not available if in album mode) *
radio_stn    = 0    # selected radio station at startup *
volume       = 30   # range 0 - 100 *
max_volume   = 80   # set MAXIMUM volume
sleep_timer  = 0    # sleep_timer timer in minutes,use 15,30,45,60 etc...set to 0 to disable *
sleep_shutdn = 1    # set to 1 to shutdown when sleep times out
gapless      = 0    # set to 1 for gapless play *
gaptime      = 2    # set pre-start time for gapless,in seconds
show_clock   = 1    # set to 1 to show clock time, only use if on internet / RTC fitted
use_USB      = 1    # set to 0 if you only use /home/USERNAME/Music/Artist/Album/... on SD card
bl_timeout   = 30   # backlight timeout in seconds,set to 0 to disable
md_timeout   = 10   # timeout to switch back to main mode in seconds

# NOTE * These settings will be overridden by the config file stored after the first run.

Radio_Stns = ["R Paradise Rock","http://stream.radioparadise.com/rock-192",
              "R Paradise Main","http://stream.radioparadise.com/mp3-320",
              "R Paradise Mellow","http://stream.radioparadise.com/mellow-192",
              "Radio Caroline","http://sc6.radiocaroline.net:10558/"
              ]
              
# setup rotary encoders
from gpiozero import Button
from gpiozero import RotaryEncoder
SEL_rotor  = RotaryEncoder(16,20,wrap=True, max_steps=32)
SEL_button = 12  # SELECT button
button_SEL = Button(SEL_button)
VOL_rotor  = RotaryEncoder(5,6,  wrap=False,max_steps=32)
VOL_button = 13  # VOLUME button
button_VOL = Button(VOL_button)
    
if lcd_type == 0: # 16x2 or 20x4 LCD
	# setup LCD
    from rpi_lcd import LCD
    lcd = LCD()
    def safe_exit(signum,frame):
        exit(1)
    signal(SIGTERM,safe_exit)
    signal(SIGHUP,safe_exit)

elif lcd_type == 1: # OLED SSD 1306
    # setup OLED
    # To install SSD1306 driver...
    # pip3 install adafruit-circuitpython-ssd1306
    # pip3 install adafruit-blinka
    # pip3 install pillow
    # Enable I2C on Pi. Pi Menu > Preferences > RPI Configuration > Interfaces > I2C
    # reboot

    import board
    import busio
    import adafruit_ssd1306
    from PIL import Image
    from PIL import ImageDraw
    from PIL import ImageFont
    i2c = busio.I2C(board.SCL, board.SDA)
    display = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)
    image  = Image.new("1", (display.width, display.height))
    draw   = ImageDraw.Draw(image)
    font   = ImageFont.load_default()
    width  = display.width
    height = display.height
    top    = -2

# read stations.txt (Station Name,URL)
if os.path.exists ("radio_stns.txt"): 
    with open("radio_stns.txt","r") as textobj:
        line = textobj.readline()
        while line:
            if line.count(",") == 2:
                a,b,c = line.split(",")
                if a[0:1] != "#":
                    Radio_Stns.append(a)
                    Radio_Stns.append(b)
            elif line.count(",") == 1:
                a,b = line.split(",")
                if a[0:1] != "#":
                    Radio_Stns.append(a)
                    Radio_Stns.append(b.strip())
            line = textobj.readline()

# check LCD_ConfigX.txt exists, if not then write default values
config_file = "LCD_Config3.txt"
# delete config file if size = 0
if os.path.exists(config_file) and os.path.getsize(config_file) == 0:
	os.remove(config_file)
# write the config file if required
if not os.path.exists(config_file):
    defaults = [boot_mode,volume,randomed,album_mode,radio_stn,gapless]
    with open(config_file, 'w') as f:
        for item in defaults:
            f.write("%s\n" % item)
# read config file
defaults    = []
with open(config_file, "r") as file:
   line = file.readline()
   while line:
      defaults.append(line.strip())
      line = file.readline()
defaults = list(map(int,defaults))

boot_mode   = defaults[0]
volume      = defaults[1]
randomed    = defaults[2]
album_mode  = defaults[3]
radio_stn   = defaults[4]
gapless     = defaults[5]

# initialise parameters
Track_No        = 0
old_album       = ""
old_artist      = ""
titles          = [0,0,0,0,0,0,0]
freedisk        = ["0","0","0","0"]
backlight_on    = 1
stimer          = 0
ctracks         = 0
cplayed         = 0
played_pc       = 0
old_SEL_rotor   = 0
VOL_rotor.value = ((volume/100)*2) - 1
old_VOL_rotor   = VOL_rotor.value
old_volume      = volume
next_           = 0
prev_           = 0
mode            = -1
radio_next      = 0
radio_prev      = 0
md_1            = " "
md_2            = " "
md_3            = " "
trace           = 0
a               = 0
save_config     = 0
menu            = 0
msg1            = "MP3 Player: v" + str(version)
msg2            = ""
msg3            = ""
msg4            = ""
msg5            = ""
MP3_Play        = 0
if lcd_lines == 2:
	length = 15
elif lcd_type == 0:
	length = 19
else:
	length = 23
	
def display_screen():
    global image,top,msg1,msg2,msg3,msg4,msg5,width,height,font,display,lcd_type,lcd_lines,backlight_on,MP3_Play
    if lcd_type == 0:
		# LCD display
        lcd.text(msg1,1) 
        lcd.text(msg2,2) 
        if lcd_lines == 4:
            lcd.text(msg3,3) 
            lcd.text(msg4,4) 
    elif lcd_type == 1:
        # OLED display
        draw.rectangle((0,0,width,height), outline=0, fill=0)
        if backlight_on == 1:
            draw.text((0, top + 0), msg1,  font=font, fill=255)
            draw.text((0, top + 16),msg2,  font=font, fill=255)
            draw.text((0, top + 28),msg3,  font=font, fill=255)
            draw.text((0, top + 40),msg4,  font=font, fill=255)
            if MP3_Play == 1:
                draw.text((0, top + 56),msg5,  font=font, fill=255)
        display.image(image)
        display.show()

# reload MP3 tracks
def reload():
    global tracks,users,randomed,Track_No
    tracks  = []
    msg1 = "Tracks: " + str(len(tracks))
    time.sleep(0.05)
    msg2 = "Reloading... "
    display_screen()
    usb_tracks = glob.glob("/media/" + users[0] + "/*/*/*/*.mp3")
    sd_tracks  = glob.glob("/home/" + users[0] + "/Music/*/*/*.mp3")
    titles = [0,0,0,0,0,0,0]
    if len(sd_tracks) > 0:
        for x in range(0,len(sd_tracks)):
            titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = sd_tracks[x].split("/")
            track = titles[4] + "/" + titles[5] + "/" + titles[6] + "/" + titles[0] + "/" + titles[1] + "/" + titles[2] + "/" + titles[3]
            tracks.append(track)
            if len(tracks)/200 == int(len(tracks)/200):
                msg1 = "Tracks: " + str(len(tracks))
    if len(usb_tracks) > 0:
        for x in range(0,len(usb_tracks)):
            titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = usb_tracks[x].split("/")
            track = titles[4] + "/" + titles[5] + "/" + titles[6] + "/" + titles[0] + "/" + titles[1] + "/" + titles[2] + "/" + titles[3]
            tracks.append(track)
            if len(tracks)/200 == int(len(tracks)/200):
                msg1 = "Tracks: " + str(len(tracks))
    if randomed == 1:
        shuffle(tracks)
    else:
        tracks.sort()
    Track_No = 0
    with open('tracks.txt','w') as f:
        for item in tracks:
            f.write("%s\n" % item)
    msg1 = "Tracks: " + str(len(tracks))
    display_screen()
    time.sleep(0.05)
    msg2 = " "
    time.sleep(1)

# read SELECT rotary encoder
def Read_Rotor_SELECT():
    global old_SEL_rotor,MP3_Play,next_,prev_,radio_next,radio_prev,mode,sleep_timer,sleep_timer_start,Track_No,stimer,menu
    global gapless,gap,gaptime,tracks,album_mode,mode,trace,randomed,radio,boot_mode,save_config,md_start,bl_start,backlight_on
    global msg1,msg2,msg3,msg4
    if trace == 1:
        print("read rotary SELECT",SEL_rotor.value)
    if old_SEL_rotor != SEL_rotor.value:
        md_start = time.monotonic()
        bl_start = time.monotonic()
        backlight_on = 1
        if lcd_type == 0:
            lcd.backlight(turn_on=True)
        if SEL_rotor.value < old_SEL_rotor:
          old_SEL_rotor = SEL_rotor.value
          if mode == -1:
                menu +=1
                if menu > 9:
                    menu = 0
                if menu == 0:
                    msg1 = ">Set Artist A-Z"
                    if lcd_lines == 2:
                        msg2 = titles[0]
                elif menu == 1:
                    msg1 = ">Set Artist"
                    if lcd_lines == 2:
                        msg2 = titles[0]
                elif menu == 2:
                    msg1 = ">Set Album"
                    if lcd_lines == 2:
                        msg2 = titles[1]
                elif menu == 3:
                    msg1 = ">Set Track"
                    if lcd_lines == 2:
                        msg2 = titles[2][:-4]
                elif menu == 4:
                    msg1 = ">Set SLEEP "
                    if lcd_lines == 2:
                        if sleep_timer == 0:
                            msg2 = "OFF"
                        else:
                            msg2 = str(int(sleep_timer))
                elif menu == 5:
                    msg1 = ">Set RANDOM"
                    if lcd_lines == 2:
                        if randomed == 1:
                            msg2 = "ON"
                        else:
                            msg2 = "OFF"
                elif menu == 6:
                    msg1 = ">Set GAPLESS"
                    if lcd_lines == 2:
                        if gapless == 1:
                            msg2 = "ON"
                        else:
                            msg2 = "OFF"
                elif menu == 7:
                    msg1 = ">Set ALBUM MODE"
                    if lcd_lines == 2:
                        if album_mode == 1:
                            msg2 = "ON"
                        else:
                            msg2 = "OFF"
                elif menu == 8:
                    msg1 = ">Set BOOT MODE"
                    if lcd_lines == 2:
                        if boot_mode == 0:
                            msg2 = "STOPPED"
                        elif boot_mode == 1:
                            msg2 = "MP3 PLAY"
                        elif boot_mode == 2:
                            msg2 = "RADIO PLAY"
                elif menu == 9:
                    msg1 = ">RELOAD TRACKS"
                    msg2 = " "
                display_screen()
          else:		
            if mode == 4:
                if album_mode == 1:
                    album_length()
                    sleep_timer = int(stimer/60)
                else:
                    sleep_timer +=15
                    if sleep_timer > 120:
                        sleep_timer = 0
                sleep_timer_start = time.monotonic()
                msg1 = ">SLEEP.. " + str(int(sleep_timer))
                save_config = 1
            elif mode == 5:
                randomed = 1
                msg1 = ">RANDOM ON "
                shuffle(tracks)
                Track_No = 0
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
                if lcd_lines == 2:
                    msg2 = titles[2][0:length]
                elif lcd_lines == 4:
                    msg2 = md_1 + titles[0][0:length]
                    msg3 = md_2 + titles[1][0:length]
                    msg4 = md_3 + titles[2][0:length]
                album_mode = 0
                if gapless == 0:
                    gap = 0
                elif gapless != 0:
                    gap = gaptime
                save_config = 1
            elif mode == 6:
                gapless = 1
                msg1 = ">GAPLESS ON "
                if randomed == 1:
                    gap = gaptime
                    shuffle(tracks)
                else:
                    gap = gaptime
                    tracks.sort()
                save_config = 1
            elif mode == 7:
                album_mode = 1
                msg1 = ">ALBUM MODE ON "
                if randomed == 1:
                    randomed = 0
                    titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
                    old_album  = titles[1]
                    old_artist = titles[0]
                    tracks.sort()
                    Track_No = 0
                    titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
                    while titles[1] != old_album or titles[0] != old_artist:
                        Track_No +=1
                        if Track_No > len(tracks) - 1:
                            Track_No = Track_No - len(tracks)
                        titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
                if lcd_lines == 2:
                    msg2 = titles[2][0:length]
                elif lcd_lines == 4:
                    msg2 = md_1 + titles[0][0:length]
                    msg3 = md_2 + titles[1][0:length]
                    msg4 = md_3 + titles[2][0:length]
                album_length()
                save_config = 1
            elif mode == 8:
                boot_mode +=1
                boot_mode = min(boot_mode,2)
                if boot_mode == 0:
                    msg1 = ">BOOT:STOPPED"
                elif boot_mode == 1:
                    msg1 = ">BOOT:MP3 PLAY"
                elif boot_mode == 2:
                    msg1 = ">BOOT:RADIO PLAY"
                save_config = 1
            elif mode == 9:
                msg1 = ">RELOADING..."
                reload()
            elif radio == 1:
                mode = 0
                radio_next = 1
            elif MP3_Play == 0:
                next_ = 1
            elif MP3_Play == 1:
                if trace == 1:
                    print("MP3_Play")
                mode = 3
                status()
                next_ = 1
            display_screen()
        else:
          old_SEL_rotor = SEL_rotor.value
          if mode == -1:
                menu -=1
                if menu < 0:
                    menu = 9
                if menu == 0:
                    msg1 = ">Set Artist A-Z"
                    if lcd_lines == 2:
                        msg2 = titles[0]
                elif menu == 1:
                    msg1 = ">Set Artist"
                    if lcd_lines == 2:
                        msg2 = titles[0]
                elif menu == 2:
                    msg1 = ">Set Album"
                    if lcd_lines == 2:
                        msg2 = titles[1]
                elif menu == 3:
                    msg1 = ">Set Track"
                    if lcd_lines == 2:
                        msg2 = titles[2][:-4]
                elif menu == 4:
                    msg1 = ">Set SLEEP "
                    if lcd_lines == 2:
                        if sleep_timer == 0:
                            msg2 = "OFF"
                        else:
                            msg2 = str(int(sleep_timer))
                elif menu == 5:
                    msg1 = ">Set RANDOM"
                    if lcd_lines == 2:
                        if randomed == 1:
                            msg2 = "ON"
                        else:
                            msg2 = "OFF"
                elif menu == 6:
                    msg1 = ">Set GAPLESS"
                    if lcd_lines == 2:
                        if gapless == 1:
                            msg2 = "ON"
                        else:
                            msg2 = "OFF"
                elif menu == 7:
                    msg1 = ">Set ALBUM MODE"
                    if lcd_lines == 2:
                        if album_mode == 1:
                            msg2 = "ON"
                        else:
                            msg2 = "OFF"
                elif menu == 8:
                    msg1 = ">Set BOOT MODE"
                    if lcd_lines == 2:
                        if boot_mode == 0:
                            msg2 = "STOPPED"
                        elif boot_mode == 1:
                            msg2 = "MP3 PLAY"
                        elif boot_mode == 2:
                            msg2 = "RADIO PLAY"
                elif menu == 9:
                    msg1 = ">RELOAD TRACKS"
                    msg2 = " "
                display_screen()
          else:
            if mode == 4:
                sleep_timer -=15
                if sleep_timer < 0:
                    sleep_timer = 0
                sleep_timer_start = time.monotonic()
                msg1 = ">SLEEP.. " + str(int(sleep_timer))
                display_screen()
                save_config = 1
            elif mode == 5:
                randomed = 0
                msg1 = ">RANDOM OFF "
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
                old_album  = titles[1]
                old_artist = titles[0]
                tracks.sort()
                Track_No = 0
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
                while titles[1] != old_album or titles[0] != old_artist:
                    Track_No +=1
                    if Track_No > len(tracks) - 1:
                        Track_No = Track_No - len(tracks)
                    titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
                if lcd_lines == 2:
                    msg2 = titles[2][0:length]
                elif lcd_lines == 4:
                    msg2 = md_1 + titles[0][0:length]
                    msg3 = md_2 + titles[1][0:length]
                    msg4 = md_3 + titles[2][0:length]
                if gapless == 0:
                    gap = 0
                elif gapless != 0:
                    gap = gaptime
                display_screen()
                save_config = 1
            elif mode == 6:
                gapless = 0
                msg1 = ">GAPLESS OFF "
                if randomed == 1:
                    gap = 0
                    shuffle(tracks)
                elif randomed == 0:
                    gap = 0
                    tracks.sort()
                save_config = 1
            elif mode == 7:
                album_mode = 0
                msg1 = ">ALBUM MODE OFF "
                randomed = 0
                tracks.sort()
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
                if lcd_lines == 2:
                    msg2 = titles[2][0:length]
                elif lcd_lines == 4:
                    msg2 = md_1 + titles[0][0:length]
                    msg3 = md_2 + titles[1][0:length]
                    msg4 = md_3 + titles[2][0:length]
                display_screen()
                album_length()
                save_config = 1
            elif mode == 8:
                boot_mode -=1
                boot_mode = max(boot_mode,0)
                if boot_mode == 0:
                    msg1 = ">BOOT:STOPPED"
                elif boot_mode == 1:
                    msg1 = ">BOOT:MP3 PLAY"
                elif boot_mode == 2:
                    msg1 = ">BOOT:RADIO PLAY"
                display_screen()
                save_config = 1
            elif mode == 9:
                msg1 = ">RELOADING"
                reload()
            elif radio == 1:
                mode = 0
                radio_prev = 1
            elif MP3_Play == 0:
                prev_ = 1
            elif MP3_Play == 1:
                if trace == 1:
                    print("MP3_Play")
                mode = 3
                status()
                prev_ = 1
            display_screen()

# read VOLUME rotary encoder 
def Read_Rotary_VOLUME():
    global old_VOL_rotor,volume,save_config,max_volume,md_start,bl_start,backlight_on
    global msg1,msg2,msg3,msg4
    if trace == 1:
        print("read rotary VOLUME",VOL_rotor.value)
    if old_VOL_rotor != VOL_rotor.value:
        old_VOL_rotor = VOL_rotor.value
        md_start = time.monotonic()
        backlight_on = 1
        if lcd_type == 0:
            lcd.backlight(turn_on=True)
        bl_start = time.monotonic()
        volume = int(((VOL_rotor.value + 1)/2) * 100)
        volume = min(volume,max_volume)
        volume = max(volume,0)
        if len(alsaaudio.mixers()) > 0 and lver < 13:
            m.setvolume(volume)
            os.system("amixer -D pulse sset Master " + str(volume) + "%")
            if mixername == "DSP Program":
                os.system("amixer set 'Digital' " + str(volume + 107))
        else:
            os.system("wpctl set-volume @DEFAULT_AUDIO_SINK@ " + str(volume/100))
        msg1 = ">Set Volume.. " + str(volume)
        display_screen()
        save_config = 1
        
# set current status display
def status():
    global txt,RANDOM,gapless,album_mode,sleep_timer
    txt = " "
    if randomed ==1:
        txt +="R"
    else:
        txt +=" "
    if album_mode == 1:
        txt +="A"
    else:
        txt +=" "
    if gapless == 1:
        txt +="G"
    else:
        txt +=" "
    if sleep_timer > 0:
        txt +="S"
    else:
        txt +=" "

# read previous usb free space of upto 4 usb devices,to see if usb data has changed
if not os.path.exists('freedisk.txt'):
    with open("freedisk.txt","w") as f:
        for item in freedisk:
            f.write("%s\n" % item)
freedisk = []            
with open("freedisk.txt","r") as file:
    line = file.readline()
    while line:
         freedisk.append(line.strip())
         line = file.readline()

# find user
users  = []
users.append(os.getlogin())

# check if USB mounted and find USB storage
start = time.monotonic()
msg1 = "Loading..."
usb = glob.glob("/media/" + users[0] + "/*")
for c in range(0,len(usb)):
    if os.path.getsize(usb[c]) < 5000:
        usb[c] = "x"
usb = [i for i in usb if i!="x"]
print(usb)
usb_found = len(usb)
if use_USB == 1:
    while time.monotonic() - start < 3 and usb_found == 0:
        usb = glob.glob("/media/" + users[0] + "/*")
        for c in range(0,len(usb)):
            if os.path.getsize(usb[c]) < 5000:
                usb[c] = "x"
        usb = [i for i in usb if i!="x"]
        usb_found = len(usb)
        msg1 = "Checking for USB..."
        time.sleep(.25)
        msg2 = " "
        time.sleep(.25)
        display_screen()
    if usb_found > 0:
        # check if usb has changed,if so then reload tracks
        free = ["0","0","0","0"]
        for x in range(0,len(usb)):
            st3 = os.statvfs(usb[x])
            free[x] = str((st3.f_bavail * st3.f_frsize)/1100000)
        for x in range(0,3):
            if str(free[x]) != freedisk[x]:
                with open("freedisk.txt","w") as f:
                    for item in free:
                        f.write("%s\n" % item)
                reload()
    else:
        freedisk = ["0","0","0","0"]
        with open("freedisk.txt","w") as f:
                for item in freedisk:
                    f.write("%s\n" % item)

#check linux version.
lv = os.popen("cat /etc/os-release").read()
lva = lv.split("\n")
for w in range(0,len(lva)):
    title = lva[w].split("=")
    if title[0] == "VERSION_ID":
        lver = int(title[1][1:3])
print(lver)

# check for audio mixers
print(alsaaudio.mixers())
if len(alsaaudio.mixers()) > 0 and lver < 13:
    for mixername in alsaaudio.mixers():
        print(str(mixername))
        if str(mixername) == "PCM" or str(mixername) == "DSP Program" or str(mixername) == "Master" or str(mixername) == "Capture" or str(mixername) == "Headphone" or str(mixername) == "HDMI":
            m = alsaaudio.Mixer(mixername)
        else:
            m = alsaaudio.Mixer(alsaaudio.mixers()[0])
    m.setvolume(volume)
    os.system("amixer -D pulse sset Master " + str(volume) + "%")
    if mixername == "DSP Program":
        os.system("amixer set 'Digital' " + str(volume + 107))
else:
    os.system("wpctl set-volume @DEFAULT_AUDIO_SINK@ " + str(volume/100))
    
msg1 = "Version: " + str(version)  
display_screen()
time.sleep(1)  
        
# load MP3 tracks
tracks  = []
if os.path.exists('tracks.txt') and os.path.getsize("tracks.txt") == 0:
    os.remove('tracks.txt')
    
if not os.path.exists('tracks.txt') :
    reload()
else:
    with open("tracks.txt","r") as file:
        line = file.readline()
        while line:
             tracks.append(line.strip())
             line = file.readline()
msg1 = "Tracks: " + str(len(tracks))
display_screen()

if len(tracks) > 0:
    if randomed == 1:
        shuffle(tracks)
    else:
        tracks.sort()
        
# At power on
if boot_mode == 0:
	MP3_Play = 0
	radio = 0
elif boot_mode == 1:
    MP3_Play = 1
    radio = 0
    mode = 3
elif boot_mode == 2:
	radio = 1
	MP3_Play = 0
    
# wait for internet connection for radio at power up
if radio == 1:
    msg1 = "Waiting..."
    display_screen()
    time.sleep(10)

# disable randomise if in album mode
if album_mode == 1:
    randomed = 0

# try reloading tracks if one selected not found
if len(tracks) > 0:
    titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
    track = titles[3] + "/" + titles[4] + "/" + titles[5] + "/" + titles[6] + "/" + titles[0] + "/" + titles[1] + "/" + titles[2]
    if not os.path.exists (track):
        reload()

# determine album length and number of tracks
def album_length():
    global album_mode,Track_No,tracks,audio,stimer,ctracks,Tack_No,fTack_No
    cplayed = 0
    fTack_No = 0
    if album_mode == 1:
        Tack_No = Track_No
        stimer  = 0
        stitles = [0,0,0,0,0,0,0]
        stitles[0],stitles[1],stitles[2],stitles[3],stitles[4],stitles[5],stitles[6] = tracks[Tack_No].split("/")
        talbum = stitles[1]
        tartist = stitles[0]
        # find start of album
        while stitles[1] == talbum and stitles[0] == tartist:
            stitles[0],stitles[1],stitles[2],stitles[3],stitles[4],stitles[5],stitles[6] = tracks[Tack_No].split("/")
            strack = stitles[3] + "/" + stitles[4] + "/" + stitles[5] + "/" + stitles[6] + "/" + stitles[0] + "/" + stitles[1] + "/" + stitles[2]
            Tack_No -=1
            Track_No -=1
        Tack_No +=2
        Track_No +=2
        if Tack_No < 0:
            Tack_No = 0
        if Track_No < 0:
            Track_No = 0
        fTack_No = Track_No
        stitles = [0,0,0,0,0,0,0]
        stitles[0],stitles[1],stitles[2],stitles[3],stitles[4],stitles[5],stitles[6] = tracks[Tack_No].split("/")
        talbum = stitles[1]
        tartist = stitles[0]
        # until end of album,length in time and number of tracks
        while stitles[1] == talbum and stitles[0] == tartist:
            stitles[0],stitles[1],stitles[2],stitles[3],stitles[4],stitles[5],stitles[6] = tracks[Tack_No].split("/")
            strack = stitles[3] + "/" + stitles[4] + "/" + stitles[5] + "/" + stitles[6] + "/" + stitles[0] + "/" + stitles[1] + "/" + stitles[2]
            audio = MP3(strack)
            stimer += audio.info.length
            Tack_No +=1
        Tack_No -=2
        audio = MP3(strack)
        stimer -= audio.info.length
        ctracks = (Tack_No - Track_No) + 1
        if trace == 1:
            print("Ctracks",fTack_No,Tack_No,Track_No,ctracks,stimer)

# get album length
if len(tracks) > 0:
    album_length()

# display track number
if album_mode == 0:
    track_n = str(Track_No+1) + "     "
else:
    track_n = "1/" + str(ctracks) + "       "

# get RAGS status
status()

# setup gapless and randomise  
if randomed == 1 and gapless == 0:
    gap = 0
    shuffle(tracks)
elif randomed == 0 and gapless == 0:
    gap = 0
elif randomed == 1 and gapless != 0:
    gap = gaptime
    shuffle(tracks)
elif randomed == 0 and gapless != 0:
    gap = gaptime

# show display   
if len(tracks) > 0:
    md_1 = " "
    md_2 = " "
    md_3 = " "
    msg1 = ">Set Artist A-Z"
    time.sleep(0.05)
    titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
    if lcd_lines == 2:
        if mode <= 1:
            msg2 = titles[0][0:length]
        if mode == 2:
            msg2 = titles[1][0:length]
        if mode == 3:
            msg2 = titles[2][0:length]
    if lcd_lines == 4:
        msg2 = md_1 + titles[0][0:length]
        msg3 = md_2 + titles[1][0:length]
        msg4 = md_3 + titles[2][0:length]
    display_screen()
else:
    msg1 = "No tracks found..."
    msg2 = "HOLD PLAY for RADIO"
    display_screen()
    
time.sleep(0.05)

# start radio at power up if set
if radio == 1:
    msg2 = " "
    q = subprocess.Popen(["cvlc",Radio_Stns[radio_stn + 1]] ,shell=False)
    msg1 = ">Choose Radio Stn"
    msg2 = Radio_Stns[radio_stn]
    display_screen()
    time.sleep(0.05)

# start SLEEP and BACKLIGHT timers
sleep_timer_start = time.monotonic()
bl_start          = time.monotonic()
md_start          = time.monotonic()

# main loops
while True:
    # loop while stopped
    while MP3_Play == 0 and radio == 0:
        time.sleep(0.1)
        # read VOLUME rotary encoder 
        Read_Rotary_VOLUME()
        # read rotary encoder 
        Read_Rotor_SELECT()
        if button_SEL.is_pressed:
            if lcd_type == 0:
                lcd.backlight(turn_on=True)
            bl_start = time.monotonic()
            md_start = time.monotonic()
            a = 0
            md_1 = " "
            md_2 = " "
            md_3 = " "
            if mode == -1:
                mode = menu
                if mode == 0:
                    msg1 = "> Artist A-Z"
                elif mode == 1:
                    msg1 = "Choose Artist"
                    md_1 = ">"
                elif mode == 2:
                    msg1 = "Choose Album"
                    md_2 = ">"
                elif mode == 3:
                    msg1 = "Choose Track"
                    md_3 = ">"
                elif mode == 4:
                    msg1 = ">SLEEP..  " + str(int(sleep_timer))
                elif mode == 5:
                    if randomed == 0:
                        msg1 = ">RANDOM OFF"
                    else:
                        msg1 = ">RANDOM ON"
                elif mode == 6:
                    if gapless == 0:
                        msg1 = ">GAPLESS OFF"
                    else:
                        msg1 = ">GAPLESS ON"
                elif mode == 7:
                    if album_mode == 0:
                        msg1 = ">ALBUM MODE OFF"
                    else:
                        msg1 = ">ALBUM MODE ON"
                elif mode == 8:
                    if boot_mode == 0:
                        msg1 = ">BOOT: STOPPED"
                    elif boot_mode == 1:
                        msg1 = ">BOOT: MP3 PLAY"
                    elif boot_mode == 2:
                        msg1 = ">BOOT: RADIO PLAY"
                elif mode == 9:
                    msg1 = ">RELOADING TRACKS"
                    reload()
                display_screen()
            else:
                mode = -1
                menu +=1
                if menu == 0:
                    msg1 = ">Set Artist A-Z"
                    if lcd_lines == 2:
                        msg2 = titles[0]
                elif menu == 1:
                    msg1 = ">Set Artist"
                    if lcd_lines == 2:
                        msg2 = titles[0]
                elif menu == 2:
                    msg1 = ">Set Album"
                    if lcd_lines == 2:
                        msg2 = titles[1]
                elif menu == 3:
                    msg1 = ">Set Track"
                    if lcd_lines == 2:
                        msg2 = titles[2][:-4]
                elif menu == 4:
                    msg1 = ">Set SLEEP "
                    if lcd_lines == 2:
                        if sleep_timer == 0:
                            msg2 = "OFF"
                        else:
                            msg2 = str(int(sleep_timer))
                elif menu == 5:
                    msg1 = ">Set RANDOM"
                    if lcd_lines == 2:
                        if randomed == 1:
                            msg2 = "ON"
                        else:
                            msg2 = "OFF"
                elif menu == 6:
                    msg1 = ">Set GAPLESS"
                    if lcd_lines == 2:
                        if gapless == 1:
                            msg2 = "ON"
                        else:
                            msg2 = "OFF"
                elif menu == 7:
                    msg1 = ">Set ALBUM MODE"
                    if lcd_lines == 2:
                        if album_mode == 1:
                            msg2 = "ON"
                        else:
                            msg2 = "OFF"
                elif menu == 8:
                    msg1 = ">Set BOOT MODE"
                    if lcd_lines == 2:
                        if boot_mode == 0:
                            msg2 = "STOPPED"
                        elif boot_mode == 1:
                            msg2 = "MP3 PLAY"
                        elif boot_mode == 2:
                            msg2 = "RADIO PLAY"
                elif menu == 9:
                    msg1 = ">RELOAD TRACKS"
                    msg2 = " "
                display_screen()
                defaults[0] = boot_mode
                defaults[1] = volume 
                defaults[2] = randomed 
                defaults[3] = album_mode 
                defaults[4] = radio_stn
                defaults[5] = gapless
                if save_config == 1:   
                    with open(config_file, 'w') as f:
                        for item in defaults:
                            f.write("%s\n" % item)
                    save_config = 0
            time.sleep(0.5)
        else: 
          if len(tracks) > 0:
			# display artist / album / track info   
            if lcd_lines == 2 and not button_SEL.is_pressed:
                if (mode == 0 or mode == 1) and len(titles[0]) > 15:
                    if a < len(titles[0])-14:
                        msg2 = titles[0][a:a+16]
                        a +=1
                    else:
                        a = 0
                elif (mode == 0 or mode == 1):
                    msg2 = titles[0][0:length]
                if mode == 2 and len(titles[1]) > 15:
                    if a < len(titles[1])-14:
                        msg2 = titles[1][a:a+16]
                        a +=1
                    else:
                        a = 0
                elif mode == 2:
                    msg2 = titles[1][0:length]
                if mode == 3 and len(titles[2]) > 15:
                    if a < len(titles[2])-14:
                        msg2 = titles[2][a:a+16]
                        a +=1
                    else:
                        a = 0
                elif mode == 3:
                    msg2 = titles[2][0:length]
            if lcd_lines == 4 and not button_SEL.is_pressed:
                msg2 = md_1 + titles[0][0:length]
                msg3 = md_2 + titles[1][0:length]
                msg4 = md_3 + titles[2][0:length]
          else:
                msg1 = "No MP3 tracks"
                msg2 = "HOLD 5s for RADIO"
          display_screen()
          time.sleep(0.5)

        # backlight OFF timer
        if time.monotonic() - bl_start > bl_timeout and bl_timeout > 0:
            if lcd_type == 0:
                lcd.backlight(turn_on=False)
            elif lcd_type == 1:
                draw.rectangle((0,0,width,height), outline=0, fill=0)
                display.image(image)
                display.show()
            backlight_on = 0
            defaults[0] = boot_mode
            defaults[1] = volume 
            defaults[2] = randomed 
            defaults[3] = album_mode 
            defaults[4] = radio_stn
            defaults[5] = gapless
            if save_config == 1:   
                with open(config_file, 'w') as f:
                    for item in defaults:
                         f.write("%s\n" % item)
                save_config = 0
            
        # mode timer
        if time.monotonic() - md_start > md_timeout and mode != -1:
            mode = -1
            menu = 0
            msg1 = ">Set Artist A-Z"
            md_1 = " "
            md_2 = " "
            md_3 = " "
            display_screen()
            defaults[0] = boot_mode
            defaults[1] = volume 
            defaults[2] = randomed 
            defaults[3] = album_mode 
            defaults[4] = radio_stn
            defaults[5] = gapless
            if save_config == 1:   
                with open(config_file, 'w') as f:
                    for item in defaults:
                        f.write("%s\n" % item)
                save_config = 0
            
        # sleep_timer timer
        if time.monotonic() - sleep_timer_start > (sleep_timer * 60) and sleep_timer > 0:
            if lcd_type == 0:
                lcd.backlight(turn_on=True)
            bl_start = time.monotonic()
            abort_shutdown = 0
            t = 30
            while t > 0 and abort_shutdown == 0:
                if sleep_shutdn == 1:
                    msg2 = "SHUTDOWN in " + str(t)
                else:
                    msg2 = "STOPPING in " + str(t)
                display_screen()
                if button_VOL.is_pressed:
                    sleep_timer_start = time.monotonic()
                    sleep_timer = 15
                    abort_shutdown = 1
                t -=1
                time.sleep(1)
            if abort_shutdown == 0:
                if sleep_shutdn == 1:
                    msg1 = "SHUTTING DOWN..."
                else:
                    msg1 = "STOPPING........"
                 
                msg2 = " "
                display_screen()
                if lcd_lines == 4:
                    msg3 = ""
                    msg4 = ""
                    display_screen()
                time.sleep(3)
                if lcd_type == 0:
                    lcd.backlight(turn_on=False)
                msg1 = " "
                sleep_timer = 0 
                if sleep_shutdn == 1:
                    os.system("shutdown -h now")
            else:
                status()
                msg1 = "Play.." + str(Track_No)[0:5] + txt
                display_screen()
                time.sleep(0.05)
            bl_start = time.monotonic()
            
        # PLAY 
        if button_VOL.is_pressed:
            if lcd_type == 0:
                lcd.backlight(turn_on=True)
            backlight_on = 1
            bl_start = time.monotonic()
            time.sleep(0.1)
            timer1 = time.monotonic()
            msg2 = "HOLD 5s for RADIO"
            if lcd_lines == 4:
                msg3 = ""
                msg4 = ""
            display_screen()
            time.sleep(0.5)
            mode = 3
            md_1 = " "
            md_2 = " "
            md_3 = " "
            while button_VOL.is_pressed and time.monotonic() - timer1 < 5:
                pass
            if time.monotonic() - timer1 < 5 and len(tracks) > 0:
                # determine album length and number of tracks
                cplayed = 0
                md_3 = ">"
                if album_mode == 1:
                    album_length()
                MP3_Play = 1
                mode = 3
            elif time.monotonic() - timer1 < 5 and len(tracks) == 0:
                reload()
            elif time.monotonic() - timer1 >= 5:
                msg1 = " "
                msg2 = " "
                if lcd_lines == 4:
                    msg3 = " "
                    msg4 = " "
                q = subprocess.Popen(["cvlc",Radio_Stns[radio_stn+1]] ,shell=False)
                time.sleep(0.05)
                msg1 = ">Choose Radio Stn"
                msg2 = Radio_Stns[radio_stn][0:length]
                rs = Radio_Stns[radio_stn] + "                "[0:length]
                while button_VOL.is_pressed:
                    pass
                time.sleep(1)
                radio = 1
                mode = 0
                msg1 = ">Choose Radio Stn"
                
        # NEXT ALBUM 
        if next_ == 1 and len(tracks) > 0 and mode == 2:
            next_ = 0
            otrack_no = Track_No
            while titles[1] == old_album and titles[0] == old_artist:
                Track_No +=1
                if Track_No > len(tracks) - 1:
                    Track_No = Track_No - len(tracks)
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            if titles[0] != old_artist and randomed == 0:
                Track_No = otrack_no
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            old_album  = titles[1]
            old_artist = titles[0]
            if lcd_lines == 2:
                msg2 = titles[1][0:length]
            elif lcd_lines == 4:
                msg2 = md_1 + titles[0][0:length]
                msg3 = md_2 + titles[1][0:length]
                msg4 = md_3 + titles[2][0:length]
            time.sleep(0.05)
            display_screen()
            timer3 = time.monotonic()
            bl_start = time.monotonic()

        # NEXT ARTIST 
        if next_ == 1 and len(tracks) > 0 and mode == 1:
            next_ = 0
            while titles[0] == old_artist:
                Track_No +=1
                if Track_No > len(tracks) - 1:
                    Track_No = Track_No - len(tracks)
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            old_artist = titles[0]
            if lcd_lines == 2:
                msg2 = titles[0][0:length]
            elif lcd_lines == 4:
                msg2 = md_1 + titles[0][0:length]
                msg3 = md_2 + titles[1][0:length]
                msg4 = md_3 + titles[2][0:length]
            display_screen()
            
        # NEXT LETTER
        if next_ == 1 and len(tracks) > 0 and mode == 0:
            next_ = 0
            while titles[0][0:1] == old_artist[0:1]:
                Track_No +=1
                if Track_No > len(tracks) - 1:
                    Track_No = Track_No - len(tracks)
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            old_artist = titles[0]
            if lcd_lines == 2:
                msg2 = titles[0][0:length]
            elif lcd_lines == 4:
                msg2 = md_1 + titles[0][0:length]
                msg3 = md_2 + titles[1][0:length]
                msg4 = md_3 + titles[2][0:length]
            display_screen()

        # NEXT TRACK
        if next_ == 1 and len(tracks) > 0 and mode == 3:
            next_ = 0
            otitles = [0,0,0,0,0,0,0]
            otitles[0],otitles[1],otitles[2],otitles[3],otitles[4],otitles[5],otitles[6] = tracks[Track_No].split("/")
            Track_No +=1
            if Track_No > len(tracks) - 1:
                Track_No = Track_No - len(tracks)
            titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            if (otitles[0] != titles[0] or otitles[1] != titles[1]) and randomed == 0:
                Track_No -=1
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            if lcd_lines == 2:
                msg2 = titles[2][0:length]
            elif lcd_lines == 4:
                msg2 = md_1 + titles[0][0:length]
                msg3 = md_2 + titles[1][0:length]
                msg4 = md_3 + titles[2][0:length]
            display_screen()
                
        # PREVIOUS ALBUM 
        if  prev_ == 1 and len(tracks) > 0 and mode == 2:
            prev_ = 0
            otrack_no = Track_No
            while titles[1] == old_album and titles[0] == old_artist:
                Track_No -=1
                if Track_No < 0:
                    Track_No = len(tracks) + Track_No
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            if titles[0] != old_artist and randomed == 0:
                Track_No = otrack_no
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            old_album = titles[1]
            old_artist = titles[0]
            while titles[1] == old_album and titles[0] == old_artist:
                Track_No -=1
                if Track_No < 0:
                    Track_No = len(tracks) + Track_No
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            Track_No +=1
            if Track_No > len(tracks) - 1:
                Track_No = Track_No - len(tracks)
            titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            old_album  = titles[1]
            old_artist = titles[0]
            if lcd_lines == 2:
                msg2 = titles[1][0:length]
            elif lcd_lines == 4:
                msg2 = md_1 + titles[0][0:length]
                msg3 = md_2 + titles[1][0:length]
                msg4 = md_3 + titles[2][0:length]
            display_screen()
            timer3 = time.monotonic()
            bl_start = time.monotonic()

        # PREVIOUS ARTIST 
        if prev_ == 1 and len(tracks) > 0 and mode == 1:
            prev_ = 0
            while titles[0] == old_artist:
                Track_No -=1
                if Track_No < 0:
                    Track_No = len(tracks) + Track_No
                if Track_No > len(tracks) - 1:
                    Track_No = Track_No - len(tracks)
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            old_album  = titles[1]
            old_artist = titles[0]
            while titles[0] == old_artist and titles[1] == old_album:
                Track_No -=1
                if Track_No < 0:
                    Track_No = len(tracks) + Track_No
                if Track_No > len(tracks) - 1:
                    Track_No = Track_No - len(tracks)
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            Track_No +=1
            if Track_No > len(tracks) - 1:
                Track_No = Track_No - len(tracks)
            titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            old_album  = titles[1]
            old_artist = titles[0]
            if lcd_lines == 2:
                msg2 = titles[0][0:length]
            elif lcd_lines == 4:
                msg2 = md_1 + titles[0][0:length]
                msg3 = md_2 + titles[1][0:length]
                msg4 = md_3 + titles[2][0:length]
            display_screen()
                   
        # PREV LETTER
        if  prev_ == 1 and len(tracks) > 0 and mode == 0:
            prev_ = 0
            while titles[0][0:1] == old_artist[0:1]:
                Track_No -=1
                if Track_No < 0:
                    Track_No = len(tracks) + Track_No
                if Track_No > len(tracks) - 1:
                    Track_No = Track_No - len(tracks)
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            old_album  = titles[1]
            old_artist = titles[0]
            while titles[1][0:1] == old_album[0:1] and titles[0] == old_artist:
                Track_No -=1
                if Track_No < 0:
                    Track_No = len(tracks) + Track_No
                if Track_No > len(tracks) - 1:
                    Track_No = Track_No - len(tracks)
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            Track_No +=1
            if Track_No > len(tracks) - 1:
                Track_No = Track_No - len(tracks)
            titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            old_album  = titles[1]
            old_artist = titles[0]
            if lcd_lines == 2:
                msg2 = titles[0][0:length]
            elif lcd_lines == 4:
                msg2 = md_1 + titles[0][0:length]
                msg3 = md_2 + titles[1][0:length]
                msg4 = md_3 + titles[2][0:length]
            display_screen()
                    
            bl_start = time.monotonic()

        # PREVIOUS TRACK
        if prev_ == 1 and len(tracks) > 0 and mode == 3:
            prev_ = 0
            otitles = [0,0,0,0,0,0,0]
            otitles[0],otitles[1],otitles[2],otitles[3],otitles[4],otitles[5],otitles[6] = tracks[Track_No].split("/")
            Track_No -=1
            if Track_No < 0:
                Track_No = len(tracks) - 1
            titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            if (otitles[0] != titles[0] or otitles[1] != titles[1]) and randomed == 0:
                Track_No +=1
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            if lcd_lines == 2:
                msg2 = titles[2][0:length]
            elif lcd_lines == 4:
                msg2 = md_1 + titles[0][0:length]
                msg3 = md_2 + titles[1][0:length]
                msg4 = md_3 + titles[2][0:length]
            display_screen()
           
    # loop while playing Radio
    while radio == 1:
        time.sleep(0.2)
        # read VOLUME rotary encoder 
        Read_Rotary_VOLUME()
        # read SELECT rotary encoder
        Read_Rotor_SELECT()
        # read rotary button    
        if button_SEL.is_pressed:
            backlight_on = 1
            if lcd_type == 0:
                lcd.backlight(turn_on=True)
            bl_start = time.monotonic()
            md_start = time.monotonic()
            mode +=1
            if mode > 4:
                mode = 0
            if mode == 0:
                msg1 = ">Choose Radio Stn"
            if mode == 1:
                mode = 3
            if mode == 4:
                msg1 = ">SLEEP..  " + str(int(sleep_timer))
            display_screen()
            time.sleep(1)

        # backlight timer
        if time.monotonic() - bl_start > bl_timeout and bl_timeout > 0:
            if lcd_type == 0:
                lcd.backlight(turn_on=False)
            elif lcd_type == 1:
                draw.rectangle((0,0,width,height), outline=0, fill=0)
                display.image(image)
                display.show()
            backlight_on = 0
            defaults[0] = boot_mode
            defaults[1] = volume 
            defaults[2] = randomed 
            defaults[3] = album_mode 
            defaults[4] = radio_stn
            defaults[5] = gapless
               
            if save_config == 1:   
               with open(config_file, 'w') as f:
                 for item in defaults:
                   f.write("%s\n" % item)
            save_config = 0
            
        # mode timer
        if time.monotonic() - md_start > md_timeout and mode != 0:
            mode = 0
            defaults[0] = boot_mode
            defaults[1] = volume 
            defaults[2] = randomed 
            defaults[3] = album_mode 
            defaults[4] = radio_stn
            defaults[5] = gapless
               
            if save_config == 1:   
               with open(config_file, 'w') as f:
                 for item in defaults:
                   f.write("%s\n" % item)
            save_config = 0
            
        # sleep_timer timer
        if time.monotonic() - sleep_timer_start > (sleep_timer * 60) and sleep_timer > 0:
            if lcd_type == 0:
                lcd.backlight(turn_on=True)
            bl_start = time.monotonic()
            abort_shutdown = 0
            t = 30
            while t > 0 and abort_shutdown == 0:
                if sleep_shutdn == 1:
                    msg1 = "SHUTDOWN in " + str(t)
                else:
                    msg1 = "STOPPING in " + str(t)
                if button_SEL.is_pressed or button_VOL.is_pressed:
                    sleep_timer_start = time.monotonic()
                    sleep_timer = 15
                    abort_shutdown = 1
                t -=1
                time.sleep(1)
                if sleep_shutdn == 1:
                    msg1 = "SHUTTING DOWN..."
                else:
                    msg1 = "STOPPING........"
                time.sleep(0.05)
                msg2 = " "
                display_screen()
                time.sleep(3)
                if lcd_type == 0:
                    lcd.backlight(turn_on=False)
                msg1 = " "
                display_screen()
                q.kill()
                if sleep_shutdn == 1:
                    os.system("sudo shutdown -h now")
                radio = 0
                sleep_timer = 0
                time.sleep(1)
            bl_start = time.monotonic()
        
        # show station name    
        if mode == 0 and len(Radio_Stns[radio_stn]) > length:
            if a < len(Radio_Stns[radio_stn])-(length-2):
                msg2 = Radio_Stns[radio_stn][a:a+length]
                a +=1
            else:
                a = 0
            display_screen()
        elif mode == 0:
            msg2 = Radio_Stns[radio_stn][0:length]
            display_screen()
            
        # display sleep_timer time left and clock
        now = datetime.datetime.now()
        clock = now.strftime("%H:%M:%S")
        time_left = int(((sleep_timer * 60) - (time.monotonic() - sleep_timer_start))/60)
        if mode == 0:
            if show_clock == 1:
                if sleep_timer > 0:
                    msg1 = str(clock) + " SLP: " + str(time_left)
                else:
                    msg1 = str(clock)
                display_screen()
            elif sleep_timer > 0:
                msg1 =  " SLEEP " + str(time_left)
                display_screen()
                
        # PREVIOUS Radio Station
        if radio_prev == 1:
            radio_prev = 0
            if lcd_type == 0:
                lcd.backlight(turn_on=True)
            bl_start = time.monotonic()
            radio_stn -=2
            if radio_stn < 0:
               radio_stn = len(Radio_Stns) - 2
            q.kill()
            q = subprocess.Popen(["cvlc",Radio_Stns[radio_stn+1]] ,shell=False)
            msg2 = Radio_Stns[radio_stn][0:length]
            display_screen()
            rs = Radio_Stns[radio_stn] + "               "[0:length]
            time.sleep(.25)
            save_config = 1
            
        # NEXT Radio Station
        if radio_next == 1:
            radio_next = 0
            if lcd_type == 0:
                lcd.backlight(turn_on=True)
            bl_start = time.monotonic()
            radio_stn +=2
            if radio_stn > len(Radio_Stns)- 2:
               radio_stn = 0
            q.kill()
            q = subprocess.Popen(["cvlc",Radio_Stns[radio_stn+1]] ,shell=False)
            msg2 = Radio_Stns[radio_stn][0:length]
            display_screen()
            rs = Radio_Stns[radio_stn] + "               "[0:length]
            time.sleep(.25)
            save_config = 1
            
        # STOP
        if button_VOL.is_pressed:
            if lcd_type == 0:
                lcd.backlight(turn_on=True)
            bl_start = time.monotonic()
            q.kill()
            radio = 0
            MP3_Play = 0
            mode = 0
            md_1 = " "
            md_2 = " "
            md_3 = " "
            display_screen()
            if len(tracks) > 0:
                msg1 = ">Set Artist A-Z"
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
                if lcd_lines == 2:
                    msg2 = titles[0][0:length]
                if lcd_lines == 4:
                    msg2 = md_1 + titles[0][0:length]
                    msg3 = md_2 + titles[1][0:length]
                    msg4 = md_3 + titles[2][0:length]
                display_screen()
            time.sleep(0.05)

                   
    # loop while playing MP3 tracks
    while MP3_Play == 1 :
        if trace == 1:
             print("MP3_Play == 1",MP3_Play)
        # read VOLUME rotary encoder 
        Read_Rotary_VOLUME()
        # read SELECT rotary encoder
        Read_Rotor_SELECT()
        if button_SEL.is_pressed:
            backlight_on = 1
            #lcd.backlight(turn_on=True)
            bl_start = time.monotonic()
            md_start = time.monotonic()
        # stop playing if end of album,in album mode
        cplayed +=1
        if cplayed > ctracks and album_mode == 1:
            status()
            msg1 = "Play.." + str(track_n)[0:5] + txt
            MP3_Play = 0
            if trace == 1:
                print("End of Album",cplayed,ctracks)
            mode = 0
            msg1 = ">Set Artist A-Z"
            display_screen()
        # backlight timer
        if time.monotonic() - bl_start > bl_timeout and bl_timeout > 0:
            if lcd_type == 0:
                lcd.backlight(turn_on=False)
            elif lcd_type == 1:
                draw.rectangle((0,0,width,height), outline=0, fill=0)
                display.image(image)
                display.show()
            backlight_on = 0
            defaults[0] = boot_mode
            defaults[1] = volume 
            defaults[2] = randomed 
            defaults[3] = album_mode 
            defaults[4] = radio_stn
            defaults[5] = gapless
               
            if save_config == 1:   
               with open(config_file, 'w') as f:
                 for item in defaults:
                   f.write("%s\n" % item)
            save_config = 0
                 
        # sleep_timer timer
        if time.monotonic() - sleep_timer_start > (sleep_timer * 60) and sleep_timer > 0:
            #lcd.backlight(turn_on=True)
            backlight_on = 1
            bl_start = time.monotonic()
            abort_shutdown = 0
            t = 30
            while t > 0 and abort_shutdown == 0:
                if sleep_shutdn == 1:
                    msg2 = "SHUTDOWN in " + str(t)
                else:
                    msg2 = "STOPPING in " + str(t)
                display_screen()
                if button_VOL.is_pressed:
                    sleep_timer_start = time.monotonic()
                    sleep_timer = 15
                    abort_shutdown = 1
                t -=1
                time.sleep(1)
            if abort_shutdown == 0:
                if sleep_shutdn == 1:
                    msg1 = "SHUTTING DOWN..."
                else:
                    msg1 = "STOPPING........"
                time.sleep(0.05)
                msg2 = " "
                if lcd_lines == 4:
                    msg3 = ""
                    msg4 = ""
                display_screen()
                time.sleep(3)
                if lcd_type == 0:
                    lcd.backlight(turn_on=False)
                backlight_on = 0
                msg1 = " "
                poll = p.poll()
                if poll == None:
                    os.killpg(p.pid,SIGTERM)
                if sleep_shutdn == 1:
                    os.system("sudo shutdown -h now")
                sleep_timer = 0
                MP3_Play = 0
                if trace == 1:
                    print("SLEEP",MP3_Play)
            else:
                status()
                msg1 = "Play.." + str(track_n)[0:5] + txt
                display_screen()
                time.sleep(0.05)
                bl_start = time.monotonic()
            poll = p.poll()
            if poll == None:
                os.killpg(p.pid,SIGTERM)
                time.sleep(1)
        # try reloading tracks if none found
        if len(tracks) == 0:
            reload()
        # try reloading tracks if one selected not found
        if len(tracks) > 0:
            titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            track = titles[3] + "/" + titles[4] + "/" + titles[5] + "/" + titles[6] + "/" + titles[0] + "/" + titles[1] + "/" + titles[2]
            if not os.path.exists (track) :
                reload()
            
        # play selected track
        if MP3_Play == 1 and len(tracks) > 0:
          timer2 = time.monotonic()
          if trace == 1:
              print("play track")
          titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
          if album_mode == 0:
              track_n = str(Track_No+1) + "     "
          else:
              track_n = str(cplayed) + "/" + str(ctracks)
          track = titles[3] + "/" + titles[4] + "/" + titles[5] + "/" + titles[6] + "/" + titles[0] + "/" + titles[1] + "/" + titles[2]
          if mode == 3:
              if album_mode == 0:
                  msg1 = "Track:" + str(track_n)[0:5] + "   0%"
              else:
                  msg1 = "Track:" + str(track_n)[0:5] + "  " + str(played_pc)[-2:] + "%"
              display_screen()
          rpistr = "mplayer " + " -quiet " +  '"' + track + '"'
          time.sleep(0.05)
          if lcd_lines == 2:
              msg2 = titles[2][0:length]
          elif lcd_lines == 4:
              msg2 = md_1 + titles[0][0:length]
              msg3 = md_2 + titles[1][0:length]
              msg4 = md_3 + titles[2][0:length]
          display_screen()
          audio = MP3(track)
          track_len = audio.info.length
          p = subprocess.Popen(rpistr,shell=True,preexec_fn=os.setsid)
          time.sleep(0.05)
          poll = p.poll()
          while poll != None:
            poll = p.poll()
          timer2 = time.monotonic()
          timer1 = time.monotonic()
          xt = 0
          go = 1
          played = time.monotonic() - timer1
          
          # loop while playing selected MP3 track
          while poll == None and track_len - played > gap and (time.monotonic() - sleep_timer_start < (sleep_timer * 60) or sleep_timer == 0):
            time_left = int(((sleep_timer * 60) - (time.monotonic() - sleep_timer_start))/60)
            # read VOLUME rotary encoder 
            Read_Rotary_VOLUME()
            # read SELECT rotary encoder
            Read_Rotor_SELECT()
            # read SELECT rotary button
            if button_SEL.is_pressed:
                backlight_on = 1
                if lcd_type == 0:
                    lcd.backlight(turn_on=True)
                bl_start = time.monotonic()
                md_start = time.monotonic()
                mode +=1
                md_3 = " "
                if mode == 5:
                    mode = 6
                if mode > 6:
                    mode = 0
                if mode < 3:
                    mode = 3
                if mode == 3:
                    msg1 = "Choose Track"
                    md_3 = ">"
                    if lcd_lines == 4:
                        msg4 = md_3 + titles[2][0:length]
                    else:
                        msg2 = titles[2][0:length]
                elif mode == 4:
                    msg1 = ">SLEEP..  " + str(int(sleep_timer))
                elif mode == 6:
                    if gapless == 0:
                        msg1 = ">GAPLESS OFF"
                    else:
                        msg1 = ">GAPLESS ON"
                if lcd_lines == 4:
                    msg4 = md_3 + titles[2][0:length]
                display_screen()
                time.sleep(0.5)
                
            # backlight OFF
            if time.monotonic() - bl_start > bl_timeout and bl_timeout > 0 and backlight_on == 1:
                if lcd_type == 0:
                    lcd.backlight(turn_on=False)
                backlight_on = 0
                defaults[0] = boot_mode
                defaults[1] = volume 
                defaults[2] = randomed 
                defaults[3] = album_mode 
                defaults[4] = radio_stn
                defaults[5] = gapless
                if save_config == 1:   
                    with open(config_file, 'w') as f:
                        for item in defaults:
                            f.write("%s\n" % item)
                    save_config = 0
                
            # mode timer
            if time.monotonic() - md_start > md_timeout and mode != 3:
                mode = 3
                if lcd_lines == 4:
                    md_3 = ">"
                    display_screen()
                
            # get track played time    
            time.sleep(0.2)
            played  = time.monotonic() - timer1
            played_pc = int((played/track_len) *100)
  
            # display Artist / Album / Track names
            if mode == 3: 
                if lcd_lines == 4:
                    msg2 = md_1 + titles[0][0:length]
                    msg3 = md_2 + titles[1][0:length]
                    msg4 = md_3 + titles[2][0:length]
                display_screen()
                played_pc =  "     " + str(played_pc)
                if album_mode == 0:
                    track_n = str(Track_No+1) + "     "
                else:
                    track_n = str(cplayed) + "/" + str(ctracks) + "       "
                if xt == 0 and lcd_lines == 2:
                    msg1 = "Artist:"
                    if lcd_lines == 2 and len(titles[0]) > length:
                        if a < len(titles[0])-(length - 2):
                            msg2 = titles[0][a:a+length]
                            a +=1
                        else:
                            a = 0
                    elif lcd_lines == 2:
                        msg2 = titles[0]
                elif xt == 1 and lcd_lines == 2:
                    msg1 = "Album:"
                    if lcd_lines == 2 and len(titles[1]) > length:
                        if a < len(titles[1])-(length-2):
                            msg2 = titles[1][a:a+length]
                            a +=1
                        else:
                            a = 0
                    elif lcd_lines == 2:
                        msg2 = titles[1]
                elif (xt < 2 and lcd_lines == 4) or (xt == 2 and lcd_lines == 2):
                    msg1 = "Track:" + str(track_n)[0:5] + "  " + str(played_pc)[-2:] + "%"
                   
                    if lcd_lines == 2 and len(titles[2]) > length:
                        if a < len(titles[2])-(length-2):
                            msg2 = titles[2][a:a+length]
                            a +=1
                        else:
                            a = 0
                    elif lcd_lines == 2:
                        msg2 = titles[2]
                elif xt == 3 and sleep_timer != 0 and lcd_lines == 4:
                    time_left = int(((sleep_timer * 60) - (time.monotonic() - sleep_timer_start))/60)
                    msg1 = "SLEEP: " + str(time_left) + " mins"

                elif xt == 4 and show_clock == 1:
                    now = datetime.datetime.now()
                    clock = now.strftime("%H:%M:%S")
                    msg1 = str(clock)
                    if lcd_lines == 2:
                        msg2 = "        "

                elif xt == 5:
                    status()
                    msg1 = "Status...  " +  txt
                    if lcd_lines == 2:
                        if sleep_timer == 0:
                            msg2 = "           "
                        else:
                            time_left = int(((sleep_timer * 60) - (time.monotonic() - sleep_timer_start))/60)
                            msg2 = "SLEEP: " + str(time_left) + " mins"
                tp = timedelta(seconds=played)
                tl = timedelta(seconds=track_len)
                msg5 = str(tp)[0:7] + " of " + str(tl)[0:7]    
                                
                if time.monotonic() - timer2 > 4:      
                    xt +=1
                    timer2 = time.monotonic()
                    if lcd_lines == 2 and xt == 3:
                        msg2 = titles[2][0:length]
                    if xt > 5:
                        xt = 0
                display_screen()
                    
            # check for VOLUME button (STOP)
            if button_VOL.is_pressed:
                if lcd_type == 0:
                    lcd.backlight(turn_on=True)
                bl_start = time.monotonic()
                timer1 = time.monotonic()
                os.killpg(p.pid,SIGTERM)
                msg1 = "Track Stopped"
                display_screen()
                time.sleep(2)
                status()
                mode = -1
                menu = 0
                md_3 = " "
                msg1 = ">Set Artists A-Z"
                if lcd_lines == 2:
                    msg2 = titles[0][0:length]
                elif lcd_lines == 4:
                    msg2 = md_1 + titles[0][0:length]
                    msg3 = md_2 + titles[1][0:length]
                    msg4 = md_3 + titles[2][0:length]
                display_screen()
                time.sleep(0.05)
                go = 0
                backlight_on = 1
                MP3_Play = 0
                
            # NEXT TRACK
            if next_ == 1 and len(tracks) > 0 and mode == 3:
                next_ = 0
                Track_No +=1
                if Track_No > len(tracks) - 1:
                    Track_No = Track_No - len(tracks)
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
                time.sleep(0.05)
                if lcd_lines == 2:
                    msg2 = titles[2][0:length]
                elif lcd_lines == 4:
                    msg2 = md_1 + titles[0][0:length]
                    msg3 = md_2 + titles[1][0:length]
                    msg4 = md_3 + titles[2][0:length]
                display_screen()
                poll = p.poll()
                if poll == None:
                    os.killpg(p.pid,SIGTERM)
                Track_No -=1
                time.sleep(0.5)

            # PREVIOUS TRACK
            if prev_ == 1 and len(tracks) > 0 and mode == 3:
                prev_ = 0
                Track_No -=1
                print(Track_No,fTack_No)
                if Track_No < fTack_No:
                    Track_No = fTack_No
                cplayed -=2
                if cplayed < 0:
                    cplayed = 0
                if Track_No < 0:
                    Track_No =  len(tracks) - 1
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
                time.sleep(0.05)
                if lcd_lines == 2:
                    msg2 = titles[2][0:length]
                elif lcd_lines == 4:
                    msg2 = md_1 + titles[0][0:length]
                    msg3 = md_2 + titles[1][0:length]
                    msg4 = md_3 + titles[2][0:length]
                display_screen()
                poll = p.poll()
                if poll == None:
                    os.killpg(p.pid,SIGTERM)
                Track_No -=1
                if Track_No < 0:
                    Track_No =  len(tracks) - 1
                time.sleep(0.5)
                
            # get current playing status
            poll = p.poll()
          
          # play next track  
          if go == 1:
              Track_No +=1
              if trace == 1:
                  print("Play next track",MP3_Play)
          if Track_No < 0:
              Track_No = len(tracks) + Track_No
          elif Track_No > len(tracks) - 1:
              Track_No = Track_No - len(tracks)
        





            
