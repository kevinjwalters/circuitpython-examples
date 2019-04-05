### cpx-threeosc-synth v1.3
### CircuitPython (on CPX) three oscillator synth module (needs some external hardware)
### Midi channels 1 and 2 combined are a duophonic velocity sensitive synth
### with ADSR envelopes, pitch bend and LFO for amplitude and duty cycle
### controlled by mod wheel, aftertouch and various CC
### Midi 3 is a simple coarse triangle synth with no velocity
###
### Wiring
### A0  Ana0
### A1  Osc1 
### A2  VCS1 
### A3  VCA2
### A6  Osc2 
### GND and 3V3 to power external board

### Tested with CPX and CircuitPython 4.0.0 beta5 

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
import digitalio
import analogio
import pulseio
import neopixel

import adafruit_midi  

from adafruit_midi.note_on          import NoteOn
from adafruit_midi.note_off         import NoteOff
from adafruit_midi.control_change   import ControlChange
from adafruit_midi.pitch_bend       import PitchBend

# PR #9 review changes consumed more memory and cannot now import ChannelPressure
#from adafruit_midi.channel_pressure import ChannelPressure

### MIDI messages (events) not in use
### for testing to see how much memory is consumed
### Need to sacrifice all of these!
#from adafruit_midi.timing_clock      import TimingClock
#from adafruit_midi.system_exclusive  import SystemExclusive
#from adafruit_midi.polyphonic_key_pressure import PolyphonicKeyPressure
#from adafruit_midi.program_change    import ProgramChange


import audioio

import gc

gc.collect()
print(gc.mem_free())

#from waveforms import make_waveforms, waveform_names
from synthfunctions import make_waveforms, waveform_names, ADSR, LFO

gc.collect()
print(gc.mem_free())

A4refhz = 440
midinoteC4 = 60
midinoteA4 = 69
#basesamplerate = 42240  ### this makes A4 exactly 96 samples
#basesamplerate = 21120  ### this makes A4 exactly 48 samples
#basesamplerate = 10560  ### this makes A4 exactly 24 samples
basesamplerate = 5280  ### this makes A4 exactly 12 samples

### brightness 1.0 saves memory by removing need for a second buffer
### 10 is number of NeoPixels on
numpixels = const(10)
### brightness of 1.0 prevents an extra array from being created
pixels = neopixel.NeoPixel(board.NEOPIXEL, numpixels, brightness=1.0)


### Turn NeoPixel on to represent a note using RGB x 10
### to represent 30 notes
### Doesn't do anything with pitch bend
def noteled(pixels, note, velocity):
    note30 = ( note - midinoteC4 ) % (3 * numpixels)
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

### Setup oscillators which are variable frequency square waves
### And envelopes which are high frequency pwm outputs
### Capacitors on the external board smooth envelope pwm output
### and limit rate of change and smooth envelope voltage

### TODO - might be interesting to drop this to lower frequencies
### for the tremolo effect

### Attempt at a workaround for the unpredictable current behaviour of PWMOut()
### with under-the-covers shared counters
### https://forums.adafruit.com/viewtopic.php?f=60&t=148017
### https://github.com/adafruit/circuitpython/issues/1626
vca1pwm = pulseio.PWMOut(board.A2, duty_cycle=0,
                         frequency=2*1000*1000, variable_frequency=False)
vca2pwm = pulseio.PWMOut(board.A3, duty_cycle=0,
                         frequency=2*1000*1000, variable_frequency=False)
### TODO - might be interesting to drop this to lower frequencies
### for the tremolo effect                           

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
oscvcas = []
oscvcas.append([osc1, vca1pwm, -1, 0, 0, 0.0, 0.0, 0.0])
oscvcas.append([osc2, vca2pwm, -1, 0, 0, 0.0, 0.0, 0.0])

### Audio output via DAC on A0
audio_out_a0 = audioio.AudioOut(board.A0)

### 0 is MIDI channel 1
### This is listening on channels 1 and 2
### Testing with bigger in_bug_size as MIDI file driven
### pitch bends may be overwhelming buffering causing byte loss
### 600 helps a bit but obviously audible issue with processing
### slowing down on bursty pitch bends
duochannels = (0,1)
extrachannel = (2,)
combinedchannels = duochannels + extrachannel
channels = len(combinedchannels)
midi = adafruit_midi.MIDI(in_channel=combinedchannels,
                          debug=False, in_buf_size=30)

#veltovol = int(65535 / 127)
### Multiplier for MIDI velocity ^ 0.40
### 0.5 would be correct for velocity = power
### but 0.4 sounds more natural - ymmv
velcurve = 0.40
veltovolc040 = 9439

### volume is integer between 0 and 127
### volduo is the latest value received on protocol
### channel 0, 1 (MIDI channels 1,2)
### volextra is value from protocol channel 2 (MIDI channel 3) 
volduo   = 127
volextra = 127

# pitchbendrange in semitones - often 2 or 12
pitchrange = 2
pitchbendmultiplier = pitchrange / 8192
pitchbendvalue = 8192  # mid point - no bend

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

wavenames = waveform_names()
wavename = wavenames[1]  ### TODO - "grep" sawtooth or replace these with enum
waves = []
make_waveforms(waves, wavename, basesamplerate)             
silenceat0 = audioio.RawSample(array.array("H",[0]))

### The voice for extrachannel - a non ADSR wave played with AudioOut
### object to A0
### TODO - move more stuff into here
extravoice = [audio_out_a0, 0]
### Set the output to 0 (0V) rather than its normal midpoint 32768 (1.65V)
### to allow for the imperfectections in the external mixer
audio_out_a0.play(silenceat0)

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
lfodcdepth = 0.0  ### off
lfoamdepth = 0.0  ### off
lforate = 1     ### Initial rate in Hz
lfostart_t = time.monotonic()
lfoshape = "triangle"
boardled = digitalio.DigitalInOut(board.D13)
boardled.direction = digitalio.Direction.OUTPUT

aftertouch = 0.0

gc.collect()
print(gc.mem_free())

print("Ready to play")

### TODO - time.monotonic() loses decimal places as the number gets large
###      - problematic for long running code

while True:
    msg = midi.receive()  ### channels are protocol number
    if isinstance(msg, NoteOn) and msg.velocity != 0:
        if debug:
            print("NoteOn", msg.channel + 1, msg.note, msg.velocity)
        lastnote = msg.note
        pitchbend = (pitchbendvalue - 8192) * pitchbendmultiplier
        ### TODO BUG - S/B also triggered Invalid PWM frequency (0?? extreme pitch bending??)
        ### if remote + time is sent then basefreq can equal some value in the millions
        frequency = round(A4refhz * math.pow(2, (lastnote - midinoteA4 + pitchbend) / 12.0))

        ##print(msg.note, msg.velocity, basefreq)

        if msg.channel in duochannels:
            (oscvcatouse, next) = assignvoice(oscvcas, nextoscvca)
            if next is not None:
                nextoscvca = next  ### Advance voice selection as required

            ### Set everything bar the VCA (element 1) which will be set RSN
            ### at end of if statement
            oscvcas[oscvcatouse][0].frequency = frequency
            oscvcas[oscvcatouse][2] = msg.channel
            oscvcas[oscvcatouse][3] = msg.note
            oscvcas[oscvcatouse][4] = msg.velocity
            oscvcas[oscvcatouse][5] = time.monotonic()
            oscvcas[oscvcatouse][6] = 0.0
            oscvcas[oscvcatouse][7] = 0.0
        elif msg.channel in extrachannel:
            notesamplerate = basesamplerate * frequency / A4refhz 

            ### Select the sine wave with volume for the note velocity
            ### 11.3 is a touch bigger than the square root of 127
            wavevol = int(math.sqrt(msg.velocity) / 11.3 * len(waves))
            ##print(msg.note, notefreq, notesamplerate, ":", msg.velocity, wavevol, len(waves))
            wave = waves[wavevol]
            wave.sample_rate = round(notesamplerate)  ### integer only
            extravoice[0].play(wave, loop=True)
            extravoice[1] = msg.note
        else:
            print("Unexpected msg.channel", msg.channel)

        noteled(pixels, msg.note, msg.velocity)

    elif (isinstance(msg, NoteOff) or 
          isinstance(msg, NoteOn) and msg.velocity == 0):
        if debug:
            print("NoteOff", msg.channel + 1, msg.note, msg.velocity)
        ### Our duophonic "synth module" needs to ignore keys that were pressed before the
        ### 0/1/2 notes that are currently playing
        ### TODO - currently disregards channel number - review this

        if msg.channel in duochannels:
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
        elif msg.channel in extrachannel:
            if msg.note == extravoice[1]:
                ### Avoid use of stop() as this would go to 32768 midpoint
                ## extravoice[0].stop()
                extravoice[0].play(silenceat0, loop=True)
        noteled(pixels, msg.note, 0)

    elif isinstance(msg, PitchBend):
        pitchbendvalue = msg.pitch_bend   ### 0 to 16383
        ### TODO - undo cut and paste here
        pitchbend = (pitchbendvalue - 8192) * pitchbendmultiplier
        for voice in oscvcas:
            ### Check velocity which indicates active voice and 
            ### look for channel match
            if voice[3] > 0 and voice[2] == msg.channel:
                frequency = round(A4refhz * math.pow(2, (voice[3] - midinoteA4 + pitchbend) / 12.0))
                voice[0].frequency = frequency

#    elif isinstance(msg, ChannelPressure):
#        aftertouch = msg.pressure / 127.0
                
    elif isinstance(msg, ControlChange):
        if msg.control == 1:  # modulation wheel - TODO MOVE THIS TO adafruit_midi
            ### msg.value is 0 (none) to 127 (max)
            lfodcdepth = msg.value / 127.0
            
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
            lfoamdepth = msg.value / 127.0
        elif msg.control == 7:   # LFO depth
            if msg.channel in duochannels:
                volduo = msg.value
            elif msg.channel in extrachannel:
                volextra = msg.value

    elif msg is not None:
        if debug:
            print("Something else:", msg.channel + 1, msg)

    ### Create envelopes for any active voices
    now_t = time.monotonic()
    lfovalue = LFO(lfostart_t, now_t, lforate, lfoshape)
    for voiceidx, voice in enumerate(oscvcas):
        if voice[4] > 0:   ### velocity is used as indicator for active voice
            ADSRvol = ADSR(voice[4],
                           voice[5], voice[6], now_t,
                           attack, decay, sustain, release,
                           voice[7])
            ### magic number in 1/math.sqrt(127)
            envampl = round(math.pow(ADSRvol, velcurve) * veltovolc040
                            * math.sqrt(volduo * (1.0 - lfoamdepth * lfovalue))
                            * 0.088735651)
            ### TODO BUG - somewhere as this breached 0 - 65535 during S/B (try multiple restarts at bar 1)
            voice[1].duty_cycle = envampl
            if ADSRvol == 0.0:
                voice[4] = 0  ### end of note playing
            else:
                ### Modulate duty_cycle of oscillator with LFO from 56.25% to 93.75%
                offset = 4096 + round(24576 * max(aftertouch, lfovalue * lfodcdepth))
                if voiceidx % 2 == 0:
                    offset = -offset  ### or 43.75% to 6.25%
                voice[0].duty_cycle = 32768 + offset
    ### Show LFO rate on D13 LED
    boardled.value = lfovalue > 0.85
