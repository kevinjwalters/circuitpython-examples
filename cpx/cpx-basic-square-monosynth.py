### cpx-basic-square-monosynth v1.2
### CircuitPython (on CPX) two oscillator synth module (needs some external hardware)
### Monophonic velocity sensitive synth with pitch bend and mod wheel
### Wiring
### A0  EG2 
### A1  OSC1 
### A3  EG1
### A6  OSC2 
### GND and 3V3 to power external board

### Tested with CPX and CircuitPython 4.0.0 beta2 and
### 4.0.0-beta.2-141-g2c9fbb5d4-dirty

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

#veltovol = int(65535 / 127)
### Multiplier for MIDI velocity ^ 0.40
### 0.5 would be correct for velocity = power
### but 0.4 sounds more natural - ymmv
velcurve = 0.40
veltovolc040 = 9439

# pitchbendrange in semitones - often 2 or 12
pitchbendmultiplier = 12 / 8192
pitchbendvalue = 8192  # mid point - no bend

# Commenting out debug as I just got a Memory Error linked with code size :(
# TODO - look into mpy vs py saving and generation
#debug = True
lastnote = 0
keyvelocity = 0
keytrigger_t = 0.0
keyrelease_t = 0.0

### TODO - ponder how this should handle release during the attack
### TODO - Take out parameters (cc control them?)
### Returns an ADSR's velocity as a float which is <= velocity
### and if 0.0 indicates end of envelope
def ADSR(velocity, trigger_t, release_t, current_t):
    t_attack = current_t - trigger_t
    if (t_attack < 0.200):
        velocity_attack = velocity * t_attack / 0.200
        ### bit of a fudge to stop attack starting at 0.0
        if velocity_attack > 1.0:
            return velocity_attack
        else:
            return 1.0
    
    if release_t == 0.0:
        return velocity  ### no decay yet
    else:
        releasevol = velocity - velocity * ((current_t - release_t) / 2.000)
        if releasevol > 0.0:
            return releasevol
        else:
            return 0.0


while True:    
    msg = midi.read_in_port()
    if isinstance(msg, adafruit_midi.NoteOn) and msg.vel != 0:
#        if debug:
#            print("NoteOn", msg.note, msg.vel)
        lastnote = msg.note
        pitchbend = (pitchbendvalue - 8192) * pitchbendmultiplier
        basefreq = round(A4refhz * math.pow(2, (lastnote - midinoteA4 + pitchbend) / 12.0))
        osc1.frequency = basefreq
        osc2.frequency = basefreq + 1

        keyvelocity = msg.vel
        keytrigger_t = time.monotonic()
        keyrelease_t = 0.0

    elif (isinstance(msg, adafruit_midi.NoteOff) or 
          isinstance(msg, adafruit_midi.NoteOn) and msg.vel == 0):
#        if debug:
#            print("NoteOff", msg.note, msg.vel)
        # Our monophonic "synth module" needs to ignore keys that lifted on
        # overlapping presses
        if msg.note == lastnote:
            keyrelease_t = time.monotonic()
#    elif msg is not None:
#        if debug:
#            print("Something else:", msg)
    elif isinstance(msg, adafruit_midi.PitchBendChange):
        pitchbendvalue = msg.value   ### 0 to 16383
        ### TODO - undo cut and paste here
        pitchbend = (pitchbendvalue - 8192) * pitchbendmultiplier
        basefreq = round(A4refhz * math.pow(2, (lastnote - midinoteA4 + pitchbend) / 12.0))
        osc1.frequency = basefreq
        osc2.frequency = basefreq + 1
    elif isinstance(msg, adafruit_midi.ControlChange):
        if msg.control == 1:  # modulation wheel - TODO MOVE THIS TO adafruit_midi
            ### msg.value is 0 (none) to 127 (max)
            newdutycycle = round(32768 + msg.value * 24000 / 127)
            osc1.duty_cycle = newdutycycle
            osc2.duty_cycle = newdutycycle

    if keyvelocity > 0:
        ADSRvel = ADSR(keyvelocity, keytrigger_t, keyrelease_t, time.monotonic())
        envampl = round(math.pow(ADSRvel, velcurve) * veltovolc040)
        ### TODO - volume match these
        eg1pwm.duty_cycle = envampl
        eg2dac.value = envampl
        if ADSRvel == 0.0:            
            keyvelocity = 0  ### end of note playing
