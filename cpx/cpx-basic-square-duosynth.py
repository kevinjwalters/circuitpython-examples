### cpx-basic-square-duosynth v1.2
### CircuitPython (on CPX) two oscillator synth module (needs some external hardware)
### Duophonic velocity sensitive synth with pitch bend and mod wheel
### and ADSR control
### Wiring
### A0  Ana0
### A1  Osc1 
### A2  VCS1 
### A3  VCA2
### A6  Osc2 
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
##import analogio
import pulseio
import neopixel
import adafruit_midi
##import audioio

A4refhz = 440
midinoteC4 = 60
midinoteA4 = 69

### brightness 1.0 saves memory by removing need for a second buffer
### 10 is number of NeoPixels on
numpixels = const(10)
pixels = neopixel.NeoPixel(board.NEOPIXEL, numpixels, brightness=1.0)
black = (0, 0, 0)
pixels.fill(black)

### Turn NeoPixel on to represent a note using RGB x 10
### to represent 30 notes
### Doesn't do anything with pitch bend
### TODO BUG - does not deal with dyads which light same led in red then green, etc
def noteled(pixels, note, velocity):
    note30 = ( note - midinoteC4 ) % (3 * numpixels)
    pos = note30 % numpixels
    if velocity == 0:
        colour = black
    else:
        ### max brightness will be 32
        colour = round(velocity / 127 * 30 + 2) << ((2 - note30 // numpixels) * 8)
    pixels[pos] = colour

### Setup oscillators which are variable frequency square waves
### And envelopes which are high frequency pwm outputs
### Capacitors on the external board smooth envelope pwm output
### and limit rate of change and smooth envelope voltage
oscvcas = []

def HFfixedpwm(pin):
    pwm = None
    for attempt in range(3):
        try:
            pwm = pulseio.PWMOut(pin, duty_cycle=0,
                                 frequency=2*1000*1000, variable_frequency=False)
            break
        except Exception as e:
            time.sleep(0.01)   ### time isn't a factor, its memory contents
    return pwm

### Attempt at a workaround for the unpredictable current behaviour of PWMOut()
### with under-the-covers shared counters
### https://forums.adafruit.com/viewtopic.php?f=60&t=148017
### https://github.com/adafruit/circuitpython/issues/1626
vca1pwm = HFfixedpwm(board.A2)
vca2pwm = HFfixedpwm(board.A3)

### If anything failed, clean up then try in reverse order as workaround for #1626
if vca1pwm is None or vca2pwm is None:
    print("Shared couter PWM failure - soft/hard reset suggested or use 4.0.0 beta 4 or later")
else:
    print("High frequency shared counter PWM initialised ok")

### TODO A6 looks a bit clicky when duty_cycle is modified maybe swap
### pins if another one is clean for osc2
### https://github.com/adafruit/circuitpython/issues/1644
    
osc1 = pulseio.PWMOut(board.A1, duty_cycle=2**15, frequency=440, variable_frequency=True)
osc2 = pulseio.PWMOut(board.A6, duty_cycle=2**15, frequency=441, variable_frequency=True)

### A dict or class would be a cleaner/safer representation
### but the memory efficiency of a nested list is attractive
### [Oscillator PWMOut, VCA PWMOut, 
### midi channel number (0-15), note number,
### velocity (0 indicates voice not active),
### key trigger time, key release time, volume at release]
oscvcas.append([osc1, vca1pwm, -1, 0, 0, 0.0, 0.0, 0.0])
oscvcas.append([osc2, vca2pwm, -1, 0, 0, 0.0, 0.0, 0.0])

### Not in use
#dac = analogio.AnalogOut(board.A0)

### TODO implement volume per channel based on midi cc 7 

### 0 is MIDI channel 1
### This is listening on channels 1 and 2
### Testing with bigger in_bug_size as MIDI file driven
### pitch bends may be overwhelming buffering causing byte loss
### 600 helps a bit but obviously audible issue with processing
### slowing down on bursty pitch bends
midi = adafruit_midi.MIDI(in_channel=(0,1), debug=False, in_buf_size=30)

#veltovol = int(65535 / 127)
### Multiplier for MIDI velocity ^ 0.40
### 0.5 would be correct for velocity = power
### but 0.4 sounds more natural - ymmv
velcurve = 0.40
veltovolc040 = 9439

# pitchbendrange in semitones - often 2 or 12
pitchrange = 2
pitchbendmultiplier = pitchrange / 8192
pitchbendvalue = 8192  # mid point - no bend

# Commenting out debug as I just got a Memory Error linked with code size :(
# TODO - look into mpy vs py saving and generation
debug = False

### Voice assignment
### returns index of voice to use and either None or
### the next index if next voice has been advanced
### check each starting at nextoscvca
### if same note is playing then re-use that (i.e. in release phase)
### if a voice is free use that
### if nothing then rescan looking for a voice in release phase
### otherwise use next one
def assignvoice(oscvcas, nextoscvca):
    oscvcatouse = None
    next = None
    
    voiceidx = nextoscvca
    for i in range(len(oscvcas)):
        if oscvcas[voiceidx][4] != 0 and oscvcas[voiceidx][3] == msg.note:
            oscvcatouse = voiceidx
            break
        if oscvcas[voiceidx][4] == 0:  ### velocity 0 voice not in use
            oscvcatouse = voiceidx
            break
        voiceidx = ( voiceidx + 1 ) % len(oscvcas)

    if oscvcatouse is None:
        voiceidx = nextoscvca
        for i in range(len(oscvcas)):
            if oscvcas[voiceidx][6] != 0.0:  ### key released
                oscvcatouse = voiceidx
                break
            voiceidx = ( voiceidx + 1 ) % len(oscvcas)
                
    if oscvcatouse is None:
        oscvcatouse = nextoscvca
        next = ( nextoscvca + 1 ) % len(oscvcas)  ### advance next
    
    return (oscvcatouse, next)

### The next oscillator / vca to use to 
nextoscvca = 0

### Returns volume as a float based on simple ADSR envelope
### this will be <= velocity and 0.0 if at end of envelope
### release_t should be 0.0 until key is released
### attack is seconds
### decay is seconds
### sustain is fraction of velocity, e.g. 0.6 is 60%
### release is seconds
### vol_release is the volume when key was released
def ADSR(velocity, trigger_t, release_t, current_t,
         attack, decay, sustain, release,
         vol_release):
    vol = velocity
    rel_t = current_t - trigger_t

    if release_t == 0.0:
        if (rel_t < attack):
            ### Attack phase
            vol_attack = vol * rel_t / attack
            ### bit of a fudge to stop attack starting at 0.0 as this return
            ### value is used to signify end of envelope
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
        
        return vol
    else:
        ### Release phase
        if release == 0.0:
            return 0.0  ### no release and need to prevent div by zero
        vol = vol_release - vol_release * ((current_t - release_t) / release)
        if vol > 0.0:
            return vol
        else:
            return 0.0   ### end of release/note


### Return an LFO value between 0.0 and 1.0
def LFO(start_t, now_t, rate, shape):
    ### phase will be 0.0 at start to 1.0 at end
    wavelengths = (now_t - start_t) * rate
    phase = wavelengths - int(wavelengths)
    if shape == "triangle":
        value = 1.0 - 2 * abs(0.5 - phase)
    else:
        raise ValueError("Unsupported LFO wave shape")

    return value            

### Initial ADSR values
attack  = 0.050
release = 0.500
decay = 0.1
sustain = 0.8  ### 80% level

maxattack = 2.000
maxrelease = 6.000
maxsustain = 1.0
maxdecay = 2.000

### Start with 1 free running LFO
lfomin = 1/32   ### Hz
lfomax = 16     ### Hz
lfopow2range = math.log(lfomax / lfomin) / math.log(2)
lfovalue = 0.0  ### Initial value
lforate = 1     ### Initial rate in Hz
lfostart_t = time.monotonic()
lfoshape = "triangle"

print("Ready to play")

### TODO - time.monotonic() loses decimal places as the number gets large
###      - problematic for long running code

while True:
    (msg, channel) = midi.read_in_port()  ### channels are protocol number
    if isinstance(msg, adafruit_midi.NoteOn) and msg.velocity != 0:
        if debug:
            print("NoteOn", msg.note, msg.velocity)
        lastnote = msg.note
        pitchbend = (pitchbendvalue - 8192) * pitchbendmultiplier
        ### TODO BUG - S/B also triggered Invalid PWM frequency (0?? extreme pitch bending??)
        ### if remote + time is sent then basefreq can equal some value in the millions
        frequency = round(A4refhz * math.pow(2, (lastnote - midinoteA4 + pitchbend) / 12.0))

        ##print(msg.note, msg.velocity, basefreq)
        
        (oscvcatouse, next) = assignvoice(oscvcas, nextoscvca)
        if next is not None:
            nextoscvca = next  ### Advance voice selection as required

        ### Set everything bar the VCA (element 1) which will be set RSN
        ### at end of if statement
        oscvcas[oscvcatouse][0].frequency = frequency
        oscvcas[oscvcatouse][2] = channel
        oscvcas[oscvcatouse][3] = msg.note
        oscvcas[oscvcatouse][4] = msg.velocity
        oscvcas[oscvcatouse][5] = time.monotonic()
        oscvcas[oscvcatouse][6] = 0.0
        oscvcas[oscvcatouse][7] = 0.0
        
        noteled(pixels, msg.note, msg.velocity)

    elif (isinstance(msg, adafruit_midi.NoteOff) or 
          isinstance(msg, adafruit_midi.NoteOn) and msg.velocity == 0):
        if debug:
            print("NoteOff", msg.note, msg.velocity)
        ### Our duophonic "synth module" needs to ignore keys that were pressed before the
        ### 0/1/2 notes that are currently playing
        ### TODO - currently disregards channel number - review this
        for voice in oscvcas:
            if msg.note == voice[3]:
                ### Insert calculated volume and then
                ### insert release time               
                now_t = time.monotonic()
                voice[7] = ADSR(voice[4],
                                voice[5], voice[6], now_t,
                                attack, decay, sustain, release,
                                voice[7])
                voice[6] = now_t
                
        noteled(pixels, msg.note, 0)
        
    elif isinstance(msg, adafruit_midi.PitchBendChange):
        pitchbendvalue = msg.pitch_bend   ### 0 to 16383
        ### TODO - undo cut and paste here
        pitchbend = (pitchbendvalue - 8192) * pitchbendmultiplier
        for voice in oscvcas:
            ### Check velocity which indicates active voice and 
            ### look for channel match
            if voice[3] > 0 and voice[2] == channel:
                frequency = round(A4refhz * math.pow(2, (voice[3] - midinoteA4 + pitchbend) / 12.0))
                voice[0].frequency = frequency
                
    elif isinstance(msg, adafruit_midi.ControlChange):
        if msg.control == 1:  # modulation wheel - TODO MOVE THIS TO adafruit_midi
            ### msg.value is 0 (none) to 127 (max)
            ### TODO - since LFO addition mod wheel needs to do something else
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
        elif msg.control == 91:  # LFO rate
            ### Changing this while playing a note often sounds unpleasant
            ### phase matching for old and new rates would solve this
            lforate = lfomin * math.pow(2, lfopow2range * msg.value / 127)
        elif msg.control == 93:  # LFO depth
            pass  ### TODO

    elif msg is not None:
        if debug:
            print("Something else:", msg)

    ### Create envelopes for any active voices
    now_t = time.monotonic()
    lfovalue = LFO(lfostart_t, now_t, lforate, lfoshape)
    for voiceidx, voice in enumerate(oscvcas):
        if voice[4] > 0:   ### velocity is used as indicator for active voice
            ADSRvol = ADSR(voice[4],
                           voice[5], voice[6], now_t,
                           attack, decay, sustain, release,
                           voice[7])
            envampl = round(math.pow(ADSRvol, velcurve) * veltovolc040)
            ### TODO BUG - somewhere as this breached 0 - 65535 during S/B
            voice[1].duty_cycle = envampl
            if ADSRvol == 0.0:            
                voice[4] = 0  ### end of note playing
            else:
                ### Modulate duty_cycle of oscillator with LFO
                offset = 4096 + round(24576 * lfovalue)
                if voiceidx % 2 == 0:
                    offset = -offset
                voice[0].duty_cycle = 32768 + offset
