### cpx-basic-cv-synth v0.8
### CircuitPython (on CPX) synth module using internal speaker
### Monophonic synth controlled by CV/Gate
### Gate input on A6 - 0V off, 3.3V on
### CV input on A7 - 0V C3, 1V C4 (middle C), 2V C5, 3V C6

### Tested with CPX and CircuitPython and 4.0.1

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
import analogio
import audioio
import board
import neopixel

import adafruit_midi

from adafruit_midi.midi_message     import note_parser

from adafruit_midi.note_on          import NoteOn
from adafruit_midi.note_off         import NoteOff
from adafruit_midi.control_change   import ControlChange
from adafruit_midi.pitch_bend       import PitchBend

# print note frequencies in "mu format"
console_output = True

# Turn the speaker on
speaker_enable = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
speaker_enable.direction = digitalio.Direction.OUTPUT
speaker_on = True
speaker_enable.value = speaker_on

dac = audioio.AudioOut(board.SPEAKER)

# CV and Gate inputs
input_cv   = analogio.AnalogIn(board.A7)
input_gate = digitalio.DigitalInOut(board.A6)  # default is an input

# AnalogIn value is 0-65535 with some lumpiness
# due to DAC being XX bit (TODO)
ref_voltage = input_cv.reference_voltage
adc_conv_factor = ref_voltage / 65535

# 440Hz is the standard frequency for A4 (A above middle C)
A4refhz = const(440)
midi_note_A4 = 69

# 0v is C3 (21 semitones below A4)
zero_volt_hz = A4refhz * math.pow(2, -21 / 12)

midi_cc_modwheel = const(1)
twopi = 2 * math.pi

# A length of 12 will make the sawtooth rather steppy
sample_len = 12
base_sample_rate = A4refhz * sample_len
max_sample_rate = 350000  # a CPX / M0 DAC limitation

midpoint = 32768


# A sawtooth function like math.sin(angle)
# 0 returns 1.0, pi returns 0.0, 2*pi returns -1.0
def sawtooth(angle):
    return 1.0 - angle % twopi / twopi * 2

# make a sawtooth wave between +/- each value in volumes
# phase shifted so it starts and ends near midpoint
# "H" arrays for RawSample looks more memory efficient
# see https://forums.adafruit.com/viewtopic.php?f=60&t=150894
def waveform_sawtooth(length, waves, volumes):
    for vol in volumes:
        waveraw = array.array("H",
                              [midpoint +
                               round(vol * sawtooth((idx + 0.5) / length
                                                    * twopi
                                                    + math.pi))
                               for idx in list(range(length))])
        waves.append((audioio.RawSample(waveraw), waveraw))

# Calculate the note frequency from the control voltage
# using volts per octave approach
def cv_to_freq(voltage):
    return zero_volt_hz * math.pow(2, voltage)
        
# TODO - simplify this - code originate from a velocity sensitive
# synthesizer and this code is no longer needed in this format
#
# Make some square waves of different volumes volumes, generated with
# n=10;[round(math.sqrt(x)/n*32767*n/math.sqrt(n)) for x in range(1, n+1)]
# square root is for mapping velocity to power rather than signal amplitude
# n=15 throws MemoryError exceptions when a note is played :(
waveform_by_vol = []
waveform_sawtooth(sample_len,
                  waveform_by_vol,
                  [10362, 14654, 17947, 20724, 23170,
                   25381, 27415, 29308, 31086, 32767])
# Pick maximum volume wave
wave = waveform_by_vol[-1]

# brightness 1.0 saves memory by removing need for a second buffer
# 10 is number of NeoPixels on CPX
numpixels = const(10)
pixels = neopixel.NeoPixel(board.NEOPIXEL, numpixels, brightness=1.0)

# Turn NeoPixel on to represent a note using RGB x 10
# to represent 30 notes - doesn't do anything with pitch bend
def noteLED(pix, pnote, pvel):
    note30 = (pnote - midi_note_C4) % (3 * numpixels)
    pos = note30 % numpixels
    r, g, b = pix[pos]
    if pvel == 0:
        brightness = 0
    else:
        # max brightness will be 32
        brightness = round(pvel / 127 * 30 + 2)
    # Pick R/G/B based on range within the 30 notes
    if note30 < 10:
        r = brightness
    elif note30 < 20:
        g = brightness
    else:
        b = brightness
    pix[pos] = (r, g, b)

# last frequency of the note played
last_freq = None

# Very simple polling approach checking if Gate signal
# is True (3.3V) and if so playing the sound at the frequency
# calculated from the Control Voltage (CV)
# CV is only read at start of note, no pitch bending :(
while True:
    gate = input_gate.value
    if gate and last_freq is None:
        # Only start audio if it's not playing already
        note_freq = cv_to_freq(input_cv.value * adc_conv_factor)
        ##print(base_sample_rate, note_freq, A4refhz)
        note_sample_rate = round(base_sample_rate * note_freq / A4refhz)

        if note_sample_rate > max_sample_rate:
            note_sample_rate = max_sample_rate
        wave[0].sample_rate = note_sample_rate  # must be integer
        dac.play(wave[0], loop=True)

        ##freqLED(pixels, note_freq, wave_vol)
        if console_output:
            print((note_freq,))
        last_freq = note_freq

    elif not gate and last_freq is not None:
        # Only stop audio if it's playing
        dac.stop()
        last_freq = None

        ##freqLED(pixels, last_freq, 0)  # turn off NeoPixel
