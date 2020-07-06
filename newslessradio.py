"""Newsless Radio 
Version 1 - Apr-Jun 2020
Uses Adafruit Compatible  I2C RGB character LCD Shield
Opens radio streams using VLC Player functions
Streams are saved/listed in "stations.txt"
Allows streams to be switched on a timed basis

Set your own schedule for listening, or have streams switch every 30, 60 mins etc
Cobbled together by ad.johnson@ntlworld.com as a way of avoiding news bulletins in this time of universal propaganda.
If you like this program, use any code or get some kind of benefit from it, please visit https://cvpandemicinvestigation.com/
"""
from  time import gmtime, strftime,sleep,localtime
import board
import busio
import adafruit_character_lcd.character_lcd_rgb_i2c as character_lcd
import os
import shlex
import re
import socket
import vlc
import urllib.request
import random
from subprocess import Popen, PIPE

#Menu states
NORMAL_MENU=0
STATION_SEL = 1
RELOAD_STATIONS = 2
CONNECTION_STATE = 3
LCD_MENU = 4


#Initialise variables.
menu_state=0
next_menu_state = 0
sub_menu_option=0
showing_menu_options=False
lcd_timeout = 30
change_station_period=0
old_change_station_period=0

last_update_string=""
scroll_counter = 0
station_list = []
num_stations = 0
stationFilename = "stations.txt"
station_times_list=[]
news_times_list=[]
alternate_stations=[]
current_station_no=0
next_station_no=0
exit_flag=False
last_station_no=0
menu_timeout=0
power_off_timer=0

num_stations = 0
lcd_timeout=0
lcd_timer=0

#Are we/were we at a news bulletin time ?
news_state=False
last_news_state=False
scroll_counter = 0

#These are invoked when we want to change the volume or mute the audio.
getMixerCommand = "amixer sget PCM"
setVolumeCommand = "amixer -q set PCM "
toggleMuteCommand = "amixer -q set PCM toggle"
#This is used to find the current system volume when the program is loaded
findVolumeRegex = ".*Playback (.*)\[(.*)%\] \[(.*)\] \[(.*)\]"
regex = re.compile(findVolumeRegex)

#Variables/Lists for storing station information
station_list = []
stationFilename = "stations.txt"
station_times_list=[]
news_times_list=[]
switch_to_station_no=[]

#Set up VLC media player stuff
instance = vlc.Instance('--input-repeat=-1', '--fullscreen')

#Reloard the stations from the text file.
def reload_stations(sub_menu_option):
    if sub_menu_option==1:
        load_stations()
        goToStation(0)

#This function uses the "old" Linux connection names.
def check_or_reset_connection(sub_menu_option):
    if sub_menu_option==0:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        lcd.clear()
        try:
            urllib.request.urlopen("http://google.com") #Python 3.x
            lcd.message="Connection OK\n" + s.getsockname()[0]
        except:
            lcd.message="Not connected"
        sleep(3)
    else:
        os.system ("sudo ifdown wlan0")
        os.system ("sudo ifdown eth0")
        sleep (2)
        os.system ("sudo ifup wlan0")
        os.system ("sudo ifup eth0")
    
#Set the LCD backlight timeout.    
def set_lcd_backlight(sub_menu_option):        
    global lcd_timeout,lcd_timer
    
    lcd_timeout = lcd_timer = sub_menu_option*30
        
#Menu options are stored in this array - along with sub-menu options - should be self-explanatory.  
menu_texts=[["",""],
            ["Mute","Toggle"],
            ["AutoChange ","Off","30 mins","60 mins","90 mins","120 mins"],
            ["LCD Backlight","Always on","30s Timeout"],
            ["Reload Stations","No","Yes"],
            ["Connection State","View","Reset"],
            ["Shutdown","No","Yes"]]


####Define VLC player
player=instance.media_player_new()


####Set up the stuff for the LCD keypad and display.
# Modify this if you have a different sized Character LCD
lcd_columns = 16
lcd_rows = 2
# Initialise I2C bus.
i2c = busio.I2C(board.SCL, board.SDA)
# Initialise the LCD class
lcd = character_lcd.Character_LCD_RGB_I2C(i2c, lcd_columns, lcd_rows)
sleep(0.2)
lcd.clear()
#Switch on LED backlight (This code will need changing because I wired my non-working LCD backlight to the blue LED only on my cheapo display)
sleep(0.2)
lcd.color = [0, 0, 10]

#Handle left and right keypresses on keypad selector.
def left_right_pressed(left_right_val):
    global sub_menu_option,menu_timeout
    if (menu_state != 0):
        sub_menu_option=sub_menu_option + left_right_val
        sub_menu_option=sub_menu_option%(len(menu_texts[menu_state])-1)
        lcd.clear()
        lcd.message=menu_texts[menu_state][0] + "\n" + menu_texts[menu_state][sub_menu_option+1]
    else:
        setNextStation(left_right_val)
        menu_timeout=5

#Handle up and down keypresses on keypad selector.
   
def up_down_pressed(up_down_value):
    global menu_state,menu_timeout,showing_menu_options
    if (menu_state!=0):
        if (not showing_menu_options):
            menu_state = menu_state + up_down_value
            if menu_state == 0:
                menu_state += up_down_value
                
            menu_state=menu_state%len(menu_texts)
            lcd.clear()
            lcd.message=menu_texts[menu_state][0]
    else:
        setNewVolume(-up_down_value)
        menu_timeout=0

#Handle select key press - logic is a bit more complicated due to state machine usage!
def select_pressed():
    global menu_state, menu_timeout, sub_menu_option,next_station_no,current_station_no,next_menu_state, showing_menu_options
    global change_station_period,old_change_station_period
    
    
    if (menu_state==0):
        #Check for station selection change and action that is needs be
        if (next_station_no != current_station_no):
            goToStation(next_station_no)
            update_display()
            return
        else:
            #Show the top menu
            menu_state=next_menu_state=1
            lcd.clear()
            lcd.message=menu_texts[menu_state][0] + "\n"
            menu_timeout=10
            return

    #Show the options for the selected menu
    if (showing_menu_options==False):
        showing_menu_options=True
        #menu_state=next_menu_state
        menu_timeout=10
        lcd.clear()
        lcd.message=menu_texts[menu_state][0] + "\n" + menu_texts[menu_state][1]
        sub_menu_option=0
    else:
        if menu_state==1:
            toggleMute()
        elif menu_state==2:
            change_station_period=old_change_station_period = sub_menu_option *30
        elif menu_state==3:
            set_lcd_backlight(sub_menu_option)
        elif menu_state==4:
            reload_stations(sub_menu_option)
        elif menu_state==5:
            check_or_reset_connection(sub_menu_option)
        elif menu_state==6:
            if (sub_menu_option==1):
                os.system ("sudo shutdown now")
                
        menu_timeout=1
        menu_state=next_menu_state=0
        showing_menu_options=False
        sleep(1)

#Load the station list from the file.        
def load_stations():
    global station_list, news_times_list, station_times_list,num_stations
    stationsFile = open(stationFilename, 'r')
    lines = stationsFile.read().splitlines()
    stationsFile.close()
    num_stations = len(lines)
    station_list = []
    station_times_list=[]
    news_times_list=[]
    for line in lines:
        splitLine = line.split("|")
        #print (splitLine)
        station_list.append(splitLine)
        ##How many sections have been specified.
        line_sections = len(splitLine) 
        if line_sections > 2:
            station_times_list.append (splitLine[2].split(","))
        else:
            station_times_list.append ("")
            
        if line_sections > 3:
            news_times_list.append (splitLine[3].split(","))
        else:
            news_times_list.append ("")

        if line_sections > 4:
            alternate_stations.append(int(splitLine[4])-1)
        else:
            alternate_stations.append(-1)
#This function goes through the station schedule/time list and works out whether a switch is needed.
#This checks the "switch to" channel times)
def check_station_times(current_day_minute,station_times,station_no):
    global current_station_no
    
    #Go through the list of times loaded in from the file.
    for j in range (0, len(station_times)):
        #Have any station times been specified?
        if len(station_times[j].strip()):
            #Get the listed start and end times for a station.
            start_time,end_time=station_times[j].split("-")
            start_time=start_time.strip()
            end_time=end_time.strip()
            
            #Calculate the specified start and end minute for the period.
            day_start_minute=int(start_time[:-3]) * 60 + int(start_time[-2:])
            day_end_minute=int(end_time[:-3]) * 60 + int(end_time[-2:])

            #print (station_no, "Curr Min: ",current_day_minute, day_start_minute,day_end_minute)
            #Check if we need to change to a different station.
            if current_day_minute >= day_start_minute and current_day_minute < day_end_minute:
                print ("Switch to", station_no)
                return station_no
    
    return current_station_no
    
#Similar to the previous function, this function checks the news bulletin time list (or the "switch away" from channel times)
def check_news_times(current_day_minute,news_times):
    global current_station_no
    #Go through the list of times loaded in from the file.
    #News time is specified in Start Hour:End Hour = HourMinute:Length
    for j in range (0, len (news_times)):
        #Have any news times been specified?
        if len (news_times[j].strip()):
            #Get the listed start and end times for a station.
            news_elements=news_times[j].split("=")
            #print (news_elements)
            start_hour,end_hour=news_elements[0].split("-")
            start_hour=start_hour.strip()
            end_hour=end_hour.strip()
            start_minute,news_length=news_elements[1].split(":")
            start_minute.strip()
            news_length.strip()
            #print ("News Hours",start_hour, end_hour, start_minute, news_length)
            #Check the range of given times for the news.
            for hour in range (int(start_hour),int(end_hour)):
                #Calculate the specified start and end minute for the period.
                day_start_minute=int(hour) * 60 + int(start_minute)
                day_end_minute=day_start_minute + int(news_length)
            
                #print (day_start_minute,day_end_minute)
                #Check if we need to change to a different station.
                if current_day_minute >= day_start_minute and current_day_minute < day_end_minute:
                    return True
    return False

#This is called from the main loop after a time delay there and calls the 2 functions above to check when a switch is needed.
def check_time_table(current_day_minute):
    global last_station_no,current_station_no,news_state,last_news_state
    
    new_station = current_station_no
    if (news_state):
        #Get news times for the channel previously selected
        news_times = news_times_list[last_station_no]
    else:
        #Get news times for the channel now selected
        news_times = news_times_list[current_station_no]
        
    #Check if news has started on the channel
    news_state=check_news_times(current_day_minute,news_times)
    if (last_news_state != news_state):
        last_news_state=news_state
        #News has started
        if (news_state):
            #Set to alternate station
            print ("News started")
            new_station = alternate_stations[new_station]
        else:
            #News has finished - set station back to what it was
            print ("News finished")
            new_station = last_station_no
    else:
        #Check if there is a news bulletin flagged - if so, don't switch stations yet...
        if (not news_state):
            for station_no in range(0, len(station_times_list)):
                station_times = station_times_list[station_no]
                
                if len(station_times)>0:
                   new_station=check_station_times(current_day_minute,station_times,station_no)
                   if (new_station !=current_station_no):
                       break
            
    if (new_station != current_station_no):
         goToStation(int(new_station))


#This function updates the LCD to show the current channel name and also the song playing!    
def update_display():
    global last_update_string, scroll_counter,media

    #Get the current station name from the list.
    station_name=station_list[current_station_no][0]
    station_name=(station_name+"             ")[:lcd_columns]
    #Each stream has an "info" element asssociated with it, which is decoded/extracted by the VLC player libraries.
    #As it turns out, entry 12 of this array seems to contain all the info we need...
    #This includes the track/artist playing and the stream name (which we already know)
    #This is a string, with fields separated by "-", so we then split that up.
    info_string=media.get_meta(12)
    #Build up an information string, from the stream data, to be displayed on the LCD.
    update_string=""
    if (info_string):
        item_strings =info_string.split("-")
        
        for i in range (0, len(item_strings)):
            item_string = item_strings[i].strip()
            if item_string:
                if len(item_string):
                    update_string = update_string + item_string + "-"

    #Trim off the last "-" that was added in the loop above
    update_string=update_string[:len(update_string)-1]
    #This will be the string to display.
    info_string=update_string
    curr_time = strftime("%H:%M", localtime())
    #We will add in the current time here
    update_string=curr_time + " " + update_string
        
    temp_string = update_string
    #Below is some logic for scrolling the info string across the LCD, in blocks of 4 characters
    #We keep a scroll counter, to show where we've scrolled to in the string!
    len_update_string=len(update_string)
    #Check if the string has changed since the last update - e.g. minute has rolled over, or a new track has started playing!
    if (last_update_string != info_string):
         last_update_string = info_string
         #Start showing the string from the beginning!
         scroll_counter=0
         
    #If the update string is longer than the width of the LCD....
    if (len_update_string>lcd_columns):
         scroll_counter= scroll_counter+4
         #This logic makes the string "wrap around" on the display once we've scrolled through it.
         if (scroll_counter + lcd_columns > len_update_string):
             temp_string=update_string[scroll_counter:]+ " "
             temp_string+=update_string[:lcd_columns-len(temp_string)]
             scroll_counter%= (len_update_string +1)
         else:
             #Show a block of 16 characters from whereever we've scrolled to in the string.
             temp_string=update_string[scroll_counter:scroll_counter+16]
    else:
       scroll_counter= 0

    #Output the string to the display - Station name on the top line and scrolly text on the bottom (temp string)
    lcd.message=station_name[:16] +"\n" + temp_string

#This function calls the LCD libraries to work out which key has been pressed (if any)
def check_keyboard():
    global menu_timeout,next_station_no,current_station_no
    global lcd_timer,lcd_timeout, power_off_timer
    #Check each key in turn and call the relevent handler function
    #There is some logic here to do with how the menu works.
    
    select_key_pressed = False
    if lcd.left_button and lcd.right_button:
      exit_flag=True
    elif lcd.up_button:
      menu_timeout=10
      lcd_timer=lcd_timeout
      up_down_pressed(-1)
    elif lcd.down_button:
      menu_timeout=10
      lcd_timer=lcd_timeout
      up_down_pressed(1)
    elif lcd.left_button:
      menu_timeout=10
      lcd_timer=lcd_timeout
      left_right_pressed(-1)
    elif lcd.right_button:
      menu_timeout=10
      lcd_timer=lcd_timeout
      left_right_pressed(1)
    elif lcd.select_button:
       select_key_pressed = True
       lcd_timer=lcd_timeout
    #This is to do with the feature of holding down the select button for 5 seconds to power off the Newsless Radio.
    if (select_key_pressed ):
        if power_off_timer == 0:
            power_off_timer = 5
            select_pressed()
    else:
        power_off_timer = 0
    
           
#A function to capture standard output when a system command is run!
def getStdout(cmd):
    args = shlex.split(cmd)
    proc = Popen(args, stdout=PIPE, stderr=PIPE, shell=True)
    out, err = proc.communicate()
    return out
    
#Get the system (ALSA) volume value
def getVolume():
  amixerOutput = getStdout(getMixerCommand)
  r = regex.search(amixerOutput.decode ("utf-8"))
  volume = r.groups()[1]
  active = r.groups()[3]
  return volume, active

#Set the system (ALSA) volume value
def setVolumePercent(newVolume):
  global menu_timeout
  setVolumeStr = setVolumeCommand + str(newVolume) + "%"
  os.system(setVolumeStr)
  menu_timeout=5
  show_volume()
#Swtich the system volume/sound mute on or off
def toggleMute():
  os.system(toggleMuteCommand)

#Show the current volume level on the LCD
def show_volume():
  volumePercent, soundStatus = getVolume()
  textToShow = station_list[current_station_no][0] + "\n" + "Volume: "

  if soundStatus == 'on':
    textToShow = textToShow + volumePercent + "%"
  else:
    textToShow = textToShow + "Muted"
  lcd.clear()
  lcd.message=textToShow
  
#Set the current volume level using the supplied value
def setNewVolume(increment):
  global currentVolume
  
  currentVolume=currentVolume +5*increment
  if currentVolume > 100:
    currentVolume = 100
  elif currentVolume < 0:
    currentVolume = 0
  setVolumePercent(currentVolume)

#Switch to the specified station/stream in the list that has been loaded.
def goToStation(new_station):
    
    global player,media,current_station_no,alternation_stations,last_station_no
    lcd.clear()
    #Save the station number...
    text_file = open("last_station.txt", "w")
    text_file.write(str(new_station))
    text_file.close()
    #Remeber the current station.
    last_station_no = current_station_no
    #Set the new one.    
    current_station_no=new_station
    next_station_no=current_station_no
    #Get the stream URI from the loaded list.
    url = station_list[new_station][1]
    #Invokve the VLC object
    media=instance.media_new(url.strip())
    #Set player media
    player.set_media(media)
    #Play the stream
    player.play()
    
#Show the new selected station, but don't switch to it!
def setNextStation(increment):
  global next_station_no
  
  next_station_no += increment
  next_station_no %= num_stations
  lcd.message=(station_list[next_station_no][0]+"             ")[:lcd_columns]

#Get the local IP address and display it.
def getIPAddress():
   global lcd, i2c, lcd_columns, lcd_rows
   #This will set up a socket and using this, we can most reliably determine our IP address.
   s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
   s.connect(('10.255.255.255', 1))
   i2c = busio.I2C(board.SCL, board.SDA)
   lcd = character_lcd.Character_LCD_RGB_I2C(i2c, lcd_columns, lcd_rows)
   return s.getsockname()[0]

def showIPAddress():
  ipAddr = getIPAddress()
  lcd.clear()
  lcd.message=ipAddr

###Start Main Code loop ##################################
volume_info=getVolume()
currentVolume=int(volume_info[0])
#Load the station list from the text file
load_stations()

#Check what the last station we were on is (assumes you haven't changed stations.txt since last run!)
try:
    stationsFile = open("last_station.txt", 'r')
    goToStation (int(stationsFile.read()))
    stationsFile.close()
except:
    goToStation(0)
#Set a default timer value.
tick_count=0
#These values are used to check when a new minute or second has elapsed.
last_day_minute=-1
last_second_val=-1

#Main code loop
while True:
   #Short sleep!
   sleep (0.03)
   #Count the ticks!
   tick_count = tick_count + 1;

   #Have we gone into a new second yet?
   if (last_second_val != gmtime()):
       last_second_val = gmtime()
       
       #Now look at the various timers and update them.
       if power_off_timer > 0:
            lcd.color = [0, 10, 10]
            power_off_timer -=1
            if power_off_timer == 0:
                lcd.color = [0, 0, 0]
                lcd.clear()
                lcd.message="Shutting Down"
                os.system ("sudo shutdown now")
                
       #Check for switching the menu off, if it's been shown         
       if (menu_timeout):
           menu_timeout = menu_timeout-1
           
       #Deal with the LCD timeout
       if lcd_timeout>0:
            if lcd_timer==0:
                lcd.color=[0,0,0]
            else:
                lcd_timer-=1
                lcd.color=[0,0,10]
       elif lcd_timeout==0:
            lcd.color=[0,0,10]
            
       #Calculate which minute in the day we are on.
       current_day_minute=(int(strftime("%H")) * 60) + int(strftime("%M"))
       #Has a new minute started?    
       if (current_day_minute != last_day_minute):
          last_day_minute=current_day_minute
          #This code deals with the random station change after a given period.
          if change_station_period > 0:
              change_station_period-=1
              if change_station_period==0:
                  change_station_period=old_change_station_period
                  goToStation(random.randint(0,num_stations))
          check_time_table(current_day_minute)
       
   #Update display every few ticks
   if tick_count >= 10:
      check_keyboard()
      if tick_count >= 40:
          tick_count = 0
          if menu_timeout==0:
             update_display()
             next_station_no = current_station_no
             menu_state=0

#End of code/program! Not bad for 600 odd lines!
  
