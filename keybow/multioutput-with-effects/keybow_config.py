### Layers are specified from top left going across the row first
### This is different to the Pimoroni demo code which follows the
### non-intuitive hardware switch number order

from adafruit_hid.keycode import Keycode
from config_types import CCC, MIDI

STARTUP_MESSAGE = "  keybow"

AUDIO_OUTPUT="I2S"

MIDI_CHANNEL = 1
MIDI_VELOCITY = 127

### Colours (r,g,b)
KEY_PRESS_EFFECT_COLOUR = (192, 0, 0)
LAYER_COLOURS = ((  0,   0, 255),
                 (255,   0,   0),
                 (255,   0, 255),
                 (  0, 255,   0),
                 (  0, 255, 255),
                 (255, 255,   0),
                 (255, 255, 255))


### Keypad emulation which ignores NUM LOCK
layer_001 = (Keycode.SEVEN, Keycode.EIGHT, Keycode.NINE,   "+",
             Keycode.FOUR,  Keycode.FIVE,  Keycode.SIX,    "+",
             Keycode.ONE,   Keycode.TWO,   Keycode.THREE,  Keycode.ENTER,
             Keycode.ZERO,  Keycode.ZERO,  Keycode.PERIOD, Keycode.ENTER)

### Basic click
#audio_001 = ["modelf-click-32k.wav"] * 16

### Stereo positioned clicks
audio_001 = [("modelf-click-32k.wav", None, None, pos) for pos in (-1.0, -0.5, +0.5, +1.0)] * 4

### Pimoroni's media control example
### from https://github.com/pimoroni/pmk-circuitpython/blob/main/examples/hid-keypad-fifteen-layers.py
layer_002 = (None, CCC("SCAN_PREVIOUS_TRACK"), CCC("PLAY_PAUSE"), CCC("SCAN_NEXT_TRACK"),
             None, CCC("VOLUME_DECREMENT"),    CCC("MUTE"),       CCC("VOLUME_INCREMENT"),
             None, None,                       None,              None,
             None, None,                       None,              None)

### Use a dimmed version of the layer colour to show keys in use
background_002 = tuple(None if key is None
                       else tuple(c // 15 for c in LAYER_COLOURS[2 - 1]) for key in layer_002)

### Chromatic keys starting at C2 (36)
#_BASE_NOTE = 37
_BASE_NOTE = 36
layer_003 = ([MIDI(n) for n in range(_BASE_NOTE + 12, _BASE_NOTE + 16)] +
             [MIDI(n) for n in range(_BASE_NOTE +  8, _BASE_NOTE + 12)] +
             [MIDI(n) for n in range(_BASE_NOTE +  4, _BASE_NOTE +  8)] +
             [MIDI(n) for n in range(_BASE_NOTE +  0, _BASE_NOTE +  4)])


### Some letters for testing
layer_004 = [Keycode.A, Keycode.B, Keycode.C, Keycode.D,
             Keycode.E, Keycode.F, Keycode.G, Keycode.H,
             Keycode.I, Keycode.J, Keycode.K, Keycode.L,
             Keycode.M, Keycode.N, Keycode.O, Keycode.P]

audio_004 = [(fn, vol) for vol in (0.8, 0.6, 0.4, 0.2)
                       for fn in ("defender-baiterarrivals-32k.wav",
                                  "defender-humanoiddrop-32k.wav",
                                  "defender-shootingbomber-32k.wav",
                                  "defender-smartbombpods-32k.wav")]


### Some words for testing
layer_005 = ("one",      "two",      "three",   "four",
             "five",     "six",      "seven",   "eight",
             "nine",     "ten",      "eleven",  "twelve",
             "thirteen", "fourteen", "fifteen", "sixteen")


### The real numerical keypad codes - NUM LOCK will apply to these
layer_006 = (Keycode.KEYPAD_SEVEN, Keycode.KEYPAD_EIGHT, Keycode.KEYPAD_NINE,   Keycode.KEYPAD_PLUS,
             Keycode.KEYPAD_FOUR,  Keycode.KEYPAD_FIVE,  Keycode.KEYPAD_SIX,    Keycode.KEYPAD_PLUS,
             Keycode.KEYPAD_ONE,   Keycode.KEYPAD_TWO,   Keycode.KEYPAD_THREE,  Keycode.KEYPAD_ENTER,
             Keycode.KEYPAD_ZERO,  Keycode.KEYPAD_ZERO,  Keycode.KEYPAD_PERIOD, Keycode.KEYPAD_ENTER)


### An aid for YouTubers writing scripts
layer_007 = ("No wukkas ", "bobby-dazzler ", "Bueller... Bueller... ", "for the film aficionados ",
             "winner, winner, chicken dinner ", "terrible, Muriel ", "come a gutsa ", "for those playing along at home ",
             "Bob's your uncle ", "stick it right up the clacker ", "catch you next time ", "strewth ",
             "epic fail ", "absolute junk ", "dead as a doornail ", "solar powered roadways ")

### DECtalk "Pimoroni Keybow 2040"
layer_008 = (None,) * 16

audio_008 = tuple(("samples/" + nm + "-rp-32k.wav", 1.0, rate)
                   for rate in (24_000, 32_000, 48_000, 64_000) for nm in ("pimoroni", "keybow", "twenty", "forty"))


### More sound sample fun
#layer_009 = ("in the mix", "keeping it real", "having a splendid time", "excellent") * 4
#
#audio_009 = tuple(["samples/" + nm.replace(" ", "-").replace("'", "").lower() + "-bfc-32k-8b.wav"
#                   for nm in layer_008])

### Daft Keybow
#layer_010 = (None,) * 16
#
#audio_010 = tuple(["hbfs/" + nm + ".wav"
#                   for nm in ("work-it", "make-it", "do-it", "makes-us",
#                              "harder", "better", "faster", "stronger",
#                              "more-than", "hour", "our", "never",
#                              "ever", "after", "work-is", "over")])
