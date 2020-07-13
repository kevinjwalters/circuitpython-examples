### clue-simple-rpsgame v0.5
### CircuitPython rock paper scissors game over Bluetooth LE

### Tested with CLUE and Circuit Playground Bluefruit Alpha with TFT Gizmo
### and CircuitPython and 5.3.0

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
import os
import struct

import board
from displayio import Group
import terminalio
import digitalio

from adafruit_ble import BLERadio
from adafruit_ble.advertising import Advertisement, LazyObjectField
from adafruit_ble.advertising.standard import ManufacturerData, ManufacturerDataField

from adafruit_display_text.label import Label


### TODO
### Maybe simple version is clue only
### simple version still needs win indicator (flash text?) and a score counter

### Complex version demos how to
### work on cpb
### detect gizmo
### use neopixels as alternative display (light 1, 2, 3 discreetly (discrete joke)
### and maybe use Red, Purple, Sapphire for rock paper scissors

### simple version will have a lot of issues
### unreliable transport
### lack of synchronised win announcement
### got to decide whether to do the littany of crypto mistakes or not
### could include the lack of protocol and future proofing and cite
### LDAP as good example and git perhaps as less good
### complex format not compatible with simple format so mixing the two will confuse things


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

    ### Outputs
    if tftGizmoPresent():
        from adafruit_gizmo import tft_gizmo
        display = tft_gizmo.TFT_Gizmo()
    else:
        display = None

    ### Inputs
    ### buttons reversed if it is used upside-down with Gizmo
    _button_a = digitalio.DigitalInOut(board.BUTTON_A)
    _button_a.switch_to_input(pull=digitalio.Pull.DOWN)
    _button_b = digitalio.DigitalInOut(board.BUTTON_B)
    _button_b.switch_to_input(pull=digitalio.Pull.DOWN)
    if display is None:
        button_left = lambda: _button_a.value
        button_right = lambda: _button_b.value
    else:
        button_left = lambda: _button_b.value
        button_right = lambda: _button_a.value

else:
    ### CLUE with builtin screen (240x240)

    ### Outputs
    display = board.DISPLAY

    ### Inputs
    _button_a = digitalio.DigitalInOut(board.BUTTON_A)
    _button_a.switch_to_input(pull=digitalio.Pull.UP)
    _button_b = digitalio.DigitalInOut(board.BUTTON_B)
    _button_b.switch_to_input(pull=digitalio.Pull.UP)
    button_left = lambda: not _button_a.value
    button_right = lambda: not _button_b.value


choices = ("rock", "paper", "scissors")
my_choice_idx = 0

### Top y position of first choice and pixel separate between choices
top_y_pos = 60
choice_sep = 60

DIM_TXT_COL_FG = 0x505050
DEFAULT_TXT_COL_FG = 0xa0a0a0
CURSOR_COL_FG = 0xc0c000

def set_cursor(c_idx):
    """Set the position of the cursor on-screen to indicate the player's selection."""
    ### pylint: disable=global-statement
    global cursor_dob

    if 0 <= c_idx < len(choices):
        cursor_dob.y = top_y_pos + choice_sep * c_idx


if display is not None:
    ### The 6x14 terminalio classic font
    FONT_WIDTH, FONT_HEIGHT = terminalio.FONT.get_bounding_box()
    screen_group = Group(max_size=len(choices) * 2 + 1)

    for x_pos in (20, display.width // 2 + 20):
        y_pos = top_y_pos
        for label_text in choices:
            rps_dob = Label(terminalio.FONT,
                            text=label_text,
                            scale=2,
                            color=DEFAULT_TXT_COL_FG)
            rps_dob.x = x_pos
            rps_dob.y = y_pos
            y_pos += 60
            screen_group.append(rps_dob)

    cursor_dob = Label(terminalio.FONT,
                       text=">",
                       scale=3,
                       color=CURSOR_COL_FG)
    cursor_dob.x = 0
    set_cursor(my_choice_idx)
    cursor_dob.y = top_y_pos
    screen_group.append(cursor_dob)
    display.show(screen_group)

### From adafruit_ble.advertising
MANUFACTURING_DATA_ADT = 0xFF
ADAFRUIT_COMPANY_ID = 0x0822

### pylint: disable=line-too-long
### According to https://github.com/adafruit/Adafruit_CircuitPython_BLE/blob/master/adafruit_ble/advertising/adafruit.py
### 0xf000 (to 0xffff) is for range for Adafruit customers
RPS_ACK_ID = 0xfe30
RPS_DATA_ID = 0xfe31


class RpsAdvertisement(Advertisement):
    """Broadcast an RPS message.
       This is not connectable and elicits no scan_response based on defaults
       in Advertisement parent class."""

    flags = None

    _PREFIX_FMT = "<B" "BHBH"
    _DATA_FMT = "8s"  ### this NUL pads if necessary

    prefix = struct.pack(
        _PREFIX_FMT,
        struct.calcsize(_PREFIX_FMT) - 1,
        MANUFACTURING_DATA_ADT,
        ADAFRUIT_COMPANY_ID,
        struct.calcsize("<H" + _DATA_FMT),
        RPS_DATA_ID
    )
    manufacturer_data = LazyObjectField(
        ManufacturerData,
        "manufacturer_data",
        advertising_data_type=MANUFACTURING_DATA_ADT,
        company_id=ADAFRUIT_COMPANY_ID,
        key_encoding="<H",
    )

    test_string = ManufacturerDataField(RPS_DATA_ID, "<" + _DATA_FMT)
    """RPS choice."""

NS_IN_S = 1000 * 1000  * 1000
MIN_SEND_TIME_NS = 6 * NS_IN_S
MAX_SEND_TIME_S = 20
MAX_SEND_TIME_NS = MAX_SEND_TIME_S * NS_IN_S

MIN_AD_INTERVAL = 0.02001

ble = BLERadio()

opponent_choice = None

timeout = False
round_no = 1
wins = 0
losses = 0
draws = 0
voids = 0

TOTAL_ROUND = 5

def evaluate_game(mine, yours):
    """Determine who won the game based on the two strings mine and yours_lc.
       Returns three booleans (win, draw, void)."""
    ### Return with void at True if any input is None
    try:
        mine_lc = mine.lower()
        yours_lc = yours.lower()
    except AttributeError:
        return (False, False, True)

    r_win = r_draw = r_void = False
    ### pylint: disable=too-many-boolean-expressions
    if (mine_lc == "rock" and yours_lc == "rock"
            or mine_lc == "paper" and yours_lc == "paper"
            or mine_lc == "scissors" and yours_lc == "scissors"):
        r_draw = True
    elif (mine_lc == "rock" and yours_lc == "paper"):
        pass  ### r_win default is False
    elif (mine_lc == "rock" and yours_lc == "scissors"):
        r_win = True
    elif (mine_lc == "paper" and yours_lc == "rock"):
        r_win = True
    elif (mine_lc == "paper" and yours_lc == "scissors"):
        pass  ### r_win default is False
    elif (mine_lc == "scissors" and yours_lc == "rock"):
        pass  ### r_win default is False
    elif (mine_lc == "scissors" and yours_lc == "paper"):
        r_win = True
    else:
        r_void = True

    return (r_win, r_draw, r_void)


### Advertise for 20 seconds maximum and if a packet is received
### for 5 seconds after that
while True:
    if round_no > TOTAL_ROUND:
        print("Summary: ",
              "wins {:d}, losses {:d}, draws {:d}, void {:d}".format(wins, losses, draws, voids))

        ### Reset variables for another game
        round_no = 1
        wins = 0
        losses = 0
        draws = 0
        voids = 0
        round_no = 1

    if button_left():
        while button_left():
            pass
        my_choice_idx = (my_choice_idx + 1) % len(choices)
        if display is not None:
            set_cursor(my_choice_idx)

    if button_right():
        tx_message = RpsAdvertisement()

        choice = choices[my_choice_idx]
        tx_message.test_string = choice
        d_print(2, "TXing RTA", choice)

        ### Page 126 35.5 recommends an initial 30s of 20ms intervals
        ### https://developer.apple.com/accessories/Accessory-Design-Guidelines.pdf
        ### So this low value seems appropriate but interval=0.020 gives this
        ### _bleio.BluetoothError: Unknown soft device error: 0007
        ### 0.037 ok 0.021 ok 0.0201 ok 0.02001 ok - damn FP!!
        ## ble.start_advertising(tx_message, interval=0.02001)

        opponent_choice = None
        ble.start_advertising(tx_message, interval=MIN_AD_INTERVAL)
        sending_ns = time.monotonic_ns()

        ##print("ssssssssss")
        ##message.test32bit = "ssssssss"
        ##ble.start_advertising(message)
        ##time.sleep(5)
        ##ble.stop_advertising()

        ### timeout in seconds
        ### -100 is probably minimum, -128 would be 8bit signed min
        ### window and interval are 0.1 by default - same value means
        ### continuous scanning (sending Advertisement will interrupt this)
        for adv in ble.start_scan(RpsAdvertisement, minimum_rssi=-127,
                                  timeout=MAX_SEND_TIME_S):
            received_ns = time.monotonic_ns()
            d_print(2, "RXed RTA",
                    adv.test_string)
            opponent_choice_bytes = adv.test_string
            ### TODO - could write about for (NB!!) vs for else vs while
            idx = 0
            while idx < len(opponent_choice_bytes):
                if opponent_choice_bytes[idx] == 0:
                    break
                idx += 1
            opponent_choice = opponent_choice_bytes[0:idx].decode("utf-8")
            break  ### comment out for testing how many received

        ### We have received one message or exceeded MAX_SEND_TIME_S
        ble.stop_scan()

        ### Ensure we send our message for a minimum period of time
        ### constrained by the ultimate duration cap
        if opponent_choice is not None:
            timeout = False
            remaining_ns = MAX_SEND_TIME_NS - (received_ns - sending_ns)
            extra_ad_time_ns = min(remaining_ns, MIN_SEND_TIME_NS)
            ### Only sleep if we need to, the value here could be a small
            ### negative one too so this caters for this
            if extra_ad_time_ns > 0:
                sleep_t  = extra_ad_time_ns / NS_IN_S
                d_print(2, "Additional {:f} seconds of advertising".format(sleep_t))
                time.sleep(sleep_t)
        else:
            timeout = True

        ble.stop_advertising()

        d_print(1,"ROUND", round_no,
                "MINE", choice,
                "| OPPONENT", opponent_choice)
        (win, draw, void) = evaluate_game(choice, opponent_choice)
        if void:
            voids += 1
        elif draw:
            draws += 1
        elif win:
            wins += 1
        else:
            losses += 1
        d_print(1, "wins {:d}, losses {:d}, draws {:d}, void {:d}".format(wins, losses, draws, voids))
        round_no += 1

### Do something on screen or NeoPixels

print("GAME OVER")

while True:
    pass
