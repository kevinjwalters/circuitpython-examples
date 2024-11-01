### synthio-pwm-benchmark v1.1
### Checking performance of various pwm techniques

### Tested with Pi Pico W (on EDU PICO) and 9.1.4

### copy this file to Cytron Maker Pi Pico as code.py

### MIT License

### Copyright (c) 2024 Kevin J. Walters

### Permission is hereby granted, free of charge, to any person obtaining a copy
### of this software nd associated documentation files (the "Software"), to deal
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

### For https://github.com/adafruit/circuitpython/issues/9780
### based on discussion in https://forums.adafruit.com/viewtopic.php?p=1034152


##import math
import time
import gc

import board
##import analogio
##import digitalio
##import pwmio

import audiomixer
import synthio
import audiopwmio
import ulab.numpy as np

##import usb_midi
##import adafruit_midi
##from adafruit_midi.note_on import NoteOn
##from adafruit_midi.note_off import NoteOff
##from adafruit_midi.control_change import ControlChange
##from adafruit_midi import control_change_values


debug = 1

### higher rate makes LFOs less lumpy
SAMPLE_RATE = 64_000

MIXER_BUFFER_SIZE = 2048
WAVEFORM_PEAK = 28_000
WAVEFORM_MAX = 2**15 - 1
WAVEFORM_LEN = 2048
WAVEFORM_HALFLEN = WAVEFORM_LEN // 2


def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)

audio = audiopwmio.PWMAudioOut(board.GP18, right_channel=board.GP19)
mixer = audiomixer.Mixer(channel_count=1,
                         sample_rate=SAMPLE_RATE,
                         buffer_size=MIXER_BUFFER_SIZE)
synth = synthio.Synthesizer(channel_count=1,
                            sample_rate=SAMPLE_RATE)

audio.play(mixer)
mixer.voice[0].play(synth)
mixer.voice[0].level = 0.75


waveform_square = np.concatenate((np.full(WAVEFORM_HALFLEN, WAVEFORM_PEAK, dtype=np.int16),
                                  np.full(WAVEFORM_HALFLEN, 0 - WAVEFORM_PEAK, dtype=np.int16)))

waveform_square_pwm_cp = np.array(waveform_square, dtype=np.int16)
waveform_square_pwm_ulab = np.array(waveform_square, dtype=np.int16)

### From https://forums.adafruit.com/viewtopic.php?p=1034152
### Establish some values that will be used to calculate a modulated square wave
square_ramp = np.linspace(0, WAVEFORM_LEN - 1, num=WAVEFORM_LEN, dtype=np.int16)
wave_max = np.full(WAVEFORM_LEN, WAVEFORM_PEAK, dtype=np.int16)
wave_min = np.full(WAVEFORM_LEN, 0 - WAVEFORM_PEAK, dtype=np.int16)

lfo_triangle = np.array([0, WAVEFORM_MAX, 0, 0 - WAVEFORM_MAX], dtype=np.int16)

pwm_idx = WAVEFORM_HALFLEN  ### This is first index value of second half of waveform


### Default triangle wave with period 2.4 seconds
def make_lfo_pwm():
    return synthio.LFO(rate=1/2.4,
                       scale=WAVEFORM_HALFLEN * 13//16 // 2,
                       offset=WAVEFORM_HALFLEN - WAVEFORM_HALFLEN * 13//16 // 2
                       )


lfo_pwm = make_lfo_pwm()

lfo_sawtoothpos = np.array([WAVEFORM_MAX, 0], dtype=np.int16)
lfo_revsawtoothpos = np.array([0, WAVEFORM_MAX, 0], dtype=np.int16)

lfo_glidewave = np.array([WAVEFORM_MAX, WAVEFORM_MAX//4, WAVEFORM_MAX//8, WAVEFORM_MAX//16, WAVEFORM_MAX//32,
                          WAVEFORM_MAX//64, WAVEFORM_MAX//128, WAVEFORM_MAX//256, WAVEFORM_MAX//512, WAVEFORM_MAX//1024, 0], dtype=np.int16)


def pwm_waveform_cp(wf, old_idx, new_idx, value):
    if new_idx > old_idx:
        for idx in range(old_idx, new_idx):
            wf[idx] = value
    elif new_idx < old_idx:
        neg_value = 0 - value
        for idx in range(new_idx, old_idx):
            wf[idx] = neg_value


### jepler's idea (will this allocate each time np.where is called??)
### switcharooed from original code with LE comparison rather than GT
def pwm_waveform_ulab(wf, old_idx, new_idx, value_unused):
    if new_idx != old_idx:
        wf[:] = np.where(square_ramp < new_idx, wave_max, wave_min)

time.sleep(30)

start_ns = time.monotonic_ns()
synth.blocks.append(lfo_pwm)

sleep_times = (0.001, 0.001, 0.002, 0.005, 0.010, 0.020, 0.050)
perf_cp_ms = [None] * len(sleep_times)
perf_ulab_ms = [None] * len(sleep_times)
delta = [None] * len(sleep_times)
sleep_idx = 0
t1 = t2 = t3 = 0
while True:

    time.sleep(sleep_times[sleep_idx])  ### simulate doing something else in the loop

    ### synthio LFOs are a bit lumpy
    ### "In the current implementation, LFOs are updated every 256 samples."
    new_idx = round(lfo_pwm.value)
    diff_idx = abs(new_idx - pwm_idx)
    if diff_idx != 0:
        t1 = time.monotonic_ns()
        pwm_waveform_cp(waveform_square_pwm_cp, pwm_idx, new_idx, WAVEFORM_PEAK)
        t2 = time.monotonic_ns()
        pwm_waveform_ulab(waveform_square_pwm_ulab, pwm_idx, new_idx, WAVEFORM_PEAK)
        t3 = time.monotonic_ns()

        perf_cp_ms[sleep_idx] = (t2 - t1) / 1e6
        perf_ulab_ms[sleep_idx] = (t3 - t2) / 1e6

        if debug >= 2:
            d_print(2, "FROMTO", (pwm_idx, new_idx),
                       "CHECKSUMs", np.sum(waveform_square_pwm_cp),
                                    np.sum(waveform_square_pwm_ulab))
            if debug >= 3:
                for idx in range(0, WAVEFORM_LEN):
                    d_print(3, idx, waveform_square_pwm_cp[idx], waveform_square_pwm_ulab[idx])
                time.sleep(5.0)

        pwm_idx = new_idx
    else:
        perf_cp_ms[sleep_idx] = perf_ulab_ms[sleep_idx] = 0.0

    delta[sleep_idx] = diff_idx
    sleep_idx = (sleep_idx + 1) % len(sleep_times)
    if sleep_idx == 0:
        print("DELTA", t1/1e9, delta)
        print("CP (ms)", perf_cp_ms)
        print("ULAB (ms)", perf_ulab_ms)
        gc.collect()
