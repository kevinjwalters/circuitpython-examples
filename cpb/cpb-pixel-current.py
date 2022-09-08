### cpb-pixel-current v1.0
### Some simple NeoPixel animation to examine power usage

### Tested with Circuit Playground Bluefruit (CPB)
### and CircuitPython and 7.3.2

### Will work on Circuit Playground Express (CPX) too

### copy this file to CPB board as code.py

### MIT License

### Copyright (c) 2022 Kevin J. Walters

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
##import random
import gc

from adafruit_circuitplayground import cp


def make_colour(colour_mask, value=255):
    red, green, blue = colour_mask
    return (value if red else 0, value if green else 0, value if blue else 0)


### Ensure NeoPixels are off
pixels = cp.pixels
pixels.fill(0)
pixels.auto_write = False

gc.collect()
fixed_mode = False
while True:
    if cp.switch:
        fixed_mode = False
    else:
        if not fixed_mode:
            fixed_mode = True
            ### For right switch position
            pixels.fill(0)
            pixels[0] = (255, 255, 255)
            pixels.show()
        ### The continue prevents the subsequent code from running in the loop
        continue

    ### For left switch position
    for count in (1, 3):
        for mask in ((True, False, False),  ### red
                     (False, True, False),  ### green
                     (False, False, True),  ### blue
                     (True, True, False),   ### yellow
                     (False, True, True),   ### cyan
                     (True, False, True),   ### magenta
                     (True, True, True)):   ### white (all three)
            for level in (0, 10, 20, 64, 128, 255):
                pixels.fill(0)
                colour = make_colour(mask, level)
                for idx in range(count):
                    pixels[idx] = colour
                pixels.show()
                time.sleep(0.300)
        pixels.fill(0)
        pixels.show()
        time.sleep(1.2)

    time.sleep(10)
