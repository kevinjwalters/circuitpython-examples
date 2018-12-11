### bluetooth-microscout-vll-control v1.0
### Bluetooth Remote Control for the Micro Scout from Lego(tm) Droid Developer Kit
### On an Adafruit Feather M0 Bluetooth LE board
### or a CircuitPython compatible board using the Adafruit Bluefruit LE SPI Friend
### allows a Micro Scout block to be controlled
### using the Visible Light Link (VLL) protocol sent with D13 LED

### copy this file to Feather M0 as code.py

### MIT License

### Copyright (c) 2018 Kevin J. Walters

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

import board
import busio

##import pulseio  ### might come back to this

from digitalio import DigitalInOut, Direction
from adafruit_bluefruitspi import BluefruitSPI

### Setup SPI bus and 3 control pins for Nordic nRF51822 based Raytec MDBT40
### board.D8 is not defined on the basic CircuitPython hence the strange
### need to use the adalogger variant
spi_bus = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
cs  = DigitalInOut(board.D8)
irq = DigitalInOut(board.D7)
rst = DigitalInOut(board.D4)

### debug=True triggers bug
### see https://github.com/adafruit/Adafruit_CircuitPython_BluefruitSPI/issues/8
bluefruit = BluefruitSPI(spi_bus, cs, irq, rst, debug=False)

boardled = DigitalInOut(board.D6)
##boardled = DigitalInOut(board.D13)  ### small onboard red LED
boardled.direction = Direction.OUTPUT

boardled.value = True
boardled.value = False


def vllchksum(n):
    return 7-((n+(n>>2)+(n>>4))&7)

### Lego Micro Scout commands
### Micropython's const() works only on integers
MS_FWD  = const(0)
MS_REV  = const(1)
MS_STOP = const(2)
MS_BEEP = const(4)

PAUSE = 0.15

ADVERT_NAME = b'BlueMicroScout'

### Note: incompatibile with ZX Spectrum cursors
BUTTON_1    = const(1)
BUTTON_2    = const(2)
BUTTON_3    = const(3)
BUTTON_4    = const(4)
BUTTON_UP    = const(5)
BUTTON_DOWN  = const(6)
BUTTON_LEFT  = const(7)
BUTTON_RIGHT = const(8)

### Borrowed from https://github.com/JorgePe/mindstorms-vll/blob/master/vll-atat.py
### https://github.com/JorgePe/mindstorms-vll

def vll1():
    boardled.value =  True
    time.sleep(0.02)
    boardled.value = False
    time.sleep(0.04)

def vll0():
    boardled.value = True
    time.sleep(0.04)
    boardled.value = False
    time.sleep(0.02)

def vllinit():
    boardled.value = True
    time.sleep(0.4)

def vllstart():
    boardled.value = False
    time.sleep(0.02)

def vllstop():
    boardled.value = True
    time.sleep(0.02)
    boardled.value = False
    time.sleep(0.06)
    boardled.value = True
    time.sleep(0.12)

def send(command):
    vllstart()
    v = (vllchksum(command) << 7 ) + command
    i = 0x200
    while i>0 :
        if v & i:
            vll1()
        else:
            vll0()
        i = i >> 1
    vllstop()

def pause():
    boardled.value = True
    time.sleep(PAUSE)

boardled.value = False

vllinit()

def init_bluefruit():
    # Initialize the device and perform a factory reset
    print("Initializing the Bluefruit LE SPI Friend module")
    bluefruit.init()
    bluefruit.command_check_OK(b'AT+FACTORYRESET', delay=1)
    # Print the response to 'ATI' (info request) as a string
    print(str(bluefruit.command_check_OK(b'ATI'), 'utf-8'))
    # Change advertised name
    bluefruit.command_check_OK(b'AT+GAPDEVNAME='+ADVERT_NAME)

def wait_for_connection():
    print("Waiting for a connection to Bluefruit LE Connect ...")
    # Wait for a connection ...
    dotcount = 0
    while not bluefruit.connected:
        print(".", end="")
        dotcount = (dotcount + 1) % 80
        if dotcount == 79:
            print("")
        time.sleep(0.5)

# This code will check the connection but only query the module if it has been
# at least 'n_sec' seconds. Otherwise it 'caches' the response, to keep from
# hogging the Bluefruit connection with constant queries
connection_timestamp = None
is_connected = None
def check_connection(n_sec):
    # pylint: disable=global-statement
    global connection_timestamp, is_connected
    if (not connection_timestamp) or (time.monotonic() - connection_timestamp > n_sec):
        connection_timestamp = time.monotonic()
        is_connected = bluefruit.connected
    return is_connected

### Note: read_packet looks a bit buggy
### see https://github.com/adafruit/Adafruit_CircuitPython_BluefruitSPI/issues/9

### Nabbed off MUNNY code which may have been inspired by library examples directory

# Unlike most circuitpython code, this runs in two loops
# one outer loop manages reconnecting bluetooth if we lose connection
# then one inner loop for doing what we want when connected!
while True:
    # Initialize the module
    init_bluefruit()
    try:        # Wireless connections can have corrupt data or other runtime failures
                # This try block will reset the module if that happens
        while True:
            # Once connected, check for incoming BLE UART data
            if check_connection(3):  # Check our connection status every 3 seconds
                # OK we're still connected, see if we have any data waiting
                 
                resp = bluefruit.read_packet()
                if not resp:
                    continue  # nothin'
                print("Read packet", resp)
                ### Look for a 'B' for Button packet
                if resp[0] != 'B':
                    continue
                button_num = resp[1]
                button_down = resp[2]
                ### For now only look for the down events
                if button_down:
                    if button_num == BUTTON_UP:
                        send(MS_FWD)
                    elif button_num == BUTTON_DOWN:
                        send(MS_REV)
                    elif button_num == BUTTON_1:
                        send(MS_BEEP)
                    else:
                        ### some other key pressed
                        pass
            else:  # Not connected
                pass

    except RuntimeError as e:
        print(e)  # Print what happened
        continue  # retry!
