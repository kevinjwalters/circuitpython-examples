### cpb-quick-draw v0.8
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

### CPX / CPB differences (TODO move less relevant ones somewhere else)
### no DAC on CPB, PWM is used for audio
### audioio library not present, replaced by audiocore
### time.monotonic coarser on CPB, looks like 1/256 s increments, 0.00390625

import time
import sys
import gc
import struct

import digitalio
import touchio
import board

### TODO - switch over to import cpb - NOT YET IN A LIBRARY BUNDLE
## from adafruit_circuitplayground.bluefruit import cpb
import neopixel


from adafruit_bluefruit_connect.packet import Packet

class PingPacket(Packet):
    """A ping packet of time.monotonic() and lastrtt."""

    _FMT_PARSE = '<xxffx'
    PACKET_LENGTH = struct.calcsize(_FMT_PARSE)
    # _FMT_CONSTRUCT doesn't include the trailing checksum byte.
    _FMT_CONSTRUCT = '<2sff'

    # TODO - ask for recommendations for application specific range
    _TYPE_HEADER = b'!z'

    # number of args must match _FMT_PARSE
    # for Packet.parse_private() to work
    def __init__(self, lastrtt, sendtime):
        """Construct a PingPacket."""
        self._lastrtt = lastrtt
        self._sendtime = sendtime   # over-written later

    def to_bytes(self):
        """Return the bytes needed to send this packet.
        """
        self._sendtime = time.monotonic()
        partial_packet = struct.pack(self._FMT_CONSTRUCT, self._TYPE_HEADER,
                                     self._sendtime, self._lastrtt)
        return self.add_checksum(partial_packet)

    @property
    def lastrtt(self):
        """The last rtt value or a negative number if n/a."""
        return self._lastrtt

    @property
    def sendtime(self):
        """The time packet was sent (when to_bytes() was last called)."""
        return self._sendtime

PingPacket.register_packet_type()


class StartGame(Packet):
    """A packet to indicate the receiver must start the game immediately."""
    
    _FMT_PARSE = '<xxx'
    PACKET_LENGTH = struct.calcsize(_FMT_PARSE)
    # _FMT_CONSTRUCT doesn't include the trailing checksum byte.
    _FMT_CONSTRUCT = '<2s'

    # TODO - ask for recommendations for application specific range
    _TYPE_HEADER = b'!y'

    def to_bytes(self):
        """Return the bytes needed to send this packet.
        """
        partial_packet = struct.pack(self._FMT_CONSTRUCT, self._TYPE_HEADER)
        return self.add_checksum(partial_packet)

StartGame.register_packet_type()



# from adafruit_bluefruit_connect.color_packet import ColorPacket


debug = 1

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

### From first tests master shows
###
### RTT plus a bit 0.0546875 (or 0.0507813)
### RTT plus a bit 0.0429688
### RTT plus a bit 0.0429688
### lots repeated, occasional 0.0390625, 0.046875

### With new PingPacket this is
### 0.0546875, 0.046875, 0.0390625, 0.046875, 0.0390625

### TODO - do some order of start-up testing and compare with previous code

### TODO - appearing at CIRCUITPYxxxx where xxxx last 4 hex chars of MAC-
###      - do I want to change this?

num_pings = 5
# The rtt is sent to server but for first packet client
# sent there's no value to send, -1.0 is specal first packet value
rtt = -1.0
rtts = []
offsets = []

if master_device:
    # Master code
    scanner = Scanner()
    uart_client = UARTClient()
    while True:
        uart_addresses = []
        while not uart_addresses:
            uart_addresses = uart_client.scan(scanner)
        if debug:
            print("Connecting to", uart_addresses[0])
        uart_client.connect(uart_addresses[0], 5)

        gc.collect()  # opportune moment
        while uart_client.connected:
            request = PingPacket(rtt, 0.0)
            
            try:
                uart_client.write(request.to_bytes())
                # TODO - can I split from_stream into read then parse?
                response = Packet.from_stream(uart_client)
                t2 = time.monotonic()
                if isinstance(response, PingPacket):
                    print("RX")
                    rtt = t2 - request.sendtime
                    rtts.append(rtt)
                    time_remote_cpb = response.sendtime + rtt / 2.0
                    offset = time_remote_cpb - t2
                    offsets.append(offset)
                    print("RTT plus a bit={:f}, remote_time={:f}, offset={:f}".format(rtt,
                                                                                      time_remote_cpb,
                                                                                      offset))
            except OSError as err:
                pass

            if len(rtts) >= num_pings:
                break

            pixels.fill((0,0,10))
            time.sleep(0.2)
            pixels.fill((0,0,0))

        if len(rtts) >= num_pings:
            break

    ### indicate a good rtt calculate
    quicker_rtts = sorted(rtts)[0:(num_pings // 2) + 1]
    mean_rtt = sum(rtts) / len(rtts)
    ble_send_time = mean_rtt / 2.0

else:
    # Slave code
    uart_server = UARTServer()
    responses = 0
    while True:
        uart_server.start_advertising()
        while not uart_server.connected:
            pass

        gc.collect()
        while uart_server.connected:
            # TODO - consider using uart_server.in_waiting
            packet = Packet.from_stream(uart_server)
            if isinstance(packet, PingPacket):
                print("RX")
                try:
                    uart_server.write(PingPacket(-2.0, -1.0).to_bytes())
                    responses += 1
                    pixels.fill((0,0,10))
                    # this must be less than the client inter-packet pause
                    time.sleep(0.1)
                    pixels.fill((0,0,0))
                except OSError as err:
                    print(err, file=sys.stderr)
            elif packet is None:
                pass
            else:
                print("Unexpected packet type", packet)
            if responses >= num_pings:
                break
        if responses >= num_pings:
                break

pixels.fill((0,0,100))
time.sleep(2)
pixels.fill((0,0,0))


time.sleep(5)
gc.collect()

if master_device:
    if uart_client.connected:
        try:
            uart_client.write(StartGame().to_bytes())
            print("sleeping to sync", ble_send_time)
            time.sleep(ble_send_time)
            print("StartGame TX")
        except OSError as err:
            print(err, file=sys.stderr)

    time.sleep(0.055)  ### TODO - super fudge!!!!!
else:
    if uart_server.connected:
        packet = Packet.from_stream(uart_server)
        if isinstance(packet, StartGame):
            print("StartGame RX")
        elif packet is None:
            pass
        else:
            print("Unexpected packet type", packet)

### TODO - this does not work!!!
### K42 is three frames behind at 50Hz video
### Maybe audio is best way to check sync if i can get it in L / R

### TODO - forget StartGame and check with PingPacket
### TODO - check registration isn't slowing things down

for idx in range(5):
    pixels.fill((50, 50, 50))
    time.sleep(1)
    pixels.fill((0,0,0))
    time.sleep(1)
