### electric-drips-verysimple.py v1.2
### Simple falling "LED drips" down the GP pins for Cytron Maker Pi Pico

### Tested with Pi Pico and 6.2.0-beta.2-182-g24fdda038

### copy this file to Cytron Maker Pi Pico as code.py

### MIT License

### Copyright (c) 2021 Kevin J. Walters

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

import time
import random

from board import *
from digitalio import DigitalInOut, Direction
from audiopwmio import PWMAudioOut as AudioOut
from audiocore import WaveFile


### Maker Pi Pico has small speaker (left channel) on GP18
audio_out = AudioOut(GP18)
### Audio is part of tack00's https://freesound.org/people/tack00/sounds/399257/
DRIP_FILENAME = "one-drip-16k.wav"
try:
    drip = WaveFile(open(DRIP_FILENAME, "rb"))
except OSError:
    print("Missing audio file:", DRIP_FILENAME)
    drip = None

animation_step = 0.1  ### tenth of a second
### Each "frame" in animation is either a list of pins
### to illuminate or a sound sample to start playing
animation = [[GP0],
             [GP0],
             [GP0],
             [GP0],
             [GP0],
             [GP1],
             [],  # gap
             [GP2],
             [GP3],
             [GP4],
             [GP5],
             [],  # gap
             [GP6],
             [GP7],
             [GP8],
             [GP9],
             [],
             [GP10],
             [GP11],
             [GP12],
             [GP13],
             [],  # gap
             drip,
             [GP14],
             [GP15],
             [GP15],
             [GP15],
             [GP15],
             [GP15],
             [GP15],
             [GP15]]


### Make a dictionary of digital outputs to allow the LEDs
### on the Cytron Maker Pi Pico board to be controlled
outputs = {}
for frame in animation:
    if isinstance(frame, WaveFile):
        continue
    for pin in frame:
        pin_str = str(pin)
        if not outputs.get(pin_str):
            digout = DigitalInOut(pin)
            digout.direction = Direction.OUTPUT
            outputs[pin_str] = digout


while True:
    ### Pause between 1 and 5 seconds
    time.sleep(random.uniform(1.0, 5.0))

    print("DRIP")
    for frame in animation:
        if isinstance(frame, WaveFile):
            continue 

        for pin in frame:
            outputs[str(pin)].value = True
        time.sleep(animation_step)
        for pin in frame:
            outputs[str(pin)].value = False
