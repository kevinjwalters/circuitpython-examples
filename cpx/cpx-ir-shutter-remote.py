### cpx-ir-shutter-remote v1.2
### Circuit Playground Express (CPX) shutter remote using infrared for Sony Cameras

### copy this file to CPX as code.py

### MIT License

### Copyright (c) 2020 Kevin J. Walters

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


### This uses the Circuit Playground Express with its onboard infrared LED
### to send the shutter release codes

### If the switch is to the left then the shutter fires when the left button is pressed
### together with a brief flash of Neopixels.
### The right button can be used to toggle the use of NeoPixels.

### If the switch is to the right then the CPX functions as an intervalometer
### with the shutter being fired on a timer after each interval
### The default interval is thirty seconds and this can be changed
### by reduced with the left button and increased with the right button

import time

import pulseio
import board
import adafruit_irremote
from adafruit_circuitplayground import cp


### 40kHz modulation (for Sony) with 20% duty cycle
CARRIER_IRFREQ_SONY = 40 * 1000
ir_carrier_pwm = pulseio.PWMOut(board.IR_TX,
                                frequency=CARRIER_IRFREQ_SONY,
                                duty_cycle=round(20 / 100 * 65535))
ir_pulseout = pulseio.PulseOut(ir_carrier_pwm)

### Used to observe 6.0.0-6.2.0 bug
### https://github.com/adafruit/circuitpython/issues/4602
##ir_carrier_pwm_a2debug = pulseio.PWMOut(board.A2,
##                                        frequency=CARRIER_IRFREQ_SONY,
##                                        duty_cycle=round(20 / 100 * 65535))
##ir_pulseout_a2debug = pulseio.PulseOut(ir_carrier_pwm_a2debug)

### Sony timing values (in us) based on the ones in
### https://github.com/z3t0/Arduino-IRremote/blob/master/src/ir_Sony.cpp
### Disabling the addition of trail value is required to make this work
### trail=0 did not work
ir_encoder = adafruit_irremote.GenericTransmit(header=[2400, 600],
                                               one=   [1200, 600],
                                               zero=  [600,  600],
                                               trail=None)

def fire_shutter():
    """Send infrared code to fire the shutter.
       This is a code used by Sony cameras."""
    ir_encoder.transmit(ir_pulseout, [0xB4, 0xB8, 0xF0],
                        repeat=2, delay=0.005, nbits=20)
    ### Send to A2 to help debug issue with 5.3.1 ok, 6.x broken
    ###
    ##ir_encoder.transmit(ir_pulseout_a2debug, [0xB4, 0xB8, 0xF0],
    ##                    repeat=2, delay=0.005, nbits=20)


def say_interval(number_as_words):
    words = number_as_words.split() + ["seconds"]
    for word in words:
        if word == ",":
            time.sleep(0.15)
        else:
            cp.play_file(WAV_DIR + "/" + word + ".wav")
        time.sleep(0.050)


SHUTTER_CMD_COLOUR = (8, 0, 0)
IMPENDING_COLOUR = (7, 4, 0)
BLACK = (0, 0, 0)

S_TO_NS = 1000 * 1000 * 1000
ADJ_NS = 20 * 1000 * 1000
IMPENDING_NS = 2 * S_TO_NS
### intervalometer mode announces the duration
manual_trig_wav = "button.wav"
sound_trig_wav = "noise.wav"
impending_wav = "ready.wav"
WAV_DIR="num"
interval_words = ["five",
                  "ten",
                  "fifteen",
                  "twenty",
                  "twenty five",
                  "thirty",
                  "sixty",
                  "one hundred and twenty",
                  "one hundred and eighty",
                  "two hundred and forty",
                  "three hundred",
                  "six hundred",
                  "one thousand , eight hundred",
                  "three thousand , six hundred"]
intervals = [5, 10, 15, 20, 25, 30, 60,
             120, 180, 240, 300, 600, 1800, 3600]
interval_idx = intervals.index(30)  ### default is 30 seconds
intervalometer = False
last_cmd_ns = None
first_cmd_ns = None
pixel_indication = True
impending = False
say_and_reset = False

while True:
    ### CPX switch to left
    if cp.switch:
        if intervalometer:
            cp.play_file(manual_trig_wav)
            intervalometer = False

        if cp.button_a:  ### left button_a
            if pixel_indication:
                cp.pixels.fill(SHUTTER_CMD_COLOUR)
            last_cmd_ns = time.monotonic_ns()
            fire_shutter()
            if first_cmd_ns is None:
                first_cmd_ns = last_cmd_ns
            print("Manual", "shutter release at", (last_cmd_ns - first_cmd_ns) / S_TO_NS)
            if pixel_indication:
                cp.pixels.fill(BLACK)
            while cp.button_a:
                pass  ### wait for button release

        elif cp.button_b:
            pixel_indication = not pixel_indication
            while cp.button_b:
                pass  ### wait for button release

    ### CPX switch to right
    else:
        if not intervalometer:
            say_and_reset = True
            intervalometer = True

        ### Left button decreases time
        if cp.button_a and interval_idx > 0:
            interval_idx -= 1
            while cp.button_a:
                pass  ### wait for button release
            say_and_reset = True

        ### Right button increases time
        elif cp.button_b and interval_idx < len(intervals) - 1:
            interval_idx += 1
            while cp.button_b:
                pass  ### wait for button release
            say_and_reset = True

        if say_and_reset:
            say_interval(interval_words[interval_idx])
            last_cmd_ns = time.monotonic_ns()
            say_and_reset = False

        ### If enough time has elapsed fire the shutter
        ### or show the impending colour on NeoPixels
        now_ns = time.monotonic_ns()
        interval_ns = intervals[interval_idx] * S_TO_NS
        if now_ns - last_cmd_ns >= interval_ns - ADJ_NS:
            if pixel_indication:
                cp.pixels.fill(SHUTTER_CMD_COLOUR)
            last_cmd_ns = time.monotonic_ns()
            fire_shutter()
            if first_cmd_ns is None:
                first_cmd_ns = last_cmd_ns
            print("Timer", "shutter release at", (last_cmd_ns - first_cmd_ns) / S_TO_NS)
            if pixel_indication:
                cp.pixels.fill(BLACK)
            impending = False

        elif (pixel_indication
              and not impending
              and now_ns - last_cmd_ns >= interval_ns - IMPENDING_NS):
            cp.pixels.fill(IMPENDING_COLOUR)
            cp.play_file(impending_wav)
            cp.pixels.fill(BLACK)
            impending = True
