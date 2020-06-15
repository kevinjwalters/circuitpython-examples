### clue-blue-adoddity v0.1
### CircuitPython tx/rx Advertisements to check Bluetooth LE for strange occasional
### huge packet loss

### Tested with CLUE and Circuit Playground Bluefruit Alpha 
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
import terminalio
import digitalio

from adafruit_ble import BLERadio

from adafruit_ble.advertising import Advertisement  ### ONLY NEEDED FOR DEBUGGING
import adafruit_ble.advertising.standard  ### for encode_data and decode_data
from adafruit_ble.advertising.adafruit import AdafruitColor

debug = 5

### Assuming CLUE if it's not a Circuit Playround (Bluefruit)
clue_less = "Circuit Playground" in os.uname().machine

### Note: difference in pull-up and pull-down
###       and not use for buttons
if clue_less:
    _button_a = digitalio.DigitalInOut(board.BUTTON_A)
    _button_a.switch_to_input(pull=digitalio.Pull.DOWN)
    _button_b = digitalio.DigitalInOut(board.BUTTON_B)
    _button_b.switch_to_input(pull=digitalio.Pull.DOWN)

    button_a = lambda: _button_a.value
    button_b = lambda: _button_b.value
    display = None

else:
    _button_a = digitalio.DigitalInOut(board.BUTTON_A)
    _button_a.switch_to_input(pull=digitalio.Pull.UP)
    _button_b = digitalio.DigitalInOut(board.BUTTON_B)
    _button_b.switch_to_input(pull=digitalio.Pull.UP)

    button_a = lambda: not _button_a.value
    button_b = lambda: not _button_b.value

    display = board.DISPLAY


def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


def addr_to_text(mac_addr, big_endian=False, sep=""):
    """Convert a mac_addr in bytes to text."""
    return sep.join(["{:02x}".format(b)
                     for b in (mac_addr if big_endian else reversed(mac_addr))])


NS_IN_S = 1000 * 1000  * 1000
MIN_SEND_TIME_NS = 6 * NS_IN_S
MAX_SEND_TIME_S = 20
NORM_SEND_TIME_S = 4
MAX_SEND_TIME_NS = MAX_SEND_TIME_S * NS_IN_S

### 20ms is the minimum delay between advertising packets
### in Bluetooth Low Energy
### extra 10us deals with API floating point rounding issues
MIN_AD_INTERVAL = 0.02001
### This will either be 50 Adverisement+Scan Response per seond
### or 40 taking into account the automatic random uniform delay of 0-10 if
### it is always 0-10 rather than -5 to 5


INTERVAL_TICKS = (33, 37, 41, 43, 47)  ### Do not use 32 here due to fp issues
INTERVAL_TICK_MS = 0.625

scan_and_ad_time = 30
scan_response_request = True

ble = BLERadio()

my_addr_text = addr_to_text(ble.address_bytes)

ca_ad = AdafruitColor()
ca_ad.color = 0x112233

interval = MIN_AD_INTERVAL
##interval = INTERVAL_TICKS[random.randrange(len(INTERVAL_TICKS))] * INTERVAL_TICK_MS / 1e3


### Turn off updates to stop any delays from screen updates on CLUE
if display is not None:
    display.auto_refresh = False


def tx_rx_test(round_no, debug=debug):
    d_print(2, "TXing", ca_ad, "interval", interval)
    rx_byaddr = {}
    ble.start_advertising(ca_ad, interval=interval)
    t1_ns = time.monotonic_ns()
    for adv_ss in ble.start_scan(Advertisement,
                                 ## minimum_rssi=-120,
                                 buffer_size=1536,  ### default 512
                                 active=scan_response_request,
                                 timeout=scan_and_ad_time):
        received_ns = time.monotonic_ns()
        addr_text = addr_to_text(adv_ss.address.address_bytes)
        if addr_text in rx_byaddr:
            rx_byaddr[addr_text] += 1
        else:
            rx_byaddr[addr_text] = 1
        if debug >= 4:  ### stop repr() running
            d_print(4, "RXed RTA", addr_text, repr(adv_ss))

    ble.stop_advertising()
    t2_ns = time.monotonic_ns()
    d_print(3, "Summary run", my_addr_text, round_no, (t2_ns - t1_ns) / NS_IN_S, rx_byaddr)


round = 1
while True:
    ### cry havoc, and let slip the dogs of war
    if button_a():
        tx_rx_test(round)
        round += 1
    
    if button_b():
        tx_rx_test(round, debug=3)  ### get rid of per Advertisement printing
        round += 1
