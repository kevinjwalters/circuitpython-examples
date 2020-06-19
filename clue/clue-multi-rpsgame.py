### clue-multi-rpsgame v0.25
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

from adafruit_display_text.label import Label

### https://github.com/adafruit/Adafruit_CircuitPython_BLE
from adafruit_ble import BLERadio
import _bleio  ### just for _bleio.BluetoothError

from rps_advertisements import JoinGameAdvertisement, \
                               RpsEncDataAdvertisement, \
                               RpsKeyDataAdvertisement, \
                               RpsRoundEndAdvertisement

from adafruit_ble.advertising import Advertisement  ### ONLY NEEDED FOR DEBUGGING
import adafruit_ble.advertising.standard  ### for encode_data and decode_data


### TODO
### Maybe simple version is clue only
### simple version still needs win indicator (flash text?) and a score counter

### TODO - deal with crypto flaw - maybe use XXTEA or ChaCha?

### TODO - bit of backlight fade down up between screens?

### TODO - left button to terminate scanning works on all but the penultimate device!!

### Complex version demos how to
### work on cpb
### detect gizmo
### use neopixels as alternative display (light 1, 2, 3 discreetly (discrete joke)
### and maybe use Red, Purple, Sapphire for rock paper scissors

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

### allow player to set their name - use accelerometer? JUST USING optional secrets.py for now 

### How does error detection (checksum) work on the payload? LOOKS THIS UP

### Split this into multiple files - could put Advertisement messages in file(s)
### Graphics might end up being a big lump of code?

### Going further
### - port to use Infrared for CPX - time.monotonic_ns need replacing (note CPB do not have infrared)

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
            print("No rps_name or ble_name entry found in secrets dict")
except ImportError:
    pass


debug = 3


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
###       and not use for buttons
if clue_less:
    ### CPB with TFT Gizmo (240x240)
    from adafruit_circuitplayground import cp

    ### Outputs
    if tftGizmoPresent():
        from adafruit_gizmo import tft_gizmo
        display = tft_gizmo.TFT_Gizmo()
        JG_RX_COL = 0x0000ff
    else:
        display = None
        JG_RX_COL = 0x000030  ### dimmer blue for upward facing CPB NeoPixels

    audio_out = AudioOut(board.SPEAKER)
    pixels = cp.pixels

    ### Enable the onboard amplifier for speaker
    cp._speaker_enable.value = True  ### pylint: disable=protected-access

    ### Inputs
    ### buttons reversed if it is used upside-down with Gizmo
    ##_button_a = digitalio.DigitalInOut(board.BUTTON_A)
    ##_button_a.switch_to_input(pull=digitalio.Pull.DOWN)
    ##_button_b = digitalio.DigitalInOut(board.BUTTON_B)
    ##_button_b.switch_to_input(pull=digitalio.Pull.DOWN)
    if display is None:
        ##button_left = lambda: _button_a.value
        ##button_right = lambda: _button_b.value
        button_left = lambda: cp.button_a
        button_right = lambda: cp.button_b

    else:
        ##button_left = lambda: _button_b.value
        ##button_right = lambda: _button_a.value
        button_left = lambda: cp.button_b
        button_right = lambda: cp.button_a

else:
    ### CLUE with builtin screen (240x240)
    from adafruit_clue import clue

    ### Outputs
    display = board.DISPLAY
    audio_out = AudioOut(board.SPEAKER)
    pixels = clue.pixel
    JG_RX_COL = 0x0000ff

    ### Inputs
    ##_button_a = digitalio.DigitalInOut(board.BUTTON_A)
    ##_button_a.switch_to_input(pull=digitalio.Pull.UP)
    ##_button_b = digitalio.DigitalInOut(board.BUTTON_B)
    ##_button_b.switch_to_input(pull=digitalio.Pull.UP)
    ##button_left = lambda: not _button_a.value
    ##button_right = lambda: not _button_b.value
    button_left = lambda: clue.button_a
    button_right = lambda: clue.button_b

### This will always by the top level group passed to display.show()
main_display_group = None

IMAGE_DIR = "rps/images"
AUDIO_DIR = "rps/audio"

### Tidy up memory then make one audio buffer for reading files to stop
### memory allocation per execution of WaveFile which was failing with
### MemoryError exceptions
gc.collect()
### TODO - see if there is a workaround for this serious bug
### https://github.com/adafruit/circuitpython/issues/3030
##file_buf = bytearray(2048)

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


def readyAudioSamples():
    """Open files from AUDIO_DIR and return a dict with FileIO objects
       or None if file not present."""
    files = (("searching", "welcome-to", "arena", "ready")
              + ("rock", "paper", "scissors")
              + ("rock-scissors", "paper-rock", "scissors-paper")
              + ("you-win", "draw", "you-lose")
              + ("humiliation", "excellent"))

    fhs = {}
    for file in files:
        wav_file = None
        try:
            wav_file = open(AUDIO_DIR + "/" + file + ".wav", "rb")
        except OSError as oe:
            ### OSError: [Errno 2] No such file/directory: 'filename.ext'
            pass
        fhs[file] = wav_file
    return fhs

### Check and open up audio wav samples
audio_files = readyAudioSamples()

### Top y position of first choice and pixel separate between choices
top_y_pos = 60
choice_sep = 60

BLUE=0x0000ff
BLACK=0x000000

DIM_TXT_COL_FG = 0x505050
DEFAULT_TXT_COL_FG = 0xa0a0a0
CURSOR_COL_FG = 0xc0c000
IWELCOME_COL_FG = 0x000020
WELCOME_COL_FG = 0x0000f0
BWHITE_COL_FG = 0xffffff
PLAYER_NAME_COL_FG = 0xc0c000
PLAYER_NAME_COL_BG = BLACK
OPP_NAME_COL_FG = 0x00c0c0
OPP_NAME_COL_BG = BLACK
ERROR_COL_FG = 0xff0000

RED_COL = 0xff0000
ORANGE_COL = 0xff8000
YELLOW_COL = 0xffff00

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
### NeoPixel positions for R, P, S - avoid 2 as it's under finger
CHOICE_POS = (0,     ### The one just left of USB connector
              9, 8)  ### The two just right of it

### Set to True for blue flashing when devices are annoucing players' names
JG_FLASH = True  ### TODO DISABLE THIS FOR THE ADAFRUIT RELEASE

if display is not None:
    ### The 6x14 terminalio classic font
    FONT_WIDTH, FONT_HEIGHT = terminalio.FONT.get_bounding_box()
    DISPLAY_WIDTH = display.width
    DISPLAY_HEIGHT = display.height


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


### TODO - probably no longer used...
def setCursor(idx):
    """Set the position of the cursor on-screen to indicate the player's selection."""
    global cursor_dob

    if 0 <= idx < len(CHOICES):
        cursor_dob.y = top_y_pos + choice_sep * idx


def showChoice(ch_idx, disp, pix):
    """TODO DOC"""
    global main_display_group

    if disp is None:
        pix.fill(BLACK)
        pix[CHOICE_POS[ch_idx]] = CHOICE_COL[ch_idx]
    else:
        emptyGroup(main_display_group)
        ### Would be slightly better to create this Group once and re-use it
        choice_group = Group(max_size=1)

        s_group = Group(scale=3, max_size=1)
        s_group.x = 32
        s_group.y = (DISPLAY_HEIGHT - 3 * SPRITE_SIZE) // 2 

        s_group.append(sprites[ch_idx])
        choice_group.append(s_group)

        main_display_group = choice_group
        disp.show(main_display_group)


def introduction(disp, pix):
    """Introduction screen."""
    global main_display_group

    if disp is not None:
        emptyGroup(main_display_group)  ### this should already be empty
        intro_group = Group(max_size=5)
        welcometo_dob = Label(terminalio.FONT,
                              text="Welcome To",
                              scale=3,
                              color=IWELCOME_COL_FG)
        welcometo_dob.x = (DISPLAY_WIDTH - 10 * 3 * FONT_WIDTH) // 2
        ### Y pos on screen looks lower than I would expect
        welcometo_dob.y = 3 * FONT_HEIGHT // 2
        intro_group.append(welcometo_dob)

        spacing = 3 * SPRITE_SIZE + 4
        for idx, sprite in enumerate(sprites):
            s_group = Group(scale=3, max_size=1)
            s_group.x = -96    
            s_group.y = (DISPLAY_HEIGHT - 3 * SPRITE_SIZE) // 2 + (idx - 1) * spacing
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
    audio_out.play(WaveFile(audio_files["welcome-to"]))
    while audio_out.playing:
        if disp is not None and intro_group[0].color < WELCOME_COL_FG:
            intro_group[0].color += 0x10
            time.sleep(0.120)

    onscreen_x_pos = 96
    ### Rock
    if disp is None:
        showChoice(0, disp, pix)
    audio_out.play(WaveFile(audio_files["rock"]))
    while audio_out.playing:
        if disp is not None:
            if intro_group[1].x < onscreen_x_pos:
                intro_group[1].x += 10
                time.sleep(0.050)

    ### Paper
    if disp is None:
        showChoice(1, disp, pix)
    audio_out.play(WaveFile(audio_files["paper"]))
    while audio_out.playing:
        if disp is not None:
            if intro_group[2].x < onscreen_x_pos:
                intro_group[2].x += 11
                time.sleep(0.050) 

    ### Scissors
    audio_out.play(WaveFile(audio_files["scissors"]))
    if disp is None:
        showChoice(2, disp, pix)
    while audio_out.playing:
        if disp is not None:
            if intro_group[3].x < onscreen_x_pos:
                intro_group[3].x += 7
                time.sleep(0.050)

    ### Set NeoPixels back to black
    if disp is None:
        pix.fill(BLACK)

    audio_out.play(WaveFile(audio_files["arena"]))
    while audio_out.playing:
        if disp is not None and intro_group[4].color < WELCOME_COL_FG:
            intro_group[4].color += 0x10
            time.sleep(0.060)

    audio_out.stop()
    ### TODO - I think I need to explicitly remove the sprites
    ### from the groups to allow them to be reused or fully empty everything.

    ### TODO - add text to explain how the game actually works!


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

    ## cursor_dob = Label(terminalio.FONT,
    ##                   text=">",
    ##                   scale=3,
    ##                   color=CURSOR_COL_FG)
    ##cursor_dob.x = 0
    ## setCursor(my_choice_idx)
    ##cursor_dob.y = top_y_pos
    ##gameround_group.append(cursor_dob)
    ##display.show(gameround_group)


def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


NS_IN_S = 1000 * 1000  * 1000
MIN_SEND_TIME_NS = 6 * NS_IN_S
MAX_SEND_TIME_S = 20
NORM_SEND_TIME_S = 4
MAX_SEND_TIME_NS = MAX_SEND_TIME_S * NS_IN_S

### 20ms is the minimum delay between advertising packets
### in Bluetooth Low Energy
### extra 10us deals with API floating point rounding issues
MIN_AD_INTERVAL = 0.02001
INTERVAL_TICKS = (33, 37, 41, 43, 47)  ### Do not use 32 here due to fp issues
INTERVAL_TICK_MS = 0.625

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

TOTAL_ROUNDS = 5


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
    if (mine == "rock" and yours == "rock" or
        mine == "paper" and yours == "paper" or
        mine == "scissors" and yours == "scissors"):
        draw = True
    elif (mine == "rock" and yours == "paper"):
        lose = True
    elif (mine == "rock" and yours == "scissors"):
        win = True
    elif (mine == "paper" and yours == "rock"):
        win = True
    elif (mine == "paper" and yours == "scissors"):
        lose = True
    elif (mine == "scissors" and yours == "rock"):
        lose = True
    elif (mine == "scissors" and yours == "paper"):
        win = True
    else:
        void = True

    return (win, draw, void)


wav_victory_name = { "rp": "paper-rock",
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

    return wav_victory_name.get(mine + yours)


### Networking bits BEGIN

def max_ack(acklist):
    """Return the highest ack number from a contiguous run.
       Returns 0 for an empty list."""

    if len(acklist) == 0:
        return 0
    elif len(acklist) == 1:
        return acklist[0]

    ordered_acklist = sorted(acklist)
    max_ack_sofar = ordered_acklist[0]
    for ack in ordered_acklist[1:]:
        if ack - max_ack_sofar > 1:
            break
        max_ack_sofar = ack
    return max_ack_sofar


def startScan(send_ad, send_advertising,
              sequence_number, receive_n,
              ss_rx_ad_classes, rx_ad_classes,
              scan_time, interval,
              match_locally, scan_response_request,
              enable_ack, awaiting_allrx, awaiting_allacks,
              ad_cb, name_cb, endscan_cb,
              received_ads_by_addr, blenames_by_addr,
              send_ad_rxs, acks):
    """TODO - explain what this does and think about it writing the explanation
       to ensure it all makes sense."""
    complete = False

    if send_advertising:
        try:
            ble.start_advertising(send_ad, interval=interval)
        except _bleio.BluetoothError:
            pass  ### catch and ignore "Already advertising."

    ### timeout in seconds
    ### -100 is probably minimum, -128 would be 8bit signed min
    ### window and interval are 0.1 by default - same value means
    ### continuous scanning
    cls_send_ad = type(send_ad)
    matching_ads = 0
    for adv_ss in ble.start_scan(*ss_rx_ad_classes,
                                 ## minimum_rssi=-120,
                                 buffer_size=1536,   ### default is 512 - JoinGame packet loss experiment
                                 active=scan_response_request,
                                 timeout=scan_time):
        received_ns = time.monotonic_ns()
        addr_text = addr_to_text(adv_ss.address.address_bytes)

        ### Add name of the device to dict limiting
        ### this to devices of interest by checking received_ads_by_addr
        ### plus pass data to any callback function
        if (addr_text not in blenames_by_addr
            and addr_text in received_ads_by_addr):
            name = adv_ss.complete_name  ### None indicates no value
            if name:  ### This test ignores any empty strings too
                blenames_by_addr[addr_text] = name
                if name_cb is not None:
                    name_cb(name, addr_text, adv_ss.address, adv_ss)

        ### If using application Advertisement type matching then
        ### check the Advertisement's prefix and continue for loop if it
        ### does not match
        if match_locally:
            d_print(5, "RXed RTA", addr_text, repr(adv_ss))
            adv_ss_as_bytes = adafruit_ble.advertising.standard.encode_data(adv_ss.data_dict)
            adv = None
            for cls in rx_ad_classes:
                prefix = cls.prefix
                ### TODO - this does not implement proper matching
                ### proper matching would involve parsing prefix and then matching each
                ### resulting prefix against each dict entry from decode_data()
                ### starting at 1 skips over the message length value
                if adv_ss_as_bytes[1:len(prefix)] == prefix[1:]:
                    adv = cls()
                    ### Only populating fields in use
                    adv.data_dict = adafruit_ble.advertising.standard.decode_data(adv_ss_as_bytes)
                    adv.address = adv_ss.address
                    d_print(4, "RXed mm RTA", addr_text, adv)
                    break

            if adv is None:
                if endscan_cb is not None and endscan_cb(addr_text, adv_ss.address, adv_ss):
                    complete = True
                    break
                else:
                    continue
        else:
            adv = adv_ss
            d_print(4, "RXed RTA", addr_text, adv)

        ### Must be a match if this is reached
        matching_ads += 1
        if ad_cb is not None:
            ad_cb(addr_text, adv.address, adv)

        ### Look for an ack and record it in acks if not already there
        if hasattr(adv, "ack") and isinstance(adv.ack, int):
            d_print(4, "Found ack")
            if addr_text not in acks:
                acks[addr_text] = [adv.ack]
            elif adv.ack not in acks[addr_text]:
                acks[addr_text].append(adv.ack)

        if addr_text in received_ads_by_addr:
            this_ad_b = bytes(adv)
            for existing_ad in received_ads_by_addr[addr_text]:
                if this_ad_b == existing_ad[1]:
                    break  ### already present
            else:  ### Python's unusual for/break/else 
                received_ads_by_addr[addr_text].append((adv, bytes(adv)))
                if isinstance(adv, cls_send_ad):
                    send_ad_rxs[addr_text] = True
        else:
            received_ads_by_addr[addr_text] = [(adv, bytes(adv))]
            if isinstance(adv, cls_send_ad):
                send_ad_rxs[addr_text] = True

        d_print(5, "send_ad_rxs", len(send_ad_rxs), "ack", len(acks))

        if awaiting_allrx:
            if receive_n > 0 and len(send_ad_rxs) == receive_n:
                if enable_ack and sequence_number is not None:
                    awaiting_allrx = False
                    awaiting_allacks = True
                    if send_advertising:
                        ble.stop_advertising()
                    d_print(4, "old ack", send_ad.ack, "new ack", sequence_number)
                    send_ad.ack = sequence_number
                    if send_advertising:
                        ble.start_advertising(send_ad, interval=interval)
                    d_print(3, "TXing with ack", send_ad,
                            "ack_count", len(acks))
                else:
                    complete = True
                    break  ### packets received but not sending ack nor waiting for acks
        elif awaiting_allacks:
            if len(acks) == receive_n:
                ack_count = 0
                for addr_text, acks_for_addr in acks.items():
                    if max_ack(acks_for_addr) >= sequence_number:
                        ack_count += 1
                if ack_count == receive_n:
                    complete = True
                    break  ### all acks received, can stop transmitting now

        if endscan_cb is not None:
            if endscan_cb(addr_text, adv_ss.address, adv_ss):
                complete = True
                break

    return (complete, matching_ads, awaiting_allrx, awaiting_allacks)


def broadcastAndReceive(send_ad,
                        *receive_ads_types,
                        scan_time=NORM_SEND_TIME_S,
                        receive_n=0,
                        seq_tx=None,
                        seq_rx_by_addr=None,
                        match_locally=True,
                        scan_response_request=False,
                        ad_cb=None,
                        ads_by_addr={},
                        names_by_addr={},
                        name_cb=None,
                        endscan_cb=None
                        ):
    """Send an Advertisement sendad and then wait max_time seconds to receive_n
       receive_n Advertisements from other devices.
       If receive_n is 0 then wait for the remaining max_time.
       Returns list of received Advertisements not necessarily in arrival order and
       dictionary indexed by the compressed text representation of the address with a list
       of tuples of (advertisement, bytes(advertisement)).
       This MODIFIES send_ad by setting sequence_number and ack if those
       properties are present."""

    sequence_number = None
##    acked = None    ### not used - what was this for?
    if seq_tx is not None and hasattr(send_ad, "sequence_number"):
        sequence_number = seq_tx[0]
        send_ad.sequence_number = sequence_number
        seq_tx[0] += 1

        ## acked = False   ### not used - what was this for?

    ### Page 126 35.5 recommends an initial 30s of 20ms intervals
    ### https://developer.apple.com/accessories/Accessory-Design-Guidelines.pdf
    ### So this low value seems appropriate but interval=0.020 gives this
    ### _bleio.BluetoothError: Unknown soft device error: 0007
    ### 0.037 ok 0.021 ok 0.0201 ok 0.02001 ok - damn FP!!
    ## ble.start_advertising(tx_message, interval=0.02001)

    ### A dict to store unique Advertisement indexed by mac address
    ### as text string
    cls_send_ad = type(send_ad)
    received_ads_by_addr = dict(ads_by_addr)  ### Will not be a deep copy
    if receive_ads_types:
        rx_ad_classes = receive_ads_types
    else:
        rx_ad_classes = (cls_send_ad,)

    if match_locally:
        ss_rx_ad_classes = (Advertisement,)
    else:
        ss_rx_ad_classes = rx_ad_classes

    blenames_by_addr = dict(names_by_addr)  ### Will not be a deep copy

    ### Look for packets already received of the cls_send_ad class (type)
    send_ad_rxs = {}
    ### And make a list of sequence numbers already acknowledged
    acks = {}
    for addr_text, adsnb_per_addr in received_ads_by_addr.items():
        if cls_send_ad in [type(andb[0]) for andb in adsnb_per_addr]:
            send_ad_rxs[addr_text] = True

        ### Pick out any Advertisements with an ack field with a value
        acks_thisaddr = list(filter(lambda adnb: hasattr(adnb[0], "ack")
                                                 and isinstance(adnb[0].ack, int),
                                    adsnb_per_addr))
        ### list() must have been run on acks_thisaddr to expand iterator
        if acks_thisaddr:
            seqs = [adnb[0].ack for adnb in acks_thisaddr]
            acks[addr_text] = seqs
            d_print(5, "Acks received for", addr_text,
                    "of", seqs, "in", acks_thisaddr)

    ### Determine whether there is a second phase of sending acks
    enable_ack = hasattr(send_ad, "ack")
    ### Set an initial ack for anything previously received
    if enable_ack and acks:
        send_ad.ack = max(max(li) for li in acks.values())
    awaiting_allacks = False
    awaiting_allrx = True

    ### TODO - leftover from previous experiment playing with interval times
    ##interval = INTERVAL_TICKS[random.randrange(len(INTERVAL_TICKS))] * INTERVAL_TICK_MS / 1e3
    interval = MIN_AD_INTERVAL
    d_print(2, "TXing", send_ad, "interval", interval)
    matched_ads = 0
    complete = False
    d_print(1, "Listening for", ss_rx_ad_classes)
    start_ns = time.monotonic_ns()
    target_end_ns = start_ns + round(scan_time * NS_IN_S)
    advertising_duration = 0.0
    
    while not complete and time.monotonic_ns() < target_end_ns:
        a_rand = random.random()
        if a_rand < 0.4:
            send_advertising = False
            duration = 0.5 + 1.25 * a_rand  ### 50-100ms
        else:
            send_advertising = True
            duration = 0.9  ### 900ms
            advertising_duration += duration

        (complete, ss_matched,
         awaiting_allrx,
         awaiting_allacks) = startScan(send_ad, send_advertising,
                                       sequence_number, receive_n,
                                       ss_rx_ad_classes, rx_ad_classes,
                                       duration, interval,
                                       match_locally, scan_response_request,
                                       enable_ack, awaiting_allrx, awaiting_allacks,
                                       ad_cb, name_cb, endscan_cb,
                                       received_ads_by_addr, blenames_by_addr,
                                       send_ad_rxs, acks)
        matched_ads += ss_matched

    if advertising_duration > 0.0:
        ble.stop_advertising()
    ble.stop_scan()
    d_print(2, "Matched ads", matched_ads)

    end_send_ns = time.monotonic_ns()
    d_print(4, "TXRX time", (end_send_ns - start_ns) / 1e9)

    ### Make a single list of all the received adverts from the dict
    received_ads = []
    for ads in received_ads_by_addr.values():
        ### Pick out the first value, second value is just bytes() version
        received_ads.extend([a[0] for a in ads])
    return (received_ads, received_ads_by_addr, blenames_by_addr)

### Networking bits END


def bytes_pad(text, size=8, pad=0):
    """Convert a string to bytes and add pad value if necessary to make the length up to size.
       """
    text_as_bytes = text.encode("utf-8")
    if len(text_as_bytes) >= size:
        return text_as_bytes
    else:
        return text_as_bytes + bytes([pad] * (size - len(text_as_bytes)))


def str_unpad(text_as_bytes, pad=0):
    """Convert a bytes to a str removing trailing characters matching pad."""
    if pad is not None:
        end_ex = len(text_as_bytes)
        while end_ex > 0 and text_as_bytes[end_ex - 1] == pad:
            end_ex -= 1

    return text_as_bytes[0:end_ex].decode("utf-8")


def generateOTPadKey(n_bytes):
    """Generate a random key of n_bytes bytes returned as type bytes.
       This uses the hardware TNG on boards using the nRF52840
       and the PRNG on others.
       """
    try:
        key = os.urandom(n_bytes)
    except NotImplementedError:
        key = bytes([random.getrandbits(8) for _ in range(n_bytes)])
    return key


def encrypt(plain_text, key, algorithm):
    """Encrypt plain_text bytes with key bytes using algorithm.
       Algorithm "xor" can be used for stream ciphers.
    """
    if algorithm == "xor":
        return bytes([plain_text[i] ^ key[i] for i in range(len(plain_text))])
    else:
        return ValueError("Algorithm not implemented")


def decrypt(cipher_text, key, algorithm):
    """Decrypt plain_text bytes with key bytes using algorithm.
       Algorithm "xor" can be used for stream ciphers.
    """
    if algorithm == "xor":
        return encrypt(cipher_text, key, "xor")  ### enc/dec are same
    else:
        return ValueError("Algorithm not implemented")


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


def addr_to_text(mac_addr, big_endian=False, sep=""):
    """Convert a mac_addr in bytes to text."""
    return sep.join(["{:02x}".format(b)
                     for b in (mac_addr if big_endian else reversed(mac_addr))])


def flashNP(pix, col):
    """A very brief flash of the NeoPixels."""
    pix.fill(col)
    pix.fill(BLACK)


def showGameResult():
    pass


def showPlayerVPlayerScreen(disp, me_name, op_name, my_ch_idx, op_ch_idx,
                            result, summary, win, draw, void):
    global main_display_group

    emptyGroup(main_display_group)
    if result is not None:
        pass  ### audio causing MemoryError due to bug - TODO
        ### audio_out.play(WaveFile(audio_files[result]))
    
    if void:
        ### Put error message on screen
        error_dob = Label(terminalio.FONT,
                          text="Communication\nError!",
                          scale=3,
                          color=ERROR_COL_FG)

        main_display_group = error_dob
        disp.show(main_display_group)
    else:
        ### Would be slightly better to create this Group once and re-use it
        pvp_group = Group(max_size=3)

        ### Add player's name and sprite just off left side of screen
        ### and opponent's just off right
        player_detail = [(me_name, sprites[my_ch_idx], -16 - 3 * SPRITE_SIZE,
                          PLAYER_NAME_COL_FG, PLAYER_NAME_COL_BG),
                         (op_name, opp_sprites[op_ch_idx], 16 + DISPLAY_WIDTH,
                          OPP_NAME_COL_FG, OPP_NAME_COL_BG)]
        pvp_spritentxt = []

        for (name, sprite,
             start_x,
             fg, bg) in player_detail:
            s_group = Group(scale=3, max_size=2)
            s_group.x = start_x
            s_group.y = (DISPLAY_HEIGHT - 3 * SPRITE_SIZE) // 2   ### TODO

            s_group.append(sprite)
            p_name_dob = Label(terminalio.FONT,
                               text=name,
                               scale=1,
                               color=fg,
                               background_color=bg)
            p_name_dob.y = 20  ### TODO - work out best way to place and centre this
            s_group.append(p_name_dob)

            pvp_spritentxt.append(s_group)
            
        ### The order in Group determines which one is on top
        for spr in (reversed(pvp_spritentxt) if win else pvp_spritentxt):
            pvp_group.append(spr)

        summary_dob = Label(terminalio.FONT,
                           text="---.----",
                           scale=2,
                           color=BLACK)
        summary_dob.y = 200  ### TODO - work out best way to place and centre this
        pvp_group.append(summary_dob)

        main_display_group = pvp_group
        disp.show(main_display_group)
        if draw:
            ### TODO - Sprite bounce off each other
            for idx in range(16):
                pvp_spritentxt[0].x += 5
                pvp_spritentxt[1].x -= 5
                time.sleep(0.1)
        else:
            ### Move sprites together, winning sprite overlaps loser
            for idx in range(16):
                pvp_spritentxt[0].x += 10
                pvp_spritentxt[1].x -= 10
                time.sleep(0.1)
        
        while audio_out.playing:  ### Wait for first sample to finish
            pass

        if not void:
            if summary is not None:
                pass  ### audio causing MemoryError due to bug - TODO
                ### audio_out.play(WaveFile(audio_files[summary]))
            if draw:
                sum_text = "Draw"
            elif win:
                sum_text = "You win"
            else:
                sum_text = "You lose"
            summary_dob.text = sum_text
            ### summary_.x   TODO - centre it

            if not draw and not win:
                colours = [RED_COL, ORANGE_COL, YELLOW_COL] * 5 + [RED_COL]
            else:
                colours = [0x0000f0 * sc // 16 for sc in range(1, 16 + 1)]
            for col in colours:
                summary_dob.color = col
                time.sleep(0.1)

            while audio_out.playing:  ### Ensure second sample has completed
                pass
        
        audio_out.stop()
        

def showPlayerVPlayerNeoPixels(pix, op_idx, my_ch_idx, op_ch_idx,
                               result, summary, win, draw, void):
    pass


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

    if disp is None:
        showPlayerVPlayerNeoPixels(pix, op_idx, my_ch_idx, op_ch_idx,
                                   result_wav, summary_wav, win, draw, void)
    else:
        showPlayerVPlayerScreen(disp, me_name, op_name, my_ch_idx, op_ch_idx,
                                result_wav, summary_wav, win, draw, void)


### Make a list of all the player's (name, mac address as text)
### with this player as first entry
players = []
my_name = ble.name
add_player(my_name, addr_to_text(ble.address_bytes), None, None)

### Join Game
### TODO - could have a callback to check for player terminate, i.e. 
###        could allow player to press button to say "i have got everyone"

audio_out.play(WaveFile(audio_files["searching"]), loop=True)
jg_msg = JoinGameAdvertisement(game="RPS")
other_player_ads, other_player_ads_by_addr, _ = broadcastAndReceive(jg_msg,
                                                                    scan_time=MAX_SEND_TIME_S,
                                                                    scan_response_request=True,
                                                                    ad_cb=lambda _a, _b, _c: flashNP(pixels, JG_RX_COL) if JG_FLASH else None,
                                                                    endscan_cb=lambda _a, _b, _c: button_left(),
                                                                    name_cb=add_player)
audio_out.stop()

num_other_players = len(players) - 1
d_print(2, "PLAYER ADS", other_player_ads_by_addr)
d_print(1, "PLAYERS", players)

### Sequence numbers - real packets start at 1
seq_tx = [1]  ### The next number to send
seq_rx_by_addr = {pma: 0 for pn, pma in players[1:]}  ### Per address received all up to

new_round_init = True

### Advertise for 20 seconds maximum and if a packet is received
### for 5 seconds after that
while True:
    if round_no > TOTAL_ROUNDS:
        print("Summary: ",
              "wins {:d}, losses {:d}, draws {:d}, void {:d}\n\n".format(wins, losses, draws, voids))

        ### Reset variables for another game
        round_no = 1
        wins = 0
        losses = 0
        draws = 0 
        voids = 0
        game_no += 1

    if new_round_init:
        ### Make a new initial random choice for the player and show it
        my_choice_idx = random.randrange(len(CHOICES))
        showChoice(my_choice_idx, display, pixels)
        new_round_init = False

    if button_left():
        while button_left():  ### Wait for button release
            pass
        my_choice_idx = (my_choice_idx + 1) % len(CHOICES)
        showChoice(my_choice_idx, display, pixels)

    if button_right():
        if debug >= 2:
            d_print(2, "NO collect mem_free ", gc.mem_free())

        ### TODO - this keeps blowing up with 2k allocation on CLUE despite there being 15-20k free - fragmentation??
        ###        could stop importing clue and DIY?  Would 16bit samples help?
        ### This sound cue is really for other players
        ### TODO file_buf should help massively here but waiting for further analysis on
        ### https://github.com/adafruit/circuitpython/issues/3030
        ### audio_out.play(WaveFile(audio_files["ready"]))   ### disable until file_buf ok

        my_choice = CHOICES[my_choice_idx]
        player_choices = [my_choice]

        otpad_key = generateOTPadKey(8)  ### TODO - replace with something
        d_print(3, "KEY", otpad_key)  ### TODO - discuss in the Code Discussion

        plain_bytes = bytes_pad(my_choice, size=8, pad=0)
        cipher_bytes = encrypt(plain_bytes, otpad_key, "xor")
        enc_data_msg = RpsEncDataAdvertisement(enc_data=cipher_bytes,
                                               round_no=round_no)

        ### Wait for sound sample to stop playing
        while audio_out.playing:
            pass
        audio_out.stop()
        ### Players will not be synchronised at this point as they do not
        ### have to make their choices simultaneously
        _, enc_data_by_addr, _ = broadcastAndReceive(enc_data_msg,
                                                     RpsEncDataAdvertisement,
                                                     RpsKeyDataAdvertisement,
                                                     scan_time=NORM_SEND_TIME_S*2,
                                                     receive_n=num_other_players,
                                                     seq_tx=seq_tx,
                                                     seq_rx_by_addr=seq_rx_by_addr)

        key_data_msg = RpsKeyDataAdvertisement(key_data=otpad_key, round_no=round_no)
        ### All of the programs will be loosely synchronised now
        _, key_data_by_addr, _ = broadcastAndReceive(key_data_msg,
                                                     RpsEncDataAdvertisement,
                                                     RpsKeyDataAdvertisement,
                                                     RpsRoundEndAdvertisement,
                                                     scan_time=NORM_SEND_TIME_S,
                                                     receive_n=num_other_players,
                                                     seq_tx=seq_tx,
                                                     seq_rx_by_addr=seq_rx_by_addr,
                                                     ads_by_addr=enc_data_by_addr)

        ### TODO tidy up comments here on the purpose of RoundEnd
        ### ???? With ackall RoundEnd has no purpose and wasn't really working as a substitute anyway
        re_msg = RpsRoundEndAdvertisement(round_no=round_no)
        ### The round end message is really about acknowledging receipt of the key
        ### by sending a message that holds non-critical information
        ### TODO - this one should only send for a few second, JoinGame should send for loads
        _, re_by_addr, _ = broadcastAndReceive(re_msg,
                                               RpsEncDataAdvertisement,
                                               RpsKeyDataAdvertisement,
                                               RpsRoundEndAdvertisement,
                                               scan_time=1.5,
                                               receive_n=num_other_players,
                                               seq_tx=seq_tx,
                                               seq_rx_by_addr=seq_rx_by_addr,
                                               ads_by_addr=key_data_by_addr)

        ### This will have accumulated all the messages for this round
        ##allmsg_by_addr = key_data_by_addr
        allmsg_by_addr = re_by_addr

        ### Decrypt results
        ### - if any data is incorrect the opponent_choice is left as None
        for p_idx1, playernm in enumerate(players[1:], 1):
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
                        plain_bytes = decrypt(cipher_bytes, key_bytes, "xor")
                        opponent_choice = str_unpad(plain_bytes)
                    else:
                        print("Received wrong round for {:d} {:d}: {:d} {:d}",
                              opponent_name, round_no, round_msg1, round_msg2)
                else:
                    print("Missing packets: Summary: RpsEncDataAdvertisement "
                          "{:d} and RpsKeyDataAdvertisement {:d}".format(len(cipher_ads), len(key_ads)))
            except KeyError:
                pass
            player_choices.append(opponent_choice)

        ### Chalk up wins and losses
        for p_idx1, playernm in enumerate(players[1:], 1):
            opponent_name, opponent_macaddr = playernm
            (win, draw, void) = evaluateRound(my_choice, player_choices[p_idx1])
            try:
                op_choice_idx = CHOICES.index(player_choices[p_idx1])
            except ValueError:
                op_choice_idx = None
            showPlayerVPlayer(display, pixels,
                              my_name, opponent_name, p_idx1,
                              my_choice_idx, op_choice_idx,
                              win, draw, void)
            d_print(1, players[0][0], player_choices[0], "vs",
                    opponent_name, player_choices[p_idx1],
                    "win", win, "draw", draw, "void", void)
            if void:
                voids += 1
            elif draw:
                draws += 1
            elif win:
                wins += 1
            else:
                losses += 1
        print("Game {:d}, round {:d}, wins {:d}, losses {:d}, draws {:d},"
              "void {:d}".format(game_no, round_no, wins, losses, draws, voids))
        round_no += 1
        new_round_init = True

### Not currently reached!
print("wins {:d}, losses {:d}, draws {:d}, void {:d}".format(wins, losses, draws, voids))

### Do something on screen or NeoPixels
print("GAME OVER")

while True:
    pass
