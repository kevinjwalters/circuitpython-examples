### clue-multi-rpsgame v1.9
### CircuitPython massively multiplayer rock paper scissors game over Bluetooth LE

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
from rps_comms import broadcastAndReceive, addr_to_text


### TODO - clear NeoPixel on CPB only at end of round before scores are shown
### TODO - try one extra shift on brightness
### TODO - humiliation on 0 and excellent on >= int((players-1) * rounds * 1.5)


### TODO
### Maybe simple version is clue only
### simple version still needs win indicator (flash text?) and a score counter


### Complex version demos how to

### use neopixels as alternative display (light 1, 2, 3 discreetly (discrete joke)

### simple version will have a lot of issues
### unreliable transport
### lack of synchronised win announcement
### need sequence number for packets and acks
### need higher level round numbers to detect out of synch
### need to work out who is who with N player games
### probably not deal with players who join midway?
### need to allocate player numbers - could sort by MAC - ACTUALLY this is not needed?!
### avoid election algorithms even if tempted
### got to decide whether to do the littany of crypto mistakes or not - ALREADY HAVE ONE!
### could do own crypto
### could include the lack of protocol versioning and future proofing and cite
### LDAP as good example and git perhaps as less good
### complex format not compatible with simple format so mixing the two will confuse things


### Other things of interest
### https://github.com/adafruit/Adafruit_CircuitPython_BLE_Eddystone
### A Service: https://github.com/adafruit/Adafruit_CircuitPython_BLE_iBBQ/blob/master/adafruit_ble_ibbq.py
### Yet another UART, implements TransparentUARTService(Service) https://github.com/adafruit/Adafruit_CircuitPython_BLE_BerryMed_Pulse_Oximeter
### A Service: https://github.com/adafruit/Adafruit_CircuitPython_BLE_Heart_Rate/blob/master/adafruit_ble_heart_rate.py
### EddystoneAdvertisement(Advertisement): https://github.com/adafruit/Adafruit_CircuitPython_BLE_Eddystone/blob/master/adafruit_ble_eddystone/__init__.py

### https://github.com/adafruit/Adafruit_CircuitPython_BLE_Apple_Notification_Center
### https://github.com/adafruit/Adafruit_CircuitPython_BLE_MIDI

### Dan's latest handiwork
### https://github.com/adafruit/Adafruit_CircuitPython_BLE_Adafruit

### https://learn.adafruit.com/bluetooth-le-broadcastnet-sensor-node-raspberry-pi-wifi-bridge
### explains the https://github.com/adafruit/Adafruit_CircuitPython_BLE_BroadcastNet


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

IMAGE_DIR = "rps/images"
AUDIO_DIR = "rps/audio"


### Load horizontal sprite sheet if running with a display
if display is not None:
    import adafruit_imageload
    s_bit, s_pal = adafruit_imageload.load(IMAGE_DIR + "/rps-sprites-ind4.bmp",
                                           bitmap=displayio.Bitmap,
                                           palette=displayio.Palette)
    SPRITE_SIZE = s_bit.height
    num_sprites = s_bit.width // s_bit.height
    s_pal.make_transparent(0)  ### Make the first colour (black) transparent

    ### Make some sprites from the sprite sheet
    ### Sprites can only be in one layer (Group) at a time, need two copies
    ### to allow representation of a draw on screen
    sprites = []
    opp_sprites = []
    for idx in range(num_sprites):
        sprite = displayio.TileGrid(s_bit, pixel_shader=s_pal,
                                    width=1, height=1,
                                    tile_width=SPRITE_SIZE, tile_height=SPRITE_SIZE)
        sprite[0] = idx
        sprites.append(sprite)

        opp_sprite = displayio.TileGrid(s_bit, pixel_shader=s_pal,
                                        width=1, height=1,
                                        tile_width=SPRITE_SIZE, tile_height=SPRITE_SIZE)
        opp_sprite[0] = idx
        opp_sprites.append(opp_sprite)


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

BLUE=0x0000ff
BLACK=0x000000

DIM_TXT_COL_FG = 0x505050
DEFAULT_TXT_COL_FG = 0xa0a0a0
CURSOR_COL_FG = 0xc0c000
IWELCOME_COL_FG = 0x000010
WELCOME_COL_FG = 0x0000f0
BWHITE_COL_FG = 0xffffff
PLAYER_NAME_COL_FG = 0xc0c000
PLAYER_NAME_COL_BG = BLACK
OPP_NAME_COL_FG = 0x00c0c0
OPP_NAME_COL_BG = BLACK
ERROR_COL_FG = 0xff0000
TITLE_TXT_COL_FG = 0xc000c0
INFO_COL_FG = 0xc0c000
INFO_COL_BG = 0x000080
QM_SORT_FG = 0x808000
QM_SORTING_FG = 0xff8000
RED_COL = 0xff0000
ORANGE_COL = 0xff8000
YELLOW_COL = 0xffff00
DRAWLOSE_COL = 0x0000f0

### NeoPixel colours
GAMENO_GREEN = 0x002000
ROUNDNO_WHITE = 0x0202020
PLAYER_COL = 0xff0000
SCORE_COLS = (0x3f1200, 0x3f2c00, 0x002400, 0x00003f, 0x10001c, 0x321232)

### This limit is based on displaying names on screen with scale=2 font
MAX_PLAYERS = 8

### Some code is dependent on these being lower-case
CHOICES = ("rock", "paper", "scissors")
### Colours for NeoPixels on display-less CPB
### Should be dim to avoid an opponent seeing choice from reflected light
CHOICE_COL = (0x040000,  ### Red for Rock
              0x030004,  ### Purple for Paper
              0x000004   ### Sapphire blue for Scissors
             )


def choiceToPixIdx(idx, length=10):
    """This maps the three choices to three pixels.
       It is also used for game and round numbers.
       The starting position is 0 which is just left of USB connector
       on Circuit Playground boards and going clockwise - this avoids
       the NeoPixels near the buttons which are likely to be under fingers."""
    return -idx % length


### Set to True for blue flashing when devices are annoucing players' names
JG_FLASH = True  ### TODO DISABLE THIS FOR THE ADAFRUIT RELEASE

if display is not None:
    STD_BRIGHTNESS = display.brightness  ### use to fade down/up

    ### The 6x14 terminalio classic font
    FONT_WIDTH, FONT_HEIGHT = terminalio.FONT.get_bounding_box()
    DISPLAY_WIDTH = display.width
    DISPLAY_HEIGHT = display.height


def fadeUpDown(disp, direction, duration=0.8, steps=10):
    """Fade the display up or down by varything the brightness of the backlight."""

    if disp is None:
        return

    if duration == 0.0:
        disp.brightness = 0.0 if direction == "down" else STD_BRIGHTNESS
        return

    if direction == "down":
        step_iter = range(steps - 1, -1, -1)
    elif direction == "up":
        step_iter = range(1, steps + 1)
    else:
        raise ValueError("up or down")

    time_step = duration / steps
    for bri in [idx * STD_BRIGHTNESS / steps for idx in step_iter]:
        disp.brightness = bri
        time.sleep(time_step)


def emptyGroup(dio_group):
    """Recursive depth first removal of anything in a Group.
       Intended to be used to clean-up a previous screen
       which may have elements in the new screen
       as elements cannot be in two Groups at once since this
       will cause "ValueError: Layer already in a group".
       This only deletes Groups, it does not del the non-Group content."""
    if dio_group is None:
        return

    ### Go through Group in reverse order
    for idx in range(len(dio_group) - 1, -1, -1):
        ### Avoiding isinstance here as Label is a sub-class of Group!
        if (type(dio_group[idx]) == Group):
            emptyGroup(dio_group[idx])
        del dio_group[idx]
    del dio_group


def showChoice(disp, pix, ch_idx,
               game_no=None, round_no=None, rounds_tot=None,
               won_sf=None, drew_sf=None, lost_sf=None):
    """TODO DOC"""
    global main_display_group

    if disp is None:
        pix.fill(BLACK)
        pix[choiceToPixIdx(ch_idx)] = CHOICE_COL[ch_idx]
    else:
        emptyGroup(main_display_group)
        ### Would be slightly better to create this Group once and re-use it
        round_choice_group = Group(max_size=3)

        if round_no is not None:
            title_dob = Label(terminalio.FONT,
                              text="Game {:d}  Round {:d}/{:d}".format(game_no,
                                                                       round_no,
                                                                       rounds_tot),
                              scale=2,
                              color=TITLE_TXT_COL_FG)
            title_dob.x = round((DISPLAY_WIDTH - len(title_dob.text) * 2 * FONT_WIDTH) // 2)
            title_dob.y = round(FONT_HEIGHT // 2)
            round_choice_group.append(title_dob)

        if won_sf is not None:
            gamesum_dob = Label(terminalio.FONT,
                                text="Won {:d} Drew {:d} Lost {:d}".format(won_sf,
                                                                           drew_sf,
                                                                           lost_sf),
                                scale=2,
                                color=TITLE_TXT_COL_FG)
            gamesum_dob.x = round((DISPLAY_WIDTH - len(gamesum_dob.text) * 2 * FONT_WIDTH) // 2)
            gamesum_dob.y = round(DISPLAY_HEIGHT - 2 * FONT_HEIGHT // 2)
            round_choice_group.append(gamesum_dob)

        s_group = Group(scale=3, max_size=1)
        s_group.x = 32
        s_group.y = (DISPLAY_HEIGHT - 3 * SPRITE_SIZE) // 2 
        s_group.append(sprites[ch_idx])

        round_choice_group.append(s_group)

        main_display_group = round_choice_group
        disp.show(main_display_group)


def introduction(disp, pix):
    """Introduction screen."""
    global main_display_group

    if disp is not None:
        emptyGroup(main_display_group)  ### this should already be empty
        intro_group = Group(max_size=7)
        welcometo_dob = Label(terminalio.FONT,
                              text="Welcome To",
                              scale=3,
                              color=IWELCOME_COL_FG)
        welcometo_dob.x = (DISPLAY_WIDTH - 10 * 3 * FONT_WIDTH) // 2
        ### Y pos on screen looks lower than I would expect
        welcometo_dob.y = 3 * FONT_HEIGHT // 2
        intro_group.append(welcometo_dob)

        extra_space = 8
        spacing = 3 * SPRITE_SIZE + extra_space
        for idx, sprite in enumerate(sprites):
            s_group = Group(scale=3, max_size=1)
            s_group.x = -96    
            s_group.y = round((DISPLAY_HEIGHT - 1.5 * SPRITE_SIZE) // 2
                              + (idx - 1) * spacing)
            s_group.append(sprite)
            intro_group.append(s_group)

        arena_dob = Label(terminalio.FONT,
                          text="Arena",
                          scale=3,
                          color=IWELCOME_COL_FG)
        arena_dob.x = (DISPLAY_WIDTH - 5 * 3 * FONT_WIDTH) // 2
        arena_dob.y = DISPLAY_HEIGHT - 3 * FONT_HEIGHT // 2
        intro_group.append(arena_dob)

        main_display_group = intro_group
        disp.show(main_display_group)

    ### The color modification here is fragile as it only works
    ### if the text colour is blue, i.e. data is in lsb only
    sample.play("welcome-to")
    while sample.playing():
        if disp is not None and intro_group[0].color < WELCOME_COL_FG:
            intro_group[0].color += 0x10
            time.sleep(0.120)

    onscreen_x_pos = 96

    ### Move each sprite onto the screen while saying its name with wav file
    anims = (("rock", 10, 1, 0.050),
             ("paper", 11, 2, 0.050),
             ("scissors", 7, 3, 0.050))
    for idx, (audio_name, x_shift, grp_idx, delay_s) in enumerate(anims):
        if disp is None:
            showChoice(disp, pix, idx)
        sample.play(audio_name)
        ### Audio needs to be long enough to finish movement
        while sample.playing():
            if disp is not None:
                if intro_group[grp_idx].x < onscreen_x_pos:
                    intro_group[grp_idx].x += x_shift
                    time.sleep(delay_s)

    ### Set NeoPixels back to black
    if disp is None:
        pix.fill(BLACK)

    sample.play("arena")
    while sample.playing():
        if disp is not None and intro_group[4].color < WELCOME_COL_FG:
            intro_group[4].color += 0x10
            time.sleep(0.060)

    ### Button Guide for those with a display
    if disp is not None:
        left_dob = Label(terminalio.FONT,
                         text="< Select    ",
                         scale=2,
                         color=INFO_COL_FG,
                         background_color=INFO_COL_BG)
        left_width = len(left_dob.text) * 2 * FONT_WIDTH
        left_dob.x = -left_width
        left_dob.y = BUTTON_Y_POS
        intro_group.append(left_dob)

        right_dob = Label(terminalio.FONT,
                          text=" Transmit >",
                          scale=2,
                          color=INFO_COL_FG,
                          background_color=INFO_COL_BG)
        right_width = len(right_dob.text) * 2 * FONT_WIDTH
        right_dob.x = DISPLAY_WIDTH
        right_dob.y = BUTTON_Y_POS
        intro_group.append(right_dob)

        ### Move left button text onto screen, then right
        steps = 20
        for x_pos in [left_dob.x + round(left_width * x / steps)
                      for x in range(1, steps + 1)]:
            left_dob.x = x_pos
            time.sleep(0.06)

        for x_pos in [right_dob.x - round(right_width * x / steps)
                      for x in range(1, steps + 1)]:
            right_dob.x = x_pos
            time.sleep(0.06)

        time.sleep(8)  ### leave on screen for further 6 seconds


### Intro screen with audio
introduction(display, pixels)


if display is not None:
    gameround_group = Group(max_size=len(CHOICES) * 2 + 1)

    for x_pos in (20, display.width // 2 + 20):
        y_pos = top_y_pos
        for label_text in CHOICES:
            rps_dob = Label(terminalio.FONT,
                            text=label_text,
                            scale=2,
                            color=DEFAULT_TXT_COL_FG)
            rps_dob.x = x_pos
            rps_dob.y = y_pos
            y_pos += 60
            gameround_group.append(rps_dob)

JG_MSG_TIME_S = 20
FIRST_MSG_TIME_S = 12
STD_MSG_TIME_S = 4
LAST_ACK_TIME_S = 1.5

### Enable the Bluetooth LE radio and set player's name (from secrets.py)
ble = BLERadio()
if ble_name is not None:
    ble.name = ble_name

msg_seq_last_rx = 255
msg_seq = 0

timeout = False
game_no = 1
round_no = 1
wins = 0
losses = 0
draws = 0 
voids = 0

### TOTAL_ROUNDS = 5
TOTAL_ROUNDS = 3


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


if display is not None:
    ### The 6x14 terminalio classic font
    FONT_WIDTH, FONT_HEIGHT = terminalio.FONT.get_bounding_box()
    playerlist_group = Group(max_size=MAX_PLAYERS)

    pl_x_pos = 20
    pl_y_cur_pos = 7
    pl_y_off = 2 * FONT_HEIGHT + 1
    display.show(playerlist_group)


def add_player_dob(name, p_group):
    global pl_y_cur_pos

    pname_dob = Label(terminalio.FONT,
                      text=name,
                      scale=2,
                      color=DEFAULT_TXT_COL_FG)
    pname_dob.x = pl_x_pos
    pname_dob.y = pl_y_cur_pos
    pl_y_cur_pos += pl_y_off
    p_group.append(pname_dob)


def add_player(name, addr_text, address, ad):
    global player_names
    global playerlist_group  ### Not strictly needed

    players.append((name, addr_text))
    if display is not None:
        add_player_dob(name, playerlist_group)


def flashNP(pix, col):
    """The briefest of flashes on the NeoPixels."""
    pix.fill(col)
    pix.fill(BLACK)


def showGameRound(disp, pix,
                  game_no=game_no, round_no=round_no, rounds_tot=TOTAL_ROUNDS):

    if disp is None:
        ### Gradually light NeoPixels in green to show game number
        for p_idx in range(game_no):
            pix[choiceToPixIdx(p_idx)] = GAMENO_GREEN
            time.sleep(0.5)
        
        time.sleep(2)
        
        ### Flash white five times at position to indicate round number
        bg_col = pix[round_no - 1]
        for _ in range(5):
            pix_idx = choiceToPixIdx(round_no - 1)
            pix[pix_idx] = ROUNDNO_WHITE
            time.sleep(0.1)
            pix[pix_idx] = bg_col
            time.sleep(0.3)

        pix.fill(BLACK)


def showGameResultScreen(disp, pla, sco, rounds_tot=None):
    """Display a high score table with some visual sorting."""
    global main_display_group

    fadeUpDown(disp, "down")
    emptyGroup(main_display_group)

    ### score list group + background + question mark for sorting
    gs_group = Group(max_size=3)
    
    sbg_dob = Label(terminalio.FONT,
                    text=" GAME\nSCORES",
                    scale=6,
                    color=0x202020)
    sbg_dob.x = (DISPLAY_WIDTH - 6 * 6 * FONT_WIDTH) // 2
    sbg_dob.y = DISPLAY_HEIGHT // 2
    gs_group.append(sbg_dob)
    main_display_group = gs_group
    disp.show(main_display_group)
    fadeUpDown(disp, "up")

    ### Calculate maximum length player name
    ### and see if scores happen to already be in order
    max_len = 0
    prev_score = sco[0]
    descending = True
    for idx, (name, macaddr) in enumerate(pla):
        max_len = max(max_len, len(name))
        if sco[idx] > prev_score:
            descending = False
        prev_score = sco[idx]

    fmt = "{:" + str(max_len) + "s} {:2d}"
    x_pos = (DISPLAY_WIDTH - (max_len + 3) * 2 * FONT_WIDTH) // 2
    scale = 2
    spacing = 4 if len(pla) <= 6 else 0
    top_y_pos = round((DISPLAY_HEIGHT
                      - len(pla) * scale * FONT_HEIGHT
                      - (len(pla) - 1) * spacing) // 2
                      + scale * FONT_HEIGHT // 2)
    scores_group = Group(max_size=len(pla))
    gs_group.append(scores_group)
    for idx, (name, macaddr) in enumerate(pla):
        op_dob = Label(terminalio.FONT,
                       text=fmt.format(name, sco[idx]),
                       scale=2,
                       color=(PLAYER_NAME_COL_FG if idx == 0 else OPP_NAME_COL_FG))
        op_dob.x = x_pos
        op_dob.y = top_y_pos + idx * (scale * FONT_HEIGHT + spacing) 
        scores_group.append(op_dob)
        time.sleep(0.2)

    ### Sort the entries if needed
    sort_scores = list(sco)  ### Make an independent local copy
    if not descending:
        empty_group = Group()  ### minor hack to aid swaps in scores_group
        ## TODO - remove? sbg_dob.hidden = True  ### Speed up by getting rid of background text
        step = 4
        qm_dob = Label(terminalio.FONT,
                       text="?",
                       scale=2,
                       color=QM_SORT_FG)
        qm_dob.x = round(x_pos - 1.5 * scale * FONT_WIDTH)
        gs_group.append(qm_dob)
        while True:
            swaps = 0
            for idx in range(0, len(sort_scores) -1):
                above_score = sort_scores[idx]
                above_y = scores_group[idx].y
                below_y = scores_group[idx + 1].y
                qm_dob.y = (above_y + below_y) // 2
                time.sleep(0.35)
                if above_score < sort_scores[idx + 1]:
                    qm_dob.text = "<"
                    qm_dob.color = QM_SORTING_FG
                    swaps += 1

                    ### make list of steps
                    range_y = below_y - above_y
                    offsets = list(range(step, range_y + 1, step))
                    ### Ensure this goes to the exact final position
                    if offsets[-1] != range_y:
                        offsets.append(range_y)

                    for offset in offsets:
                        scores_group[idx].y = above_y + offset
                        scores_group[idx + 1].y = below_y - offset
                        time.sleep(0.040)

                    ### swap the scores around
                    sort_scores[idx] = sort_scores[idx + 1]
                    sort_scores[idx + 1] = above_score

                    ### swap the graphical objects around using empty_group
                    ### to avoid ValueError: Layer already in a group
                    old_above_dob = scores_group[idx]
                    old_below_dob = scores_group[idx + 1]
                    scores_group[idx + 1] = empty_group
                    scores_group[idx] = old_below_dob
                    scores_group[idx + 1] = old_above_dob

                    qm_dob.text = "?"
                    qm_dob.color = QM_SORT_FG

            if swaps == 0:
                break   ### Sorted if no values were swapped 
        ## TODO - remove? sbg_dob.hidden = False
        gs_group.remove(qm_dob)

    time.sleep(10)


def showGameResultNeoPixels(pix, pla, sco, rounds_tot=None):
    """Display a high score table on NeoPixels.
       Sorted into highest first order then displayed by
       flashing position pixel to indicate player number and
       gradually lighting up pixels in a circle using rainbow
       colours for each revolution of the NeoPixels starting at orange.
       """
    idx_n_score = [(s, sco[s]) for s in range(len(sco))]
    idx_n_score.sort(key=lambda s: s[1], reverse=True)
    num_pixels = len(pix)
    
    bg_col = BLACK
    for idx, score in idx_n_score:
        playerIdx = choiceToPixIdx(idx)
        for score in range(score):
            scoreIdx = choiceToPixIdx(score)
            rev = min(score // num_pixels, len(SCORE_COLS) - 1)
            pix[scoreIdx] = SCORE_COLS[rev]
            if scoreIdx == playerIdx:
                bg_col = SCORE_COLS[rev]
            time.sleep(0.09)
            pix[playerIdx] = PLAYER_COL
            time.sleep(0.09)
            pix[playerIdx] = bg_col
            
        for _ in range(4):
            pix[playerIdx] = bg_col
            time.sleep(0.5)
            pix[playerIdx] = PLAYER_COL
            time.sleep(0.5)

        pix.fill(BLACK)
 

def showGameResult(disp, pix, pla, sco,
                   rounds_tot=None):

    if disp is None:
        showGameResultNeoPixels(pix, pla, sco, rounds_tot=rounds_tot)
    else:
        showGameResultScreen(disp, pla, sco, rounds_tot=rounds_tot)


def showPlayerVPlayerScreen(disp, me_name, op_name, my_ch_idx, op_ch_idx,
                            result, summary, win, draw, void):
    """Display a win, draw, lose or error message."""
    global main_display_group

    fadeUpDown(disp, "down")
    emptyGroup(main_display_group)

    if void:
        error_tot = 3
        error_group = Group(max_size=error_tot + 1)
        ### TODO - this would benefit from having op_name on the screen
        ### Put three error messages to go on screen to match sound sample
        op_dob = Label(terminalio.FONT,
                       text=op_name,
                       scale=2,
                       color=OPP_NAME_COL_FG)
        op_dob.x = 40
        op_dob.y = FONT_HEIGHT
        error_group.append(op_dob)
        main_display_group = error_group
        disp.show(main_display_group)
        fadeUpDown(disp, "up", duration=0.4)
        if result is not None:
            sample.play(result)
        font_scale = 2
        for idx in range(error_tot):
            error_dob = Label(terminalio.FONT,
                              text="Error!",
                              scale=font_scale,
                              color=ERROR_COL_FG)
            error_dob.x = 40
            error_dob.y = 60 + idx * 60
            error_group.append(error_dob)
            time.sleep(0.5)  ### Small attempt to synchronise audio with text
            font_scale += 1

    else:
        ### Would be slightly better to create this Group once and re-use it
        pvp_group = Group(max_size=3)

        ### Add player's name and sprite just off left side of screen
        ### and opponent's just off right
        player_detail = [[me_name, sprites[my_ch_idx], -16 - 3 * SPRITE_SIZE,
                          PLAYER_NAME_COL_FG, PLAYER_NAME_COL_BG],
                         [op_name, opp_sprites[op_ch_idx], 16 + DISPLAY_WIDTH,
                          OPP_NAME_COL_FG, OPP_NAME_COL_BG]]
        idx_lr = [0, 1]  ### index for left and right sprite
        if win:
            player_detail.reverse()  ### this player is winner so put last
            idx_lr.reverse()

        ### Add some whitespace around winner's name
        player_detail[1][0] = " " + player_detail[1][0] + " "

        for (name, sprite,
             start_x,
             fg, bg) in player_detail:
            s_group = Group(scale=2, max_size=2)  ### audio is choppy at scale=3
            s_group.x = start_x
            s_group.y = (DISPLAY_HEIGHT - 2 * (SPRITE_SIZE + FONT_HEIGHT)) // 2

            s_group.append(sprite)
            p_name_dob = Label(terminalio.FONT,
                               text=name,
                               scale=1,  ### this is scaled by the group
                               color=fg,
                               background_color=bg)
            ### Centre text below sprite - values are * Group scale
            p_name_dob.x = (SPRITE_SIZE - len(name) * FONT_WIDTH) // 2
            p_name_dob.y = SPRITE_SIZE + 4
            s_group.append(p_name_dob)

            pvp_group.append(s_group)

        summary_dob = Label(terminalio.FONT,
                           text="",
                           max_glyphs=8 + 1,  ### max len of all strings + 1
                           scale=3,
                           color=BLACK)
        summary_dob.y = round(DISPLAY_HEIGHT - (3 * FONT_HEIGHT // 2))
        pvp_group.append(summary_dob)

        main_display_group = pvp_group
        disp.show(main_display_group)
        fadeUpDown(disp, "up", duration=0.4)

        ### Start audio half way through animations
        if draw:
            ### Move sprites onto the screen leaving them at either side
            for idx in range(16):
                pvp_group[idx_lr[0]].x += 6
                pvp_group[idx_lr[1]].x -= 6
                if idx == 8 and result is not None:
                    sample.play(result)
                time.sleep(0.2)
        else:
            ### Move sprites together, winning sprite overlaps loser
            for idx in range(16):
                pvp_group[idx_lr[0]].x += 10
                pvp_group[idx_lr[1]].x -= 10
                if idx == 8 and result is not None:
                    sample.play(result)
                time.sleep(0.2)

        sample.wait()  ### Wait for first sample to finish

        if summary is not None:
            sample.play(summary)
        ### max length of sum_text must be set in max_glyphs in summary_dob
        if draw:
            sum_text = "Draw"
        elif win:
            sum_text = "You win"
        else:
            sum_text = "You lose"
        summary_dob.text = sum_text
        summary_dob.x = round((DISPLAY_WIDTH - 3 * FONT_WIDTH * len(sum_text)) // 2)

        ### Flash colours for win, fad up to blue for rest
        if not draw and win:
            colours = [YELLOW_COL, ORANGE_COL, RED_COL] * 5
        else:
            colours = [DRAWLOSE_COL * sc // 15 for sc in range(1, 15 + 1)]
        for col in colours:
            summary_dob.color = col
            time.sleep(0.120)

    sample.wait()  ### Ensure second sample has completed


def showPlayerVPlayerNeoPixels(pix, op_idx, my_ch_idx, op_ch_idx,
                               result, summary, win, draw, void):
    """This indicates the choices by putting the colours  
       associated with rock paper scissors on the first pixel
       for the player and on subsequent pixels for opponents.
       A win brightens the winning pixel as the result audio plays.
       Pixel order is based on the game's definition and not
       the native NeoPixel list order.
       Errors are indicated by flashing all pixels but keeping the
       opponent's one dark."""

    pix_op_idx = choiceToPixIdx(op_idx)
    if void:
        if result is not None:
            sample.play(result)
        ramp_updown = (list(range(8, 128 + 1, 8))
                       + list(range(128 - 8, 0 - 1, -8)))
        for _ in range(3):
            for ramp in ramp_updown:
                pix.fill((ramp, 0, 0))  ### modulate red led from RGB
                pix[pix_op_idx] = BLACK  ### blackout the opponent pixel
                time.sleep(0.013)  ### attempt to to sync with audio

    else:
        if result is not None:
            sample.play(result)

        pix[0] = CHOICE_COL[my_ch_idx]
        pix[pix_op_idx] = CHOICE_COL[op_ch_idx]

        if not draw:
            ### brighten the pixel for winner
            brigten_idx = 0 if win else pix_op_idx
            for _ in range(4):
                rr, gg, bb = pix[brigten_idx]
                pix[brigten_idx] = (rr << 1, gg << 1, bb << 1)
                time.sleep(0.35)

        if summary is not None:
            sample.wait()
            sample.play(summary)

    pix.fill(BLACK)


def showPlayerVPlayer(disp, pix, me_name, op_name, op_idx, my_ch_idx, op_ch_idx, win, draw, void):
    if void:
        result_wav = "error"
        summary_wav = None
    elif draw:
        result_wav = None
        summary_wav = "draw"
    else:
        result_wav = winnerWav(my_ch_idx, op_ch_idx)
        summary_wav = "you-win" if win else "you-lose"

    d_print(2, "Audio:", result_wav, summary_wav)

    if disp is None:
        showPlayerVPlayerNeoPixels(pix, op_idx, my_ch_idx, op_ch_idx,
                                   result_wav, summary_wav, win, draw, void)
    else:
        showPlayerVPlayerScreen(disp, me_name, op_name, my_ch_idx, op_ch_idx,
                                result_wav, summary_wav, win, draw, void)

    sample.wait()  ### Ensure any sound samples have completed


### Make a list of all the player's (name, mac address as text)
### with this player as first entry
players = []
my_name = ble.name
fadeUpDown(display, "down")
add_player(my_name, addr_to_text(ble.address_bytes), None, None)

### Join Game
### TODO - could have a callback to check for player terminate, i.e. 
###        could allow player to press button to say "i have got everyone"

gc.collect()
d_print(2, "GC before JG", gc.mem_free())

sample.play("searching", loop=True)
fadeUpDown(display, "up")
jg_msg = JoinGameAdvertisement(game="RPS")
(other_player_ads,
 other_player_ads_by_addr,
 _) = broadcastAndReceive(ble,
                          jg_msg,
                          scan_time=JG_MSG_TIME_S,
                          scan_response_request=True,
                          ad_cb=lambda _a, _b, _c: flashNP(pixels, JG_RX_COL) if JG_FLASH else None,
                          endscan_cb=lambda _a, _b, _c: button_left(),
                          name_cb=add_player)
### Wait for button release - this stops a long press
### being acted upon in the main loop further down
while button_left():
    pass
sample.stop()

scores = [0] * len(players)
num_other_players = len(players) - 1

gc.collect()
d_print(2, "GC after JG", gc.mem_free())

d_print(2, "PLAYER ADS", other_player_ads_by_addr)
d_print(1, "PLAYERS", players)

### Sequence numbers - real packets start at 1
seq_tx = [1]  ### The next number to send
seq_rx_by_addr = {pma: 0 for pn, pma in players[1:]}  ### Per address received all up to

### Important to get rid of playerlist_group variable - this allows GC
### to dispose of it when the display content is changed
if display is not None:
    del playerlist_group

new_round_init = True

### A nonce by definition must not be reused but here a random key is
### generated per round and this is used once per round so unusually it's ok
nonce = bytes(range(12, 0, -1))

while True:
    ### TODO - physically test this for need for debounce on left button

    if round_no > TOTAL_ROUNDS:
        print("Summary: ",
              "wins {:d}, losses {:d}, draws {:d}, void {:d}\n\n".format(wins, losses, draws, voids))

        showGameResult(display, pixels, players, scores,
                       rounds_tot=TOTAL_ROUNDS)

        ### Reset variables for another game
        round_no = 1
        wins = 0
        losses = 0
        draws = 0 
        voids = 0
        scores = [0] * len(players)
        game_no += 1

    if new_round_init:
        showGameRound(display, pixels,
                      game_no=game_no, round_no=round_no, rounds_tot=TOTAL_ROUNDS)
        ### Make a new initial random choice for the player and show it
        my_choice_idx = random.randrange(len(CHOICES))
        fadeUpDown(display, "down")
        showChoice(display, pixels, my_choice_idx,
                   game_no=game_no, round_no=round_no, rounds_tot=TOTAL_ROUNDS,
                   won_sf=wins, drew_sf=draws, lost_sf=losses)
        fadeUpDown(display, "up")
        new_round_init = False

    if button_left():
        while button_left():  ### Wait for button release
            pass
        my_choice_idx = (my_choice_idx + 1) % len(CHOICES)
        showChoice(display, pixels, my_choice_idx,
                   game_no=game_no, round_no=round_no, rounds_tot=TOTAL_ROUNDS,
                   won_sf=wins, drew_sf=draws, lost_sf=losses)

    if button_right():
        gc.collect()
        d_print(2, "GC before comms", gc.mem_free())

        ### This sound cue is really for other players
        sample.play("ready")

        my_choice = CHOICES[my_choice_idx]
        player_choices = [my_choice]

        ### Repeating key four times to make key for ChaCha20
        short_key = generateOTPadKey(8)
        key = enlargeKey(short_key, 4)
        d_print(3, "KEY", key)

        plain_bytes = bytesPad(my_choice, size=8, pad=0)
        cipher_bytes = encrypt(plain_bytes, key, "chacha20", nonce=nonce)
        enc_data_msg = RpsEncDataAdvertisement(enc_data=cipher_bytes,
                                               round_no=round_no)

        ### Wait for ready sound sample to stop playing
        sample.wait()
        sample.play("start-tx")
        sample.wait()
        sample.play("txing", loop=True)
        ### Players will not be synchronised at this point as they do not
        ### have to make their choices simultaneously - much longer 12 second
        ### time to accomodate this
        _, enc_data_by_addr, _ = broadcastAndReceive(ble,
                                                     enc_data_msg,
                                                     RpsEncDataAdvertisement,
                                                     RpsKeyDataAdvertisement,
                                                     scan_time=FIRST_MSG_TIME_S,
                                                     receive_n=num_other_players,
                                                     seq_tx=seq_tx,
                                                     seq_rx_by_addr=seq_rx_by_addr)

        key_data_msg = RpsKeyDataAdvertisement(key_data=short_key, round_no=round_no)
        ### All of the programs will be loosely synchronised now
        _, key_data_by_addr, _ = broadcastAndReceive(ble,
                                                     key_data_msg,
                                                     RpsEncDataAdvertisement,
                                                     RpsKeyDataAdvertisement,
                                                     RpsRoundEndAdvertisement,
                                                     scan_time=STD_MSG_TIME_S,
                                                     receive_n=num_other_players,
                                                     seq_tx=seq_tx,
                                                     seq_rx_by_addr=seq_rx_by_addr,
                                                     ads_by_addr=enc_data_by_addr)

        ### Play end transmit sound while doing next decrypt bit
        sample.play("end-tx")

        ### TODO tidy up comments here on the purpose of RoundEnd
        ### ???? With ackall RoundEnd has no purpose and wasn't really working as a substitute anyway
        re_msg = RpsRoundEndAdvertisement(round_no=round_no)
        ### The round end message is really about acknowledging receipt of the key
        ### by sending a message that holds non-critical information
        ### TODO - this one should only send for a few second, JoinGame should send for loads
        _, re_by_addr, _ = broadcastAndReceive(ble,
                                               re_msg,
                                               RpsEncDataAdvertisement,
                                               RpsKeyDataAdvertisement,
                                               RpsRoundEndAdvertisement,
                                               scan_time=LAST_ACK_TIME_S,
                                               receive_n=num_other_players,
                                               seq_tx=seq_tx,
                                               seq_rx_by_addr=seq_rx_by_addr,
                                               ads_by_addr=key_data_by_addr)

        ### This will have accumulated all the messages for this round
        allmsg_by_addr = re_by_addr

        ### Decrypt results
        ### If any data is incorrect the opponent_choice is left as None
        # TODO - get ride of [:]
        for p_idx1, playernm in enumerate(players):
            if p_idx1 == 0:
                continue  ### Only need to decrypt other players' data

            opponent_name, opponent_macaddr = playernm
            opponent_choice = None
            try:
                cipher_ads = list(filter(lambda ad: isinstance(ad[0], RpsEncDataAdvertisement),
                                  allmsg_by_addr[opponent_macaddr]))
                key_ads = list(filter(lambda ad: isinstance(ad[0], RpsKeyDataAdvertisement),
                               allmsg_by_addr[opponent_macaddr]))
                ### Two packets per class will be the packet and then packet
                ### with ackall set is received
                ### One packet will be the first packets lost but the second
                ### received with ack
                if len(cipher_ads) in (1, 2) and len(key_ads) in (1, 2):
                    cipher_bytes = cipher_ads[0][0].enc_data
                    round_msg1 = cipher_ads[0][0].round_no
                    key_bytes = key_ads[0][0].key_data
                    round_msg2 = key_ads[0][0].round_no
                    if round_no == round_msg1 == round_msg2:
                        key = enlargeKey(key_bytes, 4)
                        plain_bytes = decrypt(cipher_bytes, key, "chacha20", nonce=nonce)
                        opponent_choice = strUnpad(plain_bytes)
                    else:
                        print("Received wrong round for {:d} {:d}: {:d} {:d}",
                              opponent_name, round_no, round_msg1, round_msg2)
                else:
                    print("Missing packets: Summary: RpsEncDataAdvertisement "
                          "{:d} and RpsKeyDataAdvertisement {:d}".format(len(cipher_ads), len(key_ads)))
            except KeyError:
                pass
            player_choices.append(opponent_choice)

        ### Free up some memory by deleting data structures no longer needed
        del _, allmsg_by_addr, re_by_addr, key_data_by_addr, enc_data_by_addr
        gc.collect()
        d_print(2, "GC after comms", gc.mem_free())

        ### Ensure end-tx has completed
        sample.wait()

        ### Chalk up wins and losses - checks this player but also has to
        ### check other players against each other to calculate all the 
        ### scores for the high score table at the end of game
        for p_idx0, (p0_name, _) in enumerate(players[:len(players) - 1]):
            for p_idx1, (p1_name, _) in enumerate(players[p_idx0 + 1:], p_idx0 + 1):
                ### evaluateRound takes text strings for RPS
                (win, draw, void) = evaluateRound(player_choices[p_idx0],
                                                  player_choices[p_idx1])

                ### this_player is used to control incrementing the summary
                ### for the tally for this local player
                this_player = 0
                if p_idx0 == 0:
                    this_player = 1
                    try:
                        p0_ch_idx = CHOICES.index(player_choices[p_idx0])
                        p1_ch_idx = CHOICES.index(player_choices[p_idx1])
                        ### showPlayerVPlayer takes int index values for RPS
                        showPlayerVPlayer(display, pixels,
                                          p0_name, p1_name, p_idx1,
                                          p0_ch_idx, p1_ch_idx,
                                          win, draw, void)
                    except ValueError:
                        print("ERROR", "failed to decode",
                              player_choices[p_idx0], player_choices[p_idx1])

                if void:
                    voids += this_player
                elif draw:
                    draws += this_player
                    scores[p_idx0] += 1
                    scores[p_idx1] += 1
                elif win:
                    wins += this_player
                    scores[p_idx0] += 2
                else:
                    losses += this_player
                    scores[p_idx1] += 2

                d_print(2,
                        p0_name, player_choices[p_idx0], "vs",
                        p1_name, player_choices[p_idx1],
                        "win", win, "draw", draw, "void", void)

        print("Game {:d}, round {:d}, wins {:d}, losses {:d}, draws {:d}, "
              "void {:d}".format(game_no, round_no, wins, losses, draws, voids))

        round_no += 1
        new_round_init = True
