### cpx-basic-square-monosynth v1.2
### CircuitPython (on CPX) synth module using internal speaker
### Monophonic synth with some velocity sensitivity and a few
### different waveforms

### Tested with CPX and CircuitPython and 4.0.0-beta.2-141-g2c9fbb5d4-dirty

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
import board

import neopixel
 


import adafruit_midi

### TODO - add control over this
### and work out what's going on at 97-98
speaker_enable = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
speaker_enable.direction = digitalio.Direction.OUTPUT
speaker_enable.value = True

dac = audioio.AudioOut(board.SPEAKER)

### TO RESEARCH - is const more memory efficient?
A4refhz = const(440)
midinoteA4 = const(69)
midinoteC4 = const(60)
basesamplerate = 42240  ### this makes A4 exactly 96 samples

wavename = "square"
wavenames = ["square", 
             "sawtooth", "supersaw", "supersupersaw", 
             "sine", "sineoct2", "sinefifth", "sinemajorchord"]


### brightness 1.0 saves memory by removing need for a second buffer
### 10 is number of NeoPixels on 
numpixels = const(10)
pixels = neopixel.NeoPixel(board.NEOPIXEL, numpixels, brightness=1.0)
black = (0, 0, 0)
pixels.fill(black)

### Turn NeoPixel on to represent a note using RGB x 10 
### to represent 30 notes
### Doesn't do anything with pitch bend
def noteled(pixels, note, velocity):
    note30 = ( note - midinoteC4 ) % (3 * numpixels)
    pos = note30 % numpixels
    if velocity == 0:
        colour = black
    else:
        ### max brightness will be 32    
        colour = round(velocity / 127 * 30 + 2) << ((2 - note30 // numpixels) * 8)
    pixels[pos] = colour

### white pulsing for whatever patch we just selected
flashbrightness = 20
def flashpatch(pixels, patchnum):
    pos = patchnum % numpixels
    t1 = time.monotonic()
    oldcolour = pixels[pos]
    while time.monotonic() - t1 < 0.25:
        for i in range(0, flashbrightness, 2):
            pixels[pos] = (i, i, i)
        for i in range(flashbrightness, 0, -2):
            pixels[pos] = (i, i, i)
    pixels[pos] = oldcolour
        

### TODO - improve commenting

### Discussions in this area
### https://forums.adafruit.com/viewtopic.php?f=60&t=148191

### All just intonation
### TODO - consider putting in some 32768 values on square and sawtooths
###        to make them finish on midpoint and remove any under
###        the covers slewing 
def makewaves(waves, type, samplerate):
    cyclelength = round(samplerate // A4refhz)
    length = cyclelength  ### a default which some waves will change

    #cycles = 1
    #cycles = 3    ### for perfect fifth
    #cycles = 4    ### for major chord

    ### TODO consider volume modification for internal speaker
    ### vs non speaker use

    ### major chord has longer sample which initially works
    ### but will blow up later with four levels
    if type == "majorchord":
        volumes = [23000]
    else:
        volumes = [10000, 18000, 23000, 30000]

    ### Make some waves at different volumes
    for vol in volumes:
        ### Need to create a new array here as audio.RawSample appears not
        if type == "square":
            waveraw = array.array("h", [-vol] * (length // 2) + [vol] * (length - length // 2))
        elif type == "sawtooth":
            waveraw = array.array("h", [0] * length)
            for i in range(length):
                waveraw[i] = round((i / (length - 1) - 0.5) * 2 * vol)
        elif type == "supersaw":
            waveraw = array.array("h", [0] * length)
            halflength    = length // 2
            quarterlength = length // 4
            for i in range(length):
                ### TODO replace this with a gen function similar to sine
                waveraw[i] = round(((i / (length - 1) - 0.5 +
                                     i % halflength / (halflength - 1) - 0.5 +
                                     i % quarterlength / (quarterlength - 1) - 0.5)
                                   ) * 2 / 3 * vol)
        elif type == "supersupersaw":
            cycles = 2
            length = cycles * cyclelength
            waveraw = array.array("h", [0] * length)
            ### TODO add two 5ths
            twothirdsclen = 2 * cyclelength // 3
            halfclen    = cyclelength // 2
            thirdclen   = cyclelength // 3
            quarterclen = cyclelength // 4
            sixthclen   = cyclelength // 6
            eighthlen   = cyclelength // 8
            for i in range(length):
                ### TODO replace this with a gen function similar to sine
                waveraw[i] = round((
                                    2/8 * (i                 / (cyclelength - 1) - 0.5) +
                                    1/8 * (i % twothirdsclen / (twothirdsclen - 1) - 0.5) +
                                    1/8 * (i % halfclen      / (halfclen - 1) - 0.5) +
                                    1/8 * (i % thirdclen     / (thirdclen - 1) - 0.5) +
                                    1/8 * (i % quarterclen   / (quarterclen - 1) - 0.5) + 
                                    1/8 * (i % sixthclen     / (sixthclen - 1) - 0.5) +
                                    1/8 * (i % eighthlen     / (eighthlen - 1) - 0.5)
                                   ) * 2 * vol)
        elif type == "sine":
            waveraw = array.array("h", [0] * length)
            for i in range(length):
                waveraw[i] = round(math.sin(math.pi * 2 * i / length) * vol)
        elif type == "sineoct2":
            waveraw = array.array("h", [0] * length)
            for i in range(length):
                waveraw[i] = round((math.sin(math.pi * 2 * i / length) * 2/3 +
                                    math.sin(math.pi * 2 * i / length * 2) * 1/3
                                   ) * vol)
        elif type == "sinefifth":
            cycles = 2
            length = cycles * cyclelength
            waveraw = array.array("h", [0] * length)
            for i in range(length):
                waveraw[i] = round((math.sin(math.pi * 2 * i / cyclelength) +
                                    math.sin(math.pi * 2 * i / cyclelength * 3/2)
                                   ) * vol / 2)
        elif type == "sinemajorchord":
            cycles = 4
            length = cycles * cyclelength
            waveraw = array.array("h", [0] * length)
            for i in range(length):
                waveraw[i] = round((math.sin(math.pi * 2 * i / cyclelength) +
                                    math.sin(math.pi * 2 * i / cyclelength * 5/4) +
                                    math.sin(math.pi * 2 * i / cyclelength * 6/4)
                                   ) * vol / 2.5)
        else:
            return ValueError("Unknown type")

        waves.append(audioio.RawSample(waveraw))


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

debug = False


lastnote = None
modwheel = 0

waves = []
makewaves(waves, wavename, basesamplerate)


while True:
    msg = midi.read_in_port()
    if isinstance(msg, adafruit_midi.NoteOn) and msg.vel != 0:
#        if debug:
#            print("NoteOn", msg.note, msg.vel)
        lastnote = msg.note
        pitchbend = (pitchbendvalue - 8192) * pitchbendmultiplier
        notefreq = round(A4refhz * math.pow(2, (lastnote - midinoteA4 + pitchbend) / 12.0))

        notesamplerate = basesamplerate * notefreq / A4refhz 
        
        ### Select the sine wave with volume for the note velocity
        ### 11.3 is a touch bigger than the square root of 127
        wavevol = int(math.sqrt(msg.vel) / 11.3 * len(waves))
        ##print(msg.note, notefreq, notesamplerate, ":", msg.vel, wavevol, len(waves))
        wave = waves[wavevol]

        wave.sample_rate = round(notesamplerate)  ### integer only
        dac.play(wave, loop=True)

        noteled(pixels, msg.note, msg.vel)

    elif (isinstance(msg, adafruit_midi.NoteOff) or 
          isinstance(msg, adafruit_midi.NoteOn) and msg.vel == 0):
#        if debug:
#            print("NoteOff", msg.note, msg.vel)
        # Our monophonic "synth module" needs to ignore keys that lifted on
        # overlapping presses
        if msg.note == lastnote:
            dac.stop()
                
        noteled(pixels, msg.note, 0)
        
#    elif msg is not None:
#        if debug:
#            print("Something else:", msg)
    elif isinstance(msg, adafruit_midi.PitchBendChange):
        pitchbendvalue = msg.value   ### 0 to 16383
        ### TODO - undo cut and paste here
        pitchbend = (pitchbendvalue - 8192) * pitchbendmultiplier
        notefreq = round(A4refhz * math.pow(2, (lastnote - midinoteA4 + pitchbend) / 12.0))

        ### TODO - sounds bad, need to limit rate of change, e.g. only every 100ms

        ### TODO - BUG - this must only play if already playing   
        notesamplerate = basesamplerate * notefreq / A4refhz 
        ### TODO - review whether there's an advantage to not assigning here
        ### if value would be the same as previously set value
        wave.sample_rate = round(notesamplerate)  ### integer only
        dac.play(wave, loop=True)
        
    elif isinstance(msg, adafruit_midi.ProgramChange):
        print("patch select", msg.patch)
        
    elif isinstance(msg, adafruit_midi.ControlChange):
        if msg.control == 1:  # modulation wheel - TODO MOVE THIS TO adafruit_midi
            ### msg.value is 0 (none) to 127 (max)
            modwheel = msg.value

        elif msg.control == 74:  # filter cutoff - borrowing to switch voices
            print("filter", msg.value)
            waveidx = msg.value // 5 % len(wavenames)
            newwave = wavenames[waveidx]
            flashpatch(pixels, waveidx)
            if newwave != wavename:
                print("changing from", wavename, "to", newwave)
                wavename = newwave
                waves.clear()
                makewaves(waves, wavename, basesamplerate)
