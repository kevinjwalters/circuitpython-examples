### midi-to-cv v1.0
### MIDI to control voltage conversion using the MCP4728 Quad DAC

### Tested on Cytron Maker Nano 2040 with Adafruit MCP4728 boards via ISO1540 isolator board
### with CircuitPython 10.2.1

### copy this file to Cytron Maker Nano 2040 as code.py

### MIT License

### Copyright (c) 2026 Kevin J. Walters

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

### SPDX-FileCopyrightText: 2026 Kevin J. Walters

### See https://www.instructables.com/Microrack-Modular-Synthesizer/
### for articles on the Microrack Modular Synth


import time


import analogio
import audiomixer
import audiopwmio
import board
import busio
from rainbowio import colorwheel
import synthio
import usb_midi

import neopixel
import adafruit_mcp4728
import adafruit_midi
from adafruit_midi.channel_pressure import ChannelPressure
from adafruit_midi.control_change import ControlChange
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff
from adafruit_midi.pitch_bend import PitchBend

from adafruit_midi import control_change_values


##BASE_NOTE = 36  ### C2
BASE_NOTE = 35  ### B1
MIDI_CHANNEL_IN = 1
OUTPUT_TYPES = "CV,ENV CV,ENV"  ### duophonic
DAC_SUPPLY = 4.88
PITCHBEND_RANGE = 2  ### semi-tones


### could try 800k or 1M
### isolator is 1M, DAC is 3.4M
I2C_FREQUENCY = 400_000
MICROCONTROLLER_SUPPLY = 3.3
OUTPUT_DEVICES = "I2C_ISOL_DAC:GP0,GP1"
PIXEL_PIN = board.RGB
PIXEL_COUNT = 2

### Cytron Maker Nano 2040 Maker Port 0 and 1
DEFAULT_PINS = [("GP0", "GP1"), ("GP26", "GP27")]

MAX_CC_V = 5.0

#OUTPUT_TYPES = "CV,ENV CV,ENV"  ### TODO update() is buggy
#OUTPUT_TYPES = "CV,GATE CV,VELOCITY"  ### TODO update() is buggy

#OUTPUT_TYPE = "CV,VGATE CV,VGATE"
#OUTPUT_TYPE = "CV,GATE,VEL,LFO CV,VGATE,LFO,LFO LFO 5LFO MOD CC74"
##OUTPUT_TYPES = "CV,GATE,VELOCITY,PRESSURE"
##OUTPUT_TYPES = "CV,GATE,VEL CLOCK:24 CLOCK:12 CLOCK"
### OUTPUT = "I2CISOLDAC:GP0,GP1 I2CISOLDAC:GP27,GP28,VREF=2.048 INTDAC:A0 INTDAC:A0,A1"

MIDI_NOTE_C4 = 60
BLACK = (0, 0, 0)
OUTPUT_NAMES = ("CV", "GATE", "ENV", "VELOCITY")


def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


### https://stackoverflow.com/questions/66388336/python-property-setter-only
def setterOnly(f):
    return property(None, f)


class MegaDAC:
    def __init__(self, dac_min, dac_max):
        self._setMinMax(dac_min, dac_max)

    def _setMinMax(self, dac_min, dac_max):
        self.dac_min = dac_min
        self.dac_max = dac_max
        self.dac_range = self.dac_max - self.dac_min
        self._scale_norm = 65535.9
        self._scale = self._scale_norm / self.dac_range

    def set(self, name, value):  ### pylint: disable=no-self-use,unused-argument
        """A request to set a parameter, returns False if not supported."""
        return False

    @setterOnly
    def voltage(self, value):
        """Set a value between minimum and maximum voltage."""
        value_16u = int((value - self.dac_min) * self._scale)
        if not 0 <= value_16u <= 65535:
            raise ValueError("out of DAC range")
        self.value = value_16u

    @setterOnly
    def normal(self, value):
        """Set a normalised value between 0.0 and 1.0."""
        value_16u = int((value - self.dac_min) * self._scale_norm)
        if not 0 <= value_16u <= 65535:
            raise ValueError("out of DAC range")
        self.value = value_16u

    @setterOnly
    def logic(self, value):
        """Set a boolean (evaluated) value."""
        self.value = 65535 if value else 0


class DAC_MCP4728_channel(MegaDAC):
    def __init__(self, mcp, channel_name, set_args):
        self._mcp = mcp
        self._mcp_channel = getattr(mcp, channel_name)
        super().__init__(0.0, MICROCONTROLLER_SUPPLY)

        for arg in set_args:
            self.set(*arg)

        self._channel_name = channel_name
        self.value = 0  ### set output to 0


    def set(self, name, value):
        max_v = None
        if name == "vref_mv" and value in (2048, 4096):
            self._mcp_channel.vref = adafruit_mcp4728.Vref.INTERNAL
            self._mcp_channel.gain = value // 2048   ### gain is 1 or 2
            max_v = value / 1000.0
        elif name == "max":
            self._mcp_channel.vref = adafruit_mcp4728.Vref.VDD
            max_v = value
        if max_v is not None:
            self._setMinMax(0.0, max_v)
            return True
        return False


    @property
    def value(self):
        return self._mcp_channel.value

    @value.setter
    def value(self, value):
        ##print("SET", self._channel_name, value)
        self._mcp_channel.value = value


class DAC_Analogio(MegaDAC):
    def __init__(self, pin_name):
        self._analogio_obj = analogio.AnalogOut(getattr(board, pin_name))
        super().__init__(0.0, self._analogio_obj.vref)

    @setterOnly
    def value(self, value):
        self._analogio_obj.value = value


if PIXEL_COUNT:
    pixels = neopixel.NeoPixel(PIXEL_PIN, PIXEL_COUNT, brightness=1.0)
    pixels.fill(BLACK)
else:
    pixels = None


dac_channel_count = 0
### Elements are dac_object
dacs = []
pin_idx = 0
for output in OUTPUT_DEVICES.split():
    fields = output.split(":")
    if len(fields) >= 2:
        pin_names = fields[1].split(",")
    else:
        pin_names = DEFAULT_PINS[pin_idx]
        pin_idx += 1

    new_dacs = []
    if fields[0] in ("I2C_ISOL_DAC", "I2C_DAC"):
        i2c = busio.I2C(scl=getattr(board, pin_names[1]),
                        sda=getattr(board, pin_names[0]),
                        frequency=I2C_FREQUENCY)
        try:
            mcp_dac = adafruit_mcp4728.MCP4728(i2c)
        except ValueError as ex:
            print(repr(ex))
            print("Is DAC powered on?")

        ### Look for the four channels
        chan_names = [s for s in dir(mcp_dac) if s.startswith("channel_")]
        set_arg = ("max", DAC_SUPPLY if fields[0] == "I2C_ISOL_DAC" else MICROCONTROLLER_SUPPLY)
        new_dacs = [DAC_MCP4728_channel(mcp_dac, cn,
                                        [set_arg]) for cn in chan_names]
        dac_channel_count += 4
    elif fields[0] == "INT_DAC":
        ### DACs: 10bit on SAMD21, 12bit on SAMD51
        new_dacs = [DAC_Analogio(pin_names[0])]
    dacs.extend(new_dacs)


class Voice:

    INACTIVE = 0x0
    ATTACK = 0x01
    DECAY = 0x02
    SUSTAIN = 0x03
    RELEASE = 0x04


    def __init__(self, names, dac_list, idx, *,
                 base_note_num=BASE_NOTE,
                 volts_per_octave=1.0,
                 synth=None):

        self.phase = Voice.INACTIVE
        self.note_num = None
        self.voice_idx = idx
        self._base_note_num = base_note_num
        self._volts_per_semitone = volts_per_octave / 12.0
        self._synth = synth

        self._note_obj = None
        self._cv_dac = None
        self._gate_dac = None
        self._velocity_dac = None
        self._env_dac = None

        dacs_iter = iter(dac_list)
        try:
            for name in names:
                if name == "CV":
                    self._cv_dac = next(dacs_iter)
                    self._cv_dac.set("vref_mv", 4096)  ### request precision internal reference
                elif name == "GATE":
                    self._gate_dac = next(dacs_iter)
                elif name == "VELOCITY":
                    self._velocity_dac = next(dacs_iter)
                elif name == "ENV":
                    self._env_dac = next(dacs_iter)
        except StopIteration:
            print("Not enough dacs:", names, "for", dac_list)

        self.ts_ns = 0   ### when this is 0 the voice is not in use
        self._cv_note_v = 0.0
        self._last_pb = 0.0
        self._last_release_time = 0.0

    def on(self, note_num, velocity, pb, env_vals):
        if self._cv_dac is not None:
            self._cv_note_v = (note_num - self._base_note_num) * self._volts_per_semitone
            pb_v = pb * self._volts_per_semitone
            try:
                self._cv_dac.voltage = self._cv_note_v + pb_v
            except ValueError:
                return False
            self._last_pb = pb

        self.note_num = note_num
        self.ts_ns = time.monotonic_ns()

        if self._velocity_dac is not None:
            volts = map_midi7b_range(velocity, 0.0, 1.0)
            self._velocity_dac.normal = volts

        if self._gate_dac is not None:
            self._gate_dac.logic = True

        if self._env_dac is not None:
            env = synthio.Envelope(attack_time=env_vals[0],
                                   decay_time=env_vals[1],
                                   sustain_level=env_vals[2],
                                   release_time=env_vals[3])
            self._last_release_time = env_vals[3]
            ### 4Hz can be seen as pulsing on GPIO LEDs
            note = synthio.Note(frequency=4,
                                envelope=env,
                                panning=left_right_mapping[self.voice_idx])
            self._note_obj = note
            self._synth.press(self._note_obj)
            _, amplitude = self._synth.note_info(self._note_obj)
            self._env_dac.normal = amplitude
        else:
            self.phase = Voice.SUSTAIN

        return True

    def off(self, note_num, *,
            hard=False):
        if not hard and (note_num != self.note_num or self.ts_ns == 0):
            return False

        ### Leave CV where it was?
        #if self._cv_dac is not None:
        #    self._cv_dac.value = 0.0

        if self._velocity_dac is not None:
            self._velocity_dac.logic = False

        if self._gate_dac is not None:
            self._gate_dac.logic = False

        ### If there's no envelope then we're done, otherwise
        ### need to produce the envelope's release phase
        if self._env_dac is None:
            self.ts_ns = 0
            self.phase = Voice.INACTIVE
        else:
            if hard:
                self.ts_ns = 0
                self._env_dac.logic = False
                self._updateReleaseTime(0.0)
                self._synth.release(self._note_obj)
                self._note_obj = None
                self.phase = Voice.INACTIVE
            else:
                ### go into the release phase of envelope
                self._synth.release(self._note_obj)
                self.phase = Voice.RELEASE

        return True

    def update(self, pb, release_time):
        updated = False
        if self.ts_ns == 0:
            return updated

        if self._env_dac is None and pb == 0.0:
            return updated

        ### Change control voltage for any new pitch bend values
        if pb != self._last_pb and self._cv_dac is not None:
            pb_v = pb * self._volts_per_semitone
            try:
                self._cv_dac.voltage = self._cv_note_v + pb_v
                updated = True
            except ValueError:
                pass
            self._last_pb = pb

        if self._env_dac is not None:
            if release_time != self._last_release_time:
                ### Need to clone envelope to change the release time
                ### https://github.com/adafruit/circuitpython/issues/10902
                self._updateReleaseTime(release_time)
                self._last_release_time = release_time

            ### Update envelope output if in use
            if self._note_obj:
                state, amplitude = self._synth.note_info(self._note_obj)
                self._env_dac.normal = amplitude
                updated = True
                ### Check if release has completed
                if state is None:
                    self.ts_ns = 0
                    self._note_obj = None
                    self.phase = Voice.INACTIVE
        return updated

    def _updateReleaseTime(self, new_time):
        if self._note_obj:
            old_env = self._note_obj.envelope
            new_amp_env = synthio.Envelope(attack_time=old_env.attack_time,
                                           decay_time=old_env.decay_time,
                                           release_time=new_time,
                                           attack_level=old_env.attack_level,
                                           sustain_level=old_env.sustain_level)
            self._note_obj.envelope = new_amp_env


### The frequency / 256 is the update rate of calculated "blocks" like
### envelope and LFO - 32k is an update every 0.8ms
SAMPLE_RATE=32_000

### Annoyingly, Synthesizer doesn't work without it being
### attached to an audio output
dummy_audio = audiopwmio.PWMAudioOut(board.GP18, right_channel=board.GP19)
mixer = audiomixer.Mixer(sample_rate=SAMPLE_RATE, channel_count=2)
silent_synth = synthio.Synthesizer(sample_rate=SAMPLE_RATE, channel_count=2)
dummy_audio.play(mixer)
mixer.voice[0].play(silent_synth)


v_idx = 0
voices = []
lfos = []
dac_iter = iter(dacs)
for output in OUTPUT_TYPES.split():
    osc = [None, None, None, None]
    fields = output.split(",")

    if not all([f in OUTPUT_NAMES for f in fields]):  ### pylint: disable=use-a-generator
        print("Bad output:", output)
        continue

    if "CV" in fields:
        voices.append(Voice(fields,
                            [next(dac_iter) for _ in range(len(fields))],
                            v_idx,
                            synth=silent_synth))
        v_idx +=1

    if fields[0] == "MOD":
        pass ### TODO

    if fields[0] == "LFO":
        pass ### TODO
del dac_iter


### This is used to pan full left (-1) or full right (1) as GPIO LEDs
### happen to be next to the RGB pixels on Cytron Maker Nano 2040
### Low frequency Notes can make the LEDs for the (unused) PWM outputs
### pulse
left_right_mapping = tuple(-1 if vi % 2 == 0 else 1 for vi in range(len(voices)))


def select_voice(midi_note):
    """Find a free voice, if all in use steal the oldest."""
    free_idx = None
    oldest_idx = None
    oldest_released_idx = None
    activenotematch_idx = None
    oldest_t_ns = oldest_released_t_ns = time.monotonic_ns()

    for voice_idx, voice in enumerate(voices):
        t_on_ns = voice.ts_ns
        if free_idx is None and t_on_ns == 0:
            free_idx = voice_idx
        if t_on_ns < oldest_t_ns:
            oldest_idx = voice_idx
            oldest_t_ns = t_on_ns
        if voice.phase == Voice.RELEASE and t_on_ns < oldest_released_t_ns:
            oldest_released_idx = voice_idx
            oldest_released_t_ns = t_on_ns
        if t_on_ns != 0 and midi_note == voice.note_num:
            activenotematch_idx = voice_idx

    if activenotematch_idx is not None:
        selected_voice = voices[activenotematch_idx]
    elif free_idx is not None:
        return voices[free_idx]
    elif oldest_released_idx is not None:
        selected_voice = voices[oldest_released_idx]
    else:
        selected_voice = voices[oldest_idx]

    selected_voice.off(selected_voice.note_num, hard=True)
    return selected_voice


### Indicate the note C to B as a colour and velocity as brightness
### Does not show pitch bend
def noteled(pxls, voice_idx, note, velocity):
    if pxls is None:
        return

    if velocity == 0:
        colour = BLACK
    else:
        ### Map semitones to 0-255
        octave_st = (note - MIDI_NOTE_C4) % 12
        hue = colorwheel(octave_st * 21.25)
        r = (hue & 0xff0000) >> 16
        g = (hue & 0x00ff00) >> 8
        b = hue & 0x0000ff

        ### scale 0-255 to 0.0 to 40.0 based on velocity of 0 to 127 (40/127/255)
        scale = velocity * .001235140
        colour = (round(r * scale) + 10, round(g * scale) + 10, round(b * scale) + 10)

    pxls[voice_idx % len(pxls)] = colour


midi = adafruit_midi.MIDI(in_channel=MIDI_CHANNEL_IN - 1,
                          midi_in=usb_midi.ports[0])
debug = 1


### Simple (full 7bit) MIDI range mapper
def map_midi7b_range(s, b1, b2):
    return b1 + (s * (b2 - b1) / 127.0)


pitchbend_multiplier = PITCHBEND_RANGE / 8192.0
pitchbend_midpoint = 8192
pitch_bend = 0.0  ### semi-tones

aftertouch = aftertouch_old = 0

SV_CURRENT = 0
SV_NEW = 1
SV_LOW = 2
SV_HIGH = 3
synth_vars = {
    "amp_env_attack_time":   [0.5, 0.5, 0.0, 2.0],
    "amp_env_decay_time":    [0.5, 0.5, 0.0, 2.0],
    "amp_env_sustain_value": [0.8, 0.8, 0.0, 1.0],
    "amp_env_release_time":  [0.250, 0.250, 0.0, 4.0],

    "portamento_time": [0.0, 0.0, 0.0, 1.0],
    "portamento":      [0.0, 0.0, 0.0, 1.0],

    "mod":              [0.0, 0.0, 0.0, MAX_CC_V],
    "filter_cutoff":    [0.0, 0.0, 0.0, MAX_CC_V],
    "filter_resonance": [0.0, 0.0, 0.0, MAX_CC_V]
}


while True:
    sv_name = None
    msg = midi.receive()
    if isinstance(msg, NoteOn) and msg.velocity != 0:
        d_print(2, "NoteOn", msg.note, msg.velocity)

        free_voice = select_voice(msg.note)
        if free_voice.on(msg.note, msg.velocity, pitch_bend,
                         (synth_vars["amp_env_attack_time"][SV_CURRENT],
                          synth_vars["amp_env_decay_time"][SV_CURRENT],
                          synth_vars["amp_env_sustain_value"][SV_CURRENT],
                          synth_vars["amp_env_release_time"][SV_CURRENT]
                         )):
            noteled(pixels, free_voice.voice_idx, msg.note, msg.velocity)

    elif (isinstance(msg, NoteOff) or
          isinstance(msg, NoteOn) and msg.velocity == 0):
        d_print(2, "NoteOff", msg.note, msg.velocity)

        for vo in voices:
            if msg.note == vo.note_num:
                vo.off(msg.note)
                noteled(pixels, vo.voice_idx, msg.note, 0)

    elif isinstance(msg, PitchBend):
        ### 14bit unsigned value, 0 to 16383
        pitch_bend = (msg.pitch_bend - pitchbend_midpoint) * pitchbend_multiplier

    elif isinstance(msg, ControlChange):
        d_print(2, "CC", msg.control, "=", msg.value)

        if msg.control == control_change_values.MOD_WHEEL:           ### cc1
            sv_name = "mod"
        elif msg.control == control_change_values.CUTOFF_FREQUENCY:  ### cc74
            sv_name = "filter_cutoff"
        elif msg.control == control_change_values.FILTER_RESONANCE:  ### cc71
            sv_name = "filter_resonance"
        elif msg.control == control_change_values.ATTACK_TIME:       ### cc73
            ### This is only applied to new Notes
            sv_name = "amp_env_attack_time"
        elif msg.control == control_change_values.RELEASE_TIME:      ### cc72
            sv_name = "amp_env_release_time"
        elif msg.control == control_change_values.PORTAMENTO_TIME:   ### cc5
            sv_name = "portamento_time"
        elif msg.control == control_change_values.PORTAMENTO:        ### cc65
            sv_name = "portamento"

        if sv_name is not None:
            sv = synth_vars[sv_name]
            sv[SV_NEW] = map_midi7b_range(msg.value,
                                          sv[SV_LOW],
                                          sv[SV_HIGH])
            sv[SV_CURRENT] = sv[SV_NEW]

    elif isinstance(msg, ChannelPressure):
        d_print(2, "AT:", msg.pressure)
        aftertouch_old = aftertouch
        aftertouch = msg.pressure

    elif msg is not None:
        if debug:
            d_print(3, "Something else:", msg)

    ### This will update any envelopes or pitch bended notes and
    ### also clean-up any voices/notes that have completed their release phase
    for vo in voices:
        vo.update(pitch_bend, synth_vars["amp_env_release_time"][SV_CURRENT])
