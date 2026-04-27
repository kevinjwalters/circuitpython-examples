### Layers are specified from top left going across the row first
### This is different to the Pimoroni demo code which follows the
### non-intuitive hardware switch number order

from adafruit_hid.keycode import Keycode
from config_types import CCC, MIDI

STARTUP_MESSAGE = "   keybow"

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

audio_001 = ["modelf-click-32k.wav"] * 16


### Pimoroni's media conrol example
### from https://github.com/pimoroni/pmk-circuitpython/blob/main/examples/hid-keypad-fifteen-layers.py
layer_002 = (None, CCC("SCAN_PREVIOUS_TRACK"), CCC("PLAY_PAUSE"), CCC("SCAN_NEXT_TRACK"),
             None, CCC("VOLUME_DECREMENT"),    CCC("MUTE"),       CCC("VOLUME_INCREMENT"),
             None, None,                       None,              None,
             None, None,                       None,              None)


### Chromatic keys starting at C2 (36)
layer_003 = ([MIDI(n) for n in range(48, 52)] +
             [MIDI(n) for n in range(44, 48)] +
             [MIDI(n) for n in range(40, 44)] +
             [MIDI(n) for n in range(36, 40)])


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
