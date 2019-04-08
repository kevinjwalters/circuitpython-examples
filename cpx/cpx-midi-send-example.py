### cpx-midi-send-example v0.9
### CircuitPython (on CPX) MIDI sending midi notes

### Tested with CPX and CircuitPython and 4.0.0-beta.5

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

import digitalio
import board

import usb_midi
import adafruit_midi

from adafruit_midi.midi_message     import note_parser

from adafruit_midi.note_on          import NoteOn
from adafruit_midi.note_off         import NoteOff
from adafruit_midi.control_change   import ControlChange

board_led = digitalio.DigitalInOut(board.D13)
board_led.direction = digitalio.Direction.OUTPUT



# TODO - add some NeoPixel magic to this using dict and 10 popular drums?




# MIDI channel 10 is often used for drums
# constructor takes wire protocol MIDI channel number
midi_channel = 10
midi = adafruit_midi.MIDI(midi_out=usb_midi.ports[1],
                          out_channel=midi_channel-1)

# A sequence of MIDI notes with a simple representation in time order
# (start_time, message_type, parameter1, parameter2)
# Recorded with a CPX board from MIDI file played in real-time from
# MIDI file from https://www.simonv.com/tutorials/drum_patterns.php
bpm = 175
midi_sequence = [(0.00, "on",  36, 127),
                 (0.01, "on",  45, 96),
                 (0.18, "off", 36, 0),
                 (0.18, "off", 45, 0),
                 (0.19, "on",  36, 127),
                 (0.20, "on",  45, 64),
                 (0.35, "off", 36, 0),
                 (0.35, "off", 45, 0),
                 (0.36, "on",  37, 127),
                 (0.37, "on",  45, 127),
                 (0.52, "off", 37, 0),
                 (0.52, "off", 45, 0),
                 (0.53, "on",  40, 127),
                 (0.54, "on",  45, 64),
                 (0.61, "on",  38, 127),
                 (0.69, "off", 40, 0),
                 (0.69, "off", 45, 0),
                 (0.70, "on",  40, 127),
                 (0.71, "on",  45, 96),
                 (0.71, "off", 38, 0),
                 (0.78, "on",  38, 127),
                 (0.86, "off", 40, 0),
                 (0.87, "off", 45, 0),
                 (0.87, "on",  36, 127),
                 (0.88, "on",  45, 64),
                 (0.88, "off", 38, 0),
                 (0.94, "off", 36, 0),
                 (0.95, "on",  36, 90),
                 (1.03, "off", 45, 0),
                 (1.03, "on",  37, 127),
                 (1.04, "on",  45, 127),
                 (1.05, "off", 36, 0),
                 (1.20, "off", 45, 0),
                 (1.21, "on",  40, 127),
                 (1.22, "on",  45, 64),
                 (1.28, "off", 37, 0),
                 (1.37, "off", 40, 0),
                 (1.37, "off", 45, 0),
                 (1.38, "on",  36, 127),
                 (1.39, "on",  45, 96),
                 (1.54, "off", 36, 0),
                 (1.55, "off", 45, 0),
                 (1.55, "on",  36, 127),
                 (1.56, "on",  45, 64),
                 (1.72, "off", 36, 0),
                 (1.73, "off", 45, 0),
                 (1.73, "on",  37, 127),
                 (1.74, "on",  45, 127),
                 (1.89, "off", 37, 0),
                 (1.90, "off", 45, 0),
                 (1.90, "on",  40, 127),
                 (1.91, "on",  45, 64),
                 (1.98, "on",  38, 127),
                 (2.06, "off", 40, 0),
                 (2.07, "off", 45, 0),
                 (2.07, "on",  40, 127),
                 (2.08, "on",  45, 96),
                 (2.09, "off", 38, 0),
                 (2.15, "on",  38, 127),
                 (2.23, "off", 40, 0),
                 (2.24, "off", 45, 0),
                 (2.24, "on",  36, 127),
                 (2.25, "on",  45, 64),
                 (2.26, "off", 38, 0),
                 (2.32, "off", 36, 0),
                 (2.40, "off", 45, 0),
                 (2.41, "on",  40, 127),
                 (2.41, "on",  45, 64),
                 (2.57, "off", 40, 0),
                 (2.58, "off", 45, 0),
                 (2.58, "on",  37, 127),
                 (2.59, "on",  45, 127),
                 (2.74, "off", 45, 0),
                 (2.75, "on",  40, 127),
                 (2.75, "on",  45, 96),
                 (2.83, "off", 37, 0),
                 (2.91, "off", 40, 0),
                 (2.92, "off", 45, 0),
                 (2.92, "on",  36, 127),
                 (2.93, "on",  45, 64),
                 (3.00, "off", 36, 0),
                 (3.01, "on",  36, 110),
                 (3.08, "off", 45, 0),
                 (3.09, "on",  37, 127),
                 (3.09, "on",  45, 127),
                 (3.10, "off", 36, 0),
                 (3.26, "off", 37, 0),
                 (3.27, "off", 45, 0),
                 (3.28, "on",  40, 127),
                 (3.28, "on",  45, 64),
                 (3.35, "on",  38, 127),
                 (3.43, "off", 40, 0),
                 (3.44, "off", 45, 0),
                 (3.45, "on",  40, 127),
                 (3.45, "on",  45, 96),
                 (3.46, "off", 38, 0),
                 (3.53, "on",  38, 127),
                 (3.60, "off", 40, 0),
                 (3.61, "off", 45, 0),
                 (3.62, "on",  36, 127),
                 (3.62, "on",  43, 127),
                 (3.63, "on",  45, 64),
                 (3.63, "off", 38, 0),
                 (3.77, "off", 36, 0),
                 (3.78, "off", 43, 0),
                 (3.79, "off", 45, 0),
                 (3.79, "on",  37, 127),
                 (3.80, "on",  45, 96),
                 (3.94, "off", 37, 0),
                 (3.95, "off", 45, 0),
                 (3.96, "on",  40, 127),
                 (3.96, "on",  45, 64),
                 (4.11, "off", 40, 0),
                 (4.12, "off", 45, 0),
                 ]

# Play the tune three times at different bpms
for playback_bpm in [175, 100, 120]:
    start_t = time.monotonic()
    print("Start of MIDI sequence at", playback_bpm, "bpm")
    playback_bpm_ratio = bpm / playback_bpm
    for note_t, type, param1, param2 in midi_sequence:
        note_t *= playback_bpm_ratio
        if type == "on":
            msg = NoteOn(param1, param2)
        elif type == "off":
            msg = NoteOff(param1, param2)
        else:
            print("unknown type:", type)
        # calculate the delay until the next note from the relative time now
        delay = note_t - (time.monotonic() - start_t)
        if delay > 0.0:
            time.sleep(delay)
        if type == "on":
            board_led.value = True
        midi.send(msg)
        if type == "on":
            board_led.value = False
