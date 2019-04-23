### cpx-noise-synth v1.0
### CircuitPython (on CPX) synth module for crude noise on internal speaker
### Very basic noise with constant pitch and volume
### for any note on MIDI channel 10

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

#import array
import time
#import math
import random

import digitalio
import analogio
import board
import usb_midi
#import neopixel

import adafruit_midi

#from adafruit_midi.midi_message     import note_parser

from adafruit_midi.note_on          import NoteOn
from adafruit_midi.note_off         import NoteOff
#from adafruit_midi.control_change   import ControlChange
#from adafruit_midi.pitch_bend       import PitchBend

# Turn the speaker on
speaker_enable = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
speaker_enable.direction = digitalio.Direction.OUTPUT
speaker_on = True
speaker_enable.value = speaker_on

# Approach is to write to the DAC directly rather than play
# samples as the audioio library doesn't work well for
# various reasons with looping samples
# NEED to try a long sample (2 seconds?) which terminates early
# on note off
dac_out = analogio.AnalogOut(board.SPEAKER)  # same as board.A0 for CPX

midi_channel = 10
midi = adafruit_midi.MIDI(midi_in=usb_midi.ports[0],
                          in_channel=midi_channel-1)


# Check how long a loop takes to assign to DAC
# about 2 seconds for 3k on a CPX with 4.0.0 beta 7
timed_run_length = 3000
start_t = time.monotonic()
for rep in range(timed_run_length):
    dac_out.value = random.randint(32767, 32769)
    dac_out.value = random.randint(32767, 32769)
    dac_out.value = random.randint(32767, 32769)
    dac_out.value = random.randint(32767, 32769)

duration = time.monotonic() - start_t

# Bursts of noise in 1/32 of a second
# value is 46 on a CPX with 4.0.0 beta 7
noise_len = int(timed_run_length / duration / 32)
#print(noise_len)

noise_on = False

# Read any incoming MIDI messages (events) over USB
# looking for note on, note off to turn noise on and off
while True:
    msg = midi.receive()
    if isinstance(msg, NoteOn) and msg.velocity != 0:
        last_note = msg.note
        noise_on = True

    elif (isinstance(msg, NoteOff) or
          isinstance(msg, NoteOn) and msg.velocity == 0):
        # Our monophonic "synth module" needs to ignore keys that lifted on
        # overlapping presses
        if msg.note == last_note:
            noise_on = False
            last_note = None

    if noise_on:
        # make a burst of noise using random values +/- 5000
        # from 32768 midpoint
        # avoiding any calculations inside loop to avoid delays
        for rep in range(noise_len):
            dac_out.value = random.randint(27768, 37768)
            dac_out.value = random.randint(27768, 37768)
            dac_out.value = random.randint(27768, 37768)
            dac_out.value = random.randint(27768, 37768)
