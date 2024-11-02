### synthio-filter-breadkdown v1.0
### Exploration of synthio filter sometimes producing white noise

### Tested with Pi Pico W (on EDU PICO) and 9.1.4

### copy this file to Cytron Maker Pi Pico as code.py

### MIT License

### Copyright (c) 2024 Kevin J. Walters

### Permission is hereby granted, free of charge, to any person obtaining a copy
### of this software nd associated documentation files (the "Software"), to deal
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

### low-pass filter iscussion in https://forums.adafruit.com/viewtopic.php?p=1034152

### Focus on C7 (note 84) - the Biquad filter turns to noise if low pass filter frequency
### is above half the sample rate (the Nyquist rate)
### Sample rate is set the same on Mixer and Sythenszier


import os
import time

import board
##import analogio
##import digitalio
##import pwmio

import audiomixer
import synthio
import audiopwmio
import ulab.numpy as np

import usb_midi
import adafruit_midi
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff
from adafruit_midi.control_change import ControlChange
from adafruit_midi import control_change_values


debug = 2


SAMPLE_RATE = 64_000

MIXER_BUFFER_SIZE = 2048
WAVEFORM_PEAK = 28_000
WAVEFORM_MAX = 2**15 - 1
WAVEFORM_LEN = 8
WAVEFORM_HALFLEN = WAVEFORM_LEN // 2
MIDI_KEY_CHANNEL = 1
### Wire protocol values
MIDI_KEY_CHANNEL_WIRE = MIDI_KEY_CHANNEL - 1

if os.uname().machine.find("EDU PICO"):
    LEFT_AUDIO_PIN = board.GP20
    RIGHT_AUDIO_PIN = board.GP21
elif os.uname().sysname == "rp2040":
    ### Cytron Maker Pi Pico
    LEFT_AUDIO_PIN = board.GP18
    RIGHT_AUDIO_PIN = board.GP19
else:
    ### Custom RP2350B board
    LEFT_AUDIO_PIN = board.GP36
    RIGHT_AUDIO_PIN = board.GP37




def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)



waveform_saw    = np.linspace(WAVEFORM_PEAK, 0 - WAVEFORM_PEAK, num=WAVEFORM_LEN,
                              dtype=np.int16)
midi_usb  = adafruit_midi.MIDI(midi_in=usb_midi.ports[0],
                               in_channel=MIDI_KEY_CHANNEL_WIRE)
audio = audiopwmio.PWMAudioOut(LEFT_AUDIO_PIN, right_channel=RIGHT_AUDIO_PIN)
mixer = audiomixer.Mixer(channel_count=1,
                         sample_rate=SAMPLE_RATE,
                         buffer_size=MIXER_BUFFER_SIZE)
synth = synthio.Synthesizer(channel_count=1,
                            sample_rate=SAMPLE_RATE)

audio.play(mixer)
mixer.voice[0].play(synth)
mixer.voice[0].level = 0.75

filter_freq_lo = 100   # filter lowest freq
filter_freq_hi = 4500  # filter highest freq
filter_note_offset_low = 58
filter_note_offset_high = 62
filter_res_lo = 0.1    # filter q lowest value
filter_res_hi = 2.0    # filter q highest value

filter_note_offset = 37
filter_res = 1.0    # current setting of filter
amp_env_attack_time = 1.0
amp_env_decay_time = 0.5
amp_env_sustain = 0.8
amp_env_release_time = 1.100

pressed = []
oscs = []



### Simple range mapper, like Arduino map()
def map_range(s, a1, a2, b1, b2):
    return  b1 + ((s - a1) * (b2 - b1) / (a2 - a1))


### pylint: disable=consider-using-in,too-many-branches
def note_on(notenum, vel):

    new_osc = []
    f_1 = synthio.midi_to_hz(notenum)
    filt_f_1 = synthio.midi_to_hz(notenum + filter_note_offset)
    filter_1 = synth.low_pass_filter(filt_f_1, filter_res)
    d_print(2, "FILTER FREQ", filt_f_1, "AM+S rate", SAMPLE_RATE)
    new_osc.append(synthio.Note(frequency=f_1,
                                waveform=waveform_saw,
                                amplitude=0.5,
                                envelope=synthio.Envelope(attack_time=amp_env_attack_time,
                                                          attack_level=1.0,
                                                          decay_time=amp_env_decay_time,
                                                          sustain_level=amp_env_sustain,
                                                          release_time=amp_env_release_time),
                                filter=filter_1
                                ))

    oscs.clear()
    pressed.clear()

    oscs.extend(new_osc)
    synth.press(oscs)
    pressed.append(notenum)


def notes_off():

    synth.release(oscs)
    oscs.clear()
    pressed.clear()


last_note = None
start_ns = time.monotonic_ns()
while True:
    msg = midi_usb.receive()

    if msg:
        if isinstance(msg, NoteOn) and msg.velocity != 0:
            d_print(2, "Note:", msg.note, "vel={:d}".format(msg.velocity))
            if last_note is not None:
                notes_off()
            note_on(msg.note, msg.velocity)
            last_note = msg.note

        elif (isinstance(msg, NoteOff)
              or isinstance(msg, NoteOn) and msg.velocity == 0):
            d_print(2, "Note:", msg.note, "vel={:d}".format(msg.velocity))
            if msg.note in pressed:  # only release note that's sounding
                notes_off()

        elif isinstance(msg, ControlChange):
            d_print(2, "CC:", msg.control, "=", msg.value)
            if msg.control == control_change_values.CUTOFF_FREQUENCY:  ### 74
                ##filter_freq = map_range( msg.value, 0,127, filter_freq_lo, filter_freq_hi)
                filter_note_offset = map_range(msg.value,
                                               0, 127,
                                               filter_note_offset_low, filter_note_offset_high)
            elif msg.control == control_change_values.FILTER_RESONANCE:  ### 71
                filter_res = map_range(msg.value, 0, 127, filter_res_lo, filter_res_hi)
            elif msg.control == control_change_values.RELEASE_TIME: ### 72
                amp_env_release_time = map_range(msg.value, 0, 127, 0.05, 3)

        else:
            d_print(1, "MIDI MSG:", msg)
