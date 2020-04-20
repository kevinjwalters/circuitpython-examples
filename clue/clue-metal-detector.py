### clue-metal-detector v0.6
### A metal detector using a minimum number of external components

### Tested with an Adafruit CLUE (Alpha) and CircuitPython and 5.2.0

### Pad P0 is an output and pad P1 is an input

### copy this file to CLUE board as code.py

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

import time
import math
import struct
import array
import time

import board
import pulseio
import analogio
import digitalio
##import gc
from displayio import Group
import terminalio
### TODO - ensure these are good for 5.2.0 and ideally would work on CPX
import audiopwmio
import audiocore

### TODO - add manual re-calibrate
### TODO - track drifts
### TODO - audio on/off
### TODO - make uT and mV static to reduce dirty part

### https://circuitpython.readthedocs.io/projects/display-shapes/en/latest/api.html#rect

from adafruit_clue import clue
from adafruit_display_text.label import Label
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.circle import Circle

### globals
debug = 1
samples = []


### Initialise sound
vol = 32767
midpoint = 32768
wave_samples_n = 10
raw_samples = array.array("H",
                          [round(vol * math.sin(2 * math.pi
                                     * (idx / wave_samples_n)))
                           + midpoint
                           for idx in range(wave_samples_n)])
sound_samples = audiocore.RawSample(raw_samples)
audio_out = audiopwmio.PWMAudioOut(board.SPEAKER)

### TODO is looking for board.DISPLAY a reasonable
### way to work out if we are on CPB+Gizmo
display = board.DISPLAY

# screen_group = displayio.Group(max_size=4)
# screen_group.append(operand1_gob.displayio_group())
# screen_group.append(operand2_gob.displayio_group())
# screen_group.append(operator_gob.displayio_group())
# screen_group.append(result_gob.displayio_group())
# screen_ops[selected_op_idx].cursor_visible = True


def sample_sum(pin, num):
    global samples
    samples[:] = [pin.value for _ in range(num)]
    return sum(samples)


def start_beep(freq):
    sound_samples.sample_rate = freq * wave_samples_n
    audio_out.play(sound_samples, loop=True)


### Start-up splash screen

### Initialise detector display

magnet_dob = Label(font=terminalio.FONT,
                   text="----.-uT",
                   scale=3,
                   color=0xc0c000)
magnet_dob.y = 90

magnet_circ_dob = Circle(60, 180, 5,
                         fill=0xc0c000)

voltage_dob = Label(font=terminalio.FONT,
                    text="----.-mV",
                    scale=3,
                    color=0x00c0c0)
voltage_dob.y = 30

voltage_barneg_dob = Rect(160, 117, 80, 1, fill=0x00c0c0)

voltage_sep_dob = Rect(160,119, 80,4, fill=0x0000ff)

voltage_barpos_dob = Rect(160, 122, 80, 1, fill=0x00c0c0)

screen_group = Group(max_size=6)
screen_group.append(magnet_dob)
screen_group.append(voltage_dob)
screen_group.append(voltage_sep_dob)
screen_group.append(magnet_circ_dob)
screen_group.append(voltage_barneg_dob)
screen_group.append(voltage_barpos_dob)

display.show(screen_group)

### TODO check whether values have changed before replacing objects

def voltage_bar_set(volt_diff):
    global voltage_barneg_dob, voltage_barpos_dob
    if volt_diff < 0:
        negbar_len = max(min(-round(volt_diff * 5e3), 118), 1)
        posbar_len = 1
    else:
        negbar_len = 1
        posbar_len = max(min(round(volt_diff * 5e3), 118), 1)

    screen_group.remove(voltage_barneg_dob)
    voltage_barneg_dob = Rect(160, 118 - negbar_len, 80, negbar_len,
                                  fill=0x00c0c0)
    screen_group.append(voltage_barneg_dob)
    
    screen_group.remove(voltage_barpos_dob)
    voltage_barpos_dob = Rect(160, 121, 80, posbar_len,
                              fill=0x00c0c0)
    screen_group.append(voltage_barpos_dob)


def magnet_circ_set(mag_ut):
    global magnet_circ_dob
    radius = min(round(math.sqrt(mag_ut) * 4), 59)

    screen_group.remove(magnet_circ_dob)
    magnet_circ_dob = Circle(60, 180, radius,
                             fill=0xc0c000)
    screen_group.append(magnet_circ_dob)


### P1 for analogue input
pin_input = analogio.AnalogIn(board.P1)
CONV_FACTOR = pin_input.reference_voltage / 65535

### Start pwm output
pwm = pulseio.PWMOut(board.P0, frequency=400 * 1000,
                     duty_cycle=0, variable_frequency=True)
pwm.duty_cycle = 55000


### Get magnetic value
totals = [0.0] * 3
mag_samples_n = 10
for _ in range(mag_samples_n):
   mx, my, mz = clue.magnetic
   totals[0] += mx
   totals[1] += my
   totals[2] += mz
   time.sleep(0.05)

base_mx = totals[0] / mag_samples_n
base_my = totals[1] / mag_samples_n
base_mz = totals[2] / mag_samples_n

### Wait a bit for P1 input to stabilise
base_voltage = sample_sum(pin_input, 3000) / 3000 * CONV_FACTOR
voltage_dob.text = "{:6.1f}mV".format(base_voltage * 1000.0)

### Auto refresh off
### TODO review this
##display.auto_refresh = False

while True:
    ### read p1 value
    voltage = sample_sum(pin_input, 500) / 500.0 * CONV_FACTOR
    
    ### update text
    voltage_dob.text = "{:6.1f}mV".format(voltage * 1000.0)
    
    ### update bargraphs
    
    ### update audio
    diff_v = voltage - base_voltage
    voltage_bar_set(diff_v)
    #### make an andio frequency between 100 and 5000
    frequency = min(100 + diff_v**2 * 1e8, 5000)
    start_beep(round(frequency))
    
    ### read magnetometer
    mx, my, mz = clue.magnetic
    diff_x = mx - base_mx
    diff_y = my - base_my
    diff_z = mz - base_mz
    mag_z = math.sqrt(diff_x * diff_x + diff_y * diff_y + diff_z * diff_z)
    magnet_dob.text = "{:6.1f}uT".format(mag_z)
    magnet_circ_set(mag_z)
    
    ### update circle

    ### check for buttons
