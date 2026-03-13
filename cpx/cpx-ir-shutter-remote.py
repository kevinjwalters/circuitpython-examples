### cpx-ir-shutter-remote v1.6
### Circuit Playground Express (CPX) shutter remote using infrared for Sony Cameras

### copy this file to CPX as code.py

### MIT License

### Copyright (c) 2020-2026 Kevin J. Walters

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

import board
import digitalio
import pulseio

import neopixel
from audiocore import WaveFile
from audioio import AudioOut
import adafruit_irremote
### Unfortunately the cp object and library are too large to use,
### causes MemoryError for multiple wav plays
#from adafruit_circuitplayground import cp


WAV_DIR="num"
SHUTTER_CMD_COLOUR = 0x080000
IMPENDING_COLOUR = 0x070400
BLACK = 0x000000

### 40kHz modulation (for Sony) with 20% duty cycle
CARRIER_IRFREQ_SONY = 40_000
CARRIER_DC_SONY = round(20 / 100 * 65535)
ir_pulseout = pulseio.PulseOut(board.IR_TX,
                               frequency=CARRIER_IRFREQ_SONY,
                               duty_cycle=CARRIER_DC_SONY)

### Sony timing values (in us) based on the ones in
### https://github.com/z3t0/Arduino-IRremote/blob/master/src/ir_Sony.cpp
### Disabling the addition of trail value is required to make this work
### trail=0 did not work
ir_encoder = adafruit_irremote.GenericTransmit(header=[2400, 600],
                                               one=   [1200, 600],
                                               zero=  [600,  600],
                                               trail=None)

pixels = neopixel.NeoPixel(board.NEOPIXEL, 10, brightness=1.0)
pixels.fill(BLACK)

### A is left, B is right (usb at top)
button_left = digitalio.DigitalInOut(board.BUTTON_A)
button_left.switch_to_input(pull=digitalio.Pull.DOWN)
button_right = digitalio.DigitalInOut(board.BUTTON_B)
button_right.switch_to_input(pull=digitalio.Pull.DOWN)

switch_left = digitalio.DigitalInOut(board.SLIDE_SWITCH)
switch_left.switch_to_input(pull=digitalio.Pull.UP)

### Speaker control
speaker_enable = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
speaker_enable.direction = digitalio.Direction.OUTPUT

audio_out = AudioOut(board.SPEAKER)


def fire_shutter():
    """Send infrared code to fire the shutter.
       This is a code used by Sony cameras."""
    ir_encoder.transmit(ir_pulseout, [0xB4, 0xB8, 0xF0],
                        repeat=2, delay=0.005, nbits=20)


def say_interval(number_as_words):
    words = number_as_words.split() + ["seconds"]
    for word in words:
        if word == ",":
            time.sleep(0.15)
        else:
            play_file(WAV_DIR + "/" + word + ".wav")
        time.sleep(0.050)


def play_file(filename):
    speaker_enable.value = True
    with WaveFile(open(filename, "rb")) as wavefile:
        audio_out.play(wavefile)
        while audio_out.playing:
            pass
    speaker_enable.value = False


S_TO_NS = 1_000_000_000
PREFLASH_NS = 20_000_000
MANUAL_MIN_INT_NS = 400_000_000  ### helps with debounce
IMPENDING_NS = 2 * S_TO_NS
### intervalometer mode announces the duration
manual_trig_wav = "button.wav"
## sound_trig_wav = "noise.wav"  ### To implement
impending_wav = "ready.wav"

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
last_cmd_ns = time.monotonic_ns() - MANUAL_MIN_INT_NS
pixel_indication = True
impending = False
say_and_reset = False
shot_num = 1
first_cmd_ns = time.monotonic_ns()

while True:
    ### CPX switch to left
    if switch_left.value:
        if intervalometer:
            play_file(manual_trig_wav)
            intervalometer = False

        ### Only fire shutter if it's been a while since last press
        ### this helps to debounce this bouncy buttons
        if button_left.value and time.monotonic_ns() - last_cmd_ns >= MANUAL_MIN_INT_NS:
            if pixel_indication:
                pixels.fill(SHUTTER_CMD_COLOUR)
            last_cmd_ns = time.monotonic_ns()
            fire_shutter()
            if shot_num == 1:
                first_cmd_ns = last_cmd_ns
            print("Manual", "shutter release at", (last_cmd_ns - first_cmd_ns) / S_TO_NS)
            if pixel_indication:
                pixels.fill(BLACK)
            shot_num += 1
            while button_left.value:
                pass  ### wait for button release

        elif button_right.value:
            pixel_indication = not pixel_indication
            while button_right.value:
                pass  ### wait for button release

    ### CPX switch to right
    else:
        if not intervalometer:
            say_and_reset = True
            intervalometer = True

        ### Left button (A) decreases time
        if button_left.value and interval_idx > 0:
            interval_idx -= 1
            while button_left.value:
                pass  ### wait for button release
            say_and_reset = True

        ### Right button (B) increases time
        elif button_right.value and interval_idx < len(intervals) - 1:
            interval_idx += 1
            while button_right.value:
                pass  ### wait for button release
            say_and_reset = True

        if say_and_reset:
            say_interval(interval_words[interval_idx])
            last_cmd_ns = time.monotonic_ns()
            say_and_reset = False

        ### If enough time has elapsed fire the shutter
        ### or show the impending colour on NeoPixels
        cum_interval_ns = intervals[interval_idx] * S_TO_NS * shot_num
        now_ns = time.monotonic_ns()
        if now_ns - first_cmd_ns >= cum_interval_ns - PREFLASH_NS:
            if pixel_indication:
                pixels.fill(SHUTTER_CMD_COLOUR)
            ### Wait for exact time
            ### NB: assigment expressions can need care with brackets
            while (last_cmd_ns := time.monotonic_ns()) - first_cmd_ns < cum_interval_ns:
                pass
            fire_shutter()
            if shot_num == 1:
                first_cmd_ns = last_cmd_ns
            print("Timer", "shutter release at", (last_cmd_ns - first_cmd_ns) / S_TO_NS)
            if pixel_indication:
                pixels.fill(BLACK)
            shot_num += 1
            impending = False

        elif (pixel_indication
              and not impending
              and now_ns - first_cmd_ns >= cum_interval_ns - IMPENDING_NS):
            pixels.fill(IMPENDING_COLOUR)
            play_file(impending_wav)
            pixels.fill(BLACK)
            impending = True
