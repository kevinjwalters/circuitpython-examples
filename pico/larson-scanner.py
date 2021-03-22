### larson-scanner.py v2.0
### Larson scanner for Cytron Maker Pi Pico

### Tested with Maker Pi Pico and CircuitPython 6.2.0-beta.4
### with audio daughterboard as workaround for
### https://github.com/adafruit/circuitpython/issues/4208

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

import board
import busio  ### for UART
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


AUDIO_DAUGHTERBOARD = True

if AUDIO_DAUGHTERBOARD:
    ### Using pins presented on ESP-01 to talk to Feather nRF52840
    adb_uart = busio.UART(board.GP16, board.GP17, baudrate=115200)
    scanner_left = 1
    scanner_right = 2
    PWMAUDIO_CLASH_PINS = ()
else:
    ### TODO - PIO PWM would be nice to avoid losing GP2 GP3 for audio
    AUDIO_PIN_L = board.GP18
    AUDIO_PIN_R = board.GP19
    audio_out = AudioOut(AUDIO_PIN_L, right_channel=AUDIO_PIN_R)
    left_file = open("scanner-left-16k.wav", "rb")
    right_file = open("scanner-right-16k.wav", "rb")

    ### These crackle very unpleasantly and/or CP just crashes
    #scanner_left = WaveFile(left_file)
    #scanner_right = WaveFile(right_file)

    ### This blows up on first play during PWM animation
    ### but at least it doesn't crackle!!
    ### https://github.com/adafruit/circuitpython/issues/4431
    buffer = bytearray(80 * 1024)  ### TODO - remove this
    scanner_left = WaveFile(left_file, buffer)
    scanner_right = WaveFile(right_file, buffer)

    ### The use of GP18 also effectively reserves GP19
    ### and the RP2040 hardware cannot then offer PWM on GP2 and GP3
    ### PIO PWM could be a solution here when it works in CircuitPython
    PWMAUDIO_CLASH_PINS = (board.GP2, board.GP3,
                           board.GP18, board.GP19)

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
              (board.GP19, 15),  ### clash with GP18 audio due to PWM architecture
              (board.GP18, 16),  ### clash with GP18 audio
              # gap
              (board.GP17, 18),
              (board.GP16, 19))


PIN_SPACING_M = 2.54 / 10 / 100
BOARD_LENGTH_M = 20 * PIN_SPACING_M

### This is a duty_cycle value
MAX_BRIGHTNESS = 65535
PWM_LED_FREQUENCY = 7000


class FakePWMOut:
    """A basic, fixed-brightness emulation of the PWMOut object used for
       variable brightness LED driving."""

    def __init__(self, pin,
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
        if AUDIO_DAUGHTERBOARD:
            adb_uart.write(bytes([sample]))
        else:
            audio_out.play(sample)


def wait_sound():
    if AUDIO_DAUGHTERBOARD:
        pass  ### not implemented
    else:
        while audio_out.playing:
            pass


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

left_pwms = pwm_init([p for p, d in left_pins])
left_pin_pos = tuple([d * PIN_SPACING_M for p, d in left_pins])

### Indices for point fields
POS = 0
RAD = 1
BRI = 2

start_radius = PIN_SPACING_M / 2.0

### GP8 is about the middle
lead_pos = left_pin_pos[8]
### position, size, brightness
points.append([lead_pos, start_radius, 65535])
for _ in range(5):
    points.append([lead_pos, points[-1][RAD], points[-1][BRI] >> 1])
trail_spc = 12
last_pos = [0] * ((len(points) - 1) * trail_spc)

### Track if sound effect has been started
left_se = False
right_se = False

left_se_pos = left_pin_pos[4]
right_se_pos = left_pin_pos[-4]

### The real thing goes "out of bounds"
far_left = left_pin_pos[0] - PIN_SPACING_M * 2
far_right = left_pin_pos[-1] + PIN_SPACING_M * 2

### 1.333 seconds to go from one side to other
target_speed_mpns = (far_right - far_left) / 1.333 / 1e9
speed_mpns = 0.0
accel_mpns2 = target_speed_mpns / 15.0 / 1e9

direction = -1  ### to the left

start_ns = time.monotonic_ns()
last_move_ns = start_ns


while True:
    ### Move the main dot and trailing dots
    while far_left <= lead_pos <= far_right:
        show_points(left_pwms, left_pin_pos, points)

        now_ns = time.monotonic_ns()
        elapsed_ns = now_ns - last_move_ns
        if speed_mpns < target_speed_mpns:
            speed_mpns += accel_mpns2 * elapsed_ns

        lead_pos += direction * speed_mpns * elapsed_ns
        last_move_ns = now_ns

        ### Start the scanner return sound as it approaches either end
        if direction > 0 and not right_se and lead_pos >= right_se_pos:
            start_sound(scanner_right)
            right_se = True
        elif direction < 0 and not left_se and lead_pos <= left_se_pos:
            start_sound(scanner_left)
            left_se = True

        ### Move the trailing points and set main point's new position
        for tr_idx in range(1, len(points)):
            points[tr_idx][POS] = last_pos[tr_idx * trail_spc - 1]
        points[0][POS] = lead_pos

        ### Shuffle the point position history along and add new position
        last_pos = [lead_pos] + last_pos[:-1]

    ### Put position back into bounds and change direction
    lead_pos = far_right if direction > 0 else far_left
    direction = 0 - direction

    ### Clear sound start flags
    left_se = right_se = False
