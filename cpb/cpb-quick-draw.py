### cpb-quick-draw v1.3
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

### TODO - fully switch over to import cpb - NOT YET IN A LIBRARY BUNDLE
### From https://github.com/adafruit/Adafruit_CircuitPython_CircuitPlayground/tree/master/adafruit_circuitplayground
from adafruit_circuitplayground.bluefruit import cpb

from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService

from adafruit_bluefruit_connect.packet import Packet

class TimePacket(Packet):
    """A time packet of time.monotonic() and lastrtt."""

    _FMT_PARSE = '<xxffx'
    PACKET_LENGTH = struct.calcsize(_FMT_PARSE)
    # _FMT_CONSTRUCT doesn't include the trailing checksum byte.
    _FMT_CONSTRUCT = '<2sff'

    # TODO - ask for recommendations for application specific range
    _TYPE_HEADER = b'!z'

    # number of args must match _FMT_PARSE
    # for Packet.parse_private() to work
    def __init__(self, duration, sendtime):
        """Construct a TimePacket."""
        self._duration = duration
        self._sendtime = sendtime  # over-written later

    def to_bytes(self):
        """Return the bytes needed to send this packet.
        """
        self._sendtime = time.monotonic()
        partial_packet = struct.pack(self._FMT_CONSTRUCT, self._TYPE_HEADER,
                                     self._duration, self._sendtime)
        return self.add_checksum(partial_packet)

    @property
    def duration(self):
        """The last rtt value or a negative number if n/a."""
        return self._duration

    @property
    def sendtime(self):
        """The time packet was sent (when to_bytes() was last called)."""
        return self._sendtime

TimePacket.register_packet_type()


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

##switch_left = digitalio.DigitalInOut(board.SLIDE_SWITCH)
##switch_left.switch_to_input(pull=digitalio.Pull.UP)

master_device = cpb.switch  # True when switch is left (near ear symbol)

# brightness 1 saves memory by removing need for a second buffer
# 10 is number of NeoPixels on CPX
numpixels = const(10)
halfnumpixels = const(5)
pixels = cpb.pixels

##pixels = neopixel.NeoPixel(board.NEOPIXEL, numpixels, brightness=1)

# The touch pads calibrate themselves as they are created, just once here
##touchpad = touchio.TouchIn(board.A1)

if master_device:
    # button A is on left (usb at top
    player_button = lambda: cpb.button_a
    ## player_button.switch_to_input(pull=digitalio.Pull.DOWN)

    player_px = (0, halfnumpixels)
    opponent_px = (halfnumpixels, numpixels)
else:
    # button B is on right
    player_button = lambda: cpb.button_b
    ## player_button.switch_to_input(pull=digitalio.Pull.DOWN)

    player_px = (halfnumpixels, numpixels)
    opponent_px = (0, halfnumpixels)

win_colour     = [(0,  30, 0) ] * halfnumpixels
misdraw_colour = [(40, 0,  0) ] * halfnumpixels
draw_colour    = [(40, 30, 0) ] * halfnumpixels

### From first tests master shows
###
### RTT plus a bit 0.0546875 (or 0.0507813)
### RTT plus a bit 0.0429688
### RTT plus a bit 0.0429688
### lots repeated, occasional 0.0390625, 0.046875

### With new TimePacket this is
### 0.0546875, 0.046875, 0.0390625, 0.046875, 0.0390625

### TODO - do some order of start-up testing and compare with previous code

### TODO - appearing at CIRCUITPYxxxx where xxxx last 4 hex chars of MAC-
###      - do I want to change this?

num_pings = 8
# The rtt is sent to server but for first packet client
# sent there's no value to send, -1.0 is specal first packet value
rtt = -1.0
rtts = []
offsets = []

# default timeout is 1.0 and on latest library with UARTService this
# cannot be changed
ble = BLERadio()
if master_device:
    # Master code
    uart_client = None
    while True:
        gc.collect()  # opportune moment
        while ble.connected:
            request = TimePacket(rtt, 0.0)

            try:
                print("TX")
                uart_client.write(request.to_bytes())
                # TODO - can I split from_stream into read then parse?
                response = Packet.from_stream(uart_client)
                t2 = time.monotonic()
                if isinstance(response, TimePacket):
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
                print("OSError", err, file=sys.stderr)

            if len(rtts) >= num_pings:
                break

            pixels.fill((0,0,10))
            time.sleep(0.1)
            pixels.fill((0,0,0))
            time.sleep(0.1)

        if len(rtts) >= num_pings:
            break

        print("disconnected, scanning")
        for advertisement in ble.start_scan(ProvideServicesAdvertisement,
                                            timeout=2):
            if UARTService not in advertisement.services:
                continue
            print("connecting")   ### TODO - added what connecting to
            ble.connect(advertisement)
            break
        for conn in ble.connections:
            if UARTService in conn:
                print("Set uart_client")
                uart_client = conn[UARTService]
                break
        ble.stop_scan()

else:
    # Slave code
    uart_server = UARTService()
    advertisement = ProvideServicesAdvertisement(uart_server)
    responses = 0
    while True:
        ble.start_advertising(advertisement)
        while not ble.connected:
            pass

        print("Incoming connection")
        gc.collect()
        while ble.connected:
            # TODO - consider using uart_server.in_waiting
            packet = Packet.from_stream(uart_server)
            if isinstance(packet, TimePacket):
                print("RX")
                try:
                    uart_server.write(TimePacket(-2.0, -1.0).to_bytes())
                    responses += 1
                    rtts.append(packet.duration)
                    pixels.fill((0,0,10))
                    # this must be less than the client inter-packet pause
                    time.sleep(0.1)
                    pixels.fill((0,0,0))
                except OSError as err:
                    print("OSError", err, file=sys.stderr)
            elif packet is None:
                pass
            else:
                print("Unexpected packet type", packet)
            if responses >= num_pings:
                break
        if responses >= num_pings:
                break

### indicate a good rtt calculate, skip first one
### as it's not present on slave
print(rtts)
if master_device:
    rtt_start = 1
    rtt_end   = len(rtts) - 1
else:
    rtt_start = 2
    rtt_end   = len(rtts)

quicker_rtts = sorted(rtts[rtt_start:rtt_end])[0:(num_pings // 2) + 1]
mean_rtt = sum(quicker_rtts) / len(quicker_rtts)
ble_send_time = mean_rtt / 2.0

print("BSE:", ble_send_time)  ### TODO delete this.


pixels.fill((0,0,100))
time.sleep(2)
pixels.fill((0,0,0))

### TODO randomise this sleep
time.sleep(5)

# TODO - ponder whether I want any gc in here or not
# perhaps leave it for second program
# CPB has loads (?) of memory too...
gc.collect()

if master_device:
    if ble.connected:
        try:
            uart_client.write(StartGame().to_bytes())
            print("StartGame TX")
            packet = Packet.from_stream(uart_client)
            if isinstance(packet, StartGame):
                print("StartGame RX")
            elif packet is None:
                pass
            else:
                print("Unexpected packet type", packet)
        except OSError as err:
            print(err, file=sys.stderr)

else:
    if ble.connected:
        packet = Packet.from_stream(uart_server)
        if isinstance(packet, StartGame):
            print("StartGame RX")
            try:
                uart_server.write(StartGame().to_bytes())
                print("StartGame TX")
            except OSError as err:
                print(err, file=sys.stderr)
        elif packet is None:
            pass
        else:
            print("Unexpected packet type", packet)
    print("Sleeping to sync up", ble_send_time)
    time.sleep(ble_send_time)

# The CPBs should now be synchronised and this could will run at the
# same time
##for idx in range(10):
##    pixels.fill((30, 30, 30))
##    time.sleep(1)
##    pixels.fill((0,0,0))
##    time.sleep(1)

# FOR THIS VERSION USE BUTTON AND USE IT ON THE SIDE THE SWITCH IS SET TO
# replicate the style of the original quick draw
# pass results between the two
# wait 5 seconds for data packet exchange
# in notes document it behaves slightly differently as it cannot tell
# how long other play took until it receives data
#

# TODO - need to change at the very least code exchanging TimePacket
# after this because timeout can no longer be set and 


# Start the game
pixels.fill((30, 30, 30))
start_t = time.monotonic()
while not player_button():
   pass
finish_t = time.monotonic()

pixels.fill((0, 0, 0))
cpb.play_file("PistolRicochet.wav")


### The CPBs are no longer synchronised due to variability of
### reaction time between players
player_reaction_dur = finish_t - start_t

### TODO exchange times over bluetooth
### test with length delay from other player for
### both cases to check buffering saves the day
error_dur = -1.0
opponent_reaction_dur = error_dur
if master_device:
    if ble.connected:
        try:
            uart_client.write(TimePacket(player_reaction_dur,
                                         0.0).to_bytes())
            print("TimePacket TX")
            packet = Packet.from_stream(uart_client)
            if isinstance(packet, TimePacket):
                print("TimePacket RX")
                opponent_reaction_dur = packet.duration
            elif packet is None:
                pass
            else:
                print("Unexpected packet type", packet)
        except OSError as err:
            print(err, file=sys.stderr)

else:
    if ble.connected:
        packet = Packet.from_stream(uart_server)
        if isinstance(packet, TimePacket):
            print("TimePacket RX")
            opponent_reaction_dur = packet.duration
            try:
                uart_server.write(TimePacket(player_reaction_dur,
                                             0.0).to_bytes())
                print("TimePacket TX")
            except OSError as err:
                print(err, file=sys.stderr)
        elif packet is None:
            pass
        else:
            print("Unexpected packet type", packet)

print("({:f}, {:f})".format(player_reaction_dur, opponent_reaction_dur))

if player_reaction_dur < 0.1 or opponent_reaction_dur < 0.1:
    if player_reaction_dur != error_dur and player_reaction_dur < 0.1:
        pixels[player_px[0]:player_px[1]] = misdraw_colour
    if opponent_reaction_dur != error_dur and opponent_reaction_dur < 0.1:
        pixels[opponent_px[0]:opponent_px[1]] = misdraw_colour
else:
    if player_reaction_dur < opponent_reaction_dur:
        pixels[player_px[0]:player_px[1]] = win_colour
    elif opponent_reaction_dur < player_reaction_dur:
        pixels[opponent_px[0]:opponent_px[1]] = win_colour
    else:
        # Very unlikely to reach here
        pixels[player_px[0]:player_px[1]] = draw_colour
        pixels[opponent_px[0]:opponent_px[1]] = draw_colour


### TODO
#print values in mu friendly format
#print running stats in my friendly format


### TODO - this appears to fix a bug which may related to closing the
###        connection by program termination and other end not receiving it
### Bluetooth connection needs to be kept connected for the read to work
### TODO - reproduce this in smaller code
time.sleep(5)
