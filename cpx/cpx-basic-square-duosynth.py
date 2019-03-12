### cpx-basic-square-duosynth v0.6
### CircuitPython (on CPX) two oscillator synth module (needs some external hardware)
### Duophonic velocity sensitive synth with pitch bend and mod wheel
### and ADSR control
### Wiring
### A0  ANA1
### A1  OSC1 
### A2  vca1 
### A3  vca2
### A6  OSC2 
### GND and 3V3 to power external board

### Tested with CPX and CircuitPython 4.0.0 beta3 

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
import random
import array

import board
import analogio
import pulseio
import adafruit_midi
##import audioio

A4refhz = 440
midinoteA4 = 69

### Setup oscillators which are variable frequency square waves
### And envelopes which are high frequency pwm outputs
### Capacitors on the external board smooth envelope pwm output
### and limit rate of change and smooth envelope voltage
oscvcas = []

def twomegfixedpwm(pin):
    pwm = None
    for attempt in range(40):
        try:
            pwm = pulseio.PWMOut(pin, duty_cycle=0,
                                 frequency=2*1000*1000, variable_frequency=False)
            break
        except Exception as e:
            ### A guess that timing could be a factor
            time.sleep(attempt / 234)
    return pwm

### Attempt at a workaround for the unpredictable current behaviour of PWMOut()
### with under-the-covers shared counters
### https://forums.adafruit.com/viewtopic.php?f=60&t=148017
### https://github.com/adafruit/circuitpython/issues/1626
vca1pwm = twomegfixedpwm(board.A2)
vca2pwm = twomegfixedpwm(board.A3)

### If anything failed, clean up then try in reverse order as workaround for #1626
if vca1pwm is None or vca2pwm is None:
    print("Shared couter PWM failure I - trying in reverse order")
    if vca1pwm is not None:
        vca1pwm.deinit()
        vca1pwm = None
    if vca2pwm is not None:
        vca2pwm.deinit()
        vca2pwm = None
    vca2pwm = twomegfixedpwm(board.A3)
    vca1pwm = twomegfixedpwm(board.A2)

if vca1pwm is None or vca2pwm is None:
    print("Shared couter PWM failure II - soft/hard reset suggested")
else:
    print("High frequency shared counter PWM initialised ok")
    
osc1 = pulseio.PWMOut(board.A1, duty_cycle=2**15, frequency=440, variable_frequency=True)
osc2 = pulseio.PWMOut(board.A6, duty_cycle=2**15, frequency=441, variable_frequency=True)

### A dict or class would be a cleaner/safer representation
### but the memory efficiency of a nested list is attractive
### [Oscillator PWMOut, VCA PWMOut, midi note number,
### velocity (0 indicates voice not active),
### key trigger time, key release time]
oscvcas.append([osc1, vca1pwm, 0, 0, 0.0, 0.0])
oscvcas.append([osc2, vca2pwm, 0, 0, 0.0, 0.0])

### Not in use
#dac = analogio.AnalogOut(board.A0)

### 0 is MIDI channel 1 - 
### TODO ensure you have actually implemented this in library
### and work out how to handle reading multiple channels as may want to do that
midi = adafruit_midi.MIDI(in_channel=0)

#veltovol = int(65535 / 127)
### Multiplier for MIDI velocity ^ 0.40
### 0.5 would be correct for velocity = power
### but 0.4 sounds more natural - ymmv
velcurve = 0.40
veltovolc040 = 9439

# pitchbendrange in semitones - often 2 or 12
pitchrange = 12
pitchbendmultiplier = pitchrange / 8192
pitchbendvalue = 8192  # mid point - no bend

# Commenting out debug as I just got a Memory Error linked with code size :(
# TODO - look into mpy vs py saving and generation
#debug = True

### The next oscillator / vca to use to 
nextoscvca = 0

### TODO - ponder how this should handle release during the attack
### TODO - Take out parameters (cc control them?)
### Returns an ADSR's velocity as a float which is <= velocity
### and if 0.0 indicates end of envelope
### release_t should be 0.0 until it happens
### attack is seconds
### release is seconds
def ADSR(velocity, trigger_t, release_t, current_t,
         attack, decay, sustain, release):
    vol = velocity
    rel_t = current_t - trigger_t
    if (rel_t < attack):
        ### Attack phase
        vol_attack = vol * rel_t / attack
        ### bit of a fudge to stop attack starting at 0.0
        if vol_attack > 1.0:
            return vol_attack
        else:
            return 1.0

    ### Decay/Sustain phase
    if decay != 0.0 and sustain != 1.0:
        sus_t = rel_t - attack
        ### Calculate a new vol level
        if sus_t < decay:
            vol = vol - sus_t / decay * (1.0 - sustain) * vol
        else:
            vol = vol * sustain

    if release_t == 0.0:
        return vol
    else:
        ### Release phase
        if release == 0.0:
            return 0.0  ### no release and need to prevent div by zero
        releasevol = vol - vol * ((current_t - release_t) / release)
        if releasevol > 0.0:
            return releasevol
        else:
            return 0.0

attack  = 0.200
release = 2.000
decay = 0.4
sustain = 0.6  ### 60% level

maxattack = 2.000
maxrelease = 6.000
maxsustain = 1.0
maxdecay = 2.000

print("Ready to play")

while True:
    msg = midi.read_in_port()
    if isinstance(msg, adafruit_midi.NoteOn) and msg.vel != 0:
#        if debug:
#            print("NoteOn", msg.note, msg.vel)
        lastnote = msg.note
        pitchbend = (pitchbendvalue - 8192) * pitchbendmultiplier
        basefreq = round(A4refhz * math.pow(2, (lastnote - midinoteA4 + pitchbend) / 12.0))
        
        ### Set everything bar the VCA (element 1) which will be set RSN
        ### at end of if statement
        oscvcas[nextoscvca, 0].frequency = basefreq
        oscvcas[nextoscvca, 2] = msg.note
        oscvcas[nextoscvca, 3] = msg.vel
        oscvcas[nextoscvca, 4] = time.monotonic()
        oscvcas[nextoscvca, 5] = 0.0
        nextoscvca = ( nextoscvca + 1 ) % len(nextoscvca)
        
    elif (isinstance(msg, adafruit_midi.NoteOff) or 
          isinstance(msg, adafruit_midi.NoteOn) and msg.vel == 0):
#        if debug:
#            print("NoteOff", msg.note, msg.vel)
        # Our duophonic "synth module" needs to ignore keys that were pressed before the
        # 0/1/2 notes that are currently playing
        for voice in oscvcas:
            if msg.note == voice[2]:
                voice[5] = time.monotonic()  ### Insert key release time

    elif isinstance(msg, adafruit_midi.PitchBendChange):
        pitchbendvalue = msg.value   ### 0 to 16383
        ### TODO - undo cut and paste here
        pitchbend = (pitchbendvalue - 8192) * pitchbendmultiplier
        ### TODO - research whether pitch bend affects all notes playing
        ##basefreq = round(A4refhz * math.pow(2, (lastnote - midinoteA4 + pitchbend) / 12.0))
        ##osc1.frequency = basefreq
        ##osc2.frequency = basefreq + 1
    elif isinstance(msg, adafruit_midi.ControlChange):
        if msg.control == 1:  # modulation wheel - TODO MOVE THIS TO adafruit_midi
            ### msg.value is 0 (none) to 127 (max)
            newdutycycle = round(32768 + msg.value * 24000 / 127)
            osc1.duty_cycle = newdutycycle
            osc2.duty_cycle = newdutycycle
        elif msg.control == 73:  # attack - TODO MOVE THIS TO adafruit_midi
            attack = maxattack * msg.value / 127
        elif msg.control == 72:  # release - TODO MOVE THIS TO adafruit_midi
            release = maxrelease * msg.value / 127
        elif msg.control == 5:   # portamento level borrowed for decay for now
            decay = maxdecay * msg.value / 127
        elif msg.control == 84:  # what is this? using for sustain level
            sustain = maxsustain * msg.value / 127
    elif msg is not None:
        if debug:
            print("Something else:", msg)
            
    ### Create envelopes for any active voices
    for voice in oscvcas:
        ### TODO - finish converting code below for duophonic    
        if voice[3] > 0:
            ADSRvel = ADSR(voice[3],
                           voice[4], voice[5], time.monotonic(),
                           attack, decay, sustain, release)
            envampl = round(math.pow(ADSRvel, velcurve) * veltovolc040)
            voice[1].duty_cycle = envampl
            if ADSRvel == 0.0:            
                voice[3] = 0  ### end of note playing
