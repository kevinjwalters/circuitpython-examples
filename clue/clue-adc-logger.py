### clue-adc-logger v1.0
### Record ADC samples with different grounds

### This collects samples from an analogue pin and writes them to flash
### The ground cycles from the normal ground pins, a low output and an
### input with pull down
###
### This is intended to be used to study the differences and ADC noise on the
### nNF52840 in Adafruit CLUE form
###
### Hold left button on at power-up to enable writes to CLUE's CIRCUITPY
### file system then press right button to start each of the three tests

### Tested with an Adafruit CLUE and CircuitPython 8.1.0

### copy this file to CPX board as code.py

### MIT License

### Copyright (c) 2023 Kevin J. Walters

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


### TODO analogbufio if it appears on nRF52840 boards

### TODO check if brightness values between
### off (0.0) and on (1.0) introduce noise from PWM


import time
import gc
import sys
import array

import board
import storage
import analogio
import digitalio

import neopixel


### Avoid P0/P1/P2 as these are different with the 1M resistors to GND
adc_pin = board.P4
pseudo_gnd_pin = board.P10
ain = analogio.AnalogIn(adc_pin)


GREEN = 0x004000
RED = 0x800000

pin_a = board.BUTTON_A
pin_b = board.BUTTON_B
pin_but_a = digitalio.DigitalInOut(pin_a)
pin_but_a.switch_to_input(pull=digitalio.Pull.UP)
pin_but_b = digitalio.DigitalInOut(pin_b)
pin_but_b.switch_to_input(pull=digitalio.Pull.UP)
left_button = lambda: not pin_but_a.value
right_button = lambda: not pin_but_b.value

status_led = neopixel.NeoPixel(board.NEOPIXEL, 1)

sample_count = 20000
sample_buffer = array.array("H", [0] * sample_count)

intra_step_pause = 0.25


def pixelFlash(colour=GREEN, duration=0.5):
    status_led.fill(colour)
    time.sleep(duration)
    status_led.fill(0x000000)
    return True


def bigPause():
    time.sleep(15)
    return True


def collectSamples(buf, adc, p_g_pin_, gnd_type_, cnt, optargs=None):

    p_g = digitalio.DigitalInOut(p_g_pin_)
    if gnd_type_ == "gnd":
        pass
    elif gnd_type_ == "output low":
        p_g.switch_to_output(value=False)
    elif gnd_type_ == "input pull-down":
        p_g.switch_to_input(pull=digitalio.Pull.DOWN)
    else:
        p_g.deinit()
        raise ValueError("Unknown gnd_type_: " + gnd_type_)

    args_ = {} if optargs is None else optargs
    pause = args_.get("pause")
    pause = 0 if pause is None else pause

    ### Separate loops to keep them as fast as possible
    print("COLLECTING", cnt)
    if pause > 0:
        for idx in range(cnt):
            buf[idx] = adc.value
            time.sleep(pause)
    else:
        for idx in range(cnt):
            buf[idx] = adc.value

    p_g.deinit()


def saveSamples(fname, buffer, cnt):
    """Write buffer data to the filename in machine order
       erasing any prior content."""
    exception = None

    try:
        with open(fname, "wb") as fh:
            fh.write(memoryview(buffer)[:cnt])
    except OSError as oe:
        exception = oe

    return exception


### Screen off including power hungry backlight
board.DISPLAY.root_group = None
board.DISPLAY.brightness = 0

steps = (
         (right_button, None, None, None, {}),
         (pixelFlash, None, None, None, {}),
         (bigPause, None, None, None, {}),
         (pixelFlash, None, None, None, {}),
         (ain, pseudo_gnd_pin, "gnd", sample_count, {"pause": 0}),
         (ain, pseudo_gnd_pin, "gnd", sample_count, {"pause": 0.01}),
         (right_button, None, None, None, {}),
         (pixelFlash, None, None, None, {}),
         (bigPause, None, None, None, {}),
         (pixelFlash, None, None, None, {}),
         (ain, pseudo_gnd_pin, "output low", sample_count, {"pause": 0}),
         (ain, pseudo_gnd_pin, "output low", sample_count, {"pause": 0.01}),
         (right_button, None, None, None, {}),
         (pixelFlash, None, None, None, {}),
         (bigPause, None, None, None, {}),
         (pixelFlash, None, None, None, {}),
         (ain, pseudo_gnd_pin, "input pull-down", sample_count, {"pause": 0}),
         (ain, pseudo_gnd_pin, "input pull-down", sample_count, {"pause": 0.01}),
         )

collection = 1

### Warn user if file system isn't writeable
if storage.getmount("/").readonly:
    for _ in range(30):
        pixelFlash(RED, 0.2)
        time.sleep(0.1)
else:
    print("Ready for sampling")

while True:
    for action_or_input, p_g_pin, gnd_type, count, args in steps:

        if callable(action_or_input):
            while not action_or_input():
                pass
            time.sleep(intra_step_pause)
            continue

        print("Collecting samples run=" + str(collection) +
              " type=" + gnd_type + " samples=" + str(count) + " args", args)
        gc.collect()
        collectSamples(sample_buffer, action_or_input, p_g_pin, gnd_type, count, args)
        filename = "samples.{:s}.{:d}.{:s}.bin".format(gnd_type.replace(" ", "-"),
                                                       collection,
                                                       sys.byteorder)
        collection += 1
        print("Saving samples to:", filename)
        ose = saveSamples(filename, sample_buffer, count)
        if ose is not None:
            print("Exception: " + str(ose))
            pixelFlash(RED)
        time.sleep(intra_step_pause)
