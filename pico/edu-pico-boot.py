### boot.py for clue-mutlitemplogger.py v1.0
### Enables writing data to CIRCUITPY if EDU PICO switch
### ON GP15 is set to enable (low)

### Tested with Cytron EDU PICO (with Pi Pico W) and CircuitPython 9.1.4

### MIT License

### Copyright (c) 2024 Kevin J. Walters

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


### Inspired by switch example in
### https://learn.adafruit.com/circuitpython-essentials/circuitpython-storageapproach in

import board
import digitalio
import storage

switch_low_for_enable = digitalio.DigitalInOut(board.GP15)

if not switch_low_for_enable.value:
    ### Switch on EDU PICO is set to enable
    print("Remounting / read-write")
    storage.remount("/", readonly=False)
else:
    ### Switch on EDU PICO is set to disable
    print("Leaving / as read-only")
