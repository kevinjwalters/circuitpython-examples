### synthfunctions v1.0

### Tested with CPX and CircuitPython 4.0.0 beta5 

### copy this file or mpy version of this file to CPX

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

import math
import random
import array
import audioio

### TODO - review whether this should be set by user
A4refhz = const(440)

### All just intonation
### TODO - consider putting in some 32768 values on square and sawtooths
###        to make them finish on midpoint and remove any under
###        the covers slewing 
def make_waveforms(waves, type, samplerate):
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
        volumes = [23000]  ### 30000 clips 
        #volumes = [10000, 18000, 23000, 30000]

    ### Make some waves at different volumes
    for vol in volumes:
        ### Need to create a new array here as audio.RawSample appears not
        if type == "square":
            waveraw = array.array("h", [-vol] * (length // 2) + [vol] * (length - length // 2))
        else:
            waveraw = array.array("h", [0] * length)
            if type == "sawtooth":
                for i in range(length):
                    waveraw[i] = round((i / (length - 1) - 0.5) * 2 * vol)
            elif type == "supersaw":
                halflength    = length // 2
                quarterlength = length // 4
                for i in range(length):
                    ### TODO replace this with a gen function similar to sine
                    waveraw[i] = round(((i / (length - 1) - 0.5 +
                                         i % halflength / (halflength - 1) - 0.5 +
                                         i % quarterlength / (quarterlength - 1) - 0.5)
                                       ) * 2 / 3 * vol)
            elif type == "noise":
                waveraw = array.array("h", [0] * length)
                for i in range(length):
                    waveraw[i] = random.randint(0, 65536)
            else:
                return ValueError("Unknown type")

        waves.append(audioio.RawSample(waveraw))

def waveform_names():
    return ["square", "sawtooth", "supersaw", "noise" ]
 

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
