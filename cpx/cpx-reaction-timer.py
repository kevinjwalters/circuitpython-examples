### cpx-reaction-timer v0.8
### A human reaction timer using light and sound with touch pads
### Measures the time it takes for user to press A1

### Tested on
### CPX running CircuitPython 4.1.0
### CPB running CircuitPython 5.0.0-beta.2

### copy this file to CPX as code.py

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

import time
import math
import random
import array
import gc

import board
import pulseio
import touchio
import digitalio
import analogio
import os

# This code works on both CPB and CPX boards by bringing
# in classes with same name
try:
    from audiocore import RawSample
except ImportError:
    from audioio import RawSample
try:
    from audioio import AudioOut
except ImportError:
    from audiopwmio import PWMAudioOut as AudioOut

import neopixel
import adafruit_motor.servo


def seed_with_noise():
    """Set random seed based on four reads from analogue pads.
       Disconnected pads on CPX produce slightly noisy 12bit ADC values.
       Shuffling bits around a little to distribute that noise."""
    a2 = analogio.AnalogIn(board.A2)
    a3 = analogio.AnalogIn(board.A3)
    a4 = analogio.AnalogIn(board.A4)
    a5 = analogio.AnalogIn(board.A5)
    random_value = ((a2.value >> 4) + (a3.value << 1) +
                    (a4.value << 6) + (a5.value << 11))
    for pin in (a2, a3, a4, a5):
        pin.deinit()
    random.seed(random_value)

# Without os.urandom() the random library does not set a useful seed
try:
    os.urandom(4)
except NotImplementedError:
    seed_with_noise()

# create a PWMOut object on pad A6
pwma6 = pulseio.PWMOut(board.A6, duty_cycle=2 ** 15, frequency=50)
servo = adafruit_motor.servo.Servo(pwma6)
servo.angle = 0

# Turn the speaker on
speaker_enable = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
speaker_enable.direction = digitalio.Direction.OUTPUT
speaker_enable.value = False

audio = AudioOut(board.SPEAKER)

# Number of seconds
SHORTEST_DELAY = 3.0
LONGEST_DELAY = 7.0

red = (40, 0, 0)
black = (0, 0, 0)

A4refhz = 440
midpoint = 32768
twopi = 2 * math.pi


def sawtooth(angle):
    """A sawtooth function like math.sin(angle).
    Input of 0 returns 1.0, pi returns 0.0, 2*pi returns -1.0."""

    return 1.0 - angle % twopi / twopi * 2

# make a sawtooth wave between +/- each value in volumes
# phase shifted so it starts and ends near midpoint
# "H" arrays for RawSample looks more memory efficient
# see https://forums.adafruit.com/viewtopic.php?f=60&t=150894
vol = 32767
sample_len = 10
waveraw = array.array("H",
                      [midpoint +
                       round(vol * sawtooth((idx + 0.5) / sample_len
                                            * twopi
                                            + math.pi))
                       for idx in range(sample_len)])

beep = RawSample(waveraw, sample_rate = sample_len * A4refhz)

# play something to get things inside audio libraries initialised
audio.play(beep, loop=True)
time.sleep(0.1)
audio.stop()
audio.play(beep)


# brightness 1.0 saves memory by removing need for a second buffer
# 10 is number of NeoPixels on CPX/CPB
numpixels = const(10)
pixels = neopixel.NeoPixel(board.NEOPIXEL, numpixels, brightness=1.0)

### TODO - switch over to button as this may be quicker to press
### CPX/CPB touchpad (A0 cannot be used)
### video of pressing touchpad shows 20-25 ms travel time for about 4mm 
touchpad = touchio.TouchIn(board.A1)

def wait_finger_off_and_random_delay():
    while touchpad.value:
        pass
    duration = (SHORTEST_DELAY +
                random.random() * (LONGEST_DELAY - SHORTEST_DELAY))
    time.sleep(duration)


def update_stats(stats, type, test_num, duration):
    """Update stats dict and return data in tuple for printing."""
    stats[type]["values"].append(duration)
    stats[type]["sum"] += duration
    stats[type]["mean"] = stats[type]["sum"] / test_num

    if test_num > 1:
        var_s = (sum([(x - stats[type]["mean"])**2 for x in stats[type]["values"]])
                 / (test_num - 1))
    else:
        var_s = 0.0

    stats[type]["sd_sample"] = var_s ** 0.5

    return ("Trial " + str(test_num), type, duration,
            stats[type]["mean"], stats[type]["sd_sample"])

### servo on a CPX appears to be risky, possibly placing
### the audio amp at risk of over-heating perhaps in combination
### with a 500mA capped power supply (from ASUS motherboard)
### https://forums.adafruit.com/viewtopic.php?f=58&t=157190
tactile_enable = False

run = 1
statistics = {"visual": {"values": [], "sum": 0.0, "mean": 0.0, "sd_sample": 0.0},
              "auditory" : {"values": [], "sum": 0.0, "mean": 0.0, "sd_sample": 0.0},
              "tactile" : {"values": [], "sum": 0.0, "mean": 0.0, "sd_sample": 0.0}}

### serial console output is printed as tuple to allow Mu to graph it
while True:
    wait_finger_off_and_random_delay()
    gc.collect()
    pixels[0] = red
    start_t = time.monotonic()
    while not touchpad.value:
        pass
    react_t = time.monotonic()
    reaction_dur = react_t - start_t
    print(update_stats(statistics, "visual", run, reaction_dur))
    pixels[0] = black

    wait_finger_off_and_random_delay()
    speaker_enable.value = True
    gc.collect()
    audio.play(beep, loop=True)
    start_t = time.monotonic()
    while not touchpad.value:
        pass
    react_t = time.monotonic()
    reaction_dur = react_t - start_t
    print(update_stats(statistics, "auditory", run, reaction_dur))
    audio.stop()
    speaker_enable.value = False

    if tactile_enable:
        wait_finger_off_and_random_delay()
        gc.collect()
        servo.angle = 10
        start_t = time.monotonic()
        while not touchpad.value:
            pass
        react_t = time.monotonic()
        reaction_dur = react_t - start_t
        print(update_stats(statistics, "tactile", run, reaction_dur))
        servo.angle = 0

    run += 1
