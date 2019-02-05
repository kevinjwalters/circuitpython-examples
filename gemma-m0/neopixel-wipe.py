### neopixel-wipe v1.0
### CircuitPython (on Gemma M0) example for NeoPixel RGB LEDs
### This wipes a list of colours across the NeoPixels with some
### changes of direction.

### Tested with Gemma M0 and CircuitPython 3.1.2

### copy this file to Gemma M0 as code.py

### MIT License

### Copyright (c) 2019 Kevin J. Walters

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

### For very simple example see
### https://learn.adafruit.com/adafruit-gemma-m0/circuitpython-dotstar

import board
import digitalio

import neopixel
import time
import random

numpix = 12  # Number of NeoPixels (e.g. 12-pixel ring)
pixpin = board.D0  # Pin where NeoPixels are connected
### Leave on default brightness of 1.0 and use dull colours
### to give better performance
strip = neopixel.NeoPixel(pixpin, numpix, auto_write=False)

#boardled = digitalio.DigitalInOut(board.D13)
#boardled.direction = digitalio.Direction.OUTPUT

black   = (0 ,0 ,0)
red     = (25,0 ,0)
green   = (0 ,20,0)
blue    = (0 ,0 ,22)
magenta = (15,0 ,14)
cyan    = (0 ,13,14)
yellow  = (15,13,0)
white   = (10,8,10)

### Wipe a colour across the RGB LEDs with some direction alternation
forwardWipe = True   ### controls the wipe direction
colourlist = [red, white, blue, black]
while True:
    for alternatingDirection in [False, False, True, True]:
        for colour in colourlist:
            ### Wipe the colour one pixel per loop
            for upto in range(0, numpix):
                if forwardWipe:
                    strip[upto] = colour
                else:
                    strip[numpix - upto - 1] = colour
                strip.show()
                time.sleep(0.1)  ### 100ms pause
            if alternatingDirection:
                forwardWipe = not forwardWipe
