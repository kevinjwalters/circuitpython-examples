### cpx-noise-synth v1.0
### CircuitPython (on CPX) synth module for noise on internal speaker
### This plays a noise with some pitch colouration 
### listening on MIDI channel 10

### Tested with CPX and CircuitPython and 4.0.0-beta.7

### Needs recent adafruit_midi module

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

import array
import time
import math
import random
#import gc

import digitalio
#import analogio
import audioio
import board
import usb_midi
#import neopixel

import adafruit_midi

from adafruit_midi.note_on          import NoteOn
from adafruit_midi.note_off         import NoteOff
#from adafruit_midi.control_change   import ControlChange
#from adafruit_midi.pitch_bend       import PitchBend

# Turn the speaker on
speaker_enable = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
speaker_enable.direction = digitalio.Direction.OUTPUT
speaker_enable.value = True

dac = audioio.AudioOut(board.SPEAKER)

# 440Hz is the standard frequency for A4 (A above middle C)
# MIDI defines middle C as 60 and modulation wheel is cc 1 by convention
A4refhz = const(440)
midi_note_A4 = 69

# magic_factor is playing things slower as the noise needs
# to cover a long period to be convincing
# Can get this to 1536 if it's allocated before import adafruit_midi
# but half_wave_len must be an integer so dictates lower magic_factor
sample_len = 1024
magic_factor = 512
# base_sample_rate may end up as non integer
base_sample_rate = A4refhz / magic_factor * sample_len
max_sample_rate = 350000  # a CPX / M0 DAC limitation

midpoint = 32768

noise_wave_raw = array.array("H", [0] * sample_len)

# Switchin to use of "H" based on research about unsigned values
# see https://forums.adafruit.com/viewtopic.php?f=60&t=150894
#noise_wave_raw = array.array("H", [midpoint] * sample_len)
square_offset = 1500
noise_vol = 10000
half_wave_len = int(sample_len / magic_factor / 2)
for idx in range(0, sample_len):
    # change "polarity" to create small square wave with lots of noise
    if idx % half_wave_len == 0:
        square_offset = 0 - square_offset
    sample = random.randint(midpoint + square_offset - noise_vol,
                            midpoint + square_offset + noise_vol)
    noise_wave_raw[idx] = sample
noise_wave_raw[0] = midpoint # start at midpoint

#noise_wave_raw = array.array("H",
#                             [random.randint(midpoint-5000, midpoint+5000)
#                              for x in range(sample_len)])
#noise_wave_raw = array.array("h", [0] * sample_len)
noise_wave = audioio.RawSample(noise_wave_raw)
del noise_wave_raw

midi_channel = 10
midi = adafruit_midi.MIDI(midi_in=usb_midi.ports[0],
                          in_channel=midi_channel-1,
                          in_buf_size=6)

last_note = None

# Read any incoming MIDI messages (events) over USB
# looking for note on, note off to turn noise on and off
while True:
    #gc.collect()
    #print(gc.mem_free())
    #print(gc.mem_free())
    msg = midi.receive()
    if isinstance(msg, NoteOn) and msg.velocity != 0:
        note_sample_rate = round(base_sample_rate
                                 * math.pow(2, (msg.note - midi_note_A4) / 12.0))
        if note_sample_rate > max_sample_rate:
            note_sample_rate = max_sample_rate
        noise_wave.sample_rate = note_sample_rate  # must be integer
        dac.play(noise_wave, loop=True)

        last_note = msg.note


    elif (isinstance(msg, NoteOff) or
          isinstance(msg, NoteOn) and msg.velocity == 0):
        # Our monophonic "synth module" needs to ignore keys that lifted on
        # overlapping presses
        if msg.note == last_note:
            dac.stop()
            last_note = None


