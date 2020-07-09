### bar-hammer v1.0
### Trying to recreate MemoryError with broadcastAndReceive

### Tested with CLUE and Circuit Playground Bluefruit Alpha with TFT Gizmo
### using CircuitPython and 5.3.0

### copy this file to CLUE/CPB board as code.py

### MIT License

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
import gc
import os
import struct
import random

import board
import displayio
from displayio import Group
import terminalio
import digitalio
from audiocore import WaveFile
import _bleio  ### just for _bleio.BluetoothError

import neopixel
from adafruit_display_text.label import Label
### https://github.com/adafruit/Adafruit_CircuitPython_BLE
from adafruit_ble import BLERadio

from rps_advertisements import JoinGameAdvertisement, \
                               RpsEncDataAdvertisement, \
                               RpsKeyDataAdvertisement, \
                               RpsRoundEndAdvertisement
from rps_audio import SampleJukebox
from rps_crypto import bytesPad, strUnpad, generateOTPadKey, \
                       enlargeKey, encrypt, decrypt
from rps_comms import broadcastAndReceive, addrToText
from rps_display import showPlayerVPlayer, \
                        showGameResult, \
                        showGameRound, \
                        flashNeoPixels, \
                        addPlayerDOB, \
                        choiceToPixIdx, \
                        fadeUpDown, \
                        blankScreen, \
                        introductionScreen, \
                        getDisplayInfo, \
                        getFontInfo, \
                        loadSprites, \
                        playerListScreen, \
                        showChoice

### These imports works on CLUE, CPB (and CPX on 5.x)
from audiocore import RawSample
try:
    from audioio import AudioOut
except ImportError:
    from audiopwmio import PWMAudioOut as AudioOut

### Look for ble_name in secrets.py file if present
ble_name = None
try:
    from secrets import secrets
    ble_name = secrets.get("rps_name")
    if ble_name is None:
        ble_name = secrets.get("ble_name")
        if ble_name is None:
            print("INFO: No rps_name or ble_name entry found in secrets dict")
except ImportError:
    pass


debug = 3

def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


def tftGizmoPresent():
    """Determine if the TFT Gizmo is attached.
       The TFT's Gizmo circuitry for backlight features a 10k pull-down resistor.
       This attempts to verify the presence of the pull-down to determine
       if TFT Gizmo is present.
       This is likely to get confused if anything else is connected to pad A3.
       Only use this on Circuit Playground Express (CPX)
       or Circuit Playground Bluefruit (CPB) boards."""
    present = True
    try:
        with digitalio.DigitalInOut(board.A3) as backlight_pin:
            backlight_pin.pull = digitalio.Pull.UP
            present = not backlight_pin.value
    except ValueError:
        ### The Gizmo is already initialised, i.e. showing console output
        pass

    return present


### Assuming CLUE if it's not a Circuit Playround (Bluefruit)
clue_less = "Circuit Playground" in os.uname().machine

### Note: difference in pull-up and pull-down
###       and logical not use for buttons
if clue_less:
    ### CPB with TFT Gizmo (240x240)
    ### from adafruit_circuitplayground import cp  ### Avoiding to save memory

    ### Outputs
    if tftGizmoPresent():
        from adafruit_gizmo import tft_gizmo
        display = tft_gizmo.TFT_Gizmo()
        JG_RX_COL = 0x0000ff
        BUTTON_Y_POS = 120
    else:
        display = None
        JG_RX_COL = 0x000030  ### dimmer blue for upward facing CPB NeoPixels

    audio_out = AudioOut(board.SPEAKER)
    ###pixels = cp.pixels
    pixels = neopixel.NeoPixel(board.NEOPIXEL, 10)

    ### Enable the onboard amplifier for speaker
    ###cp._speaker_enable.value = True  ### pylint: disable=protected-access
    speaker_enable = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
    speaker_enable.switch_to_output(value=False)
    speaker_enable.value = True

    ### Inputs
    ### buttons reversed if it is used upside-down with Gizmo
    _button_a = digitalio.DigitalInOut(board.BUTTON_A)
    _button_a.switch_to_input(pull=digitalio.Pull.DOWN)
    _button_b = digitalio.DigitalInOut(board.BUTTON_B)
    _button_b.switch_to_input(pull=digitalio.Pull.DOWN)
    if display is None:
        button_left = lambda: _button_a.value
        button_right = lambda: _button_b.value
        ##button_left = lambda: cp.button_a
        ##button_right = lambda: cp.button_b

    else:
        button_left = lambda: _button_b.value
        button_right = lambda: _button_a.value
        ##button_left = lambda: cp.button_b
        ##button_right = lambda: cp.button_a

else:
    ### CLUE with builtin screen (240x240)
    ### from adafruit_clue import clue  ### Avoiding to save memory

    ### Outputs
    display = board.DISPLAY
    audio_out = AudioOut(board.SPEAKER)
    ###pixels = clue.pixel
    pixels = neopixel.NeoPixel(board.NEOPIXEL, 1)
    JG_RX_COL = 0x0000ff
    BUTTON_Y_POS = 152

    ### Inputs
    _button_a = digitalio.DigitalInOut(board.BUTTON_A)
    _button_a.switch_to_input(pull=digitalio.Pull.UP)
    _button_b = digitalio.DigitalInOut(board.BUTTON_B)
    _button_b.switch_to_input(pull=digitalio.Pull.UP)
    button_left = lambda: not _button_a.value
    button_right = lambda: not _button_b.value
    ##button_left = lambda: clue.button_a
    ##button_right = lambda: clue.button_b

### This will always by the top level group passed to display.show()
main_display_group = None
main_display_group = blankScreen(display, pixels, main_display_group)

### TODO - need to change loads of stuff to pass main_display_group
### TODO - need to change loads of stuff to pass main_display_group
### TODO - need to change loads of stuff to pass main_display_group

IMAGE_DIR = "rps/images"
AUDIO_DIR = "rps/audio"

### None, None, None for no display
(sprites,
 opp_sprites,
 SPRITE_SIZE) = loadSprites(display, IMAGE_DIR + "/rps-sprites-ind4.bmp")

files = (("searching", "welcome-to", "arena", "ready")
          + ("rock", "paper", "scissors")
          + ("start-tx", "end-tx", "txing")
          + ("rock-scissors", "paper-rock", "scissors-paper")
          + ("you-win", "draw", "you-lose", "error")
          + ("humiliation", "excellent"))

gc.collect()
d_print(2, "GC before SJ", gc.mem_free())
sample = SampleJukebox(audio_out, files,
                       directory=AUDIO_DIR, error_output=True)
del files  ### not needed anymore
gc.collect()
d_print(2, "GC after SJ", gc.mem_free())

### Top y position of first choice and pixel separate between choices
top_y_pos = 60
choice_sep = 60

### This limit is based on displaying names on screen with scale=2 font
MAX_PLAYERS = 8

### Some code is dependent on these being lower-case
CHOICES = ("rock", "paper", "scissors")

### Transmit maximum times in seconds
JG_MSG_TIME_S = 20
FIRST_MSG_TIME_S = 12
STD_MSG_TIME_S = 4
LAST_ACK_TIME_S = 1.5

### For the "hammer" test
SHORTER_FIRST_MSG_TIME_S = 3


(DISPLAY_WIDTH,
 DISPLAY_HEIGHT,
 STD_BRIGHTNESS) = getDisplayInfo(display)

### The 6x14 terminalio classic monospaced font
(FONT_WIDTH, FONT_HEIGHT) = getFontInfo()

### Intro screen with audio
main_display_group = introductionScreen(display, pixels, main_display_group,
                                        sample, sprites, BUTTON_Y_POS)

### Enable the Bluetooth LE radio and set player's name (from secrets.py)
ble = BLERadio()
if ble_name is not None:
    ble.name = ble_name


game_no = 1
round_no = 1
wins = 0
losses = 0
draws = 0
voids = 0

### TOTAL_ROUNDS = 5
TOTAL_ROUNDS = 3

CRYPTO_ALGO = "chacha20"
KEY_SIZE = 8  ### in bytes
KEY_ENLARGE = 256 // KEY_SIZE // 8


def evaluateRound(mine, yours):
    """Determine who won the game based on the two strings mine and yours.
       Returns three booleans (win, draw, void)."""
    ### Return with void at True if any input is None
    try:
        mine_lc = mine.lower()
        yours_lc = yours.lower()
    except AttributeError:
        return (False, False, True)

    win = draw = void = False
    if (mine_lc == "rock" and yours_lc == "rock" or
        mine_lc == "paper" and yours_lc == "paper" or
        mine_lc == "scissors" and yours_lc == "scissors"):
        draw = True
    elif (mine_lc == "rock" and yours_lc == "paper"):
        lose = True
    elif (mine_lc == "rock" and yours_lc == "scissors"):
        win = True
    elif (mine_lc == "paper" and yours_lc == "rock"):
        win = True
    elif (mine_lc == "paper" and yours_lc == "scissors"):
        lose = True
    elif (mine_lc == "scissors" and yours_lc == "rock"):
        lose = True
    elif (mine_lc == "scissors" and yours_lc == "paper"):
        win = True
    else:
        void = True

    return (win, draw, void)


### A lookup table in Dict form for win/lose
### does not need to cater for draw condition
WAV_VICTORY_NAME = { "rp": "paper-rock",
                     "pr": "paper-rock",
                     "ps": "scissors-paper",
                     "sp": "scissors-paper",
                     "sr": "rock-scissors",
                     "rs": "rock-scissors"}

def winnerWav(mine_idx, yours_idx):
    """Return the sound file to play to describe victory or None for draw."""

    ### Take the first characters
    mine = CHOICES[mine_idx][0]
    yours = CHOICES[yours_idx][0]

    return WAV_VICTORY_NAME.get(mine + yours)

main_display_group = playerListScreen(display, pixels, main_display_group,
                                      MAX_PLAYERS)
playerlist_group = main_display_group

def addPlayer(name, addr_text, address, ad):
    global players
    global playerlist_group

    players.append((name, addr_text))
    if display is not None:
        addPlayerDOB(name, playerlist_group)


### Make a list of all the player's (name, mac address as text)
### where both are strings with this player as first entry
players = []
my_name = ble.name
fadeUpDown(display, "down", STD_BRIGHTNESS)
addPlayer(my_name, addrToText(ble.address_bytes), None, None)

### Join Game
gc.collect()
d_print(2, "GC before JG", gc.mem_free())

sample.play("searching", loop=True)
fadeUpDown(display, "up", STD_BRIGHTNESS)
jg_msg = JoinGameAdvertisement(game="RPS")
(_, _, _) = broadcastAndReceive(ble,
                                jg_msg,
                                scan_time=JG_MSG_TIME_S,
                                scan_response_request=True,
                                ad_cb=lambda _a, _b, _c: flashNeoPixels(pixels, JG_RX_COL) if JG_FLASH else None,
                                endscan_cb=lambda _a, _b, _c: button_left(),
                                name_cb=addPlayer)
_ = None  ### Clear to allow GC
sample.stop()
### Wait for button release - this stops a long press
### being acted upon in the main loop further down
while button_left():
    pass

scores = [0] * len(players)
num_other_players = len(players) - 1

gc.collect()
d_print(2, "GC after JG", gc.mem_free())

d_print(1, "PLAYERS", players)

### Sequence numbers - real packets start at 1
seq_tx = [1]  ### The next number to send
seq_rx_by_addr = {pma: 0 for pn, pma in players[1:]}  ### Per address received all up to

### Important to get rid of playerlist_group variable - this allows GC
### to dispose of it when the display content is changed
if playerlist_group is not None:
    del playerlist_group

new_round_init = True

### A nonce by definition must not be reused but here a random key is
### generated per round and this is used once per round so this is ok
static_nonce = bytes(range(12, 0, -1))

while True:
    if new_round_init:
        showGameRound(display, pixels,
                      game_no=game_no, round_no=round_no, rounds_tot=TOTAL_ROUNDS)
        ### Make a new initial random choice for the player and show it
        my_choice_idx = random.randrange(len(CHOICES))
        fadeUpDown(display, "down", STD_BRIGHTNESS)
        main_display_group = showChoice(display, pixels, main_display_group, sprites,
                                        my_choice_idx,
                                        game_no=game_no, round_no=round_no, rounds_tot=TOTAL_ROUNDS,
                                        won_sf=wins, drew_sf=draws, lost_sf=losses)
        fadeUpDown(display, "up", STD_BRIGHTNESS)
        new_round_init = False

    if True:
        gc.collect()
        d_print(2, "GC before comms", gc.mem_free())

        ### This sound cue is really for other players
        sample.play("ready")

        my_choice = CHOICES[my_choice_idx]
        player_choices = [my_choice]

        ### Repeating key four times to make key for ChaCha20
        short_key = generateOTPadKey(KEY_SIZE)
        key = enlargeKey(short_key, KEY_ENLARGE)
        d_print(3, "KEY", key)

        plain_bytes = bytesPad(my_choice, size=8, pad=0)
        cipher_bytes = encrypt(plain_bytes, key, CRYPTO_ALGO,
                               nonce=static_nonce)
        ### NOTE modified value passed to round_no to keep it in range
        enc_data_msg = RpsEncDataAdvertisement(enc_data=cipher_bytes,
                                               round_no=round_no % 256)

        ### Wait for ready sound sample to stop playing
        sample.wait()
        sample.play("start-tx")
        sample.wait()
        sample.play("txing", loop=True)
        ### Players will not be synchronised at this point as they do not
        ### have to make their choices simultaneously - much longer 12 second
        ### time to accomodate this

        seq_tx[0] = seq_tx[0] % 256  ### Keep this within range

        _, enc_data_by_addr, _ = broadcastAndReceive(ble,
                                                     enc_data_msg,
                                                     RpsEncDataAdvertisement,
                                                     RpsKeyDataAdvertisement,
                                                     scan_time=SHORTER_FIRST_MSG_TIME_S,
                                                     receive_n=num_other_players,
                                                     seq_tx=seq_tx,
                                                     seq_rx_by_addr=seq_rx_by_addr)

        ### Play end transmit sound while doing next decrypt bit
        sample.play("end-tx")
        sample.wait()

        print("HAMMER TEST Game {:d}, round {:d}".format(game_no, round_no))

        round_no += 1
        new_round_init = True
