### cpx-midi-touch v1.0
### CircuitPython on CPX simple midi controller using touch pads
### Uses A1-A7 starting at A4 counterclockwise for C to B, major scale

### Tested with CPX and CircuitPython 4.0.0 beta2

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
import touchio
import digitalio
### This library will only work with CircuitPython 4.0.0
import adafruit_midi

### Current version uses wire protocol channel numbers 0-15
### 0 will be channel 1
### see https://github.com/adafruit/Adafruit_CircuitPython_MIDI/issues/2
midi = adafruit_midi.MIDI(out_channel=0)

### CPX order of touchio capable pads (i.e. not A0)
pads = [ board.A4,
         board.A5,
         board.A6,
         board.A7,
         board.A1,
         board.A2,
         board.A3]

touchpads = [touchio.TouchIn(pad) for pad in pads]
del pads  ### done with that

### IDEAS 
### Change scale / octave / minor scales
### Sensitivity change
### Local speaker mode

### a is left (usb at top)
buttonleft = digitalio.DigitalInOut(board.BUTTON_A)
buttonleft.switch_to_input(pull=digitalio.Pull.DOWN)
buttonright = digitalio.DigitalInOut(board.BUTTON_B)
buttonright.switch_to_input(pull=digitalio.Pull.DOWN)

majorscale = [0,2,4,5,7,9,11]
basenote = 60  ### C4 middle C

midinotes = [semitone + basenote for semitone in majorscale]
keydown = [False] * 7

velocity = 127
minoct = -3
maxoct = +3
octave = 0

### Scan each pad and look for changes by comparing
### with keystate stored in keydown boolean list
### and send note on/off messages accordingly
### The two buttons are used to shift octave
while True:
    for idx in range(len(touchpads)):
        if touchpads[idx].value != keydown[idx]:
            keydown[idx] = touchpads[idx].value
            note = midinotes[idx] + octave * 12
            if (keydown[idx]):
                midi.note_on(note, velocity)
            else:
                midi.note_off(note, velocity)
    if buttonleft.value and octave > minoct:
        ### TODO - clear any notes
        octave -= 1
        while buttonleft.value:
            pass   ### wait for button up
    if buttonright.value and octave < maxoct:
        ### TODO - clear any notes
        octave += 1
        while buttonright.value:
            pass   ### wait for button up
