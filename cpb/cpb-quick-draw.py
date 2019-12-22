### cpb-quick-draw v1.7
### CircuitPython (on CPB) Quick Draw reaction game

### Tested with Circuit Playground Bluefruit Alpha
### and CircuitPython and 5.0.0-beta.2

### Needs recent adafruit_ble and adafruit_circuitplayground.bluefruit libraries

### Need two CPB boards with switches set to different positions

### copy this file to CPB board as code.py

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
import sys
import gc
import struct
import random  # On a CPB this seeds from a hardware RNG

import digitalio
import touchio
import board

### NOT YET IN A LIBRARY BUNDLE
### From https://github.com/adafruit/Adafruit_CircuitPython_CircuitPlayground/tree/master/adafruit_circuitplayground
from adafruit_circuitplayground.bluefruit import cpb

from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService

from adafruit_bluefruit_connect.packet import Packet

# Bluetooth scanning timeout
BLESCAN_TIMEOUT = 2

TURNS = 10
# Integer number of seconds
SHORTEST_DELAY = 1
LONGEST_DELAY = 10

# The duration of the short blue flashes (in seconds)
# during time delay measurement in ping_for_rtt()
SYNC_FLASH_DUR = 0.1

# A special value used to indicate failed exchange of reaction times
ERROR_DUR = -1.0

class TimePacket(Packet):
    """A packet for exchanging time information, time.monotonic() and lastrtt."""

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
        self._sendtime = sendtime  # over-written later in to_bytes()

    def to_bytes(self):
        """Return the bytes needed to send this packet.
        """
        self._sendtime = time.monotonic()  # refresh _sendtime
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


debug = 1

master_device = cpb.switch  # True when switch is left (near ear symbol)

# The default brightness is 1.0 - leaving at that as it
# improves performance by removing need for a second buffer in memory
# 10 is number of NeoPixels on CPX/CPB
numpixels = const(10)
halfnumpixels = const(5)
pixels = cpb.pixels

win_colour     = [(0,  30, 0) ] * halfnumpixels
misdraw_colour = [(40, 0,  0) ] * halfnumpixels
draw_colour    = [(40, 30, 0) ] * halfnumpixels

blue = (0, 0, 10)
brightblue = (0, 0, 100)
white = (30, 30, 30)
black = (0, 0, 0)


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


### TODO - do some order of start-up testing and compare with previous code

### TODO - appearing in BLE 
###      - as CIRCUITPYxxxx where xxxx last 4 hex chars of MAC-
###      - do I want to change this?

def connect():
    uart = None
    if master_device:
        # Master code
        while uart is None:
            print("disconnected, scanning")
            for advertisement in ble.start_scan(ProvideServicesAdvertisement,
                                                timeout=BLESCAN_TIMEOUT):
                if UARTService not in advertisement.services:
                    continue
                print("connecting")   ### TODO - added what connecting to
                ble.connect(advertisement)
                break
            for conn in ble.connections:
                if UARTService in conn:
                    print("Set uart")
                    uart = conn[UARTService]
                    break
            ble.stop_scan()

    else:
        # Slave code
        uart = UARTService()
        advertisement = ProvideServicesAdvertisement(uart)
        print("Advertising")
        ble.start_advertising(advertisement)
        while not ble.connected:
            pass
        print("Incoming connection")
    
    return uart
    

num_pings = 8

def ping_for_rtt():
    # The rtt is sent to server but for first packet client
    # sent there's no value to send, -1.0 is specal first packet value
    rtt = -1.0
    rtts = []
    offsets = []

    if master_device:
        # Master code
        while True:
            gc.collect()  # opportune moment
            request = TimePacket(rtt, 0.0)

            try:
                print("TX")
                uart.write(request.to_bytes())
                # TODO - can I split from_stream into read then parse?
                response = Packet.from_stream(uart)
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

            pixels.fill(blue)
            time.sleep(SYNC_FLASH_DUR)
            pixels.fill(black)
            # This second sleep is very important to ensure that the
            # server is awaiting the next packet before client
            # sends it to avoid server reading buffered packets
            time.sleep(SYNC_FLASH_DUR)

    else:
        responses = 0
        while True:
            gc.collect()

            # TODO - consider using uart.in_waiting
            packet = Packet.from_stream(uart)
            if isinstance(packet, TimePacket):
                print("RX")
                try:
                    uart.write(TimePacket(-2.0, -1.0).to_bytes())
                    responses += 1
                    rtts.append(packet.duration)
                    pixels.fill(blue)
                    time.sleep(SYNC_FLASH_DUR)
                    pixels.fill(black)
                    
                except OSError as err:
                    print("OSError", err, file=sys.stderr)
            elif packet is None:
                pass
            else:
                print("Unexpected packet type", packet)
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
    
    pixels.fill(brightblue)
    time.sleep(2)
    pixels.fill(black)
    return ble_send_time


def barrier():
    if master_device:
        try:
            uart.write(StartGame().to_bytes())
            print("StartGame TX")
            packet = Packet.from_stream(uart)
            if isinstance(packet, StartGame):
                print("StartGame RX")
            elif packet is None:
                pass
            else:
                print("Unexpected packet type", packet)
        except OSError as err:
            print(err, file=sys.stderr)

    else:
        packet = Packet.from_stream(uart)
        if isinstance(packet, StartGame):
            print("StartGame RX")
            try:
                uart.write(StartGame().to_bytes())
                print("StartGame TX")
            except OSError as err:
                print(err, file=sys.stderr)
        elif packet is None:
            pass
        else:
            print("Unexpected packet type", packet)

        print("Sleeping to sync up", ble_send_time)
        time.sleep(ble_send_time)


def random_pause():
    """This is the pause before the players draw.
       It only runs on the master (BLE client) as it should be followed
       by a synchronisation step."""
    if master_device:
        time.sleep(random.randint(SHORTEST_DELAY, LONGEST_DELAY))


def sync_test():
    """Only here as it is useful for testing."""
    for _ in range(10):
        pixels.fill(white)
        time.sleep(0.25)
        pixels.fill(black)
        time.sleep(0.25)

# TODO in notes document it behaves slightly differently as it cannot tell
# how long other play took until it receives data

# TODO - need to change at the very least code exchanging TimePacket
# after this because timeout can no longer be set and 


def get_opponent_reactiontime(player_reaction_dur):
    ### TODO test with length delay from other player for
    ### both cases to check buffering saves the day,
    ### e.g. player1 0.2s player2 6s
    ###      player1 4s   player2 0.5s
    opponent_reaction_dur = ERROR_DUR
    if master_device:       
        try:
            uart.write(TimePacket(player_reaction_dur,
                                  0.0).to_bytes())
            print("TimePacket TX")
            packet = Packet.from_stream(uart)
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
        packet = Packet.from_stream(uart)
        if isinstance(packet, TimePacket):
            print("TimePacket RX")
            opponent_reaction_dur = packet.duration
            try:
                uart.write(TimePacket(player_reaction_dur,
                                      0.0).to_bytes())
                print("TimePacket TX")
            except OSError as err:
                print(err, file=sys.stderr)
        elif packet is None:
            pass
        else:
            print("Unexpected packet type", packet)
    return opponent_reaction_dur


# TODO add victory/defeat/misdraw tunes??
def show_winner_and_misraws(player_reaction_dur, opponent_reaction_dur):
    win = False
    misdraw = False
    draw = False
    
    if player_reaction_dur < 0.1 or opponent_reaction_dur < 0.1:
        if player_reaction_dur != ERROR_DUR and player_reaction_dur < 0.1:
            misdraw = True
            pixels[player_px[0]:player_px[1]] = misdraw_colour
        if opponent_reaction_dur != ERROR_DUR and opponent_reaction_dur < 0.1:
            pixels[opponent_px[0]:opponent_px[1]] = misdraw_colour
    else:
        if player_reaction_dur < opponent_reaction_dur:
            win = True
            pixels[player_px[0]:player_px[1]] = win_colour
        elif opponent_reaction_dur < player_reaction_dur:
            pixels[opponent_px[0]:opponent_px[1]] = win_colour
        else:
            # Equality! Very unlikely to reach here
            pixels[player_px[0]:player_px[1]] = draw_colour
            pixels[opponent_px[0]:opponent_px[1]] = draw_colour
            draw = False

    return (win, misdraw, draw)


### TODO - this appears to fix a bug which may related to closing the
###        connection by program termination and other end not receiving it
### Bluetooth connection needs to be kept connected for the read to work
### TODO - reproduce this in smaller code
##time.sleep(5)


# CPB seeds from the hardware random number generation on its nRF52840 chip
# Note: CPX code used A4-A7 analogue inputs, CPB cannot use A7 for analogue in

wins = 0
misdraws = 0
losses = 0
draws = 0

# default timeout is 1.0 and on latest library with UARTService this
# cannot be changed
ble = BLERadio()

# Connect the two boards over Bluetooth Low Energy
# Switch on left will be client, switch on right will be server
if debug:
    print("connect()")
uart = connect()

# Calculate round-trip time (rtt) delay between the two CPB boards
# flashing blue to indicate the packets and longer 2s flash when done
if debug:
    print("ping_for_rtt()")
ble_send_time = ping_for_rtt()

for _ in range(TURNS):
    # TODO - could test and remake connection here?
    # TODO - decide on exception catching strategy
    # TODO - can i print stack trace from a caught exception

    # This is a good time to garbage collect
    gc.collect()
    
    # Random pause to stop players preempting the draw
    random_pause()

    # Synchronise the two boards by exchanging a Start message
    if debug:
        print("barrier()")
    barrier()

    # Show white on all NeoPixels to indicate draw now
    # This will execute at the same time on both boards
    pixels.fill(white)

    # Wait for and time how long it takes for player to press button
    start_t = time.monotonic()
    while not player_button():
        pass
    finish_t = time.monotonic()

    # Turn-off NeoPixels
    pixels.fill(black)
        
    # Play the shooting sound
    # 16k mono 8bit normalised version of
    # https://freesound.org/people/Diboz/sounds/213925/
    cpb.play_file("PistolRicochet.wav")

    # Exchange draw times
    # The CPBs are no longer synchronised due to variability of
    # reaction time between players
    player_reaction_dur = finish_t - start_t

    opponent_reaction_dur = get_opponent_reactiontime(player_reaction_dur)

    # Show green for winner and red for any misdraws
    (win, misdraw, draw) = show_winner_and_misraws(player_reaction_dur,
                                                   opponent_reaction_dur)
    if misdraw:
        misdraw += 1
    elif draw:
        draws += 1
    elif win:
        wins += 1
    else:
        losses += 1
    
    # Output reaction times to serial console in Mu friendly format
    print("({:d}, {:d}, {:f}, {:f})".format(wins, misdraws,
                                            player_reaction_dur,
                                            opponent_reaction_dur))

    # Keep NeoPixel result colour for 5 seconds then turn-off and repeat    
    time.sleep(5)
    pixels.fill(black)
