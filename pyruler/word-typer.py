### word-typer.py v1.0
### Type words from the word list whilst cycling colours on DotStar pixel

### copy this file to Adafruit PyRuler as code.py

### MIT License

### Copyright (c) 2022 Kevin J. Walters

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


import gc
import time

import board
from digitalio import DigitalInOut, Direction
import touchio
import usb_hid

gc.collect()
from rainbowio import colorwheel
gc.collect()
from mini_dotstar import DotStar
gc.collect()
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
gc.collect()

### The time to spin the colour wheel for the RGB DotStar pixel
CYCLE_TIME = 30.0
### Use third button as a space (short press) or return key (long press)
SPACE_RETURN = 3


pixel = DotStar(board.DOTSTAR_CLOCK, board.DOTSTAR_DATA, 1, brightness=0.07)

### Some Adafruit code has a sleep
### "Sleep for a bit to avoid a race condition on some systems"
time.sleep(1)
try:
    ### timeout argument appears to be important for this to work without a keyboard
    ### as seen in https://github.com/songxxzp/pyKeyboardOS/blob/main/docs/final_report.md
    keyboard = Keyboard(usb_hid.devices, timeout=2)
    keyboard_layout = KeyboardLayoutUS(keyboard)
except:
    keyboard = None
    keyboard_layout = None

touches = [DigitalInOut(board.CAP0)]
for p in (board.CAP1, board.CAP2, board.CAP3):
    touches.append(touchio.TouchIn(p))

leds = []
for p in (board.LED4, board.LED5, board.LED6, board.LED7):
    led = DigitalInOut(p)
    led.direction = Direction.OUTPUT
    led.value = True
    time.sleep(0.25)
    leds.append(led)
for led in leds:
    led.value = False


def cap_touch(pin):
    count = 0
    pin.direction = Direction.OUTPUT
    pin.value = True
    pin.direction = Direction.INPUT
    # funky idea but we can 'diy' the one non-hardware captouch device by hand
    # by reading the drooping voltage on a tri-state pin.
    count = pin.value + pin.value + pin.value + pin.value + pin.value + \
            pin.value + pin.value + pin.value + pin.value + pin.value
    return min(count, 4)


### Adafruit's read_caps() tweaked
CAP_THRESHOLD = 3000
buttons = [False, False, False, False]
cap_value = 0.0
cap_press = False
def read_caps():
    global buttons, cap_value, cap_press

    cap_value = (cap_value * 0.875) + cap_touch(touches[0]) / 8
    cap_press = cap_value >= (2.2 if cap_press else 2.7)
    buttons[0] = cap_press
    buttons[1] = touches[1].raw_value > CAP_THRESHOLD
    buttons[2] = touches[2].raw_value > CAP_THRESHOLD
    buttons[3] = touches[3].raw_value > CAP_THRESHOLD
    return buttons


### Spin the colour wheel every CYCLE_TIME
def update_pixel(px, time_s):
    px[0] = colorwheel(time_s % CYCLE_TIME * (255.9 / CYCLE_TIME))


file_line = [1] * len(buttons)
def get_string(b_idx):
    word = ""
    try:
        line_no = 1
        with open("strings-{:d}.txt".format(b_idx),
                  encoding="UTF-8") as fh:
            word = fh.readline()
            first_word = word
            while True:
                if word:
                    if line_no == file_line[b_idx]:
                        file_line[b_idx] += 1
                        break
                else:
                    word = first_word
                    file_line[b_idx] = 1
                    break

                word = fh.readline()
                line_no += 1
    except OSError:
        return None

    return word.rstrip()


### Wait for release whilst running update_pixel
def wait_release(timeout_s):
    waituntil_s = time.monotonic() + timeout_s
    while (now_s := time.monotonic()) < waituntil_s and any(read_caps()):
        update_pixel(pixel, now_s)

    return now_s >= waituntil_s


while True:
    update_pixel(pixel, time.monotonic())
    caps = read_caps()

    for idx, val in enumerate(caps):
        leds[idx].value = val

    if keyboard_layout:
        for idx, val in enumerate(caps):
            if val:
                if idx == SPACE_RETURN:
                    long_press = wait_release(0.5)
                    chars = "\n" if long_press else " "
                else:
                    chars = get_string(idx)

                if chars:
                    keyboard_layout.write(chars)

        ### Wait for finger to lift from all pads
        if any(caps):
            wait_release(1.0)
            time.sleep(0.05)
