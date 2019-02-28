### cpx-basic-square-monosynth v1.0
### CircuitPython (on CPX) two oscillator synth module (needs some external hardware)
### Wiring
### A0  EG2 
### A1  OSC1 
### A3  EG1
### A6  OSC2 
### GND and 3V3 to power external board

### Tested with CPX and CircuitPython 4.0.0 beta2
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

import time
import math

import board
import analogio
import pulseio
#from adafruit_midi import NoteOn, NoteOff
import adafruit_midi

A4refhz = 440
midinoteA4 = 69

### Setup oscillators which are variable frequency square waves
### And envelopes, one of which is a DAC and the other is a pwm output
### Capacitors on the external board smooth envelope pwm output
### and limit rate of change and smooth envelope voltage
eg1pwm = pulseio.PWMOut(board.A3, duty_cycle=0, frequency=2*1000*1000, variable_frequency=False)
osc1 = pulseio.PWMOut(board.A1, duty_cycle=2**15, frequency=440, variable_frequency=True)

eg2dac = analogio.AnalogOut(board.A0)
osc2   = pulseio.PWMOut(board.A6, duty_cycle=2**15, frequency=441, variable_frequency=True)

### 0 is MIDI channel 1
midi = adafruit_midi.MIDI(in_channel=0)

veltovol = int(65535 / 127)

# Commenting out debug as I just got a Memory Error linked with code size :(
# TODO - look into mpy vs py saving and generation
#debug = True
lastnote = 0

while True:
    msg = midi.read_in_port()
    if isinstance(msg, adafruit_midi.NoteOn):
#        if debug:
#            print("NoteOn", msg.note, msg.vel)

# TODO - handle vel == 0 same as NoteOff with same lastnote logic
        lastnote = msg.note
        basefreq = round(A4refhz * math.pow(2,(lastnote - midinoteA4) / 12.0))
        osc1.frequency = basefreq
        osc2.frequency = basefreq + 1
        envvol = msg.vel * veltovol
        ### TODO - volume match these
        eg1pwm.duty_cycle = envvol
        eg2dac.value = envvol
    elif isinstance(msg, adafruit_midi.NoteOff):
#        if debug:
#            print("NoteOff", msg.note, msg.vel)
        # Our monophonic "synth module" needs to ignore keys that lifted on
        # overlapping presses
        if msg.note == lastnote:
            eg1pwm.duty_cycle = 0
            eg2dac.value = 0
#    elif msg is not None:
#        if debug:
#            print("Something else:", msg)
