### ana-dig-reader-mcp3208 v1.0
### Respond to simple serial commands with analogue values from MCP3208

### Tested on Cytron EDU Pi Pico running CircuitPython 10.2.1

### copy this file to Pico WH as code.py

### MIT License

### Copyright (c) 2026 Kevin J. Walters

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

### SPDX-FileCopyrightText: 2026 Kevin J. Walters

### Variant of ana-dig-reader (derived from pico-input-read)


import os
import time

import board
import busio
import digitalio

import adafruit_mcp3xxx.mcp3208 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn as MCPAnalogIn


SOFTWARE_NAME = "ana-dig-reader-mcp3208"
SOFTWARE_VERSION = "1.0"

LED_ON = True
LED_OFF = False

### TX pin must be even-numbered on RPxxxx
sysname = os.uname().sysname
machine = os.uname().machine
if machine.find("Cytron EDU PICO") >= 0:
    ### EDU PICO's pins for sdcard reader - reused here for MCP3208
    SPI_RX  = board.GP16
    SPI_CS  = board.GP17
    SPI_SCK  = board.GP18
    SPI_TX  = board.GP19
    SERIAL_TX_PIN = board.GP0  ### blue/yellow buttons use these
    SERIAL_RX_PIN = board.GP1  ### DO NOT PRESS THEM!
    MCP_PIN = MCP.P0
    LED_BUILTIN_PIN = board.LED
else:
    raise ValueError("Unsupported board...")

BOARD_MANU = "MicroChip"
BOARD_NAME = "MCP3208"
BOARD_MCU = "MCP3208"


ANALOGUE_PIN = str(MCP_PIN).replace("board.", "")
ADC_VREF = 3.3
ADC_RESOLUTION = 12
SHIFT_BITS = 16 - ADC_RESOLUTION


if LED_BUILTIN_PIN is not None:
    led_builtin = digitalio.DigitalInOut(LED_BUILTIN_PIN)
    led_builtin.direction = digitalio.Direction.OUTPUT
    led_builtin.value = LED_OFF
else:
    led_builtin = None


SERIAL_BAUDRATE = 38400
CMD_READ_TIMEOUT_S = 1.0

spi = busio.SPI(clock=SPI_SCK, MISO=SPI_RX, MOSI=SPI_TX)
cs = digitalio.DigitalInOut(SPI_CS)
mcp = MCP.MCP3208(spi, cs, ref_voltage=ADC_VREF)
mcp_chan = MCPAnalogIn(mcp, MCP_PIN)


### receiver_buffer_size is documented as having default value of 64
serial = busio.UART(tx=SERIAL_TX_PIN, rx=SERIAL_RX_PIN,
                    baudrate=SERIAL_BAUDRATE,
                    timeout=CMD_READ_TIMEOUT_S)

READ_ANA_CMD = "A"
READM_ANA_CMD = "B"
READV_ANA_CMD = "C"


INFO_CMD = "I"
COUNT_OFFSET = ord(" ")

ENCODING = "utf-8"


SAMPLE_COUNT = 32
sample_store = [0] * SAMPLE_COUNT
def get_sample_analogue(ana, *,
                        samples=None,
                        iqrmean=True):
    if not iqrmean:
        return ana.value

    for idx in range(SAMPLE_COUNT):
        sample_store[idx] = ana.value

    ### Make a copy of elements of samples before sorting if requested
    if samples is not None:
        samples[:] = sample_store[:len(samples)]

    sample_store.sort()
    total = 0
    ### Discard bottom two and top two for IQR style arithmetic mean
    for idx in range(2, SAMPLE_COUNT - 2):
        total += sample_store[idx]
    return total / (SAMPLE_COUNT - 4)


def str_to_bytes(text):
    try:
        text_as_bytes = text.encode(ENCODING)
    except AttributeError:
        text_as_bytes = bytes(ord(c) for c in text)
    return text_as_bytes


def flash(f_count):
    if led_builtin is not None:
        for _ in range(f_count):
            led_builtin.value = LED_ON
            time.sleep(0.3)
            led_builtin.value = LED_OFF
            time.sleep(0.3)


flash(2)
one_byte_buf = bytearray(1)
original_samples = [0] * SAMPLE_COUNT
while True:
    if serial.in_waiting:
        serial.readinto(one_byte_buf)
        cmd = chr(one_byte_buf[0])

        value = None
        if cmd in (READ_ANA_CMD, READM_ANA_CMD, READV_ANA_CMD):
            if cmd == READ_ANA_CMD:
                value = get_sample_analogue(mcp_chan)
            elif cmd == READM_ANA_CMD:
                _ = get_sample_analogue(mcp_chan, samples=original_samples)
                value = ",".join([f"{x:05d}" for x in original_samples])
                pass   ### pylint: disable=unnecessary-pass
            else:
                one_byte_buf[0] = COUNT_OFFSET
                serial.readinto(one_byte_buf)  ### a timeout should leave buffer alone...
                count = one_byte_buf[0] - COUNT_OFFSET
                if count > 0:
                    for _ in range(count - 1):
                        serial.write(str_to_bytes(f"{get_sample_analogue(mcp_chan, iqrmean=False) >> SHIFT_BITS:05d} "))
                    serial.write(str_to_bytes(f"{get_sample_analogue(mcp_chan, iqrmean=False) >> SHIFT_BITS:05d}\n"))
                else:
                    value = ""
        elif cmd == INFO_CMD:
            flash(3)
            value = (f'"INFO","{SOFTWARE_NAME:s}","{SOFTWARE_VERSION:s}",' +
                     f'"{BOARD_MANU:s}","{BOARD_NAME:s}","{BOARD_MCU:s}",' +
                     '"CircuitPython",' +
                     f'"adc_bits={ADC_RESOLUTION:d};aref={ADC_VREF:.1f};' +
                     f'input_pin={ANALOGUE_PIN:s};read=raw"')
        elif cmd in ("\r", "\n", "\0"):
            pass   ### just ignore EOL, no response
        elif len(cmd) > 0:
            value = ""

        if value is not None:
            serial.write(str_to_bytes(f"{value}\n"))
