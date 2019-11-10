### cpb-quick-draw v0.5
### CircuitPython (on CPB) Quick Draw reaction game

### Tested with Circuit Playground Bluefruit Alpha
### and CircuitPython and 5.0.0-alpha.5

### Needs recent adafruit_ble module

### copy this file to CPB as code.py

### MIT License

### Copyright (c) 2019 Kevin J. Walters

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

import digitalio
import touchio
import board
import neopixel

from adafruit_bluefruit_connect.packet import Packet
from adafruit_bluefruit_connect.color_packet import ColorPacket

switch_left = digitalio.DigitalInOut(board.SLIDE_SWITCH)
switch_left.switch_to_input(pull=digitalio.Pull.UP)

master_device = switch_left.value

if master_device:
    # The master device
    from adafruit_ble.scanner import Scanner
    from adafruit_ble.uart_client import UARTClient
else:
    # The slave device
    from adafruit_ble.uart_server import UARTServer

# brightness 1 saves memory by removing need for a second buffer
# 10 is number of NeoPixels on CPX
numpixels = const(10)
pixels = neopixel.NeoPixel(board.NEOPIXEL, numpixels, brightness=1)

# The touch pads calibrate themselves as they are created, just once here
touchpad = touchio.TouchIn(board.A1)

# button A is on left (usb at top
button_left = digitalio.DigitalInOut(board.BUTTON_A)
button_left.switch_to_input(pull=digitalio.Pull.DOWN)
button_right = digitalio.DigitalInOut(board.BUTTON_B)
button_right.switch_to_input(pull=digitalio.Pull.DOWN)

if master_device:
    # Master code
    scanner = Scanner()
    uart_client = UARTClient()
    while True:
        uart_addresses = []
        while not uart_addresses:
            uart_addresses = uart_client.scan(scanner)
        print("Connecting to", uart_addresses[0])
        uart_client.connect(uart_addresses[0], 5)

        while uart_client.connected:
            color_packet = ColorPacket((1,2,3))
            try:
                t1 = time.monotonic()
                uart_client.write(color_packet.to_bytes())
                packet = Packet.from_stream(uart_client)
                t2 = time.monotonic()
            except OSError:
                 pass
            print("RTT plus a bit", t2 - t1)
            time.sleep(1)
    
else:
    # Slave code
    uart_server = UARTServer()
    while True:
        uart_server.start_advertising()
        while not uart_server.connected:
            pass

        while uart_server.connected:
            packet = Packet.from_stream(uart_server)
            if isinstance(packet, ColorPacket):
                uart_server.write(packet.to_bytes())
                print(packet.color)
            else:
                print("Unexpected packet type", packet)
