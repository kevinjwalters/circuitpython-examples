### electric-drips.py v0.6
### Falling "drips" down the GP pins intended for Cytron Maker Pi Pico

### TODO PARTIALLY WORKS Tested with Pi Pico and CircuitPython 6.2.0-beta.2-18-g2a467f137
### TODO https://github.com/adafruit/circuitpython/issues/4210

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
import math
import random

import board
import pwmio
import digitalio
from audiopwmio import PWMAudioOut as AudioOut
from audiocore import WaveFile

debug = 1

def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)

AUDIO_PIN = board.GP18
audio_out = AudioOut(AUDIO_PIN)
drip = WaveFile(open("one-drip-16k.wav", "rb"))


### Pins and vertical displacement
left_pins = ((board.GP0, 0),
             (board.GP1, 1),
             # gap
             (board.GP2, 3),  ### clash with GP18 audio due to PWM architecture
             (board.GP3, 4),  ### clash with GP18 audio due to PWM architecture
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

### GP28 is NeoPixel - will be interesting...
right_pins = (# 6 absences (green LED for 3v3)
              (board.GP28, 6),
              # gap
              (board.GP27, 8),
              (board.GP26, 9),
              # gap
              (board.GP27, 8),
              (board.GP26, 9),
              # gap
              (board.GP22, 11),
              # gap
              (board.GP21, 13),
              (board.GP20, 14),
              (board.GP19, 15),  ### clash with GP18 audio
              ##(board.GP18, 16),  ### clash with GP18 audio
              # gap
              (board.GP17, 18),
              (board.GP16, 19))

### The use of GP18 also effectively reserves GP19
### and the RP2040 hardware cannot then offer PWM on GP2 and GP3
PWMAUDIO_CLASH_PINS = (board.GP2, board.GP3,
                       board.GP19)

PIN_SPACING_M = 2.54 / 10 / 100
BOARD_LENGTH_M = 20 * PIN_SPACING_M

### This is a duty_cycle value
MAX_BRIGHTNESS = 65535
PWM_LED_FREQUENCY = 7000


class FakePWMOut:
    """A basic, fixed-brightness emulation of the PWMOut object used for variable brightness
       LED driving."""

    def __init__(self, pin, frequency=None, duty_cycle=32767):
        self._pin = pin
        self._duty_cycle = duty_cycle
        self._digout = digitalio.DigitalInOut(self._pin)
        self._digout.direction = digitalio.Direction.OUTPUT
        
        self.duty_cycle = duty_cycle  ### set value using property


    @property
    def duty_cycle(self):
        return self._duty_cycle

    @duty_cycle.setter
    def duty_cycle(self, value):
        self._duty_cycle = value
        self._digout.value = (value >= 32768)


def show_points(pwms, pin_posis, points):
    ##min_y = pin_posis[0][1]
    ##max_y = pin_posis[-1][1]

    levels = [0] * len(pwms)
    
    ### Iterate over points accumulating the brightness value
    ### for the pin positions they cover
    for pos, rad, bri in points:
        top = pos - rad
        bottom = pos + rad
        for idx, pin_pos in enumerate(pin_posis):
            if top <= pin_pos <= bottom:
                levels[idx] += bri

    for idx, level in enumerate(levels):
        ### Use of min() caps the value within legal duty cycle range
        pwms[idx].duty_cycle = min(level, MAX_BRIGHTNESS)

def start_sound(wav):
    audio_out.play(wav)


def pwm_init(pins, duty_cycle=0):
    pwms = []
    for p in pins:
        if p in PWMAUDIO_CLASH_PINS:
            pwms.append(FakePWMOut(p, duty_cycle=duty_cycle))
        else:
            pwms.append(pwmio.PWMOut(p, frequency=PWM_LED_FREQUENCY,
                                     duty_cycle=duty_cycle))
    return pwms


points = []
gravity = 9.81 / 30.0
half_gravity = 0.5 * gravity

left_pwms = pwm_init([p for p, d in left_pins])
left_pin_pos = tuple([d * PIN_SPACING_M for p, d in left_pins])

while True:
    time.sleep(random.random() * 5.0)
    d_print(1, "START")

    ### position, size, brightness
    points.append([left_pin_pos[0], PIN_SPACING_M / 2.0, 0])

    ### TODO - change this to be time based
    for brighten in range(0, 65535, 3276):
        points[0][2] = brighten
        points[0][1] *= 1.04  ### 1.04 to get to just over twice size
        show_points(left_pwms, left_pin_pos, points)
        time.sleep(0.1)
    
    start_fall_ns = time.monotonic_ns()
    start_y_pos = points[0][0]
    current_y_pos = start_y_pos
    end_y_pos = left_pin_pos[-1] + points[0][1]
    splashed = False
    while current_y_pos <= end_y_pos:
        now_ns = time.monotonic_ns()
        fall_time = (now_ns - start_fall_ns) * 1e-9
        current_y_pos = start_y_pos + half_gravity * fall_time * fall_time
        points[0][0] = current_y_pos
        ### Start sound a bit before impact to synchronise
        if not splashed and current_y_pos >= left_pin_pos[-2]:
            start_sound(drip)
            splashed = True
        show_points(left_pwms, left_pin_pos, points)

    points.clear()
