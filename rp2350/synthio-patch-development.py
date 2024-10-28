### synthio-patch-development.py v1.1
### Synthio patch with increasing complexity playable via MIDI

### Tested with Pimoroni PGA2350 and 9.2.0-beta.1

### copy this file to Pimoroni PGA2350 as code.py

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


import math
import os
import random
import time

import board

import audiomixer
import synthio
import audiopwmio
import ulab.numpy as np

import usb_midi
import adafruit_midi
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff
from adafruit_midi.control_change import ControlChange
from adafruit_midi.pitch_bend import PitchBend
from adafruit_midi.channel_pressure import ChannelPressure
from adafruit_midi.program_change import ProgramChange
from adafruit_midi import control_change_values


debug = 2

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

MIDI_KEY_CHANNEL = 1
MIDI_PAD_CHANNEL = 10
### Wire protocol values
MIDI_KEY_CHANNEL_WIRE = MIDI_KEY_CHANNEL - 1
MIDI_PAD_CHANNEL_WIRE = MIDI_PAD_CHANNEL - 1
SAMPLE_RATE = 64_000
MIXER_BUFFER_SIZE = 2048  ### TODO - how to choose this value?
WAVEFORM_PEAK = 28_000
WAVEFORM_MAX = 2**15 - 1
WAVEFORM_LEN = 8
WAVEFORM_HALFLEN = WAVEFORM_LEN // 2

PRODUCT = synthio.MathOperation.PRODUCT
SUM = synthio.MathOperation.SUM

midi_usb  = adafruit_midi.MIDI(midi_in=usb_midi.ports[0],
                               in_channel=(MIDI_KEY_CHANNEL_WIRE,
                                           MIDI_PAD_CHANNEL_WIRE))
audio = audiopwmio.PWMAudioOut(LEFT_AUDIO_PIN,
                               right_channel=RIGHT_AUDIO_PIN)
mixer = audiomixer.Mixer(channel_count=1,
                         sample_rate=SAMPLE_RATE,
                         buffer_size=MIXER_BUFFER_SIZE)
synth = synthio.Synthesizer(channel_count=1,
                            sample_rate=SAMPLE_RATE)

audio.play(mixer)
mixer.voice[0].play(synth)
mixer.voice[0].level = 0.75


def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


patches = (("One osc",),   ### 0
           ("Two osc",),   ### 1
           ("Three osc",), ### 2
           ("Three osc ADSR",),      ### 3
           ("Three osc ADSR LPF",),  ### 4
           ("Three osc ADSR LPF velocity ",),  ### 5
           ("Three osc ADSR LPF velocity pitch-bend vibrato",),  ### 6
           ("Three osc ADSR LPF velocity pitch-bend aftertouch-vibrato",),  ### 7
           ("Three osc ADSR LPF velocity pitch-bend aftertouch-vibrato pitch-slides"))  ### 8

note_to_button = {36: 1, 38: 2, 42: 3, 46: 4,
                  50: 5, 45: 6, 51: 7, 49: 8}

## oscs_per_note = 3      # how many oscillators for each note
oscs_per_note = 2      # TODO - clean this all up for 2 osc
osc_detune = 0.001     # how much to detune oscillators for phatness
filter_freq_lo = 100   # filter lowest freq
filter_freq_hi = 4500  # filter highest freq
filter_note_offset_low = -12
filter_note_offset_high = 60 + 1
filter_res_lo = 0.1    # filter q lowest value
filter_res_hi = 2.0    # filter q highest value
vibrato_note_lfo_hi = 0.5/12   # vibrato amount when modwheel is maxxed out
vibrato_note_rate = 5       # vibrato frequency

amp_env_attack_time_lo = 0.080
amp_env_attack_time_hi = 2.000
amp_env_attack_level_lo = 0.85
amp_env_attack_level_hi = 1.0

waveform_saw    = np.linspace(WAVEFORM_PEAK, 0 - WAVEFORM_PEAK, num=WAVEFORM_LEN,
                              dtype=np.int16)

lfo_note_vibrato = synthio.LFO(rate=vibrato_note_rate, scale=vibrato_note_lfo_hi)
lfo_slowstart_note_vibrato = synthio.LFO(waveform=np.array([0, 0, 4096, 8192, 16384, 24576, 32767],
                                                           dtype=np.int16),
                                         interpolate=True, once=True, rate=1/1)
lfo_pitch_slide = synthio.LFO(waveform=np.array([0, 32767], dtype=np.int16),
                              interpolate=True, once=True, scale=0, rate=0)

### The value is set in property "a"
pitch_bend_control_math = synthio.Math(SUM, 0.0, 0.0, 0.0)
aftertouch_math = synthio.Math(SUM, 0.0, 0.0, 0.0)
modwheel_math = synthio.Math(SUM, 0.0, 0.0, 0.0)

pressed = []  ### pressed keys
oscs = []     ### holds currently sounding oscillators
filter_freq = 2000  # current setting of filter
filter_note_offset = 37
filter_res = 1.0    # current setting of filter
amp_env_attack_time = 0.300

amp_env_decay_time = 0.100
amp_env_sustain = 0.8
amp_env_release_time = 1.100
last_note = None
last_portamento_note = None
osc_note = None
osc_target_note = None
current_patch = 0


### Simple range mapper, like Arduino map()
def map_range(s, a1, a2, b1, b2):
    return  b1 + ((s - a1) * (b2 - b1) / (a2 - a1))


### pylint: disable=consider-using-in,too-many-branches
def note_on(notenum, vel, patch_no):

    new_osc = []
    level = 0.65 if patch_no >=3 else 0.50
    f1 = synthio.midi_to_hz(notenum
                            + random.uniform(-0.003, 0.003))
    new_osc.append(synthio.Note(frequency=f1,
                                waveform=waveform_saw,
                                amplitude=level))
    if patch_no >= 1:
        ### Detune of 0.03 (3 cents)
        f2 = synthio.midi_to_hz(notenum
                                + random.uniform(-0.003, 0.003)
                                + random.uniform(0.034, 0.036))
        new_osc.append(synthio.Note(frequency=f2,
                                    waveform=waveform_saw,
                                    amplitude=level * 0.9))

    if patch_no >= 2:
        ### Detune of -0.045 (-4.5 cents)
        f3 = synthio.midi_to_hz(notenum
                                + random.uniform(-0.003, 0.003)
                                + random.uniform(-0.044, -0.046))
        new_osc.append(synthio.Note(frequency=f3,
                                    waveform=waveform_saw,
                                    amplitude=level * 0.9))

    amp_env = None
    if patch_no == 3 or patch_no == 4:
        amp_env = synthio.Envelope(attack_time=amp_env_attack_time,
                                   decay_time=amp_env_decay_time,
                                   sustain_level=amp_env_sustain,
                                   release_time=amp_env_release_time)
    elif patch_no >= 5:
        amp_level = map_range(vel,
                              0, 127,
                              amp_env_attack_level_lo, amp_env_attack_level_hi)
        attack_time = map_range(math.sqrt(vel),
                                0, math.sqrt(127),
                                amp_env_attack_time_hi, amp_env_attack_time_lo)
        amp_env = synthio.Envelope(attack_time=attack_time,
                                   attack_level=amp_level,
                                   decay_time=amp_env_decay_time,
                                   sustain_level=amp_level*amp_env_sustain,
                                   release_time=amp_env_release_time)
    if amp_env:
        for osc in new_osc:
            osc.envelope = amp_env

    if patch_no >= 4:
        lpf = synth.low_pass_filter(synthio.midi_to_hz(notenum + filter_note_offset), filter_res)
        for osc in new_osc:
            osc.filter = lpf

    pitch_bend = None
    if patch_no == 5:
        ### Key-triggered vibrato with delay
        pitch_bend = synthio.Math(PRODUCT,
                                  lfo_slowstart_note_vibrato,
                                  lfo_note_vibrato)
    elif patch_no == 6:
        ### Vibrato via mod wheel and after touch with pitch bend
        pitch_bend = synthio.Math(SUM,
                                  synthio.Math(PRODUCT,
                                               lfo_slowstart_note_vibrato,
                                               modwheel_math,
                                               lfo_note_vibrato),
                                  pitch_bend_control_math,
                                  0.0)
    elif patch_no >= 7:
        ### Vibrato via mod wheel and after touch with pitch bend
        ### and pitch slide using Axiom pad buttons
        pitch_bend = synthio.Math(SUM,
                                  synthio.Math(PRODUCT,
                                               synthio.Math(SUM,
                                                            synthio.Math(PRODUCT,
                                                                         aftertouch_math,
                                                                         0.8),
                                                            modwheel_math,
                                                            0.0),
                                               lfo_note_vibrato),
                                  pitch_bend_control_math,
                                  lfo_pitch_slide if patch_no >= 8 else 0.0)
    if pitch_bend:
        for osc in new_osc:
            osc.bend = pitch_bend

    oscs.clear()
    pressed.clear()
    lfo_slowstart_note_vibrato.retrigger()

    ### Add oscillattors to list and presss the 'note' (a collection
    ### of oscs acting in concert)
    oscs.extend(new_osc)
    synth.press(oscs)
    pressed.append(notenum)


def notes_off():

    synth.release(oscs)
    oscs.clear()
    pressed.clear()


start_ns = time.monotonic_ns()
while True:
    msg = midi_usb.receive()

    if msg:
        if isinstance(msg, ProgramChange):
            d_print(2, "PC: ", msg.patch)
            if 0 <= msg.patch < len(patches):
                current_patch = msg.patch

        elif msg.channel == MIDI_KEY_CHANNEL_WIRE and isinstance(msg, NoteOn) and msg.velocity != 0:
            d_print(2, "Note:", msg.note, "vel={:d}".format(msg.velocity))
            if last_note is not None:
                notes_off()
            note_on(msg.note, msg.velocity, current_patch)
            last_note = msg.note

        elif msg.channel == MIDI_KEY_CHANNEL_WIRE and (isinstance(msg, NoteOff)
                                                       or isinstance(msg, NoteOn)
                                                       and msg.velocity == 0):
            d_print(2, "Note:", msg.note, "vel={:d}".format(msg.velocity))
            if msg.note in pressed:  # only release note that's sounding
                notes_off()

        elif isinstance(msg, ControlChange):
            d_print(2, "CC:", msg.control, "=", msg.value)
            if msg.control == control_change_values.MOD_WHEEL:  ### 1 mod wheel
                modwheel_math.a = msg.value / 127.0
            elif msg.control == control_change_values.CUTOFF_FREQUENCY:  ### 74
                ##filter_freq = map_range( msg.value, 0,127, filter_freq_lo, filter_freq_hi)
                filter_note_offset = map_range(msg.value,
                                               0, 127,
                                               filter_note_offset_low, filter_note_offset_high)
            elif msg.control == control_change_values.FILTER_RESONANCE:  ### 71
                filter_res = map_range(msg.value, 0, 127, filter_res_lo, filter_res_hi)
            elif msg.control == control_change_values.RELEASE_TIME: ### 72
                amp_env_release_time = map_range(msg.value, 0, 127, 0.05, 3)

        elif isinstance(msg, PitchBend):
            d_print(2, "PB:", msg.pitch_bend)
            pitch_bend_control_math.a = (msg.pitch_bend - 8192) / 8192

        elif isinstance(msg, ChannelPressure):
            d_print(2, "AT:", msg.pressure)
            aftertouch_math.a = msg.pressure / 127.0

        elif msg.channel == MIDI_PAD_CHANNEL_WIRE:
            if isinstance(msg, NoteOn) and msg.velocity != 0:
                button_pad = note_to_button.get(msg.note)
                if button_pad is not None:
                    lfo_pitch_slide.scale = -8 if button_pad <= 4 else 8
                    lfo_pitch_slide.rate = 0.0625 / ((button_pad - 1) % 4 + 1)
                    lfo_pitch_slide.retrigger()
            elif isinstance(msg, NoteOff) or isinstance(msg, NoteOn) and msg.velocity == 0:
                lfo_pitch_slide.scale = 0.0
                lfo_pitch_slide.rate = 0.0

        else:
            d_print(1, "MIDI MSG:", msg)
