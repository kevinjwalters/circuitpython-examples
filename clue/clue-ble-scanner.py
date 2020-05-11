### clue-ble-scanner v0.2
### CircuitPython BLE scanner

### Tested with Circuit Playground Bluefruit Alpha with TFT Gizmo
### and CircuitPython and 5.2.0 (5.3.0 is buggy)

### copy this file to CPB board as code.py

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

### TODO
### look at logging to a file if it can be done in some moderately safe way
### what about a pre-existing fixed size file?

### TODO - keep an eye on memory - avoid the cp and clue objects - perhaps only store what is needed from Advertisement

import time
import gc
import os

import board
from displayio import Group
import terminalio
import digitalio

from adafruit_display_text.label import Label

### https://github.com/adafruit/Adafruit_CircuitPython_BLE
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import Advertisement

### These imports works on CLUE, CPB (and CPX on 5.x)
from audiocore import RawSample
try:
    from audioio import AudioOut
except ImportError:
    from audiopwmio import PWMAudioOut as AudioOut

    
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

rows = 10
row_y = 30
row_spacing = FONT_HEIGHT + 2
rows_group = Group(max_size=rows)

### I have foreground and background colours I can use here

### 1234567890123456789012345678901234567890
### aa:bb:cc:dd:ee:ff -101 12345678901234567
for idx in range(rows):
    row_label = Label(font=terminalio.FONT,
                      text="",
                      max_glyphs=40,   ### maximum that will fit 240/6
                      color=0xc0c000)
    row_label.y = row_y
    row_y += row_spacing
    rows_group.append(row_label)

summary_label = Label(font=terminalio.FONT,
                      text="",
                      max_glyphs=40,   ### maximum that will fit 240/6
                      color=0x00c0c0)
                      
summary_label.y = 220       

screen_group = Group(max_size=2)
screen_group.append(rows_group)
screen_group.append(summary_label)

display.show(screen_group)  ### was screen_group

debug = 3

DATA_MASK_LEVELS = 3

data_mask = 0

def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)

screen_update_ns = 250 * 1000 * 1000
last_seen_update_ns = time.monotonic_ns()

stale_time_ns = 65 * 1000 * 1000 * 1000
scan_time_s = 10

ble = BLERadio()
ble.name = "CPB"

count = 1

complete_names_count = {}
addresses_count = {}
oui_count = {}

### An array of timestamp and advertisement by key (addr)
last_ad_by_key = {}

c_name_by_addr = {}

def remove_old(ad_by_key, expire_time_ns):
    """Delete any entry in the ad_by_key dict with a timestamp older than expire_time_ns."""
    ### the list() is needed to make a real list from the iterator 
    ### which allows modification of the dict inside the loop
    for key, value in list(ad_by_key.items()):
        if value[1] < expire_time_ns:
            del ad_by_key[key]


### TODO: arg list is getting big here
def update_screen(disp, rows_g, rows_n, ad_by_key, then_ns,
                  sum_dob, tot_mac, tot_oui, tot_names,
                  *,
                  mem_free=None):
    """Update the screen with the entries with highest RSSI, recenctly seen.
       The text colour is used to indicate how recent.
       """

    if mem_free is None:
        summary_text = "MACs:{:<4d}  OUIs:{:<4d}  Names:{:<4d}".format(tot_mac,
                                                                       tot_oui,
                                                                       tot_names)
    else:
        summary_text = "MACs:{:<4d}  OUIs:{:<4d}  Names:{:<4d} M:{:<3d}".format(tot_mac,
                                                                                tot_oui,
                                                                                tot_names,
                                                                                round(mem_free/1024.0))

    sum_dob.text = summary_text

    ### Sort by the RSSI field, then the time field
    sorted_data = sorted(ad_by_key.items(),
                         key=lambda item: (item[1][2], item[1][1]),
                         reverse=True)

    ### Add the top N rows to to the screen
    ### the key is the mac address as text without any colons
    idx = 0
    for key, value in sorted_data[:rows_n]:
        ad, ad_time_ns, rssi = value
        ### Add the colon sepators to the string version of the MAC address
        if data_mask == 0:
            masked_mac = key
        elif data_mask == 1:
            masked_mac = key[0:6] + "------"
        else:
            masked_mac = "------------"
        mac_text = ":".join([masked_mac[off:off+2] for off in range(0, len(masked_mac), 2)])
        ##name = ad.complete_name
        name = c_name_by_addr.get(key)
        if name is None:
            name = "?"
        ### Must be careful not to exceed the fixed max_glyphs field size here (40)
        rows_g[idx].text = "{:16s} {:s} {:4d}".format(name[:16],
                                                      mac_text,  ### should be 17 chars
                                                      rssi)
        ### This should be from 0 to about 65s-75s
        age = 170 - (then_ns - ad_time_ns) / stale_time_ns * 170
        brightness = min(max(round(85 + age * 2.4), 0), 255)
        rows_g[idx].color = (brightness, brightness, 0)
        idx += 1    

    #### Blank out any rows not populated with data
    if idx < rows_n:
        for _ in range(rows_n - idx):
            rows_g[idx].text = ""


while True:
    d_print(2, "Loop", count)
    for ad in ble.start_scan(minimum_rssi=-127, timeout=scan_time_s):
        now_ns = time.monotonic_ns()
        ##addr_b = ad.address.address_bytes
        c_name = ad.complete_name
        addr_text = "".join(["{:02x}".format(b) for b in reversed(ad.address.address_bytes)])
        
        last_ad_by_key[addr_text] = (ad, now_ns, ad.rssi)

        try:
            addresses_count[addr_text] += 1
        except KeyError:
            addresses_count[addr_text] = 1

        oui = addr_text[:6]
        try:
            oui_count[oui] += 1
        except KeyError:
            oui_count[oui] = 1
        
        if c_name is not None:
            c_name_by_addr[addr_text] = c_name
            try:
                complete_names_count[c_name] += 1
            except KeyError:
                complete_names_count[c_name] = 1      

        if button_right():
            data_mask = (data_mask + 1 ) % DATA_MASK_LEVELS
            while button_right():
                pass

        if now_ns - last_seen_update_ns > screen_update_ns:
            gc.collect()
            mem_free = gc.mem_free()
            update_screen(display, rows_group, rows, last_ad_by_key,
                         now_ns,
                         summary_label,
                         len(addresses_count), len(oui_count), len(complete_names_count),
                         mem_free=mem_free)

            last_seen_update_ns = now_ns

        d_print(4,
                ad.address, ad.rssi, ad.scan_response,
                ad.tx_power, ad.complete_name, ad.short_name)


    remove_old(last_ad_by_key, time.monotonic_ns() - stale_time_ns)

    d_print(2,
            "MACS", len(addresses_count),
            "OUI", len(oui_count),
            "NAMES", len(complete_names_count))

    count += 1
