### electric-drips.py v1.2
### Falling "LED drips" down the GP pins for Cytron Maker Pi Pico

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
LEFT_PINS = ((board.GP0, 0),
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

### LEDs on the right side are not used in the program currently for drips
RIGHT_PINS = (# 6 absences (green LED for 3v3)
              (board.GP28, 6),  ### NeoPixel is attached to this
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
              ##(board.GP18, 16),  ### clash with GP18 audio due to PWM architecture
              # gap
              (board.GP17, 18),
              (board.GP16, 19))

### The use of GP18 also effectively reserves GP19
### and the RP2040 hardware cannot then offer PWM on GP2 and GP3
PWMAUDIO_CLASH_PINS = (board.GP2, board.GP3,
                       board.GP19)

PIN_SPACING_M = 2.54 / 10 / 100

### This is a duty_cycle value
MAX_BRIGHTNESS = 65535
PWM_LED_FREQUENCY = 7000


class FakePWMOut:
    """A basic, fixed-brightness emulation of the PWMOut object used for
       variable brightness LED driving."""
    ### pylint: disable=too-few-public-methods

    def __init__(self,
                 pin,
                 frequency=None,  ### pylint: disable=unused-argument
                 duty_cycle=32767):
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


def show_points(pwms, pin_posis, pnts):
    levels = [0] * len(pwms)

    ### Iterate over points accumulating the brightness value
    ### for the pin positions they cover
    for pos, rad, bri in pnts:
        top = pos - rad
        bottom = pos + rad
        for idx, pin_pos in enumerate(pin_posis):
            if top <= pin_pos <= bottom:
                levels[idx] += bri

    for idx, level in enumerate(levels):
        ### Use of min() saturates and
        ### caps the value within legal duty cycle range
        pwms[idx].duty_cycle = min(level, MAX_BRIGHTNESS)


def start_sound(sample):
    if sample is not None:
        audio_out.play(sample)


def pwm_init(pins, duty_cycle=0):
    pwms = []
    for p in pins:
        if p in PWMAUDIO_CLASH_PINS:
            pwms.append(FakePWMOut(p, duty_cycle=duty_cycle))
        else:
            pwms.append(pwmio.PWMOut(p, frequency=PWM_LED_FREQUENCY,
                                     duty_cycle=duty_cycle))
    return pwms


NS_TO_S = 1e-9
REALITY_DIVISOR = 60.0  ### Real gravity is very fast!
points = []
gravity = 9.81 / REALITY_DIVISOR
half_gravity = 0.5 * gravity

left_pwms = pwm_init([p for p, d in LEFT_PINS])
left_pin_pos = tuple([d * PIN_SPACING_M for p, d in LEFT_PINS])

### Indices for point fields
POS = 0
RAD = 1
BRI = 2

count = 0
while True:
    count += 1
    time.sleep(random.uniform(1.0, 5.0))
    d_print(1, "DRIP")

    ### position, size, brightness
    start_radius = PIN_SPACING_M / 2.0
    points.append([left_pin_pos[0], start_radius, 0])

    ### Form the drip
    start_ns = time.monotonic_ns()
    brightness = 0
    target_brightness = random.randint(32768, MAX_BRIGHTNESS)
    brighten_time = random.uniform(1.5, 2.5)
    while brightness < target_brightness:
        now_ns = time.monotonic_ns()
        duration = (now_ns - start_ns) * NS_TO_S
        brightness = round(target_brightness * duration / brighten_time)
        points[0][BRI] = min(brightness, MAX_BRIGHTNESS)
        points[0][RAD] = start_radius * duration / brighten_time * 2.2
        show_points(left_pwms, left_pin_pos, points)

    start_fall_ns = time.monotonic_ns()
    start_y_pos = points[0][POS]
    current_y_pos = start_y_pos
    impact_y_pos = left_pin_pos[-1] - PIN_SPACING_M / 2.0
    splashed = False
    while current_y_pos <= impact_y_pos:
        now_ns = time.monotonic_ns()
        fall_time = (now_ns - start_fall_ns) * NS_TO_S
        current_y_pos = start_y_pos + half_gravity * fall_time * fall_time
        points[0][POS] = current_y_pos
        ### Start sound a bit before impact to synchronise
        if not splashed and current_y_pos >= left_pin_pos[-3]:
            start_sound(drip)
            splashed = True
        show_points(left_pwms, left_pin_pos, points)

    ### Bounce every fourth drip
    bouncing_drip = (count % 4) == 0
    if bouncing_drip:
        ### Make an extra bouncing drip at half the size and much dimmer
        points.append([points[0][POS],
                       points[0][RAD] / 2.0,
                       points[0][BRI] * 18 // 100])

        ### Reduce the size of the first splash
        points[0][RAD] /= 1.8

        start_bounce_ns = time.monotonic_ns()
        bounce_velocity = -gravity / 2.0 * (now_ns - start_fall_ns) * NS_TO_S
        start_bounce_y_pos = points[1][POS]
        bounce_y_pos = start_bounce_y_pos
        while bounce_y_pos <= start_bounce_y_pos:
            now_ns = time.monotonic_ns()
            fall_time = (now_ns - start_bounce_ns) * NS_TO_S
            bounce_y_pos = (start_bounce_y_pos
                            + bounce_velocity * fall_time
                            + half_gravity * fall_time * fall_time)
            points[1][POS] = bounce_y_pos
            show_points(left_pwms, left_pin_pos, points)

        _ = points.pop()  ### discard the bouncing drip

    ### Drain away - this would be slightly better if it used time
    ### and if it drained away while the bounce was happening
    for darken in range(MAX_BRIGHTNESS, 0, -1638):
        points[0][2] = darken
        points[0][1] /= 1.04
        show_points(left_pwms, left_pin_pos, points)
        time.sleep(0.050)

    points.clear()
    show_points(left_pwms, left_pin_pos, points)
