### cpx-expressive-midi-controller v0.6
### CircuitPython (on CPX) MIDI controller using the seven touch pads
### and accelerometer for modulation (cc1) and pitch bend

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
import touchio
import busio
import board

import usb_midi
import neopixel
import adafruit_lis3dh
import adafruit_midi

from adafruit_midi.midi_message     import note_parser

from adafruit_midi.note_on          import NoteOn
from adafruit_midi.note_off         import NoteOff
from adafruit_midi.control_change   import ControlChange
from adafruit_midi.pitch_bend       import PitchBend

midinoteC4 = 60

# 0x19 is the i2c address of the onboard accelerometer
acc_i2c = busio.I2C(board.ACCELEROMETER_SCL, board.ACCELEROMETER_SDA)
acc_int1 = digitalio.DigitalInOut(board.ACCELEROMETER_INTERRUPT)
acc = adafruit_lis3dh.LIS3DH_I2C(acc_i2c, address=0x19, int1=acc_int1)
acc.range = adafruit_lis3dh.RANGE_2_G
acc.data_rate = adafruit_lis3dh.DATARATE_10_HZ

# TODO - look at what can be done to average/filter/denoise the accelerometer
# set/drop its sample rate?

### brightness 1.0 saves memory by removing need for a second buffer
### 10 is number of NeoPixels on
numpixels = const(10)
### brightness of 1.0 prevents an extra array from being created
pixels = neopixel.NeoPixel(board.NEOPIXEL, numpixels, brightness=1.0)

### Turn NeoPixel on to represent a note using RGB x 10
### to represent 30 notes
### Doesn't do anything with pitch bend
def noteLED(pixels, note, velocity):
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

cc_mod = 1  # Standard control change for modulation wheel
midi_channel = 1
midi = adafruit_midi.MIDI(midi_out=usb_midi.ports[1],
                          out_channel=midi_channel-1)

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

pitch_bend_value = 8192  # mid point - no bend
debug = True
mod_wheel = 0


### A is on left (usb at top)
buttonleft = digitalio.DigitalInOut(board.BUTTON_A)
buttonleft.switch_to_input(pull=digitalio.Pull.DOWN)
buttonright = digitalio.DigitalInOut(board.BUTTON_B)
buttonright.switch_to_input(pull=digitalio.Pull.DOWN)

majorscale = [0, 2, 4, 5, 7, 9, 11]
chromatic = [0, 1, 2, 3, 4 , 5, 6 ]
chromatic_p7 = [7, 8, 9, 10, 11, 12, 13]  # could use this for two together
base_note = midinoteC4  # C4 middle C

midinotes = [semitone + base_note for semitone in majorscale]
keydown = [False] * 7

velocity = 127
minoct = -3
maxoct = +3
octave = 0

### 1/10 = 10 Hz - review data_rate setting if this is changed
acc_read_t = time.monotonic()
acc_read_period = 1/10

# Convert an accelerometer reading
# from min_msm2 to min_msm2+range to an int from 0 to value_range
# or return 0 or value_range outside those values
# the conversion is applied "symmetrically" to negative numbers
def scale_acc(acc_msm2, min_msm2, range_msm2, value_range):
    if acc_msm2 >= 0.0:
        sign_a_m = 1
        magn_acc_msm2 = acc_msm2
    else:
        sign_a_m = -1
        magn_acc_msm2 = abs(acc_msm2)

    adj_msm2 = magn_acc_msm2 - min_msm2

    # deal with out of bounds values else do scaling
    if adj_msm2 <= 0:
        return 0
    elif adj_msm2 > range_msm2:
        return sign_a_m * value_range
    else:
        return sign_a_m * round(adj_msm2 / range_msm2 * value_range)

### Scan each pad and look for changes by comparing
### with keystate stored in keydown boolean list
### and send note on/off messages accordingly
### The two buttons are used to shift octave
while True:
    for idx in range(len(touchpads)):
        if touchpads[idx].value != keydown[idx]:
            keydown[idx] = touchpads[idx].value
            note = midinotes[idx] + octave * 12
            if debug:
                print(keydown[idx], note)
            if (keydown[idx]):
                midi.send(NoteOn(note, velocity))
                noteLED(pixels, note, velocity)
            else:
                midi.send(NoteOff(note, velocity))
                noteLED(pixels, note, 0)

    # Perform rate limited checks on the accelerometer
    now_t = time.monotonic()
    if now_t - acc_read_t > acc_read_period:
        acc_read_t = time.monotonic()
        ax, ay, az = acc.acceleration

        new_mod_wheel = abs(scale_acc(ay, 1.3, 4.0, 127))
        if abs(new_mod_wheel - mod_wheel) > 5 or (new_mod_wheel == 0 and mod_wheel != 0):
            if debug:
                print("Modulation", new_mod_wheel)
            midi.send(ControlChange(cc_mod, new_mod_wheel))
            mod_wheel = new_mod_wheel

        new_pitch_bend_value = 8192 - scale_acc(ax, 1.3, 4.0, 8191)
        if abs(new_pitch_bend_value - pitch_bend_value) > 250 or (new_pitch_bend_value == 8192 and pitch_bend_value != 8192):
            if debug:
                print("Pitch Bend", new_pitch_bend_value)
            midi.send(PitchBend(new_pitch_bend_value))
            pitch_bend_value = new_pitch_bend_value

    ### change these - left octave, right scale?
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
    ### TODO - add code for switch arp mode?
