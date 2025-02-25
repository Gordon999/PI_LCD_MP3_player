#!/usr/bin/env python3
from gpiozero import Button
import glob
import subprocess
import os, sys
import time
import datetime
import random
from random import shuffle
from mutagen.mp3 import MP3
import alsaaudio
from gpiozero import RotaryEncoder
rotor = RotaryEncoder(13, 5,  wrap=False, max_steps=96)
button1     = 6  # start/stop 
but_button1 = Button(button1)
button2     = 20  # mode (ROTARY ENCODER button)
but_button2 = Button(button2)
from signal import signal, SIGTERM, SIGHUP, pause
from rpi_lcd import LCD
lcd = LCD()
def safe_exit(signum, frame):
    exit(1)
signal(SIGTERM, safe_exit)
signal(SIGHUP, safe_exit)

# version 0.1

# set starting variables
MP3_Play    = 0    # set to 1 to start playing MP3s at boot, else 0
radio       = 0    # set to 1 to start playing radio at boot, else 0
radio_stn   = 0    # selected radio station at startup 
shuffled    = 0    # 0 = Unshuffled, 1 = Shuffled
volume      = 40   # range 0 - 100
use_USB     = 1    # set to 0 if you only use /home/USERNAME/Music/... on SD card
sleep_timer = 0    # sleep_timer timer in minutes, use 15,30,45,60 etc...set to 0 to disable
sleep_shut  = 0    # set to 1 to shutdown when sleep times out
bl_timeout  = 30   # backlight timeout in seconds, set to 0 to disable
show_clock  = 0    # set to 1 to show clock, only use if on web or using RTC
gapless     = 0    # set to 1 for gapless play
gaptime     = 2    # set pre-start time for gapless, in seconds
album_mode  = 0    # set to 1 for Album Mode, will play an album then stop

Radio_Stns = ["R Paradise Rock","http://stream.radioparadise.com/rock-192",
              "R Paradise Main","http://stream.radioparadise.com/mp3-320",
              "R Paradise Mellow","http://stream.radioparadise.com/mellow-192",
              "Radio Caroline","http://sc6.radiocaroline.net:10558/"
              ]

# read Radio_Stns.txt - format: Station Name, Station URL
if os.path.exists ("Radio_Stns.txt"): 
    with open("Radio_Stns.txt","r") as textobj:
        line = textobj.readline()
        while line:
           if line.count(",") == 1:
               a,b = line.split(",")
               Radio_Stns.append(a)
               Radio_Stns.append(b.strip())
           line = textobj.readline()

# initialise parameters
Track_No    = 0
old_album   = ""
old_artist  = ""
titles      = [0,0,0,0,0,0,0]
itles       = [0,0,0,0,0,0,0]
sleep_timer = sleep_timer * 60
freedisk    = ["0","0","0","0"]
old_secs    = "00"
old_secs2   = "00"
bl_on       = 1
album       = 0
stimer      = 0
ctracks     = 0
cplayed     = 0
atimer      = time.monotonic()
aalbum_mode = album_mode
played_pc   = 0
old_rotor   = 0
button_play = 0
next_       = 0
prev_       = 0
mode        = 0
radio_next  = 0
radio_prev  = 0

def reload():
    global tracks
    tracks  = []
    lcd.text("Tracks: " + str(len(tracks)), 1)
    time.sleep(0.05)
    lcd.text("Reloading... ", 2)
    sd_tracks  = glob.glob("/media/" + users[0] + "/*/*/*/*.mp3")
    usb_tracks = glob.glob("/home/" + users[0] + "/Music/*/*/*.mp3")
    titles = [0,0,0,0,0,0,0]
    if len(sd_tracks) > 0:
      for x in range(0,len(sd_tracks)):
        titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = sd_tracks[x].split("/")
        track = titles[4] + "/" + titles[5] + "/" + titles[6] + "/" + titles[0] + "/" + titles[1] + "/" + titles[2] + "/" + titles[3]
        tracks.append(track)
    if len(usb_tracks) > 0:
      for x in range(0,len(usb_tracks)):
        titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = usb_tracks[x].split("/")
        track = titles[4] + "/" + titles[5] + "/" + titles[6] + "/" + titles[0] + "/" + titles[1] + "/" + titles[2] + "/" + titles[3]
        tracks.append(track)
    tracks.sort()
    with open('tracks.txt', 'w') as f:
        for item in tracks:
            f.write("%s\n" % item)
    lcd.text("Tracks: " + str(len(tracks)), 1)
    time.sleep(0.05)
    lcd.text(" ",2)
    time.sleep(2)

def Read_Rotors():
    global volume, mixername, m,old_rotor,MP3_Play,next_,prev_,radio_next,radio_prev,mode,sleep_timer,sleep_timer_start,shuffled,gapless,gap,gaptime,tracks
    if old_rotor != rotor.value:
        if rotor.value < old_rotor:
            old_rotor = rotor.value
            if mode == 7:
                gapless = 0
                lcd.text("GAPLESS OFF ", 1)
                if shuffled == 1:
                    gap = 0
                    shuffle(tracks)
                elif shuffled == 0:
                    gap = 0
                    tracks.sort()
            elif mode == 6:
                shuffled = 0
                lcd.text("SHUFFLED OFF ", 1)
                tracks.sort()
                if gapless == 0:
                    gap = 0
                elif gapless != 0:
                    gap = gaptime
            elif mode == 5:
                sleep_timer +=900
                if sleep_timer > 7200:
                    sleep_timer = 0
                sleep_timer_start = time.monotonic()
                lcd.text("Set SLEEP.. " + str(int(sleep_timer/60)), 1)
            elif mode == 4:
                volume +=2
                lcd.text("Set Volume.. " + str(volume), 1)
                volume = min(volume,100)
                volume = max(volume,0)
                m.setvolume(volume)
                lcd.text("Set Volume.. " + str(volume), 1)
                os.system("amixer -D pulse sset Master " + str(volume) + "%")
                if mixername == "DSP Program":
                    os.system("amixer set 'Digital' " + str(volume + 107))
            elif MP3_Play == 0:
                next_ = 1
            elif MP3_Play == 1:
                mode = 3
                status()
                next_ = 1
            elif radio == 1:
                radio_next = 1
        else:
            old_rotor = rotor.value
            if mode == 7:
                gapless = 1
                lcd.text("GAPLESS ON ", 1)
                if shuffled == 1:
                    gap = gaptime
                    shuffle(tracks)
                elif shuffled == 0:
                    gap = gaptime
                    tracks.sort()
            elif mode == 6:
                shuffled = 1
                lcd.text("SHUFFLED ON ", 1)
                shuffle(tracks)
                if gapless == 0:
                    gap = 0
                elif gapless != 0:
                    gap = gaptime
            elif mode == 5:
                sleep_timer -=900
                if sleep_timer < 0:
                    sleep_timer = 0
                sleep_timer_start = time.monotonic()
                lcd.text("Set SLEEP.. " + str(int(sleep_timer/60)), 1)
            elif mode == 4:
                volume -=2
                lcd.text("Set Volume.. " + str(volume), 1)
                volume = min(volume,100)
                volume = max(volume,0)
                m.setvolume(volume)
                lcd.text("Set Volume.. " + str(volume), 1)
                os.system("amixer -D pulse sset Master " + str(volume) + "%")
                if mixername == "DSP Program":
                    os.system("amixer set 'Digital' " + str(volume + 107))
            elif MP3_Play == 0:
                prev_ = 1
            elif MP3_Play == 1:
                mode = 3
                status()
                prev_ = 1
            elif radio == 1:
                radio_prev = 1

def status():
    global txt,shuffled,gapless,aalbum_mode,sleep_timer
    txt = " "
    if shuffled == 1:
        txt +="R"
    else:
        txt +=" "
    if gapless == 1:
        txt +="G"
    else:
        txt +=" "
    if aalbum_mode == 1:
        txt +="A"
    else:
        txt +=" "
    if sleep_timer > 0:
        txt +="S"
    else:
        txt +=" "

# read previous usb free space of upto 4 usb devices, to see if usb data has changed
if not os.path.exists('freedisk.txt'):
    with open("freedisk.txt", "w") as f:
        for item in freedisk:
            f.write("%s\n" % item)
freedisk = []            
with open("freedisk.txt", "r") as file:
    line = file.readline()
    while line:
         freedisk.append(line.strip())
         line = file.readline()

# find user
users  = []
users.append(os.getlogin())

# check if USB mounted and find USB storage
start = time.monotonic()
lcd.text("Loading...", 1)
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
        lcd.text("Checking for USB...", 1)
        time.sleep(.25)
        lcd.text(" ", 1)
        time.sleep(.25)
    if usb_found > 0:
        # check if usb has changed, if so then reload tracks
        free = ["0","0","0","0"]
        for x in range(0,len(usb)):
            st3 = os.statvfs(usb[x])
            free[x] = str((st3.f_bavail * st3.f_frsize)/1100000)
        for x in range(0,3):
            if str(free[x]) != freedisk[x]:
                with open("freedisk.txt", "w") as f:
                    for item in free:
                        f.write("%s\n" % item)
                reload()
    else:
        freedisk = ["0","0","0","0"]
        with open("freedisk.txt", "w") as f:
                for item in freedisk:
                    f.write("%s\n" % item)

# check for audio mixers
if len(alsaaudio.mixers()) > 0:
    for mixername in alsaaudio.mixers():
        if str(mixername) == "PCM" or str(mixername) == "DSP Program" or str(mixername) == "Master" or str(mixername) == "Capture" or str(mixername) == "Headphone" or str(mixername) == "HDMI":
            m = alsaaudio.Mixer(mixername)
        else:
            m = alsaaudio.Mixer(alsaaudio.mixers()[0])
    m.setvolume(volume)
    os.system("amixer -D pulse sset Master " + str(volume) + "%")
    if mixername == "DSP Program":
        os.system("amixer set 'Digital' " + str(volume + 107))
        
# load MP3 tracks
tracks  = []
if os.path.exists('tracks.txt') and os.path.getsize("tracks.txt") == 0:
    os.remove('tracks.txt')
    
if not os.path.exists('tracks.txt') :
    reload()
else:
    with open("tracks.txt", "r") as file:
        line = file.readline()
        while line:
             tracks.append(line.strip())
             line = file.readline()
lcd.text("Tracks: " + str(len(tracks)), 1)
#rotor = RotaryEncoder(24, 23, wrap=True, max_steps=len(tracks))

if MP3_Play == 1:
    radio = 0
# wait for internet connection
if radio == 1:
    lcd.text("Waiting...", 1)
    time.sleep(10)

if aalbum_mode == 1:
    shuffled = 0

# try reloading tracks if one selected not found
if len(tracks) > 0:
    titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
    track = titles[3] + "/" + titles[4] + "/" + titles[5] + "/" + titles[6] + "/" + titles[0] + "/" + titles[1] + "/" + titles[2]
    if not os.path.exists (track):
        reload()

def album_length():
    # determine album length and number of tracks
    global aalbum_mode,Track_No,tracks,audio,stimer,ctracks
    cplayed = 0
    if aalbum_mode == 1:
        Tack_No = Track_No
        stimer  = 0
        stitles = [0,0,0,0,0,0,0]
        stitles[0],stitles[1],stitles[2],stitles[3],stitles[4],stitles[5],stitles[6] = tracks[Tack_No].split("/")
        talbum = stitles[1]
        tartist = stitles[0]
        while stitles[1] == talbum and stitles[0] == tartist:
            stitles[0],stitles[1],stitles[2],stitles[3],stitles[4],stitles[5],stitles[6] = tracks[Tack_No].split("/")
            strack = stitles[3] + "/" + stitles[4] + "/" + stitles[5] + "/" + stitles[6] + "/" + stitles[0] + "/" + stitles[1] + "/" + stitles[2]
            audio = MP3(strack)
            stimer += audio.info.length
            Tack_No +=1
        audio = MP3(strack)
        stimer -= audio.info.length
        ctracks = Tack_No - Track_No - 1

if aalbum_mode == 1:
    album_length()

if aalbum_mode == 0:
    track_n = str(Track_No+1) + "     "
else:
    track_n = "1/" + str(ctracks) + "       "

status()
    
if shuffled == 1 and gapless == 0:
    gap = 0
    shuffle(tracks)
elif shuffled == 0 and gapless == 0:
    gap = 0
elif shuffled == 1 and gapless != 0:
    gap = gaptime
    shuffle(tracks)
elif shuffled == 0 and gapless != 0:
    gap = gaptime
if len(tracks) > 0:
    if mode == 0:
        lcd.text("Choose Artist A-Z", 1)
    elif mode == 1:
        lcd.text("Choose Artist", 1)
    elif mode == 2:
        lcd.text("Choose Album", 1)
    elif mode == 3:
        lcd.text("Choose Track", 1)
    elif mode == 4:
        lcd.text("Set Volume.. " + str(volume), 1)
    elif mode == 5:
        lcd.text("Set SLEEP..  " + str(int(sleep_timer/60)), 1)
    elif mode == 6:
        if shuffled == 0:
            lcd.text("SHUFFLED OFF", 1)
        else:
            lcd.text("SHUFFLED ON", 1)
    elif mode == 7:
        if gapless == 0:
            lcd.text("GAPLESS OFF", 1)
        else:
            lcd.text("GAPLESS ON", 1)
    time.sleep(0.05)
    titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
    lcd.text(titles[0][0:19], 2)
    lcd.text(titles[1][0:19], 3)
    lcd.text(titles[2][0:19], 4)
else:
    lcd.text("No tracks found...", 1)
    
time.sleep(0.05)

if radio == 1:
    lcd.text(" ", 2)
    q = subprocess.Popen(["mplayer", "-nocache", Radio_Stns[radio_stn+1]] , shell=False)
    lcd.text(Radio_Stns[radio_stn], 1)
    time.sleep(0.05)

sleep_timer_start = time.monotonic()
bl_start    = time.monotonic()
while True:
    # loop while stopped
    while MP3_Play == 0 and radio == 0:
        time.sleep(0.1)
        # read rotary encoder 
        if old_rotor != rotor.value:
            bl_on = 1
            lcd.backlight(turn_on=True)
            bl_start = time.monotonic()
            Read_Rotors()
            old_rotor = rotor.value
            time.sleep(0.25)
        if but_button1.is_pressed:
            lcd.backlight(turn_on=True)
            MP3_Play = 1
        if but_button2.is_pressed:
            lcd.backlight(turn_on=True)
            mode +=1
            if mode > 7:
                mode = 0
            if mode == 0:
                lcd.text("Choose Artist A-Z", 1)
            elif mode == 1:
                lcd.text("Choose Artist", 1)
            elif mode == 2:
                lcd.text("Choose Album", 1)
            elif mode == 3:
                lcd.text("Choose Track", 1)
            elif mode == 4:
                lcd.text("Set Volume.. " + str(volume), 1)
            elif mode == 5:
                lcd.text("Set SLEEP..  " + str(int(sleep_timer/60)), 1)
            elif mode == 6:
                if shuffled == 0:
                    lcd.text("SHUFFLED OFF", 1)
                else:
                    lcd.text("SHUFFLED ON", 1)
            elif mode == 7:
                if gapless == 0:
                    lcd.text("GAPLESS OFF", 1)
                else:
                    lcd.text("GAPLESS ON", 1)
            lcd.text(titles[0][0:19], 2)
            lcd.text(titles[1][0:19], 3)
            lcd.text(titles[2][0:19], 4)
            time.sleep(1)

            
        # display clock
        if show_clock == 1 and time.monotonic() - bl_start > 10:
            now = datetime.datetime.now()
            secs = now.strftime("%S")
            clock = now.strftime("%H:%M:%S")
            t = ""
            for r in range (0,random.randint(0, 5)):
                t += " "
            clock = t + clock
            if secs != old_secs:
                lcd.text(clock, 2)
                time.sleep(0.05)
                old_secs = secs
            lcd.text("",3)
            lcd.text("",4)
                
        # backlight OFF timer
        if time.monotonic() - bl_start > bl_timeout and bl_timeout > 0:
            lcd.backlight(turn_on=False)
            bl_on = 0
            
        # sleep_timer timer
        if time.monotonic() - sleep_timer_start > sleep_timer and sleep_timer > 0:
            lcd.backlight(turn_on=True)
            bl_start = time.monotonic()
            abort_sd = 0
            t = 30
            while t > 0 and abort_sd == 0:
                if sleep_shut == 1:
                    lcd.text("SHUTDOWN in " + str(t), 2)
                else:
                    lcd.text("STOPPING in " + str(t), 2)
                if but_button1.is_pressed:
                    sleep_timer_start = time.monotonic()
                    sleep_timer = 900
                    abort_sd = 1
                t -=1
                time.sleep(1)
            if abort_sd == 0:
                if sleep_shut == 1:
                    lcd.text("SHUTTING DOWN...", 1)
                else:
                    lcd.text("STOPPING........", 1)
                lcd.text(" ", 2)
                lcd.text("",3)
                lcd.text("",4)
                time.sleep(3)
                lcd.backlight(turn_on=False)
                lcd.text(" ", 1)
                sleep_timer = 0 
                if sleep_shut == 1:
                    os.system("sudo shutdown -h now")
            else:
                status()
                lcd.text("Play.." + str(Track_No)[0:5] + txt, 1)
                time.sleep(0.05)

            bl_start = time.monotonic()
            
        # PLAY 
        if but_button1.is_pressed:
            lcd.backlight(turn_on=True)
            bl_on = 1
            bl_start = time.monotonic()
            time.sleep(0.1)
            timer1 = time.monotonic()
            album = 0
            lcd.text("HOLD 5s for RADIO", 2)
            lcd.text("",3)
            lcd.text("",4)
            time.sleep(0.5)
            mode = 3
            while but_button1.is_pressed and time.monotonic() - timer1 < 5:
                pass
            if time.monotonic() - timer1 < 5 and len(tracks) > 0:
                # determine album length and number of tracks
                cplayed = 0
                if aalbum_mode == 1:
                    Tack_No = Track_No
                    stimer  = 0
                    stitles = [0,0,0,0,0,0,0]
                    stitles[0],stitles[1],stitles[2],stitles[3],stitles[4],stitles[5],stitles[6] = tracks[Tack_No].split("/")
                    talbum = stitles[1]
                    tartist = stitles[0]
                    while stitles[1] == talbum and stitles[0] == tartist:
                        stitles[0],stitles[1],stitles[2],stitles[3],stitles[4],stitles[5],stitles[6] = tracks[Tack_No].split("/")
                        strack = stitles[3] + "/" + stitles[4] + "/" + stitles[5] + "/" + stitles[6] + "/" + stitles[0] + "/" + stitles[1] + "/" + stitles[2]
                        audio = MP3(strack)
                        stimer += audio.info.length
                        Tack_No +=1
                    audio = MP3(strack)
                    stimer -= audio.info.length
                    ctracks = Tack_No - Track_No - 1
                atimer = time.monotonic()
                MP3_Play = 1
            elif time.monotonic() - timer1 < 5 and len(tracks) == 0:
                reload()
            elif time.monotonic() - timer1 >= 5:
                lcd.text(" ",1)
                lcd.text(" ",2)
                lcd.text("",3)
                lcd.text("",4)
                q = subprocess.Popen(["mplayer", "-nocache", Radio_Stns[radio_stn+1]] , shell=False)
                time.sleep(0.05)
                lcd.text(Radio_Stns[radio_stn], 2)
                rs = Radio_Stns[radio_stn] + "                "[0:15]
                while but_button1.is_pressed:
                    pass
                time.sleep(1)
                radio = 1
                
        # NEXT ALBUM 
        if next_ == 1 and len(tracks) > 0 and mode == 2:
            lcd.backlight(turn_on=True)
            time.sleep(0.2)
            next_ = 0
            while titles[1] == old_album and titles[0] == old_artist:
                Track_No +=1
                if Track_No > len(tracks) - 1:
                    Track_No = Track_No - len(tracks)
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            old_album  = titles[1]
            old_artist = titles[0]
            time.sleep(0.05)
            lcd.text(titles[0][0:19], 2)
            lcd.text(titles[1][0:19], 3)
            lcd.text(titles[2][0:19], 4)
            time.sleep(0.05)
            timer3 = time.monotonic()
            album = 1
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
            time.sleep(0.05)
            lcd.text(titles[0][0:19], 2)
            lcd.text(titles[1][0:19], 3)
            lcd.text(titles[2][0:19], 4)
            
        # NEXT LETTER
        if next_ == 1 and len(tracks) > 0 and mode == 0:
            next_ = 0
            print(titles[0],old_artist)
            while titles[0][0:1] == old_artist[0:1]:
                Track_No +=1
                if Track_No > len(tracks) - 1:
                    Track_No = Track_No - len(tracks)
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            old_artist = titles[0]
            time.sleep(0.05)
            lcd.text(titles[0][0:19], 2)
            lcd.text(titles[1][0:19], 3)
            lcd.text(titles[2][0:19], 4)

        # NEXT TRACK
        if next_ == 1 and len(tracks) > 0 and mode == 3:
            next_ = 0
            Track_No +=1
            if Track_No > len(tracks) - 1:
                Track_No = Track_No - len(tracks)
            titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            time.sleep(0.05)
            lcd.text(titles[0][0:19], 2)
            lcd.text(titles[1][0:19], 3)
            lcd.text(titles[2][0:19], 4)
                       
                
        # PREVIOUS ALBUM 
        if  prev_ == 1 and len(tracks) > 0 and mode == 2:
            lcd.backlight(turn_on=True)
            prev_ = 0
            while titles[1] == old_album and titles[0] == old_artist:
                Track_No -=1
                if Track_No < 0:
                    Track_No = len(tracks) + Track_No
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
            lcd.text(titles[0][0:19], 2)
            lcd.text(titles[1][0:19], 3)
            lcd.text(titles[2][0:19], 4)
            time.sleep(0.05)
            timer3 = time.monotonic()
            album = 1
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
                    while titles[1] == old_album:
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
                    lcd.text(titles[0][0:19], 2)
                    lcd.text(titles[1][0:19], 3)
                    lcd.text(titles[2][0:19], 4)
                   
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
                    lcd.text(titles[0][0:19], 2)
                    lcd.text(titles[1][0:19], 3)
                    lcd.text(titles[2][0:19], 4)
                    
                    bl_start = time.monotonic()

        # PREVIOUS TRACK
        if prev_ == 1 and len(tracks) > 0 and mode == 3:
            prev_ = 0
            Track_No -=1
            if Track_No < 0:
                Track_No = len(tracks) - 1
            titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            time.sleep(0.05)
            lcd.text(titles[0][0:19], 2)
            lcd.text(titles[1][0:19], 3)
            lcd.text(titles[2][0:19], 4)
            
           
    # loop while playing Radio
    while radio == 1:
        mode = 4
        time.sleep(0.2)
        # read rotary encoder
        if old_rotor != rotor.value:
            bl_on = 1
            lcd.backlight(turn_on=True)
            bl_start = time.monotonic()
            Read_Rotors()
            old_rotor = rotor.value
            time.sleep(0.25)
        # read rotary button    
        if but_button2.is_pressed:
            bl_on = 1
            lcd.backlight(turn_on=True)
            bl_start = time.monotonic()
            mode +=1
            if mode > 5:
                mode = 5
            if mode < 4:
                mode = 4
            if mode == 4:
                lcd.text("Set Volume.. " + str(volume), 1)
            elif mode == 5:
                lcd.text("Set SLEEP..  " + str(int(sleep_timer/60)), 1)

        # backlight timer
        if time.monotonic() - bl_start > bl_timeout and bl_timeout > 0:
            lcd.backlight(turn_on=False)
            bl_on = 0
            
        # sleep_timer timer
        if time.monotonic() - sleep_timer_start > sleep_timer and sleep_timer > 0:
            lcd.backlight(turn_on=True)
            bl_start = time.monotonic()
            abort_sd = 0
            t = 30
            while t > 0 and abort_sd == 0:
                if sleep_shut == 1:
                    lcd.text("SHUTDOWN in " + str(t), 1)
                else:
                    lcd.text("STOPPING in " + str(t), 1)
                if button_sleep.is_pressed:
                    sleep_timer_start = time.monotonic()
                    sleep_timer = 900
                    abort_sd = 1
                t -=1
                time.sleep(1)
                if sleep_shut == 1:
                    lcd.text("SHUTTING DOWN...", 1)
                else:
                    lcd.text("STOPPING........", 1)
                time.sleep(0.05)
                lcd.text(" ", 2)
                time.sleep(3)
                lcd.backlight(turn_on=False)
                lcd.text(" ", 1)
                q.kill()
                if sleep_shut == 1:
                    os.system("sudo shutdown -h now")
                radio = 0
                sleep_timer = 0
                time.sleep(1)
            bl_start = time.monotonic()
            
        # display sleep_timer time left and clock
        now = datetime.datetime.now()
        clock = now.strftime("%H:%M:%S")
        secs = now.strftime("%S")
        time_left = int((sleep_timer - (time.monotonic() - sleep_timer_start))/60)
        t = ""
        if sleep_timer > 0:
            clock = str(time_left) + " " + clock
        for r in range (0,random.randint(0, 5)):
            t += " "
        clock = t + clock 
        rs = rs[1:16] + rs[0:1]
        if radio == 1:
            lcd.text(rs, 2)
        if secs != old_secs:
            if sleep_timer > 0:
                if show_clock == 0:
                    t = ""
                    for r in range (0,random.randint(0, 12)):
                           t += " "
                    lcd.text( t + str(time_left), 2)
                else:
                    lcd.text(clock, 2)
            elif show_clock == 1:
                lcd.text(clock, 2)
                time.sleep(0.2)
            old_secs = secs
            
                
        # PREVIOUS Radio Station
        if radio_prev == 1:
            radio_prev = 0
            lcd.backlight(turn_on=True)
            bl_start = time.monotonic()
            radio_stn -=2
            if radio_stn < 0:
               radio_stn = len(Radio_Stns) - 2
            q.kill()
            q = subprocess.Popen(["mplayer", "-nocache", Radio_Stns[radio_stn+1]] , shell=False)
            lcd.text(Radio_Stns[radio_stn], 2)
            rs = Radio_Stns[radio_stn] + "               "[0:15]
            time.sleep(1)
            
        # NEXT Radio Station
        if radio_next == 1:
            radio_next = 0
            lcd.backlight(turn_on=True)
            bl_start = time.monotonic()
            radio_stn +=2
            if radio_stn > len(Radio_Stns)- 2:
               radio_stn = 0
            q.kill()
            q = subprocess.Popen(["mplayer", "-nocache", Radio_Stns[radio_stn+1]] , shell=False)
            lcd.text(Radio_Stns[radio_stn], 2)
            rs = Radio_Stns[radio_stn] + "               "[0:15]
            time.sleep(1)
            
        # STOP
        if but_button1.is_pressed:
            lcd.backlight(turn_on=True)
            bl_start = time.monotonic()
            q.kill()
            radio = 0
            MP3_Play = 0
            mode = 0
            lcd.text("Choose Artist A-Z", 1)
            titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
            lcd.text(titles[0][0:19], 2)
            lcd.text(titles[1][0:19], 3)
            lcd.text(titles[2][0:19], 4)
            time.sleep(0.05)

                   
    # loop while playing MP3 tracks
    while MP3_Play == 1 :
        # read rotary encoder
        if old_rotor != rotor.value:
            bl_on = 1
            lcd.backlight(turn_on=True)
            bl_start = time.monotonic()
            Read_Rotors()
            old_rotor = rotor.value
            time.sleep(0.25)
        if but_button2.is_pressed:
            bl_on = 1
            lcd.backlight(turn_on=True)
            bl_start = time.monotonic()
        # stop playing if end of album, in album mode
        cplayed +=1
        if cplayed > ctracks and aalbum_mode == 1:
            status()
            lcd.text("Play.." + str(track_n)[0:5] + txt, 1)
            MP3_Play = 0
            mode = 0
            lcd.text("Choose Artist A-Z", 1)
        # backlight timer
        if time.monotonic() - bl_start > bl_timeout and bl_timeout > 0:
            lcd.backlight(turn_on=False)
            lcd.text(" ", 1)
            time.sleep(0.05)
            lcd.text(" ", 2)
            lcd.text("",3)
            lcd.text("",4)
            time.sleep(0.05)
            bl_on = 0
        # sleep_timer timer
        if time.monotonic() - sleep_timer_start > sleep_timer and sleep_timer > 0:
            lcd.backlight(turn_on=True)
            bl_on = 1
            bl_start = time.monotonic()
            abort_sd = 0
            t = 30
            while t > 0 and abort_sd == 0:
                if sleep_shut == 1:
                    lcd.text("SHUTDOWN in " + str(t), 2)
                else:
                    lcd.text("STOPPING in " + str(t), 2)
                if button_sleep.is_pressed:
                    sleep_timer_start = time.monotonic()
                    sleep_timer = 900
                    abort_sd = 1
                t -=1
                time.sleep(1)
            if abort_sd == 0:
                if sleep_shut == 1:
                    lcd.text("SHUTTING DOWN...", 1)
                else:
                    lcd.text("STOPPING........", 1)
                time.sleep(0.05)
                lcd.text(" ", 2)
                if lcd_lines == 4:
                    lcd.text("",3)
                    lcd.text("",4)
                time.sleep(3)
                lcd.backlight(turn_on=False)
                bl_on = 0
                lcd.text(" ", 1)
                poll = p.poll()
                if poll == None:
                    os.killpg(p.pid, SIGTERM)
                if sleep_shut == 1:
                    os.system("sudo shutdown -h now")
                sleep_timer = 0
                MP3_Play = 0
            else:
                status()
                lcd.text("Play.." + str(track_n)[0:5] + txt, 1)
                time.sleep(0.05)
                bl_start = time.monotonic()
            poll = p.poll()
            if poll == None:
                os.killpg(p.pid, SIGTERM)
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
          titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
          if aalbum_mode == 0:
              track_n = str(Track_No+1) + "     "
          else:
              track_n = str(cplayed) + "/" + str(ctracks)
          track = titles[3] + "/" + titles[4] + "/" + titles[5] + "/" + titles[6] + "/" + titles[0] + "/" + titles[1] + "/" + titles[2]
          if aalbum_mode == 0:
              lcd.text("Track:" + str(track_n)[0:5] + "   0%", 1)
          else:
              lcd.text("Track:" + str(track_n)[0:5] + "  " + str(played_pc)[-2:] + "%", 1)
          rpistr = "mplayer " + " -quiet " +  '"' + track + '"'
          time.sleep(0.05)
          lcd.text(titles[0][0:19], 2)
          lcd.text(titles[1][0:19], 3)
          lcd.text(titles[2][0:19], 4)
          audio = MP3(track)
          track_len = audio.info.length
          p = subprocess.Popen(rpistr, shell=True, preexec_fn=os.setsid)
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
          while poll == None and track_len - played > gap and (time.monotonic() - sleep_timer_start < sleep_timer or sleep_timer == 0):
            time_left = int((sleep_timer - (time.monotonic() - sleep_timer_start))/60)
            # read rotary encoder
            if old_rotor != rotor.value:
                bl_on = 1
                lcd.backlight(turn_on=True)
                bl_start = time.monotonic()
                Read_Rotors()
                old_rotor = rotor.value
                time.sleep(0.25)
            if but_button2.is_pressed:
                bl_on = 1
                lcd.backlight(turn_on=True)
                bl_start = time.monotonic()
                mode +=1
                if mode > 7:
                    mode = 0
                if mode < 3:
                    mode = 3
                if mode == 3:
                    lcd.text("Choose Track", 1)
                elif mode == 4:
                    lcd.text("Set Volume.. " + str(volume), 1)
                elif mode == 5:
                    lcd.text("Set SLEEP..  " + str(int(sleep_timer/60)), 1)
                elif mode == 6:
                    if shuffled == 0:
                        lcd.text("SHUFFLED OFF", 1)
                    else:
                        lcd.text("SHUFFLED ON", 1)
                elif mode == 7:
                    if gapless == 0:
                        lcd.text("GAPLESS OFF", 1)
                    else:
                        lcd.text("GAPLESS ON", 1)
                
            # backlight OFF
            if time.monotonic() - bl_start > bl_timeout and bl_timeout > 0 and bl_on == 1:
                lcd.backlight(turn_on=False)
                lcd.text(" ", 1)
                time.sleep(0.05)
                lcd.text(" ", 2)
                time.sleep(0.05)
                lcd.text("",3)
                lcd.text("",4)
                bl_on = 0
                
            # display clock
            if show_clock == 1 and bl_on == 0:
                now = datetime.datetime.now()
                clock = now.strftime("%H:%M:%S")
                secs = now.strftime("%S")
                t = ""
                for r in range (0,random.randint(0, 12)):
                    t += " "
                clock = t + clock 
                if secs != old_secs2 :
                    lcd.text(clock, 2)
                    time.sleep(0.05)
                    old_secs2 = secs
                
            time.sleep(0.2)
            if aalbum_mode == 0:
                played  = time.monotonic() - timer1
                played_pc = int((played/track_len) *100)
            else:
                aplayed = time.monotonic() - atimer
                played_pc = int((aplayed/(stimer)) *100)
            

            # display Artist / Album / Track names
            if time.monotonic() - timer2 > 2 and bl_on == 1:
                lcd.text(titles[0][0:19], 2)
                lcd.text(titles[1][0:19], 3)
                lcd.text(titles[2][0:19], 4)
  
                timer2    = time.monotonic()
                played_pc =  "     " + str(played_pc)
                if aalbum_mode == 0:
                    track_n = str(Track_No+1) + "     "
                else:
                    track_n = str(cplayed) + "/" + str(ctracks) + "       "
                if xt < 2:
                    lcd.text("Track:" + str(track_n)[0:5] + "  " + str(played_pc)[-2:] + "%", 1)
                    time.sleep(0.05)
                elif xt == 2:
                    status()
                    lcd.text("Status...  " +  txt, 1)
                    time.sleep(0.05)
                if xt == 3 and sleep_timer != 0:
                    time_left = int((sleep_timer - (time.monotonic() - sleep_timer_start))/60)
                    lcd.text("SLEEP: " + str(time_left) + " mins", 1)
                    time.sleep(0.05)
                if xt == 4 and show_clock == 1:
                    # display clock
                    now = datetime.datetime.now()
                    clock = now.strftime("%H:%M:%S")
                    lcd.text(clock, 1)
                    time.sleep(0.05)
                xt +=1
                if xt > 4:
                    xt = 0
                    
            # check for PLAY (STOP) key
            if  but_button1.is_pressed:
                lcd.backlight(turn_on=True)
                bl_start = time.monotonic()
                timer1 = time.monotonic()
                os.killpg(p.pid, SIGTERM)
                lcd.text("Track Stopped", 1)
                time.sleep(2)
                status()
                mode = 0
                lcd.text("Choose Artist A-Z", 1)
                lcd.text(titles[0][0:19], 2)
                lcd.text(titles[1][0:19], 3)
                lcd.text(titles[2][0:19], 4)
                time.sleep(0.05)
                go = 0
                bl_on = 1
                MP3_Play = 0
                
            # NEXT TRACK
            if next_ == 1 and len(tracks) > 0 and mode == 3:
                next_ = 0
                Track_No +=1
                if Track_No > len(tracks) - 1:
                    Track_No = Track_No - len(tracks)
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
                if aalbum_mode == 0:
                    track_n = str(Track_No+1) + "     "
                else:
                    album_length()
                    track_n = "1/" + str(ctracks) + "       "
                lcd.text("Play.." + str(track_n)[0:5] + txt, 1)
                time.sleep(0.05)
                lcd.text(titles[0][0:19], 2)
                lcd.text(titles[1][0:19], 3)
                lcd.text(titles[2][0:19], 4)
                poll = p.poll()
                if poll == None:
                    os.killpg(p.pid, SIGTERM)
                Track_No -=1
                time.sleep(0.5)

            # PREVIOUS TRACK
            if prev_ == 1 and len(tracks) > 0 and mode == 3:
                prev_ = 0
                Track_No -=1
                if Track_No < 0:
                    Track_No =  len(tracks) - 1
                titles[0],titles[1],titles[2],titles[3],titles[4],titles[5],titles[6] = tracks[Track_No].split("/")
                if aalbum_mode == 0:
                    track_n = str(Track_No+1) + "     "
                else:
                    album_length()
                    track_n = "1/" + str(ctracks) + "       "
                lcd.text("Play.." + str(track_n)[0:5] + txt, 1)
                time.sleep(0.05)
                lcd.text(titles[0][0:19], 2)
                lcd.text(titles[1][0:19], 3)
                lcd.text(titles[2][0:19], 4)
                poll = p.poll()
                if poll == None:
                    os.killpg(p.pid, SIGTERM)
                Track_No -=1
                if Track_No < 0:
                    Track_No =  len(tracks) - 1
                time.sleep(0.5)
                

            poll = p.poll()
            
          if go == 1:
            Track_No +=1
          if Track_No < 0:
            Track_No = len(tracks) + Track_No
          elif Track_No > len(tracks) - 1:
            Track_No = Track_No - len(tracks)
        





            
