### cpb-wav-player v1.1
### Play local wave files

### Tested on
### CPB running CircuitPython 10.0.3

### copy this file to CPX or CPB as code.py

### MIT License

### Copyright (c) 2025 Kevin J. Walters

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

### SPDX-FileCopyrightText: 2025 Kevin J. Walters

### pylint: disable=wrong-import-order,consider-using-with


import time

import board
##import touchio
import digitalio
import os

### This code works on both CPB and CPX boards by bringing in classes with same name
from audiocore import WaveFile
try:
    from audioio import AudioOut
except ImportError:
    from audiopwmio import PWMAudioOut as AudioOut

import neopixel


numpixels = 10
CUED_LEVEL = 0x02
PLAYING_LEVEL = 0x18
PIXEL_REVORDER = True
BLACK = 0x000000

pixels = neopixel.NeoPixel(board.NEOPIXEL, numpixels, brightness=1.0, auto_write=False)
pixels.fill(BLACK)
pixels.show()

### Turn the speaker on
speaker_enable = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
speaker_enable.direction = digitalio.Direction.OUTPUT
speaker_enable.value = True

audio_out = AudioOut(board.SPEAKER)

### Case sensitive extension...
wavfiles = tuple([f for f in os.listdir("/") if f.endswith("wav")])  ### pylint: disable=consider-using-generator

### A is left, B is right (usb at top)
button_left = digitalio.DigitalInOut(board.BUTTON_A)
button_left.switch_to_input(pull=digitalio.Pull.DOWN)
button_right = digitalio.DigitalInOut(board.BUTTON_B)
button_right.switch_to_input(pull=digitalio.Pull.DOWN)


def isLoop(filename):
    return filename.find("-loop.") >= 0


def showPlaying(w_idx, level):
    pixels.fill(BLACK)
    if w_idx is not None:
        px_idx = w_idx % numpixels
        if PIXEL_REVORDER:
            px_idx = numpixels - px_idx - 1
        px_col = w_idx // numpixels + 1
        pixels[px_idx] = (level if px_col & 0b001 else 0,
                          level if px_col & 0b010 else 0,
                          level if px_col & 0b100 else 0)
    pixels.show()

### 0 isn't playing but this forces first call to showPlaying()
playing_idx = 0
playlast_idx = None
playnext_idx = 0
file_handle = None
wav = None

while True:
    playing = audio_out.playing
    if not playing and playing_idx is not None:
        playing_idx = None
        showPlaying(playnext_idx, CUED_LEVEL)

    if button_left.value:
        if playing_idx is None:
            if playlast_idx != playnext_idx:
                if file_handle:
                    file_handle.close()
                    wav = None
                file_handle = open(wavfiles[playnext_idx], "rb")
                wav = WaveFile(file_handle)
                playlast_idx = playnext_idx
            print("Playing", wavfiles[playnext_idx])
            audio_out.play(wav, loop=isLoop(wavfiles[playnext_idx]))
            playing_idx = playnext_idx
            showPlaying(playing_idx, PLAYING_LEVEL)

        while button_left.value:
            pass  ### wait for release

    if button_right.value:
        if playing:
            ### Stop playing if a wav is playing
            audio_out.stop()
        else:
            ### If no wav file was playing advance to next wav
            if len(wavfiles) > 1:
                playnext_idx += 1
                if playnext_idx >= len(wavfiles):
                    playnext_idx = 0
                showPlaying(playnext_idx, CUED_LEVEL)

        while button_right.value:
            pass  ### wait for release

    ### Run loop at maximum of 20 times a second
    time.sleep(1.0 / 20.0)
