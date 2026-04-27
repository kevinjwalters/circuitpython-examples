### hid-keys-visual-and-sound-effects v1.0
### Pimoroni Keybow 2040 HID/MIDI/CCC keyboard with visual effects and PWM audio effects

### Tested on Keybow 2040 with 10.1.4

### copy this file to Keybow 2040 as code.py

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

### TODO - test with hibernated laptop


import math
import time
import ulab.numpy as np

import board
import digitalio
import microcontroller
import usb_hid
import usb_midi
from audiocore import WaveFile
from audiomixer import Mixer
from audiopwmio import PWMAudioOut as AudioOut

from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.consumer_control import ConsumerControl

import adafruit_midi
from adafruit_midi.note_off import NoteOff
from adafruit_midi.note_on import NoteOn

from pmk import PMK
from pmk.platform.keybow2040 import Keybow2040 as Hardware

### For temporary i2c speed hack
import busio
from adafruit_bus_device.i2c_device import I2CDevice

from config_types import CCC, MIDI
import keybow_config as config
from keybow_font import FONT


### Going from 125MHz to 200MHz
microcontroller.cpu.frequency = 200_000_000

### Set up Keybow 2040
hardware = Hardware()
keybow = PMK(hardware)

### Temporary i2c speed hack
### The Lumissil IS31FL3731 is good for 400k
### TODO - ticket a change to board.I2C() OR the pmk library - latter may make more sense as
### adding external 100k i2c would require a drop
I2C_ADDR = 0x74
hardware._i2c.deinit()
hardware._i2c = busio.I2C(scl=board.SCL, sda=board.SDA, frequency=400_000)
hardware._display._pixels.i2c_device = I2CDevice(hardware._i2c, I2C_ADDR)
### 16 led set
### 400k: 70.0, 71.1, 79.0
### 100k: 92.3, 93.9, 101.0

keys = keybow.keys
K_WIDTH = 4
K_HEIGHT = 4
K_COUNT = K_WIDTH * K_HEIGHT

keybow_button_r_din = digitalio.DigitalInOut(board.USER_SW)
keybow_button_r = lambda: not keybow_button_r_din.value

try:
    SHORT_PRESS_NS = round(config.SHORT_PRESS * 1e9)
except AttributeError:
    SHORT_PRESS_NS = 800_000_000


try:
    STARTUP_MESSAGE = config.STARTUP_MESSAGE
except AttributeError:
    STARTUP_MESSAGE = None

### Keybow 2040 layout
###
###  3  7 10  15
###  2  6 10  14
###  1  5  9  13
###  0  4  8  12

### pylint: disable=consider-using-generator
K_TO_P2 = tuple([(k // K_WIDTH, K_HEIGHT - k % K_WIDTH - 1) for k in range(K_COUNT)])
K_TO_P_RF = tuple([(k // K_WIDTH + (K_HEIGHT - k % K_WIDTH - 1) * K_WIDTH) for k in range(K_COUNT)])
P2_TO_K = tuple([tuple([x + y * K_WIDTH for x in range(K_WIDTH - 1, 0 - 1, -1)]) for y in range(K_HEIGHT)])
### map from flattened ulab arrays to keybow key indices
P_TO_K_CF = tuple([x + y * K_WIDTH for y in range(K_HEIGHT) for x in range(K_WIDTH - 1, 0 - 1, -1)])
P_TO_K_RF = tuple([x + y * K_WIDTH for x in range(K_WIDTH - 1, 0 - 1, -1) for y in range(K_HEIGHT)])


wav_cache = {}
def wav_it(fname):
    wav_obj = wav_cache.get(fname)
    if wav_obj is None:
        try:
            wav_obj = WaveFile(open(fname, "rb"))
        except OSError:
            pass   ### probably file not found
        wav_cache[fname] = wav_obj
    return wav_obj


def get_audio_layers(l_filenames):
    a_layers = []
    for avar in [lvar.replace("layer", "audio") for lvar in l_filenames]:
        try:
            a_l = tuple([wav_it(x) if isinstance(x, str) else tuple([wav_it(x[0])] + list(x[1:]))  for x in getattr(config, avar)])
        except AttributeError:
            a_l = None
        a_layers.append(a_l)
    return a_layers


### Extract the layers from configuration
layer_fnames = sorted([x for x in dir(config) if x.startswith("layer")])
layers = tuple([getattr(config, var) for var in layer_fnames])
audio_layers = get_audio_layers(layer_fnames)

keymap = layers[0]
audmap = audio_layers[0]
key_press_colour = config.LAYER_COLOURS[0]


### Set up the keyboard for sending Keycode
### and layout for sending strings
keyboard = Keyboard(usb_hid.devices)
layout = KeyboardLayoutUS(keyboard)
### Set up consumer control (used to send media key presses)
consumer_control = ConsumerControl(usb_hid.devices)

midi = adafruit_midi.MIDI(midi_out=usb_midi.ports[1],
                          out_channel=config.MIDI_CHANNEL - 1)


try:
    DEFAULT_VOLUME = config.DEFAULT_VOLUME
except AttributeError:
    DEFAULT_VOLUME = 1.0
try:
    MASTER_VOLUME = config.MASTER_VOLUME
except AttributeError:
    MASTER_VOLUME = 1.0

### STEMMA Speaker audio mixer setup
mixer = Mixer(sample_rate=32_000,
              channel_count=1)
audio_out = AudioOut(board.TX)
audio_out.play(mixer)  ### this makes a click sound
mixer.voice[0].level = 1.0


BLACK = (0, 0, 0)

effect_idx = 3
### (sound, visual)
EFFECTS = ((False, False),
           (False, True),
           (True, False),
           (True, True))  ### value at start-up

def next_effect_mode(e_idx=None):
    global effect_idx
    if e_idx is None:
        effect_idx = (effect_idx + 1) % len(EFFECTS)
    else:
        effect_idx = e_idx
    return EFFECTS[effect_idx]

sound_effect_on, visual_effect_on = next_effect_mode(effect_idx)


class KeybowAnimation:
    def __init__(self):
        self._start_ns = time.monotonic_ns()
        self._finished = False

    def draw(self, now_ns):  ### pylint: disable=unused-argument,no-self-use
        """Draws the animation onto keyb based on time now_ns.
           Returns time remaining to end, or 0 for ended or None for continuous (infinite).
        """
        return None


class ScrollTextAnim(KeybowAnimation):
    def __init__(self, text, colour,
                 *, transparency=255, speed=4, direction="l", pad=" "):
        super().__init__()
        self._text = text
        self._colour = colour
        self._transparency = transparency
        self._speed = speed
        self._direction = direction
        self._pad = pad
        self.layer = Layer(transparency=0)
        self._text_x = 0.0
        self._speed = speed
        self._bmp_width, self._bmp_height, self._bmp = self._make_bitmap(text, self._pad)

    @classmethod
    def _make_bitmap(cls, text, pad):
        display_text = pad + text.upper() + pad
        height = len(FONT[" "]) - 1
        bitmap = [0] * height
        width = 0
        last_idx = len(display_text) - 1
        for t_idx, char in enumerate(display_text):
            font_data = FONT[char]
            char_width = font_data[0]
            space = 1
            for iy in range(height):
                bitmap[iy] = (bitmap[iy] << (char_width + space)) + font_data[iy + 1]
            width += char_width + (space if t_idx != last_idx else 0)
        return (width, height, bitmap)

    def draw(self, now_ns):  ### pylint: disable=too-many-locals
        rel_ns = now_ns - self._start_ns

        new_x = rel_ns * self._speed * 1e-9
        new_frac_x, new_intx = math.modf(new_x)
        new_intx = int(new_intx)
        mask_shift = self._bmp_width - new_intx - 1
        if mask_shift < 0:
            return 0

        new_frac_x_sqrd = new_frac_x * new_frac_x
        col_r, col_g, col_b = self._colour
        start_mask = 1 << mask_shift
        for iy in range(0, self.layer.height):
            row = self._bmp[iy]
            mask = start_mask
            next_bit = row & mask
            for ix in range(0, self.layer.width):
                bit = int(bool(next_bit))
                mask >>= 1
                next_bit = int(bool(row & mask))
                ### Brightness vs distance and alpha may need tuning

                col_bri = min(1.0, bit * (1.1 - new_frac_x_sqrd) + next_bit * (new_frac_x_sqrd + 0.1))
                p_r = round(col_r * col_bri)
                p_g = round(col_g * col_bri)
                p_b = round(col_b * col_bri)
                p_a = round(255 * col_bri)  ### maybe this should be higher?
                self.layer.set_pixela(ix, iy, (p_r, p_g, p_b), p_a)

        return 9999  ### This is supposed to be the time remaining...


class LSCAnim(KeybowAnimation):
    def __init__(self, klayer_count, colours):
        super().__init__()
        self.layer = Layer()


        for p_idx in range(klayer_count):
            rgb = colours[p_idx % len(colours)]
            self.layer.set_pixel(p_idx % K_WIDTH, p_idx // K_WIDTH,
                                 rgb)


class EMAnim(KeybowAnimation):
    COLOURS = ((0, 87, 183),
               (255, 215, 0))

    def __init__(self, from_em_idx, to_em_idx):
        super().__init__()
        self.layer = Layer(transparency=0)
        self._from_em = tuple([int(b) for b in EFFECTS[from_em_idx]])
        self._to_em = tuple([int(b) for b in EFFECTS[to_em_idx]])
        self._duration_ns = 1_600_000_000
        self._half_y = self.layer.height // 2
        self._set_bands()
        self._set_alpha(self._from_em)


    def _yranges(self):
        return (range(0, self._half_y),
                range(self._half_y, self.layer.height))

    def _set_bands(self):
        ranges = self._yranges()
        for idx in range(len(ranges)):
            col = self.COLOURS[idx]
            for ly in ranges[idx]:
                for lx in range(0, self.layer.width):
                    self.layer.set_pixel(lx, ly, col)

    def _set_alpha(self, values):
        ranges = self._yranges()
        for idx in range(len(ranges)):
            alpha = round(values[idx] * 255)
            for ly in ranges[idx]:
                for lx in range(0, self.layer.width):
                    self.layer.set_alpha(lx, ly, alpha)

    def draw(self, now_ns):
        if self._finished:
            return 0

        self.layer.changed = True  ### lazy assumption
        rel_ns = now_ns - self._start_ns
        if rel_ns <= self._duration_ns:
            ratio = rel_ns / self._duration_ns
            inv_ratio = 1.0 - ratio
            alphas = [self._from_em[idx] * inv_ratio + self._to_em[idx] * ratio for idx in range(len(self._from_em))]
            self._set_alpha(alphas)
            return self._duration_ns - rel_ns
        else:
            self._finished = True
            return 1


class PulsingBoxAnim(KeybowAnimation):
    def __init__(self, x, y, colour):
        super().__init__()
        self._centre_x = x
        self._centre_y = y
        self._colour = colour
        self.layer = Layer(transparency=0)
        self._frame_ns = 100_000_000
        self._pulse_ns = 4 * self._frame_ns
        self._duration_ns = self._pulse_ns * 3
        self._anim_frame = 0


    def draw(self, now_ns):
        """Surrounding boxes of radius 0 (nothing), 1, 2, 3 over 0.4s repeated 3 times"""
        if self._finished:
            return 0

        rel_ns = now_ns - self._start_ns
        if rel_ns >= self._duration_ns:
            self.layer.clear_rgba()
            self.layer.changed = True
            self._finished = True
            return 1

        anim_idx = rel_ns // self._frame_ns
        pulse_idx = rel_ns // self._pulse_ns
        radius = rel_ns % self._pulse_ns // self._frame_ns

        if self._anim_frame != anim_idx:
            self._anim_frame = anim_idx
            self.layer.clear_rgba()
            if radius > 0:
                opaque = 255
                ### Dim brightness of colour for later pulses
                colour = [chan >> pulse_idx for chan in (self._colour)]
                l_w = self.layer.width
                l_h = self.layer.height
                ### top and bottom
                for ix in range(max(0, self._centre_x - radius),
                                min(l_w, self._centre_x + radius + 1)):
                    if self._centre_y - radius >= 0:
                        self.layer.set_pixela(ix, self._centre_y - radius, colour, opaque)
                    if self._centre_y + radius < l_h:
                        self.layer.set_pixela(ix, self._centre_y + radius, colour, opaque)
                ### sides
                for iy in range(max(0, self._centre_y - radius + 1),
                                min(l_h, self._centre_y + radius)):
                    if self._centre_x - radius >= 0:
                        self.layer.set_pixela(self._centre_x - radius, iy, colour, opaque)
                    if self._centre_x + radius < l_w:
                        self.layer.set_pixela(self._centre_x + radius, iy, colour, opaque)

                self.layer.changed = True

        return self._duration_ns - rel_ns


class OnOffAnim(KeybowAnimation):
    def __init__(self, x, y, colour):
        super().__init__()
        self._pos_x = x
        self._pos_y = y
        self._colour = colour
        self._on = True
        self.layer = Layer(draw_x=x, draw_y=y, colour=colour)

    def off(self):
        self._on = False
        self.layer.set_pixel(self._pos_x, self._pos_y, BLACK)

    def draw(self, now_ns):
        if self._finished:
            return 0
        ### If just turned off then let this render by returning None
        ### and indicate animation has finished for clean up on next draw/render
        if not self._on:
            self._finished = True

        return None


class Layer:
    def __init__(self, *,
                 draw_x=None, draw_y=None, draw_width=None, draw_height=None,
                 colour=None, transparency=None,
                 width=K_WIDTH, height=K_HEIGHT):
        pix_chan = np.full((width, height), 0,
                           dtype=np.uint8)
        self.width = width
        self.height = height
        self.pixel_r = np.array(pix_chan, dtype=pix_chan.dtype)
        self.pixel_g = np.array(pix_chan, dtype=pix_chan.dtype)
        self.pixel_b = np.array(pix_chan, dtype=pix_chan.dtype)
        self.alpha = np.array(pix_chan, dtype=pix_chan.dtype)

        transparency = 255 if transparency is None else transparency
        ### If a box is specified then use that region
        if draw_x is not None and draw_y is not None:
            p_width = 1 if draw_width is None else draw_width
            p_height = 1 if draw_height is None else draw_height

            x2 = draw_x + p_width
            y2 = draw_y + p_height
            self.alpha[draw_x:x2, draw_y:y2] = transparency
            if colour is not None:
                self.pixel_r[draw_x:x2, draw_y:y2] = colour[0]
                self.pixel_g[draw_x:x2, draw_y:y2] = colour[1]
                self.pixel_b[draw_x:x2, draw_y:y2] = colour[2]
        elif transparency > 0:
            ### Otherwise use whole layer
            self.alpha[:] = transparency
            if colour is not None:
                self.pixel_r[:] = colour[0]
                self.pixel_g[:] = colour[1]
                self.pixel_b[:] = colour[2]

        self.changed = colour is not None and transparency > 0

    def set_alpha(self, x, y, transparency):
        self.alpha[x, y] = transparency
        self.changed = True

    def set_pixel(self, x, y, colour):
        self.pixel_r[x, y] = colour[0]
        self.pixel_g[x, y] = colour[1]
        self.pixel_b[x, y] = colour[2]
        self.changed = True

    def set_pixela(self, x, y, colour, transparency):
        self.pixel_r[x, y] = colour[0]
        self.pixel_g[x, y] = colour[1]
        self.pixel_b[x, y] = colour[2]
        self.alpha[x, y] = transparency
        self.changed = True

    def clear_rgba(self):
        self.pixel_r[:] = 0   ### TODO - should I use off, or have a fill_pixels ?
        self.pixel_g[:] = 0
        self.pixel_b[:] = 0
        self.alpha[:] = 0
        self.changed = True


class KeybowLayerStack:
    def __init__(self, keyb, width=K_WIDTH, height=K_HEIGHT):
        self._keyb = keyb
        self._layers = []
        self._anims = []
        pix_chan = np.full((width, height), 0,
                           dtype=np.uint8)
        self.new_pixel_r = np.array(pix_chan, dtype=pix_chan.dtype)
        self.new_pixel_g = np.array(pix_chan, dtype=pix_chan.dtype)
        self.new_pixel_b = np.array(pix_chan, dtype=pix_chan.dtype)
        self.fb_pixel_r = np.array(pix_chan, dtype=pix_chan.dtype)
        self.fb_pixel_g = np.array(pix_chan, dtype=pix_chan.dtype)
        self.fb_pixel_b = np.array(pix_chan, dtype=pix_chan.dtype)
        self._stack_changed = False


    def add(self, anim, *, bottom=False):
        idx = 0 if bottom else len(self._anims)

        self._anims.insert(idx, anim)
        self._layers.insert(idx, anim.layer)
        #anim.layer.changed = True   ### do I need to change this? TODO
        self._stack_changed = True

    def remove(self, anim):
        idx = 0
        while idx < len(self._layers):
            if anim is self._anims[idx]:
                self._layers.pop(idx)
                self._anims.pop(idx)
                continue
            idx += 1
        self._stack_changed = True

    def _render_layer(self, l_r, l_g, l_b, l_a):
        for iy in range(self.new_pixel_r.shape[1]):
            for ix in range(self.new_pixel_r.shape[0]):
                a = l_a[ix, iy]
                if a > 0:
                    r = l_r[ix, iy]
                    g = l_g[ix, iy]
                    b = l_b[ix, iy]
                    if a == 255:
                        self.new_pixel_r[ix, iy] = r
                        self.new_pixel_g[ix, iy] = g
                        self.new_pixel_b[ix, iy] = b
                    else:
                        inv_a = 256 - a
                        self.new_pixel_r[ix, iy] = min(255, self.new_pixel_r[ix, iy] * inv_a + (r * (a + 1)) >> 9)
                        self.new_pixel_g[ix, iy] = min(255, self.new_pixel_g[ix, iy] * inv_a + (g * (a + 1)) >> 9)
                        self.new_pixel_b[ix, iy] = min(255, self.new_pixel_b[ix, iy] * inv_a + (b * (a + 1)) >> 9)

    def render(self):
        update_count = 0

        update_time_ns = time.monotonic_ns()
        ### First pass to look for completed animations
        ### and see if any layer has changed
        idx = 0
        while idx < len(self._layers):
            layer = self._layers[idx]
            time_left = self._anims[idx].draw(update_time_ns)
            ### Remove any completed animation with its layer
            if time_left == 0:
                self._layers.pop(idx)
                self._anims.pop(idx)
                self._stack_changed = True
                continue

            if layer.changed:
                update_count += 1
            idx += 1

        ### If there have been any updates then re-render layers
        if self._stack_changed or update_count > 0:
            self.new_pixel_r[:] = 0
            self.new_pixel_g[:] = 0
            self.new_pixel_b[:] = 0
            for idx, layer in enumerate(self._layers):
                self._render_layer(layer.pixel_r, layer.pixel_g, layer.pixel_b,
                                   layer.alpha)
                layer.changed = False

            ### Copy any pixels which have changed over to keybow
            ### set_led() can take 4.3ms which adds up when there are 16 of 'em
            set_time_ns = 0
            k_keys = self._keyb.keys
            lenx, leny = self.new_pixel_r.shape
            for iy in range(leny):
                for ix in range(lenx):
                    new_r = self.new_pixel_r[ix, iy]
                    new_g = self.new_pixel_g[ix, iy]
                    new_b = self.new_pixel_b[ix, iy]
                    if (self.fb_pixel_r[ix, iy] != new_r or
                        self.fb_pixel_g[ix, iy] != new_g or
                        self.fb_pixel_b[ix, iy] != new_b):
                        set_time_ns -= time.monotonic_ns()
                        k_keys[P2_TO_K[ix][iy]].set_led(new_r, new_g, new_b)
                        set_time_ns += time.monotonic_ns()
                        self.fb_pixel_r[ix, iy] = new_r
                        self.fb_pixel_g[ix, iy] = new_g
                        self.fb_pixel_b[ix, iy] = new_b

            self._stack_changed = False

        return update_count


def add_key_handlers():
    # Attach handler functions to all of the keys
    for key in keys:
        # A press handler that sends the keycode and turns on the LED
        @keybow.on_press(key)
        def press_handler(key):
            k_idx = key.number
            data = keymap[K_TO_P_RF[k_idx]]
            if data is not None:
                if isinstance(data, MIDI):
                    midi.send(NoteOn(int(data), config.MIDI_VELOCITY))
                elif isinstance(data, str):
                    layout.write(data)  ### TODO is this causing hard faults (on 10.1.4)?????
                elif isinstance(data, CCC):
                    consumer_control.send(int(data))
                else:
                    keyboard.send(data)

            ### Adulterate the key class with animation!
            kx, ky = K_TO_P2[k_idx]
            key.anim = OnOffAnim(kx, ky, key_press_colour)
            display_layers.add(key.anim)
            if visual_effect_on:
                key.anim_extra = PulsingBoxAnim(kx, ky, config.KEY_PRESS_EFFECT_COLOUR)
                display_layers.add(key.anim_extra, bottom=True)
            if sound_effect_on and audmap is not None:
                s_info = audmap[K_TO_P_RF[k_idx]]
                try:
                    wav_file = s_info[0]
                    volume = s_info[1]
                except TypeError:
                    wav_file = s_info
                    volume = DEFAULT_VOLUME

                mixer.voice[0].level = volume
                mixer.voice[0].play(wav_file)

        # A release handler that turns off the LED
        @keybow.on_release(key)
        def release_handler(key):
            k_idx = key.number
            data = keymap[K_TO_P_RF[k_idx]]
            if data is not None:
                if isinstance(data, MIDI):
                    midi.send(NoteOff(int(data)))

            try:
                key.anim.off()
            except AttributeError:  ### releases can happen before presses!
                pass

def clear_key_handlers():
    for key in keys:
        ### There's no clean way to clear these so add do nothing functions
        @keybow.on_press(key)
        def press_handler(key):  ### pylint: disable=unused-argument
            pass

        @keybow.on_release(key)
        def release_handler(key):  ### pylint: disable=unused-argument
            pass

def change_layer():
    layer_idx = None
    clear_key_handlers()

    display_layers.add(layer_select_colours)
    display_layers.render()
    while keybow.none_pressed():
        keybow.update()

    cl_pressed = keybow.get_pressed()
    if len(cl_pressed) == 1:
        layer_idx = K_TO_P_RF[cl_pressed[0]]
        if layer_idx >= len(layers):
            layer_idx = None

    while not keybow.none_pressed():
        keybow.update()

    display_layers.remove(layer_select_colours)
    display_layers.render()

    add_key_handlers()  ### restore the key handlers
    return layer_idx


display_layers = KeybowLayerStack(keybow)
layer_select_colours = LSCAnim(len(layers), config.LAYER_COLOURS)

add_key_handlers()
if STARTUP_MESSAGE:
    display_layers.add(ScrollTextAnim(STARTUP_MESSAGE, (0, 0, 255)))
while True:
    ### PMK update() must be called frequently
    keybow.update()
    ### Set any RGB LEDs
    t1 = time.monotonic_ns()
    display_layers.render()
    t2 = time.monotonic_ns()
    ### Temp was 35 at 125MHz,  37 with desk at 25 at 200MHz
    #gc.collect()
    #print("Render Time (ms)", (t2-t1)/1e6, "Temp", microcontroller.cpu.temperature, "MF", gc.mem_free())

    if keybow_button_r():
        ### A debounced measurement of button hold duration
        pressed = 1.0
        press_duration_ns = 0
        start_ns = time.monotonic_ns()
        while pressed > 0.4 and press_duration_ns < SHORT_PRESS_NS:
            pressed = keybow_button_r() * 0.125 + pressed * 0.875
            time.sleep(0.001)
            press_duration_ns = time.monotonic_ns() - start_ns

        if press_duration_ns < SHORT_PRESS_NS:
            km_idx = change_layer()
            if km_idx is not None:
                keymap = layers[km_idx]
                audmap = audio_layers[km_idx]
                key_press_colour = config.LAYER_COLOURS[km_idx % len(config.LAYER_COLOURS)]
        else:
            old_effect_idx = effect_idx
            sound_effect_on, visual_effect_on = next_effect_mode()
            display_layers.add(EMAnim(old_effect_idx, effect_idx))

        while pressed > 0.4:
            display_layers.render()
            pressed = keybow_button_r() * 0.25 + pressed * 0.75
