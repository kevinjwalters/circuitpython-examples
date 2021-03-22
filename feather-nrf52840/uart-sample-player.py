### uart-sample-player v1.0
### An ultra-simple wav jukebox based on single byte commands over RX serial

### Tested with Feather nRF52840 and 6.1.0

### copy this file to Feather nRF52840 as code.py

### MIT License

### Copyright (c) 2021 Kevin J. Walters

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

### This plays wave samples based on the number received
### in a single byte "command" over UART
### The first sample is 1, second sample is 2, etc.
### 0 is ignored

### This is a daughterboard-style workaround for PWM audio
### not always working well at the moment on Pi Pico using wav files
### in 6.2.0 betas
### https://github.com/adafruit/circuitpython/issues/4208


import board
import busio
from audiocore import WaveFile
try:
    from audioio import AudioOut
except ImportError:
    from audiopwmio import PWMAudioOut as AudioOut
from audiomixer import Mixer

### Using mixer is a workaround for the nRF52840 PWMAudioOut
### not implementing the quiescent_value after a sample
### has completed playing
mixer = Mixer(voice_count=2,
              sample_rate=16000,
              channel_count=2,
              bits_per_sample=16,
              samples_signed=True)

wav_files = ("scanner-left-16k.wav",
             "scanner-right-16k.wav")

### Use same pins which would be used on a Feather M4 with real DACs
AUDIO_PIN_L = board.A0
AUDIO_PIN_R = board.A1
audio_out = AudioOut(AUDIO_PIN_L,
                     right_channel=AUDIO_PIN_R)

wav_fh = [open(fn, "rb") for fn in wav_files]
wavs = [WaveFile(fh) for fh in wav_fh]

### Voice 0 behaves strangely
### https://github.com/adafruit/circuitpython/issues/3210
mixer.voice[0].level = 0.0
mixer.voice[1].level = 1.0
audio_out.play(mixer)

audio = mixer.voice[1]

uart = busio.UART(board.TX, board.RX, baudrate=115200)
rx_bytes = bytearray(1)

while True:
    if uart.readinto(rx_bytes) and rx_bytes[0]:
        try:
            wav_obj = wavs[rx_bytes[0] - 1]
            audio.play(wav_obj)
        except IndexError:
            print("No wav file for:", rx_bytes[0])
