### cpb-quick-draw v1.10
### CircuitPython (on CPBs) Quick Draw reaction game

### Tested with Circuit Playground Bluefruit Alpha
### and CircuitPython and 5.0.0-beta.2

### Needs recent adafruit_ble and adafruit_circuitplayground.bluefruit libraries

### Need 2 CPB boards with switches set to different positions

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

debug = 3

# Bluetooth scanning timeout
BLESCAN_TIMEOUT = 5

TURNS = 10
# Integer number of seconds
SHORTEST_DELAY = 1
LONGEST_DELAY = 10

# The duration of the short blue flashes (in seconds)
# during time delay measurement in ping_for_rtt()
SYNC_FLASH_DUR = 0.1
# The number of "pings" sent by ping_for_rtt()
NUM_PINGS = 8

# A special value used to indicate failed exchange of reaction times
ERROR_DUR = -1.0

# A timeout value for the protocol
protocol_timeout = 14.0


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


master_device = cpb.switch  # True when switch is left (near ear symbol)

# The default brightness is 1.0 - leaving at that as it
# improves performance by removing need for a second buffer in memory
# 10 is number of NeoPixels on CPX/CPB
numpixels = const(10)
halfnumpixels = const(5)
pixels = cpb.pixels

darkest_red = (1, 0, 0)
red = (40, 0, 0)
green = (0, 30, 0)
blue = (0, 0, 10)
brightblue = (0, 0, 100)
yellow = (40, 20, 0)
white = (30, 30, 30)
black = (0, 0, 0)

win_colour = green
win_pixels = [win_colour] * halfnumpixels
opponent_misdraw_colour = darkest_red
misdraw_colour = red
misdraw_pixels = [misdraw_colour] * halfnumpixels
draw_colour = yellow
draw_pixels = [draw_colour] * halfnumpixels
lose_colour = black

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

def read_packet(uart, timeout=None):
    """Read a packet with an optional timeout."""
    if timeout is None:
        return Packet.from_stream(uart)
    else:
        packet = None
        t1 = time.monotonic()
        while packet is None and time.monotonic() - t1 < timeout:
            packet = Packet.from_stream(uart)
        return packet


def connect():
    """Connect two boards using the first UART Service the client finds
       over Bluetooth Low Energy. No timeouts, will wait forever."""
    uart = None
    if master_device:
        # Master code
        while uart is None:
            print("disconnected, scanning")
            for advertisement in ble.start_scan(ProvideServicesAdvertisement,
                                                timeout=BLESCAN_TIMEOUT):
                if debug >= 2:
                    print(advertisement.address, advertisement.rssi)
                if UARTService not in advertisement.services:
                    continue
                print("Connecting to", advertisement.address)
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
        print("Incoming connection from", "???")  # TODO - work out where to get this from?

    return uart


def ping_for_rtt():
    """Calculate the send time for Bluetooth Low Energy based from
       a series of round-trip time measurements and assuming that
       half of that is the send time.
       This code must be done at approximately the same time
       on each device as the timeout per packet is one second."""
    # The rtt is sent to server but for first packet client
    # sent there's no value to send, -1.0 is specal first packet value
    rtt = -1.0
    rtts = []
    offsets = []

    if master_device:
        # Master code
        while True:
            gc.collect()  # an opportune moment
            request = TimePacket(rtt, 0.0)

            print("TX")
            uart.write(request.to_bytes())
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
            if len(rtts) >= NUM_PINGS:
                break

            pixels.fill(blue)
            time.sleep(SYNC_FLASH_DUR)
            pixels.fill(black)
            # This second sleep is very important to ensure that the
            # server is already awaiting the next packet before client
            # sends it to avoid server instantly reading buffered packets
            time.sleep(SYNC_FLASH_DUR)

    else:
        responses = 0
        while True:
            gc.collect()  # an opportune moment
            # TODO - consider using uart.in_waiting
            packet = Packet.from_stream(uart)
            if isinstance(packet, TimePacket):
                print("RX")
                uart.write(TimePacket(-2.0, -1.0).to_bytes())
                responses += 1
                rtts.append(packet.duration)
                pixels.fill(blue)
                time.sleep(SYNC_FLASH_DUR)
                pixels.fill(black)
            elif packet is None:
                pass
            else:
                print("Unexpected packet type", packet)
            if responses >= NUM_PINGS:
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

    quicker_rtts = sorted(rtts[rtt_start:rtt_end])[0:(NUM_PINGS // 2) + 1]
    mean_rtt = sum(quicker_rtts) / len(quicker_rtts)
    # Assuming symmetry between send and receive times
    # this may not be perfectly true, the parsing is one factor here
    send_time = mean_rtt / 2.0

    print("BSE:", send_time)  ### TODO delete this.

    # Indicate sync with a longer 2 second blue flash
    pixels.fill(brightblue)
    time.sleep(2)
    pixels.fill(black)
    return send_time


def random_pause():
    """This is the pause before the players draw.
       It only runs on the master (BLE client) as it should be followed
       by a synchronising barrier."""
    if master_device:
        time.sleep(random.randint(SHORTEST_DELAY, LONGEST_DELAY))


def barrier(packet_send_time):
    """Master send a Start message and then waits for a reply.
       Slave waits for Start message, then sends reply, then pauses
       for packet_send_time so both master and slave return from
       barrier() at the same time."""

    if master_device:
        uart.write(StartGame().to_bytes())
        print("StartGame TX")
        packet = read_packet(uart, timeout=protocol_timeout)
        if isinstance(packet, StartGame):
            print("StartGame RX")
        else:
            print("Unexpected packet type", packet)

    else:
        packet = read_packet(uart, timeout=protocol_timeout)
        if isinstance(packet, StartGame):
            print("StartGame RX")
            uart.write(StartGame().to_bytes())
            print("StartGame TX")
        else:
            print("Unexpected packet type", packet)

        print("Sleeping to sync up", packet_send_time)
        time.sleep(packet_send_time)


def sync_test():
    """For testing synchronisation."""
    for _ in range(40):
        pixels.fill(white)
        time.sleep(0.1)
        pixels.fill(black)
        time.sleep(0.1)


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
        uart.write(TimePacket(player_reaction_dur,
                              0.0).to_bytes())
        print("TimePacket TX")
        packet = read_packet(uart, timeout=protocol_timeout)
        if isinstance(packet, TimePacket):
            print("TimePacket RX")
            opponent_reaction_dur = packet.duration
        else:
            print("Unexpected packet type", packet)

    else:
        packet = read_packet(uart, timeout=protocol_timeout)
        if isinstance(packet, TimePacket):
            print("TimePacket RX")
            opponent_reaction_dur = packet.duration
            uart.write(TimePacket(player_reaction_dur,
                                  0.0).to_bytes())
            print("TimePacket TX")
        else:
            print("Unexpected packet type", packet)
    return opponent_reaction_dur


# TODO add victory/defeat/misdraw tunes??
def show_winner(player_reaction_dur, opponent_reaction_dur):
    win = False
    misdraw = False
    draw = False
    colour = lose_colour

    if player_reaction_dur < 0.1 or opponent_reaction_dur < 0.1:
        if player_reaction_dur != ERROR_DUR and player_reaction_dur < 0.1:
            misdraw = True
            pixels[player_px[0]:player_px[1]] = misdraw_pixels
            colour = misdraw_colour
        if opponent_reaction_dur != ERROR_DUR and opponent_reaction_dur < 0.1:
            pixels[opponent_px[0]:opponent_px[1]] = misdraw_pixels
            colour = opponent_misdraw_colour
    else:
        if player_reaction_dur < opponent_reaction_dur:
            win = True
            pixels[player_px[0]:player_px[1]] = win_pixels
            colour = win_colour
        elif opponent_reaction_dur < player_reaction_dur:
            pixels[opponent_px[0]:opponent_px[1]] = win_pixels
        else:
            # Equality! Very unlikely to reach here
            draw = False
            pixels[player_px[0]:player_px[1]] = draw_pixels
            pixels[opponent_px[0]:opponent_px[1]] = draw_pixels
            colour = draw_colour

    return (win, misdraw, draw, colour)


def show_summary(result_colours):
    """Show the results on the NeoPixels."""
    # trim anything beyond 10
    for idx, colour in enumerate(result_colours[0:numpixels]):
        pixels[idx] = colour
        time.sleep(0.5)
        

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

my_results = []

for _ in range(TURNS):
    if uart is None:
        uart = connect()

    # This is a good time to garbage collect
    gc.collect()

    # Random pause to stop players preempting the draw
    random_pause()

    try:
        # Synchronise the two boards by exchanging a Start message
        if debug:
            print("barrier()")
        barrier(ble_send_time)

        if debug >= 4:
            sync_test()

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

        # The CPBs are no longer synchronised due to reaction time varying
        # per player
        # Exchange draw times
        player_reaction_dur = finish_t - start_t
        opponent_reaction_dur = get_opponent_reactiontime(player_reaction_dur)

        # Show green for winner and red for any misdraws
        (win, misdraw, draw, colour) = show_winner(player_reaction_dur,
                                                   opponent_reaction_dur)
        my_results.append(colour)
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
    except OSError as err:
        # TODO - can I print stack trace from a caught exception
        print("OSError", err)
        uart = None  # this will force a reconnection

    # TODO - test uart = None here to check reconnection works
    # TODO - This does not work - need some sort of connection cleanup too
    ##uart = None
    pixels.fill(black)

# show results summary on NeoPixels
show_summary(my_results)

while True:
   pass
