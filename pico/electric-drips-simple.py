### electric-drips-simple.py v1.2
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

import board
import digitalio
from audiopwmio import PWMAudioOut as AudioOut
from audiocore import WaveFile


### Maker Pi Pico has small speaker (left channel) on GP18
AUDIO_PIN = board.GP18
audio_out = AudioOut(AUDIO_PIN)
### Audio is part of tack00's https://freesound.org/people/tack00/sounds/399257/
DRIP_FILENAME = "one-drip-16k.wav"
try:
    drip = WaveFile(open(DRIP_FILENAME, "rb"))
except OSError:
    print("Missing audio file:", DRIP_FILENAME)
    drip = None


### Pins and vertical displacement
left_pins = ((board.GP0, 0),
             (board.GP1, 1),
             # gap
             (board.GP2, 3),
             (board.GP3, 4),
             (board.GP4, 5),
             (board.GP5, 6),
             # gap
             (board.GP6, 8),
             (board.GP7, 9),
             (board.GP8, 10),
             (board.GP9, 11),
             # gap
             (board.GP10, 13),
             (board.GP11, 14),
             (board.GP12, 15),
             (board.GP13, 16),
             # gap
             (board.GP14, 18),
             (board.GP15, 19))


### Make an array of digital outputs to allow the LEDs
### on the Cytron Maker Pi Pico board to be controlled
left_outputs = []
for pin, _ in left_pins:
    digout = digitalio.DigitalInOut(pin)
    digout.direction = digitalio.Direction.OUTPUT
    left_outputs.append(digout)


while True:
    time.sleep(random.uniform(1.0, 5.0))
    print("DRIP")

    drop_size = random.uniform(0.5, 1.5)
    last_led = None
    start_pos = left_pins[0][1]
    impact_pos = left_pins[-1][1]
    pos = start_pos
    led_idx = 0

    ### Make the drip fall using a position compared against the
    ### board positions in left_pins to make the movement more
    ### natural looking over the gaps
    while pos <= impact_pos:
        if last_led:
            last_led.value = False

        if left_pins[led_idx][1] == pos:
            led = left_outputs[led_idx]
            led.value = True
            last_led = led
            led_idx += 1

        ### Leave the LED on for longer at the start and end
        ### to signify the drop formation and the splash/draining away
        if pos == start_pos:
            duration = drop_size
        elif pos == impact_pos:
            duration = drop_size / 2.0
            if drip:
                audio_out.play(drip)
        else:
            duration = 0.075
        time.sleep(duration)
        pos += 1

    ### Turn off the last LED at impact_pos
    last_led.value = False
