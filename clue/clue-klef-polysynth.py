### clue-klef-polysynth v0.3
### Polyphonic synth for Kitronik KLEF with Adafruit CLUE

### Tested with an Adafruit CLUE (Alpha) and CircuitPython and 5.3.0

### copy this file to CLUE board as code.py

### MIT License

### Copyright (c) 2018 Kitronik Ltd
### Copyright (c) 2020 Kevin J. Walters

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
import board
import busio
import digitalio
import terminalio
import displayio
import math
import array

from adafruit_bus_device.i2c_device import I2CDevice
from adafruit_display_text.label import Label

### Audio bits - TODO clean this up - conditional imports?
from audiopwmio import PWMAudioOut as AudioOut
from audiocore import RawSample
from audiomixer import Mixer


def sawtooth(angle):
    return 1.0 - angle % twopi / twopi * 2

def triangle(angle):
    norm_angle = angle % twopi
    return 1.0 - 2 * abs(norm_angle - math.pi) / math.pi


debug = 3

display = board.DISPLAY
DISPLAY_WIDTH = display.width
DISPLAY_HEIGHT = display.height

### i2c code inspired by
### https://github.com/KitronikLtd/micropython-microbit-kitronik-klef-piano
### TODO - check this against data sheet
### TODO - review auto-calibration and between key stuff

std_i2c = busio.I2C(board.SCL, board.SDA)


def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


def manual_screen_refresh(disp):
    """Refresh the screen as immediately as is currently possibly with refresh method."""
    refreshed = False
    while True:
        try:
            ### 1000fps is fastest library allows - this high value
            ### minimises any delays this refresh() method introduces
            refreshed = disp.refresh(minimum_frames_per_second=0,
                                     target_frames_per_second=1000)
        except RuntimeError:
            pass
        if refreshed:
            break

# Create a bitmap with 256 colors
bitmap = displayio.Bitmap(8, 8, 256)

# Create a 256 color palette
palette = displayio.Palette(256)


BLACK=0x000000
WHITE=0xffffff


### Needs some though about how to update this
key_bitmap = displayio.Bitmap(13, 2, 2)

palette = displayio.Palette(2)
palette[0] = 0x000000
palette[1] = 0xffff00   ### YELLOW

k_tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)

k_group = displayio.Group(scale=16)

k_group.append(k_tile_grid)

k_group = displayio.Group(scale=16, max_size=1)
k_group.y = 200


sc_group = displayio.Group(max_size=2)

font_scale = 2
max_dob = Label(terminalio.FONT,
                text="    " "    ",  ### TODO HACK!
                scale=font_scale,
                background_color=BLACK,
                color=BLACK)
max_dob.y = round(DISPLAY_HEIGHT * 1/3)
min_dob = Label(terminalio.FONT,
                text="    " "    ",
                scale=font_scale,
                background_color=BLACK,
                color=BLACK)
min_dob.y = round(DISPLAY_HEIGHT * 2/3)
sc_group.append(max_dob)
sc_group.append(min_dob)


main_group = displayio.Group(max_size=2)
##main_group.append(b_group)
main_group.append(sc_group)

# Add the Group to the Display
display.show(main_group)

display.auto_refresh = False


class KitronikPiano:
    CHIP_ADDRESS = 0x0D
    
    class PianoKeys:
        KEY_K0 = 0x100
        KEY_K1 = 0x200
        KEY_K2 = 0x400
        KEY_K3 = 0x800
        KEY_K4 = 0x1000
        KEY_K5 = 0x2000
        KEY_K6 = 0x4000
        KEY_K7 = 0x8000
        KEY_K8 = 0x01
        KEY_K9 = 0x02
        KEY_K10 = 0x04
        KEY_K11 = 0x08
        KEY_K12 = 0x10
        KEY_K13 = 0x20
        KEY_K14 = 0x40
    
    keySensitivity = 8
    keyNoiseThreshold = 5
    keyRegValue = 0x0000
    
    #Function to initialise the micro:bit Piano (called on first key press after start-up)
    ### TODO LOOK UP NAME FOR 
    def __init__(self, i2c, data_ready_pin):
        buff = bytearray(1)
        buff2 = bytearray(2)
        buff3 = bytearray(5)
        
        pin1 = digitalio.DigitalInOut(data_ready_pin)
        pin1.pull = digitalio.Pull.UP
        self.pin_datanotready = pin1
        self.last_key_press = 0
        self.initialised = False
        
        self.i2c_device = I2CDevice(i2c, self.CHIP_ADDRESS)

        # Startup procedure
        # Test /change pin is low, then test basic communication
        if not self.initialised or pin1.value is False:
            # Reads the chip ID, should be 0x11 (chip ID addr = 0)
            buff[0] = 0x00
            with self.i2c_device as device:
                device.write(buff)
            reading = True
            readBuff = bytearray(1)
            while reading:
                with self.i2c_device as device:
                    device.readinto(readBuff)
                if (readBuff[0] == 0x11):
                    reading = False

            ### NTHR Default value: 10 (10 counts of threshold)
            for negativeThresholdReg in range(38, 53 + 1):
                buff2[0] = negativeThresholdReg
                buff2[1] = 12  ### 10 is default apparently
                with self.i2c_device as device:
                   device.write(buff2)

            # Change sensitivity (burst length) of keys 0-14 to keySensitivity (default is 8)
            ### This is actually the "Burst Length" from section 6.21 of datasheet
            ### Default: 4 (16 burst pulses)
            for sensitivityReg in range(54, 68 + 1):
                buff2[0] = sensitivityReg
                ### chip default is 4 which is way better than 8 (for poly??)
                buff2[1] = 4   ### self.keySensitivity 
                with self.i2c_device as device:
                    device.write(buff2)

            # Disable key 15 as it is not used
            buff2[0] = 69
            buff2[1] = 0
            with self.i2c_device as device:
                device.write(buff2)

            # Set Burst Repetition to keyNoiseThreshold (default is 5)
            buff2[0] = 13
            buff2[1] = self.keyNoiseThreshold
            with self.i2c_device as device:
                device.write(buff2)
            
            ### TODO - commenting out as a test to see if this allows polyphony
            
            #Configure Adjacent Key Suppression (AKS) Groups
            #AKS Group 1: ALL KEYS
            ##for aksReg in range(22, 37, 1):
            ##    buff2[0] = aksReg
            ##    buff2[1] = 1
            ##    with self.i2c_device as device:
            ##        device.write(buff2)

            # Send calibration command
            print("CALIBRATING")
            buff2[0] = 10
            buff2[1] = 1
            with self.i2c_device as device:
                device.write(buff2)

        # Read all change status address (General Status addr = 2)
        buff[0] = 0x02
        with self.i2c_device as device:
            ##device.write_then_readinto(buff, buff3)
            device.write(buff)
            device.readinto(buff3)
            
        # Continue reading change status address until /change pin goes high
        buff[0] = 0x02
        while pin1.value is False:
            with self.i2c_device as device:
                ##device.write_then_readinto(buff, buff3)
                device.write(buff)
                device.readinto(buff3)
                
        self.initialised = True
        
        
    #Set sensitivity of capacitive touch keys, then initialise the IC.
    #A higher value increases the sensitivity (values can be in the range 1 - 32).
    def setKeySensitivity(self, sensitivity):
        self.keySensitivity = sensitivity
        
        self.__init__()  ### TODO - review this
        
        
    #Set the noise threshold of capacitive touch keys, then initialise the IC.
    #A higher value enables the piano to be used in areas with more electrical noise (values can be in the range 1 - 63).
    def setKeyNoiseThreshold(self, noiseThreshold):
        self.keyNoiseThreshold = noiseThreshold
        self.__init__()  ### TODO - review this
    
    #Function to read the Key Press Registers
    #Return value is a combination of both registers (3 and 4) which links with the values in the 'PianoKeys' class
    def _readKeyPress(self):
        buff = bytearray(1)
        buff2 = bytearray(2)
        buff3 = bytearray(5)
        buff[0] = 0x02
        with self.i2c_device as device:
            ##device.write_then_readinto(buff, buff3)
            device.write(buff)
            device.readinto(buff3)
            
        # Address 3 is the addr for keys 0-7 (this will then auto move onto Address 4 for keys 8-15, both reads stored in buff2)
        buff[0] = 0x03
        with self.i2c_device as device:
            ##device.write_then_readinto(buff, buff2)
            device.write(buff)
            device.readinto(buff2)
            
        # keyRegValue is a 4 byte number which shows which keys are pressed
        keyRegValue = buff2[1] + (buff2[0] << 8)

        return keyRegValue
        
    #Function to determine if a piano key is pressed and returns a true or false output.
    def keyIsPressed(self, key: PianoKeys):
        keyPressed = False

        if (key & self._readKeyPress()) == key:
            keyPressed = True

        return keyPressed

    def bufferedKeyPress(self):
        if self.pin_datanotready.value:
            return self.last_key_press
        self.last_key_press = self._readKeyPress()
        return self.last_key_press


piano = KitronikPiano(std_i2c, board.P1)

audio = AudioOut(board.P0) ### P0 is klef speaker

### from 1.0 to 2.0 in equal temperament
st_mult = [2**(st/12) for st in range(12 + 1)]

midpoint = 32768
vol = 32767

samples_per_waveform = 16
c_waves = 128
buffer_size = c_waves * samples_per_waveform

twopi = 2 * math.pi
a4_hz = 440
a4_st = 9  ### 9 st above C

### TODO - could print error from exact rate or could do this more universally
### This is the sample playback rate for playing the first sample at C4 frequency
rate = round(a4_hz / st_mult[a4_st] * samples_per_waveform)


### voice 0 seems to be louder than the rest, not using it
mixer = Mixer(voice_count=len(st_mult) + 1,
              sample_rate=rate,
              channel_count=1,
              bits_per_sample=16, samples_signed=False)

### quiet audible click as this initialises
audio.play(mixer)

### Create samples for each note (semitone) from C4 to C5
note_samples = []
for st, mult in enumerate(st_mult):
    sample = RawSample(array.array("H",
                                   [round(midpoint
                                          + triangle(x * twopi / (buffer_size / round(c_waves * mult))) * vol)
                                    for x in range(buffer_size)]),
                       sample_rate=rate)
    mixer.voice[st + 1].level = 0.0
    ##mixer.voice[st].play(sample, loop=True)
    note_samples.append(sample)


def chromaticText(mxr, notes):
    """Chromatic scale test."""
    for st in range(len(st_mult)):
        mxr.voice[st + 1].play(notes[st], loop=True)
        for idx in range(20 + 1):
            mxr.voice[st + 1].level = idx / 20
            time.sleep(0.05)
        time.sleep(0.25) ### sustain
        for idx in range(20, 0 - 1, -1):
            mxr.voice[st + 1].level = idx / 20
            time.sleep(0.025)
        mxr.voice[st + 1].stop()


KEYS = [piano.PianoKeys.KEY_K9,
        piano.PianoKeys.KEY_K1,
        piano.PianoKeys.KEY_K10,
        piano.PianoKeys.KEY_K2,
        piano.PianoKeys.KEY_K11,
        piano.PianoKeys.KEY_K12,
        piano.PianoKeys.KEY_K3,
        piano.PianoKeys.KEY_K13,
        piano.PianoKeys.KEY_K4,
        piano.PianoKeys.KEY_K14,
        piano.PianoKeys.KEY_K5,
        piano.PianoKeys.KEY_K6,
        piano.PianoKeys.KEY_K7]


def processKeys(mxr, notes, ADSR_voices, old_mask, new_mask):

    ### xor the values
    diff_mask = old_mask ^ new_mask

    ### Check each key to see if it has changed state
    for st, key in enumerate(KEYS):
        if diff_mask & key:
            if new_mask & key:  ### note on 
                ADSR_voices[st + 1] = "A"
            else:  ### note off
                ADSR_voices[st + 1] = "R"


def processADSR(mxr, notes, ADSR_voices):
    """Very simple AR for ADSR with no time/level parameters..."""

    ### This modified ADSR_voices too
    for idx in range(1, len(ADSR_voices)):
        adsr = ADSR_voices[idx]
        level = mxr.voice[idx].level
        if adsr == "A":
            if level < 0.8:
                if level == 0.0:
                    mxr.voice[idx].play(notes[idx - 1], loop=True)
                mxr.voice[idx].level += 0.0125
            else:
                ADSR_voices[idx] = "S"
        elif adsr == "R":
            if level > 0.0:
                if level > 0.0015625:
                    mxr.voice[idx].level -= 0.0015625
                else:
                    mxr.voice[idx].level = 0.0
                    mxr.voice[idx].stop()
                    ADSR_voices[idx] = ""


ADSR = [""] * len(mixer.voice)

last_key_mask = 0
while True:
    key_mask = piano.bufferedKeyPress()
    ##print("LOOP", f"{key_mask:016b}")   

    if key_mask != last_key_mask:
        print("CHNG", f"{key_mask:016b}")
        processKeys(mixer, note_samples, ADSR,
                    last_key_mask, key_mask)
        last_key_mask = key_mask

    processADSR(mixer, note_samples, ADSR)
    time.sleep(0.001)


### Still getting occasional - restart of program is workaround here. could also try catching it
### Or checking i2c timing or add 1ms between write and read?
#
# CHNG 1000000000101000
# CHNG 1000000000101010
# Traceback (most recent call last):
  # File "code.py", line 415, in <module>
  # File "code.py", line 295, in bufferedKeyPress
  # File "code.py", line 276, in _readKeyPress
  # File "code.py", line 275, in _readKeyPress
  # File "adafruit_bus_device/i2c_device.py", line 104, in write
# OSError: [Errno 19] Unsupported operation
