### cpx-basic-synth v1.0
### CircuitPython (on CPX) synth module using internal speaker
### Velocity sensitive monophonic synth
### with crude amplitude modulation (cc1) and choppy pitch bend

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
import audioio
import busio
import board
import usb_midi
import neopixel

import adafruit_midi

from adafruit_midi.midi_message     import note_parser

from adafruit_midi.note_on          import NoteOn
from adafruit_midi.note_off         import NoteOff
from adafruit_midi.control_change   import ControlChange
from adafruit_midi.pitch_bend       import PitchBend

# Turn the speaker on
speaker_enable = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
speaker_enable.direction = digitalio.Direction.OUTPUT
speaker_on = True
speaker_enable.value = speaker_on

dac = audioio.AudioOut(board.SPEAKER)

# 440Hz is the standard frequency for A4, A above middle C
# MIDI defines middle C as 60 and modulation wheel is cc 1 by convention
A4refhz = const(440)
midi_note_C4 = note_parser("C4")
midi_note_A4 = note_parser("A4")
midi_cc_modwheel = const(1)

sample_len = 96
base_sample_rate = A4refhz * sample_len
max_sample_rate = 350000  # a CPX / M0 DAC limitation

# make a mostly square wave between +/- each value in volumes
def waveform_square(length, waves, volumes):
    for vol in volumes:
        waveraw = array.array("h", [-vol] * (length // 2 - 1)
                                   + [0]
                                   +  [vol] * (length - length // 2 - 1)
                                   + [0])
        waves.append((audioio.RawSample(waveraw), waveraw))

# Make some square waves of different volumes
# volumes generated with
# [round(math.sqrt(x)/(10-1)*32767*(10-1)/math.sqrt(10-1)) for x in range(1, 10)]
waveform_by_vol = []
waveform_square(sample_len,
                waveform_by_vol,
                [10922, 15447, 18918, 21845, 24423, 26754, 28898, 30893, 32767])

# brightness 1.0 saves memory by removing need for a second buffer
# 10 is number of NeoPixels on CPX
numpixels = const(10)
pixels = neopixel.NeoPixel(board.NEOPIXEL, numpixels, brightness=1.0)

# Turn NeoPixel on to represent a note using RGB x 10
# to represent 30 notes - doesn't do anything with pitch bend
def noteLED(pixels, note, velocity):
    note30 = ( note - midi_note_C4 ) % (3 * numpixels)
    pos = note30 % numpixels
    r, g, b = pixels[pos]
    if velocity == 0:
        brightness = 0
    else:
        ### max brightness will be 32
        brightness = round(velocity / 127 * 30 + 2)
    ### Pick R/G/B based on range within the 30 notes
    if note30 < 10:
        r = brightness
    elif note30 < 20:
        g = brightness
    else:
        b = brightness
    pixels[pos] = (r, g, b)

# Calculate the note frequency from the midi_note with pitch bend
# of pb_st (float) semitones
# Returns float
def note_frequency(midi_note, pb_st):
    # 12 semitones in an octave
    return A4refhz * math.pow(2, (midi_note - midi_note_A4 + pb_st) / 12.0)

midi_channel = 1
midi = adafruit_midi.MIDI(midi_in=usb_midi.ports[0],
                          in_channel=midi_channel-1)

# pitchbendrange in semitones - often 2 or 12
pb_midpoint = 8192
pitch_bend_multiplier = 2 / pb_midpoint
pitch_bend_value = pb_midpoint  # mid point - no bend

wave = None
last_note = None

# Amplitude modulation frequency in Hz
am_freq = 16
mod_wheel = 0

# Read any incoming MIDI messages (events) over USB
# looking for note on, note off, pitch bend change
# or control change for control 1 (modulation wheel)
# Apply crude amplitude modulation using speaker enable
while True:
    msg = midi.receive()
    if isinstance(msg, NoteOn) and msg.velocity != 0:
        last_note = msg.note
        # Calculate the sample rate to give the wave form the frequency
        # which matches the midi note with any pitch bending applied
        pitch_bend = (pitch_bend_value - pb_midpoint) * pitch_bend_multiplier
        note_freq = note_frequency(msg.note, pitch_bend)
        note_sample_rate = round(base_sample_rate * note_freq / A4refhz)

        # Select the wave with volume for the note velocity
        # Value slightly above 127 together with int() maps the velocities
        # to equal intervals and avoids going out of bound
        wave_vol = int(msg.velocity / 127.01 * len(waveform_by_vol))
        wave = waveform_by_vol[wave_vol]

        if note_sample_rate > max_sample_rate:
            note_sample_rate = max_sample_rate
        wave[0].sample_rate = note_sample_rate  # must be integer
        dac.play(wave[0], loop=True)

        noteLED(pixels, msg.note, msg.velocity)

    elif (isinstance(msg, NoteOff) or
          isinstance(msg, NoteOn) and msg.velocity == 0):
        # Our monophonic "synth module" needs to ignore keys that lifted on
        # overlapping presses
        if msg.note == last_note:
            dac.stop()
            last_note = None

        noteLED(pixels, msg.note, 0)  # turn off NeoPixel

    elif isinstance(msg, PitchBend):
        pitch_bend_value = msg.pitch_bend  # 0 to 16383
        if last_note is not None:
            pitch_bend = (pitch_bend_value - pb_midpoint) * pitch_bend_multiplier
            note_freq = note_frequency(last_note, pitch_bend)
            note_sample_rate = round(base_sample_rate * note_freq / A4refhz)
            if note_sample_rate > max_sample_rate:
                note_sample_rate = max_sample_rate
            wave[0].sample_rate = note_sample_rate  # must be integer
            dac.play(wave[0], loop=True)

    elif isinstance(msg, ControlChange):
        if msg.control == midi_cc_modwheel:
            mod_wheel = msg.value  # msg.value is 0 (none) to 127 (max)

    if mod_wheel > 0:
        t1 = time.monotonic() * am_freq
        # Calculate a form of duty_cycle for enabling speaker for crude
        # amplitude modulation. Empirically the divisor needs to greater
        # than 127 as can't hear much when speaker is off more than half
        # 220 works reasonably well
        new_speaker_on = ( t1 - int(t1) ) > (mod_wheel / 220)
    else:
        new_speaker_on = True

    if speaker_on != new_speaker_on:
        speaker_enable.value = new_speaker_on
        speaker_on = new_speaker_on
