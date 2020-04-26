### clue-metal-detector v0.8
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
import ulab
import gc
from displayio import Group
import terminalio
### TODO - ensure these are good for 5.2.0 and ideally would work on CPX
import audiopwmio
import audiocore

### TODO - add manual re-calibrate
### TODO - track drifts (5, 10 seconds?)
### TODO - could split avg to look for outliers
### TODO - audio on/off
### TODO - make uT and mV static to reduce dirty part
### TODO - could do something with CLUE's reverse NeoPixel
###        R G B / intensity or flashing may make more sense

### TODO - change font colour for pos / neg perhaps graduated
### TODO - deal with 90 degree spins with magnetic side of things
### TODO - do i want to do anything else with that sorted data?
###        could extra min/max or 10/90% and put them up as bars too?
### TODO - add some loop timing and print to debug and perhaps some cumulative
###        loop time
### TODO - buttons - screen on/off
###                  mu output on/off
###                  audio on/off

### https://circuitpython.readthedocs.io/projects/display-shapes/en/latest/api.html#rect

from adafruit_clue import clue
from adafruit_display_text.label import Label
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.circle import Circle

### globals
debug = 3
samples = []

quantize_tones = True

mu_output = True


def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


def voltage_bar_set(volt_diff):
    """Draw a bar based on positive or negative values.
       Width of 60 is performance compromise as more pixels take longer."""
    global voltage_sep_dob, voltage_barneg_dob, voltage_barpos_dob
    
    if voltage_sep_dob is None:
        voltage_sep_dob = Rect(160,119, voltage_width,4, fill=0x0000ff)
    
    if volt_diff < 0:
        negbar_len = max(min(-round(volt_diff * 5e3), 118), 1)
        posbar_len = 1
    else:
        negbar_len = 1
        posbar_len = max(min(round(volt_diff * 5e3), 118), 1)

    if voltage_barneg_dob is not None:
        screen_group.remove(voltage_barneg_dob)
    voltage_barneg_dob = Rect(160, 118 - negbar_len,
                              voltage_width, negbar_len,
                              fill=0x00c0c0)
    screen_group.append(voltage_barneg_dob)

    if voltage_barpos_dob is not None:
        screen_group.remove(voltage_barpos_dob)
    voltage_barpos_dob = Rect(160, 121, 60, posbar_len,
                              fill=0xc000c0)
    screen_group.append(voltage_barpos_dob)

BASE_NOTE = 261.6256  ### C4 (middle C)
QUANTIZE = 4
POSTLOG_FACTOR = QUANTIZE / math.log(2)

def start_beep(freq, wave, wave_idx):
    """Start playing a continous beep based on freq and waveform specified by wave_idx.
       A frequency of 0 will stop the note playing.
       This modifies the sample_rate property of the RawSample objects.
       """
    global last_frequency
    if freq == 0:
        if last_frequency != 0:
            audio_out.stop()
            last_frequency = 0
        return

    if quantize_tones:
       ### TODO - make constants externally
       note_freq = BASE_NOTE * 2**((round(math.log(freq / BASE_NOTE)
                                          * POSTLOG_FACTOR)) / QUANTIZE)
       d_print(3, "Quantize", freq, note_freq)
    else:
       note_freq = freq

    (waveform, wave_samples_n) = wave[wave_idx]
    new_freq = round(note_freq * wave_samples_n)
    ### Only set the new frequency if it's not the last one
    if new_freq != last_frequency:
        waveform.sample_rate = new_freq
        audio_out.play(waveform, loop=True)
        last_frequency = new_freq


### Initialise audio output
audio_out = audiopwmio.PWMAudioOut(board.SPEAKER)

### Initialise sounds
AUDIO_MIDPOINT = 32768

def make_sample_list(levels=10,
                     volume=32767,
                     range_l=24,
                     start_l=8):
    """Make a list of RawSample objects with a sine wave of varying resolution
       from high to low.
       The lower resolutions sound louder on the CLUE."""

    sample_lens = [int((x*(range_l + .99)/(levels - 1)) + start_l)
                   for x in range(0, levels)]
    sample_lens.reverse()

    wavefs = []
    for s_len in sample_lens:
        raw_samples = array.array("H",
                                  [round(volume * math.sin(2 * math.pi
                                     * (idx / s_len)))
                                   + AUDIO_MIDPOINT
                                   for idx in range(s_len)])
        sound_samples = audiocore.RawSample(raw_samples)
        wavefs.append((sound_samples, s_len))

    return wavefs
    
waveforms = make_sample_list()
last_frequency = 0

if debug >= 3:
    for idx in range(len(waveforms)):
        start_beep(440, waveforms, idx)
        time.sleep(0.1)
    start_beep(0, waveforms, idx)  ### this silences it


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
    global samples   ### Not strictly needed - indicative of r/w use
    samples[:] = [pin.value for _ in range(num)]
    return sum(samples)


### Start-up splash screen

### Initialise detector display

magnet_dob = Label(font=terminalio.FONT,
                   text="----.-uT",
                   scale=3,
                   color=0xc0c000)
magnet_dob.y = 90

magnet_circ_dob = Circle(60, 180, 5,
                         fill=0xc0c000)

voltage_width = 60

voltage_dob = Label(font=terminalio.FONT,
                    text="----.-mV",
                    scale=3,
                    color=0x00c0c0)
voltage_dob.y = 30


screen_group = Group(max_size=6)
screen_group.append(magnet_dob)
screen_group.append(voltage_dob)
screen_group.append(magnet_circ_dob)

voltage_barneg_dob = None
voltage_sep_dob = None
voltage_barpos_dob = None
### Initialise the previous displayio objects and append them
voltage_bar_set(0)

display.show(screen_group)

### TODO check whether values have changed before replacing objects




def magnet_circ_set(mag_ut):
    global magnet_circ_dob
    radius = min(max(round(math.sqrt(mag_ut) * 4), 1), 59)

    screen_group.remove(magnet_circ_dob)
    magnet_circ_dob = Circle(60, 180, radius,
                             fill=0xc0c000)
    screen_group.append(magnet_circ_dob)


def manual_screen_refresh(disp):
    refreshed = False
    while True:
        try:
            refreshed = display.refresh(minimum_frames_per_second=0,
                                        target_frames_per_second=1000)
        except Exception:
            pass
        if refreshed:
            break


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

display.auto_refresh = False
voltage_zm1 = None
voltage_zm2 = None
filt_voltage = None
mag_mag = 0.0

### Keep some historical averages of history
### aiming for about 10 reads per second so this gives
### 20 seconds
voltage_hist = ulab.zeros(201, dtype=ulab.float)
voltage_hist_idx = 0
voltage_hist_complete = False
voltage_hist_median = None

### reduce the number of more heavyweight graphical changes
update_basic_graphics_period = 2
update_complex_graphics_period = 4
update_median_period = 5

counter = 0

audio_on = True


while True:
    ### garbage collect now to reduce likelihood it occurs
    ### during sample reading
    gc.collect()
    
    ### read p1 value
    screen_updates = 0
    sample_start_time_ns = time.monotonic_ns()
    
    samples_to_read = 500  ### about 23ms worth on CLUE
    update_basic_graphics = counter % update_basic_graphics_period == 0
    if not update_basic_graphics:
        samples_to_read += 150
    update_complex_graphics = counter % update_complex_graphics_period == 0
    if not update_complex_graphics:
        samples_to_read += 400
    update_median = counter % update_median_period == 0
    if not update_median:
        samples_to_read += 50
    voltage = sample_sum(pin_input, 500) / 500.0 * CONV_FACTOR
   
    voltage_zm2 = voltage_zm1
    voltage_zm1 = voltage
   
    if voltage_zm1 is None:
        voltage_zm1 = voltage
    if voltage_zm2 is None:
        voltage_zm2 = voltage

    filt_voltage = (voltage * 0.4
                    + voltage_zm1 * 0.3 
                    + voltage_zm2 * 0.3)                    

    update_basic_graphics = counter % update_basic_graphics_period == 0
    update_complex_graphics = counter % update_complex_graphics_period == 0

    ### update text
    if update_basic_graphics:
        voltage_dob.text = "{:6.1f}mV".format(filt_voltage * 1000.0)
        screen_updates += 1

    ### read magnetometer
    mx, my, mz = clue.magnetic
    diff_x = mx - base_mx
    diff_y = my - base_my
    diff_z = mz - base_mz   ### TODO - maybe change this to only use z value if that helps with turning
    mag_mag = math.sqrt(diff_x * diff_x + diff_y * diff_y + diff_z * diff_z)

    ### update audio
    ### make an andio frequency
    ### between 100Hz (won't be audible) and 5000 (loud on miniscule speaker)
    diff_v = filt_voltage - base_voltage
    abs_diff_v = abs(diff_v)
    if audio_on:
        frequency = min(100 + abs_diff_v * 5e5, 5000) if abs_diff_v > 0.002 or mag_mag > 2.0 else 0
        start_beep(frequency, waveforms,
                   min(int(mag_mag / 2), len(waveforms) - 1))

    ### update bargraphs
    if update_complex_graphics:
       voltage_bar_set(diff_v)
       screen_updates += 1

    if update_basic_graphics:
        magnet_dob.text = "{:6.1f}uT".format(mag_mag)
        screen_updates += 1
    if update_complex_graphics:
        magnet_circ_set(mag_mag)
        screen_updates += 1

    ### update circle

    ### check for buttons

    if screen_updates:
        manual_screen_refresh(display)
    if mu_output:
        print((voltage, mag_mag))

    if voltage_hist_complete and update_median:
        voltage_hist_median = ulab.numerical.sort(voltage_hist)[len(voltage_hist) // 2]
        base_voltage = voltage_hist_median  ### TODO EXPERIMENTAL

    d_print(1, counter, sample_start_time_ns / 1e9,
            voltage * 1000.0,
            mag_mag,
            filt_voltage * 1000.0, base_voltage, voltage_hist_median)

    voltage_hist[voltage_hist_idx] = voltage
    if voltage_hist_idx >= len(voltage_hist) - 1:
        voltage_hist_idx = 0
        voltage_hist_complete = True
    else:
        voltage_hist_idx += 1

    counter += 1
