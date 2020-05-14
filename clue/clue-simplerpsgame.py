### clue-rps-game v0.2
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
from adafruit_ble.advertising import Advertisement, LazyObjectField
from adafruit_ble.advertising.standard import ManufacturerData, ManufacturerDataField


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


### Assuming CLUE if it's not a Circuit Playround (Bluefruit)
clue_less = "Circuit Playground" in os.uname().machine

### Note: difference in pull-up and pull-down
###       and not use for buttons
if clue_less:
    ### CPB with TFT Gizmo (240x240)
    ##from adafruit_circuitplayground import cp
    from adafruit_gizmo import tft_gizmo

    ### Outputs
    display = tft_gizmo.TFT_Gizmo()
    ##audio_out = AudioOut(board.SPEAKER)
    ##pixels = cp.pixels

    ### Enable the onboard amplifier for speaker
    ##cp._speaker_enable.value = True  ### pylint: disable=protected-access

    ### Inputs (buttons reversed as it is used upside-down with Gizmo)
    _button_a = digitalio.DigitalInOut(board.BUTTON_A)
    _button_a.switch_to_input(pull=digitalio.Pull.DOWN)
    _button_b = digitalio.DigitalInOut(board.BUTTON_B)
    _button_b.switch_to_input(pull=digitalio.Pull.DOWN)
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


### The 6x14 terminalio classic font
FONT_WIDTH, FONT_HEIGHT = terminalio.FONT.get_bounding_box()


def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)

### These are in adafruit_ble.advertising but are private :(
MANUFACTURING_DATA_ADT = const(0xFF)
ADAFRUIT_COMPANY_ID = const(0x0822)

### According to https://github.com/adafruit/Adafruit_CircuitPython_BLE/blob/master/adafruit_ble/advertising/adafruit.py
### 0xf000 (to 0xffff) is for range for Adafruit customers
RPS_DATA_ID = const(0xfe31)

### TODO prefix improvements mentioned in https://github.com/adafruit/Adafruit_CircuitPython_BLE/issues/82
### may not happen in time though

class RpsTestAdvertisement(Advertisement):
    """Broadcast a test RPS message."""
    
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

### https://github.com/adafruit/Adafruit_CircuitPython_BLE_BroadcastNet/blob/c6328d5c7edf8a99ff719c3b1798cb4111bab397/adafruit_ble_broadcastnet.py#L66-L67
### has a sequence_number - this will be use for for Complex Game
###    sequence_number = ManufacturerDataField(0x0003, "<B")
###    """Sequence number of the measurement. Used to detect missed packets."""
    
    test_string = ManufacturerDataField(RPS_DATA_ID, "<" + _DATA_FMT)
    """RPS choice."""


ble = BLERadio()
##ble.name = ?

choices = ("rock", "paper", "scissors")

while True:
    if button_left():
        tx_message = RpsTestAdvertisement()

        my_choice = choices[random.randrange(len(choices))]
        tx_message.test_string = my_choice
        d_print(2, "RTA txing", my_choice)
        ble.start_advertising(tx_message, interval=0.05)
        sending_ns = time.monotonic_ns()

        ##print("ssssssssss")
        ##message.test32bit = "ssssssss"
        ##ble.start_advertising(message)
        ##time.sleep(5)
        ##ble.stop_advertising()

        ### timeout in seconds
        ### -100 is probably minimum
        for adv in ble.start_scan(RpsTestAdvertisement, minimum_rssi=-127, timeout=15):
            d_print(2, "RTA rxed", adv.test_string)
        
        ble.stop_scan()
        ble.stop_advertising()

print("GAME OVER")

