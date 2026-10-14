### emfexplorer-ledanim v1.0
### Animated LEDs on Pi Pico GPIO monitoring the signals from an EMF Explorer Badge

### Tested on Pi Pico running CircuitPython 10.3.1

### copy this file to Pico as code.py

### MIT License

### Copyright (c) 2026 Kevin J. Walters

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

### SPDX-FileCopyrightText: 2026 Kevin J. Walters

### This program is intended for a Pi Pico attached to
### an EMF Explorer Badge (https://emfexplorer.space/)
### with LEDs, like Adafruit Sequins, on GPIO and the
### EMF Explorer's amplified output connected to
### analogue capable pins on Pi Pico

### See https://www.instructables.com/member/kevinjwalters for details on
### the extra components required and how to set this up


import array
import gc
import os
import time

import analogbufio
import board
import digitalio
import microcontroller
import pwmio
import ulab
from ulab import numpy as np


### 40960 / 8192 is 10 for 50 cycles, 12 for 60 cycles
### 40960 / 4096 is 5 for 50 cycles, 6 for 60 cycles
AUDIO_RATE = 40960
SAMPLE_BUFLEN = 4096  ### Needs to be 2^N in size
FFT_LAST = SAMPLE_BUFLEN // 2

### Above audible range to deal with interference issues
PWM_FREQ = 25_000

debug = 0


machine = os.uname().machine
if (machine.find("Raspberry Pi Pico") >= 0
    or machine.find("Waveshare RP2350-LCD-0.96") >=0
    or machine.find("Cytron EDU PICO") >= 0):
    LEFT_LED_PINS = (board.GP7, board.GP13, board.GP14)
    RIGHT_LED_PINS = (board.GP26, board.GP18, board.GP17)
    LEFT_AUDIO_PIN = board.GP27
    RIGHT_AUDIO_PIN = board.GP28
    LEFT_TOUCH_PIN = board.GP15
    RIGHT_TOUCH_PIN = board.GP16
else:
    raise ValueError("Unsupported board...")

if os.uname().sysname.upper() == "RP2040":
    microcontroller.cpu.frequency = 150_000_000

### Turn off the console (REPL output to display)
display = None
try:
    display = board.DISPLAY
    import displayio
    import bitmaptools
    main_group = displayio.Group()
    display.root_group = main_group
    display.auto_refresh = False
    bitmap = displayio.Bitmap(board.DISPLAY.width, board.DISPLAY.height, 4)
    palette = displayio.Palette(8)
    palette[0] = 0x000000
    palette[1] = 0xc00000   ### red
    palette[2] = 0x0000c0   ### blue
    palette[3] = 0xc000c0   ### magenta
    palette[4] = 0xc0c0c0   ### white
    palette[5] = 0xff0000   ### bright red
    palette[6] = 0x0000ff   ### bright blue
    palette[7] = 0xff00ff   ### bright magenta
    tile_grid = displayio.TileGrid(bitmap,
                                   pixel_shader=palette)
    main_group.append(tile_grid)
except AttributeError:
    pass   ### board without a display


board_led = None
try:
    board_led = digitalio.DigitalInOut(board.LED)
    board_led.direction = digitalio.Direction.OUTPUT
except AttributeError:
    pass   ### board without an LED


left_leds = tuple(pwmio.PWMOut(pin, frequency=PWM_FREQ) for pin in LEFT_LED_PINS)
right_leds = tuple(pwmio.PWMOut(pin, frequency=PWM_FREQ) for pin in RIGHT_LED_PINS)

RAMPUP = (0, 1_000, 2_000, 5000, 10_000, 15_000, 24_000, 36_000, 48_000, 65535)



def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)



d_print(1, "A pause to allow for control-c before analogbufio use")
time.sleep(10)


def led_anim1(speed=1, brightness=1):
    ##la_start_ns = time.monotonic_ns()
    ##for delay_ns in [d // speed for d in (7_000_000, 5_000_000, 3_000_000)]:
    for delay_ns in [round(d / speed) for d in (10_000_000,)]:
        for l_led, r_led in zip(reversed(left_leds), reversed(right_leds)):
            for ramp in RAMPUP:
                start_ns = time.monotonic_ns()
                l_led.duty_cycle = ramp
                r_led.duty_cycle = ramp
                while time.monotonic_ns() < start_ns + delay_ns:
                    pass
            start_ns = time.monotonic_ns()
            while time.monotonic_ns() < start_ns + delay_ns * 6:
                pass
            for idx in range(len(RAMPUP) - 1, 0 - 1, -1):
                start_ns = time.monotonic_ns()
                ramp = RAMPUP[idx]
                l_led.duty_cycle = ramp
                r_led.duty_cycle = ramp
                while time.monotonic_ns() < start_ns + delay_ns:
                    pass
            while time.monotonic_ns() < start_ns + delay_ns * 6:
                pass


def update_plot(left_spec_sig, right_spec_sig):
    bitmap.fill(0)
    for freq in range(1, 160 + 1):
        db = np.interp(left_spec_sig[freq], sigtodb_interp_x, sigtodb_interp_y)[0]
        line_level = round(db + 79)
        if line_level >= 0:
            bitmaptools.draw_line(bitmap, freq - 1, 0, freq - 1, line_level, 1)

    display.refresh()


time.sleep(5)


### This maps 0 to 16777216 (2^(12*2)) to -999999 (for -Inf) to 0
MAX_FFT_VALUE = 16777216
sigtodb_interp_y = np.array([-999999] + list(range(-100, 0 + 1)))
sigtodb_interp_x = np.array([MAX_FFT_VALUE * 10**(db / 20) for db in sigtodb_interp_y])


### CircuitPython can only sample one ADC pin at the moment with analogbufio
### https://forums.adafruit.com/viewtopic.php?t=225420
adcbufin = analogbufio.BufferedIn(LEFT_AUDIO_PIN, sample_rate=AUDIO_RATE)
##adc_buf = np.zeros(SAMPLE_BUFLEN, dtype=np.int16)  ### readinto doesn't like ulab
gc.collect()
adc_buf = array.array("H", [0]) * SAMPLE_BUFLEN
adc_npbuf = np.zeros(SAMPLE_BUFLEN, dtype=np.uint16)
adcbufin.readinto(adc_buf, loop=True)


while True:
    gc.collect()  ### TODO - put this into wait loop with sleep
    adc_npbuf[:] = adc_buf   ### this should not allocate but it appears to
    ##for idx in range(SAMPLE_BUFLEN):
    ##    adc_npbuf[idx] = adc_buf[idx]
    time.sleep(0.1)
    start_spec_ns = time.monotonic_ns()
    ### For 8192 uint16 input this takes 567ms at 125 MHz on Pi Pico
    ### For 4096 uint16 input this takes 261ms at 125 MHz on Pi Pico
    ### For 4096 uint16 input this takes 9ms at default MHz on Waveshare RP2350

    fftmag = ulab.utils.spectrogram(adc_npbuf)
    end_spec_ns = time.monotonic_ns()
    mean_val = np.sum(fftmag[1:FFT_LAST]) / FFT_LAST
    max_val = np.max(fftmag[1:FFT_LAST])
    if debug >= 3:
        d_print(3,
                (end_spec_ns - start_spec_ns) * 1e-6, mean_val, max_val, "|",
            [round(fftmag[idx]) for idx in range(0, 19)])
    if max_val >= 9_000:
        anim_speed = max_val / 7000
        led_anim1(speed=anim_speed)
    if display:
        update_plot(fftmag, None)
    del fftmag  ### Need the memory back from this large array
