### clue-multi-rpsgame v0.8
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
from displayio import Group
import terminalio
import digitalio

from adafruit_display_text.label import Label

### https://github.com/adafruit/Adafruit_CircuitPython_BLE
from adafruit_ble import BLERadio

from rps_advertisements import JoinGameAdvertisement, \
                               RpsEncDataAdvertisement, \
                               RpsKeyDataAdvertisement, \
                               RpsRoundEndAdvertisement

### BUGS
### The protocol is flawed, after receiving packets from other players it stops
### transmitting its own data but this may not have been received

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
### need sequence number for packets and acks
### need higher level round numbers to detect out of synch
### need to work out who is who with N player games
### probably not deal with players who join midway?
### need to allocate player numbers - could sort by MAC
### avoid election algorithms even if tempted
### got to decide whether to do the littany of crypto mistakes or not
### could do own crypto
### could include the lack of protocol and future proofing and cite
### LDAP as good example and git perhaps as less good
### complex format not compatible with simple format so mixing the two will confuse things

### allow player to set their name - use accelerometer

### How does error detection (checksum) work on the payload?

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
    ##from adafruit_circuitplayground import cp

    ### Outputs
    if tftGizmoPresent():
        from adafruit_gizmo import tft_gizmo
        display = tft_gizmo.TFT_Gizmo()
    else:
        display = None
    ##audio_out = AudioOut(board.SPEAKER)
    ##pixels = cp.pixels

    ### Enable the onboard amplifier for speaker
    ##cp._speaker_enable.value = True  ### pylint: disable=protected-access

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
    ##from adafruit_clue import clue

    ### Outputs
    display = board.DISPLAY
    ##audio_out = AudioOut(board.SPEAKER)
    ##pixels = clue.pixel

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


def setCursor(idx):
    """Set the position of the cursor on-screen to indicate the player's selection."""
    global cursor_dob

    if 0 <= idx < len(choices):
        cursor_dob.y = top_y_pos + choice_sep * idx


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
    setCursor(my_choice_idx)
    cursor_dob.y = top_y_pos
    screen_group.append(cursor_dob)
    display.show(screen_group)


def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


NS_IN_S = 1000 * 1000  * 1000
MIN_SEND_TIME_NS = 6 * NS_IN_S
MAX_SEND_TIME_S = 20
MAX_SEND_TIME_NS = MAX_SEND_TIME_S * NS_IN_S

MIN_AD_INTERVAL = 0.02001

ble = BLERadio()

### TODO - allow the user to set this
##ble.name = ?


opponent_choice = None

msg_seq_last_rx = 255
msg_seq = 0

timeout = False
round = 1
wins = 0
losses = 0
draws = 0 
voids = 0

TOTAL_ROUND = 5


def evaluateGame(mine, yours):
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


def broadcastAndReceive(send_ad,
                        *receive_ads_types,
                        min_time=0,
                        max_time=MAX_SEND_TIME_S,
                        receive_n=0,
                        ads_by_addr={}
                        ):
    """Send an Advertisement sendad and then wait max_time seconds to receive_n
       receive_n Advertisements from other devices.
       If receive_n is 0 then wait for the remaining max_time.
       Returns list of received Advertisements not necessarily in arrival order and
       dictionary indexed by the compressed text representation of the address with a list
       of tuples of (advertisement, bytes(advertisement))."""

    d_print(2, "TXing", send_ad)

    ### Page 126 35.5 recommends an initial 30s of 20ms intervals
    ### https://developer.apple.com/accessories/Accessory-Design-Guidelines.pdf
    ### So this low value seems appropriate but interval=0.020 gives this
    ### _bleio.BluetoothError: Unknown soft device error: 0007
    ### 0.037 ok 0.021 ok 0.0201 ok 0.02001 ok - damn FP!!
    ## ble.start_advertising(tx_message, interval=0.02001)

    opponent_choice = None
    ### TODO review this - using 20ms - maybe less agressive is better with more devices?
    ### Remember default scanning interval is 100ms and transmit is probably 1 channel
    ### changing every 5s
    ble.start_advertising(send_ad, interval=MIN_AD_INTERVAL)
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

    ### A dict to store unique Advertisement indexed by mac address
    ### as text string
    received_ads_by_addr = dict(ads_by_addr)  ### Will not be a deep copy
    if receive_ads_types:
        rx_ad_classes = receive_ads_types
    else:
        rx_ad_classes = (type(send_ad),)

    ### Count of the number of packets already received of the
    ### first type in rx_ad_classes
    rx_count = 0
    for adsnb_per_addr in received_ads_by_addr.values():
        if rx_ad_classes[0] in [type(andb[0]) for andb in adsnb_per_addr]:
            rx_count += 1

    for adv in ble.start_scan(*rx_ad_classes, minimum_rssi=-127,
                              timeout=max_time):
        received_ns = time.monotonic_ns()
        d_print(2, "RXed RTA", adv)
        addr_text = "".join(["{:02x}".format(b) for b in reversed(adv.address.address_bytes)])
        if addr_text in received_ads_by_addr:
            this_ad_b = bytes(adv)
            for existing_ad in received_ads_by_addr[addr_text]:
                if this_ad_b == existing_ad[1]:
                    break  ### already present
            else:  ### Python's unusual for/else 
                received_ads_by_addr[addr_text].append((adv, bytes(adv)))
                rx_count += 1
        else:
            received_ads_by_addr[addr_text] = [(adv, bytes(adv))]
            rx_count += 1
        if receive_n > 0 and receive_n == rx_count:
            break

    ### We have received one message or exceeded MAX_SEND_TIME_S
    ble.stop_scan()

    ### Ensure we send our message for a minimum period of time
    ### constrained by the ultimate duration cap
    ### TODO - need to rethink this
    if False:   ### opponent_choice is not None:
        timeout = False
        remaining_ns = max_time * NS_IN_S - (received_ns - sending_ns)
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

    ### Make a single list of all the received adverts from the dict
    received_ads = []
    for ads in received_ads_by_addr.values():
        ### Pick out the first value, second value is just bytes() version
        received_ads.extend([a[0] for a in ads])
    return (received_ads, received_ads_by_addr)


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


### Join Game
### TODO - could have a callback to check for player terminate, i.e. 
###        could allow player to press button to say "i have got everyone"
other_player_ads, other_player_ads_by_addr = broadcastAndReceive(JoinGameAdvertisement(game="RPS"))

### Make a list of all the player's mac addr_text
### with this player as first entry
players = (["".join(["{:02x}".format(b) for b in reversed(ble.address_bytes)])]
           + list(other_player_ads_by_addr.keys()))

num_other_players = len(players) - 1

d_print(1, "PLAYERS", players)

### Advertise for 20 seconds maximum and if a packet is received
### for 5 seconds after that
while True:
    if round > TOTAL_ROUND:
        print("Summary: ",
              "wins {:d}, losses {:d}, draws {:d}, void {:d}".format(wins, losses, draws, voids))

        ### Reset variables for another game
        round = 1
        wins = 0
        losses = 0
        draws = 0 
        voids = 0
        round = 1

    if button_left():
        while button_left():
            pass
        my_choice_idx = (my_choice_idx + 1) % len(choices)
        if display is not None:
            setCursor(my_choice_idx)

    if button_right():
        my_choice = choices[my_choice_idx]
        player_choices = [my_choice]

        otpad_key = generateOTPadKey(8)
        d_print(3, "KEY", otpad_key)  ### TODO - discuss in the Code Discussion

        plain_bytes = bytes_pad(my_choice, size=8, pad=0)
        cipher_bytes = encrypt(plain_bytes, otpad_key, "xor")
        enc_data_msg = RpsEncDataAdvertisement(enc_data=cipher_bytes,
                                               round=round)
        ### Players will not be synchronised at this point as they do not
        ### have to make their choices simultaneously
        _, enc_data_by_addr = broadcastAndReceive(enc_data_msg,
                                                  RpsEncDataAdvertisement,
                                                  RpsKeyDataAdvertisement,
                                                  receive_n=num_other_players)

        key_data_msg = RpsKeyDataAdvertisement(key_data=otpad_key, round=round)
        ### All of the programs will be loosely synchronised now
        _, key_data_by_addr = broadcastAndReceive(key_data_msg,
                                                  RpsKeyDataAdvertisement,
                                                  RpsRoundEndAdvertisement,
                                                  receive_n=num_other_players,
                                                  ads_by_addr=enc_data_by_addr)

        re_msg = RpsRoundEndAdvertisement(round=round)
        ### The round end message is really about acknowledging receipt of the key
        ### by sending a message that holds non-critical information
        ### TODO - this one should only send for a few second, JoinGame should send for loads
        _, re_by_addr = broadcastAndReceive(re_msg,                                                  
                                            receive_n=num_other_players,
                                            ads_by_addr=key_data_by_addr)
        ### This will have accumulated all the messages for this round
        allmsg_by_addr = re_by_addr

        ### Decrypt results
        ### - if any data is incorrect the opponent_choice is left as None
        for p_idx1, player in enumerate(players[1:], 1):
            opponent_choice = None
            try:
                cipher_ads = list(filter(lambda ad: isinstance(ad[0], RpsEncDataAdvertisement),
                                  allmsg_by_addr[player]))
                key_ads = list(filter(lambda ad: isinstance(ad[0], RpsKeyDataAdvertisement),
                               allmsg_by_addr[player]))
                if len(cipher_ads) == 1 and len(key_ads) == 1:
                    cipher_bytes = cipher_ads[0][0].enc_data
                    round_msg1 = cipher_ads[0][0].round
                    key_bytes = key_ads[0][0].key_data
                    round_msg2 = key_ads[0][0].round
                    if round == round_msg1 == round_msg2:
                        plain_bytes = decrypt(cipher_bytes, key_bytes, "xor")
                        opponent_choice = str_unpad(plain_bytes)
                    else:
                        print("Received wrong round for {:d}: {:d} {:d}",
                              round, round_msg1, round_msg2)
                else:
                    print("Wrong number of RpsEncDataAdvertisement {:d} and RpsKeyDataAdvertisement",
                          len(cipher_ads), len(key_ads))
            except KeyError:
                pass
            player_choices.append(opponent_choice)

        ### Chalk up wins and losses
        for p_idx1, player in enumerate(players[1:], 1):
            (win, draw, void) = evaluateGame(my_choice, player_choices[p_idx1])
            d_print(1, "player", player, "choice", player_choices[p_idx1],
                    "win", win, "draw", draw, "void", void)
            if void:
                voids += 1
            elif draw:
                draws += 1
            elif win:
                wins += 1
            else:
                losses += 1
            d_print(1, "wins {:d}, losses {:d}, draws {:d}, void {:d}".format(wins, losses, draws, voids))
            round += 1


### Do something on screen or NeoPixels
print("GAME OVER")

while True:
    pass
