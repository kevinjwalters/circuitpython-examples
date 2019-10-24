### cpx-reaction-timer v0.5
### A human reaction timer using light and sound with touch pads
### Measures the time it takes for user to press A1

### Tested with CPX and CircuitPython XXX

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
import audioio

import neopixel
import adafruit_motor.servo

# create a PWMOut object on pad A6
pwma6 = pulseio.PWMOut(board.A6, duty_cycle=2 ** 15, frequency=50)
servo = adafruit_motor.servo.Servo(pwma6)
servo.angle = 0

# Turn the speaker on
speaker_enable = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
speaker_enable.direction = digitalio.Direction.OUTPUT
speaker_on = True
speaker_enable.value = speaker_on

dac = audioio.AudioOut(board.SPEAKER)

A4refhz = 440
midpoint = 32768
twopi = 2 * math.pi

# A sawtooth function like math.sin(angle)
# 0 returns 1.0, pi returns 0.0, 2*pi returns -1.0
def sawtooth(angle):
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

beep = audioio.RawSample(waveraw, sample_rate = sample_len * A4refhz)

clicks = audioio.RawSample(array.array("H", [midpoint, 65535, 0] + [midpoint] * 93),
                           sample_rate = 4 * 100)

# play something to get things initialised
dac.play(beep, loop=True)
time.sleep(0.050)
dac.stop()

dac.play(clicks, loop=True)
time.sleep(0.5)
dac.stop()

# brightness 1.0 saves memory by removing need for a second buffer
# 10 is number of NeoPixels on CPX
numpixels = const(10)
pixels = neopixel.NeoPixel(board.NEOPIXEL, numpixels, brightness=1.0)

### CPX touchpad (A0 cannot be used)
touchpad = touchio.TouchIn(board.A1)

### a is left (usb at top)
buttonleft = digitalio.DigitalInOut(board.BUTTON_A)
buttonleft.switch_to_input(pull=digitalio.Pull.DOWN)
buttonright = digitalio.DigitalInOut(board.BUTTON_B)
buttonright.switch_to_input(pull=digitalio.Pull.DOWN)

### servo on a CPX appears to be risky, possibly placing
### the audio amp at risk of over-heating
### https://forums.adafruit.com/viewtopic.php?f=58&t=157190
tactile_enable = False

run=1

while True:
    while touchpad.value:
        pass
    time.sleep(3.0 + random.random() * 4.0)
    gc.collect()
    pixels[0] = (40, 0, 0)
    start_t = time.monotonic()
    while not touchpad.value:
        pass
    react_t = time.monotonic()
    reaction_dur = react_t - start_t
    print("Trial ", run, ": visual reaction time is ", reaction_dur)
    pixels[0] = (0, 0, 0)
        
    while touchpad.value:
        pass
    time.sleep(3.0 + random.random() * 4.0)
    gc.collect()
    dac.play(beep, loop=True)
    start_t = time.monotonic()
    while not touchpad.value:
        pass
    react_t = time.monotonic()
    reaction_dur = react_t - start_t
    print("Trial ", run, ": audio reaction time is ", reaction_dur)
    dac.stop()        
    
    if tactile_enable:
        while touchpad.value:
            pass
        time.sleep(3.0 + random.random() * 4.0)
        gc.collect()
        servo.angle = 10
        start_t = time.monotonic()
        while not touchpad.value:
            pass
        react_t = time.monotonic()
        reaction_dur = react_t - start_t
        print("Tactile reaction time is ", reaction_dur)
        servo.angle = 0

    run += 1
    
    if buttonleft.value:
        while buttonleft.value:
            pass   ### wait for button up
    if buttonright.value:
        while buttonright.value:
            pass   ### wait for button up
