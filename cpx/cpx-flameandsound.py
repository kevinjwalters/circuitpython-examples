### cpx-flameandsound v1.0
### A flame emulation with silly sounds for Circuit Playground Express (CPX)
### Emulates a variable brightness and hue mobile flame
### on the on-board ring of NeoPixels and plays sound samples when
### the board is not level or detects sound with left button setting volume.

### copy this file to CPX as main.py

### MIT License

### Copyright (c) 2018 Kevin J. Walters

### Permission is hereby granted, free of charge, to any person obtaining a copy
### of this software and associated documentation files (the "Software"), to deal
### in the Software without restriction, including without limitation the rights
### to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
### copies of the Software, and to permit persons to whom the Software is
### furnished to do so, subject to the following conditions:

### The above copyright notice and this permission notice shall be included in all
### copies or substantial portions of the Software.

### THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
### IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
### FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
### AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
### LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
### OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
### SOFTWARE.

### Based on MakeCode implementation https://makecode.com/_ejJfqW4MzWwt

### reserve some space (stack or heap?)
##contigmem = "." * 520

### For cpx.pixels, cpx.accel and cpx.play_file
from adafruit_circuitplayground.express import cpx

### For hsv functionality
### Trying without this to save memory (heap)
##import adafruit_fancyled.adafruit_fancyled as fancy



### TODO - pick up sound detection from
###        https://learn.adafruit.com/adafruit-circuit-playground-express/playground-sound-meter
###
##import gc
import audioio
import digitalio
import board

import random
import time

### default brightness is 1.0 (unlike MakeCode implementation)
cpx.pixels.auto_write = False   ### stop implicit show() after each assignment

### enable the speaker - need to find out if there's downside to leaving it on
cpx._speaker_enable.value = True

### Approximate x and y positions of onboard NeoPixels in mm
### with origin at centre
ledposx = [-8.5, -15.0, -17.0, -15.0, -8.5, 8.5, 15.0, 17.0, 15.0, 8.5]
ledposy = [15.0, 8.0, 0.0, -8.0, -15.0, -15.0, -8.0, 0.0, 8.0, 15.0]

### Current flame position
posx = 0.0
posy = 0.0

### A very approximate representation of candle temperature in spec
burn = 40.0
sat = 255.0
### 25 is a touch too green in MakeCode and perhaps greener in fancy.CHSV()
yellowhue = 22

### gravity value to determine whether CPX board is level
zflat = 9.3
mute = False

### More int based version of
### https://github.com/adafruit/Adafruit_CircuitPython_FancyLED/blob/master/adafruit_fancyled/adafruit_fancyled.py
def hsvtorgb(h, s, v):
    if s == 0:
        return (v, v, v)
 
    i = int(h / 42.5);
    r = int((h - (i * 42.5)) * 6); 

    p = (v * (255 - s)) >> 8;
    q = (v * (255 - ((s * r) >> 8))) >> 8;
    t = (v * (255 - ((s * (255 - r)) >> 8))) >> 8;

    i = i % 6
    if i == 0:
        return v, t, p
    if i == 1:
        return q, v, p
    if i == 2:
        return p, v, t
    if i == 3:
        return p, q, v
    if i == 4:
        return t, p, v
    if i == 5:
        return v, p, q

### Calculate the hue and saturation from the burn representation
def calcHS(burn):
    if burn > 75:
        return (yellowhue, 255 - (burn - 75) * 0.2)
    else:
        return (burn / 75 * yellowhue, 255)

### Numbers chosen by experimentation, the essence is the brightness drops off
### away from the centre of the flame.
def makeflame(ledstrip, x, y, hue, sat):
    for index in range(len(ledstrip)):
        posdiffx = x - ledposx[index]
        posdiffy = y - ledposy[index]
        ## distance = ((posdiffx**2 + posdiffy**2))**0.5
        distancesqrd = posdiffx**2 + posdiffy**2
        bright = 0
        if distancesqrd < 2304:
            bright = (2304 - distancesqrd) * 0.11
        ##print('({:f},{:f},{:f}'.format(hue, sat, bright))
        ### Values must be int, float must be in different range (0.0 to 1.0)
        ##ledstrip[index] = fancy.CHSV(int(hue), int(sat), int(bright)).pack()
        ledstrip[index] = hsvtorgb(int(hue), int(sat), int(bright))
        
    ledstrip.show()

def makeangry(ledstrip, speed=10):
    for up in range(0,255,speed):
        red = (up, 0, 0)
        ledstrip.fill(red)
        ledstrip.show()
    for down in reversed(range(0,255,speed)):
        red = (down, 0, 0)
        ledstrip.fill(red)
        ledstrip.show()

### Many of the values chosen here are based on a suck it and see
### (empirical) approach
while True:
    ### randrange returns int and doesn't include upper end hence the +1
    steps = random.randrange(7, 12+1)
    movex = ( random.randrange(-50, 50+1) - posx ) / steps
    movey = ( random.randrange(-50, 50+1) - posy ) / steps
    burndelta = ( random.randrange(40, 100+1) - burn) / steps
    ### move the flame around in the number of steps randomly chosen
    for step in range(steps):
        (hue, sat) = calcHS(burn)
        makeflame(cpx.pixels, posx, posy, hue, sat)
        posx += movex
        posy += movey
        burn += burndelta
        ### Additional checks
        if cpx.button_a:
            mute = not mute
            ### Wait for end of press
            while cpx.button_a:
                pass
        (x,y,z) = cpx.acceleration
        ### If not muted then get angry and laugh if not flat
        ### TODO - change logic so this still runs with makeangry but no audio
        if not mute and z < zflat:
            ### play tilted sound
            #contigmem = None
            wave_file = open("Evillaugh.wav", "rb")
            with audioio.WaveFile(wave_file) as wave:
                with audioio.AudioOut(board.SPEAKER) as audio:                    
                    audio.play(wave)
                    speed = 50
                    while audio.playing:
                        makeangry(cpx.pixels, speed)
                        if speed >= 10:
                            speed -= 5
        if False:
            ### mic sound triggered action goes here
            pass
    time.sleep(0.100)  ### 100ms pause in seconds
