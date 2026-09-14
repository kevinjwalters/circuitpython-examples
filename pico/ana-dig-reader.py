### ana-dig-reader v1.4
### Respond to simple serial commands with digital or analogue gpio

### Tested on Pi Pico running CircuitPython 10.2.1
### TODO Tested on Pi Pico 2 W running CircuitPython 10.2.1
### TODO Tested on Pimoroni Tiny 2350 running CircuitPython 10.2.1
### TODO Tested on Circuit Playground Express running CircuitPython 10.2.1
### Tested on Feather M4 Express running CircuitPython 10.2.1
### Tested on UM Feather S2 running CircuitPython 10.2.1

### copy this file to Pico as code.py

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

### Port of arduino ana-dig-reader derived from pico-input-read

### Responses to commands sent over a serial/UART connection
### with digital or adc value from a pin

### Multiple read commands added for noise analysis

### The comments show code that can be stripped out to produce a version
### which works on the Circuit Playground Express and other ATSAMD21 boards



### maybe TODO - turn off neopixel if there is one

### TODO - MicroPython version that works on the V1 microbit
### or do i just go back to C - will there be a usable UART from C?


### pylint: disable=consider-using-f-string


import os
import time

import analogio
import board
import busio
import digitalio


SOFTWARE_NAME = "ana-dig-reader"
SOFTWARE_VERSION = "1.4"

LED_ON = True
LED_OFF = False

### TX pin must be even-numbered on RPxxxx
sysname = os.uname().sysname
machine = os.uname().machine
if (machine.find("Adafruit Feather M4 Express") >= 0 or
      machine.find("CircuitPlayground Express") >= 0 or
      machine.find("FeatherS2 with ESP32S2") >= 0 or
      machine.find("Adafruit Feather nRF52840 Express") >= 0):
    SERIAL_TX_PIN = board.TX   ### D1 under the covers
    SERIAL_RX_PIN = board.RX   ### D0 under the covers
    GPIO_PIN = board.A5
    LED_BUILTIN_PIN = board.LED
#S# BEGIN
elif machine.find("MEOWBIT") >= 0:
    ### STM32 has a lot of constraints on UART
    ### https://www.kittenbot.cc/blogs/learn/meowbit-makecode-coding-quickstart
    SERIAL_TX_PIN = board.P9
    SERIAL_RX_PIN = board.P6
    GPIO_PIN = board.P1
    LED_BUILTIN_PIN = board.LED_GREEN  ### top right
    board.DISPLAY.root_group = None    ### turn off the display
elif machine.find("micro:bit") >= 0:
    SERIAL_TX_PIN = board.P15
    SERIAL_RX_PIN = board.P14
    GPIO_PIN = board.P1
    LED_BUILTIN_PIN = None
elif machine.find("Pimoroni Tiny 2350") >= 0:
    SERIAL_TX_PIN = board.GP6  ### 6
    SERIAL_RX_PIN = board.GP5  ### 5
    GPIO_PIN = board.GP26_A0   ### A0
    LED_BUILTIN_PIN = board.LED_G
    LED_ON = False
    LED_OFF = True
elif machine.find("Raspberry Pi Pico") >= 0:
    SERIAL_TX_PIN = board.GP16
    SERIAL_RX_PIN = board.GP17
    GPIO_PIN = board.GP26
    LED_BUILTIN_PIN = board.LED
elif machine.find("Teensy 4.1") >= 0:
    ### 10.2.1 just crashes "Hard fault: memory access or instruction error."
    SERIAL_TX_PIN = board.D14   ### TX3
    SERIAL_RX_PIN = board.D15   ### RX3
    GPIO_PIN = board.D19        ### A5
    LED_BUILTIN_PIN = board.LED
#S# END
else:
    raise ValueError("Unsupported board...")

if machine.find("FeatherS2 with ESP32S2") >= 0:
    BOARD_MANU = "UM"
    BOARD_NAME = machine
elif machine.find("micro:bit") >= 0:
    BOARD_MANU = "BBC"
    BOARD_NAME = "micro:bit v2"
else:
    BOARD_MANU, BOARD_NAME = machine.split(" ", 2 - 1)

with_pos = BOARD_NAME.find(" with ")
if with_pos >= 0:
    BOARD_NAME = BOARD_NAME[:with_pos]

BOARD_MCU = sysname.upper()
elems = BOARD_MCU.split("ESP32")
if len(elems) == 2 and len(elems[1]) > 0:
    ### Add a hyphen
    BOARD_MCU = "ESP32-" + elems[1]


pixels = None
if machine.find("CircuitPlayground Express") >= 0:
    import neopixel
    pixels = neopixel.NeoPixel(board.NEOPIXEL, 10)

if pixels:
    pixels.fill(0)  ### Ensure they are all off


ANALOGUE_PIN = str(GPIO_PIN).replace("board.", "")
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


### receiver_buffer_size is documented as having default value of 64
serial = busio.UART(tx=SERIAL_TX_PIN, rx=SERIAL_RX_PIN,
                    baudrate=SERIAL_BAUDRATE,
                    timeout=CMD_READ_TIMEOUT_S)

READ_ANA_CMD = "A"
READM_ANA_CMD = "B"
READV_ANA_CMD = "C"

#S# BEGIN
READ_DIG_CMD = "D"
READM_DIG_CMD = "E"
READV_DIG_CMD = "F"
#S# END

INFO_CMD = "I"
COUNT_OFFSET = ord(" ")

ENCODING = "utf-8"
gpio = None

#S# BEGIN
SAMPLE_COUNT = 32
sample_store = [0] * SAMPLE_COUNT
#S# END
def get_sample_analogue(ana, *,
                        samples=None,
                        iqrmean=True):
    if not iqrmean:
        return ana.value

#S# BEGIN
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
#S# END


#S# BEGIN
def get_digital(dig):
    return 1 if dig.value else 0
#S# END


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
#S# BEGIN
original_samples = [0] * SAMPLE_COUNT
#S# END
while True:
    if serial.in_waiting:
        serial.readinto(one_byte_buf)
        cmd = chr(one_byte_buf[0])

        value = None
        if cmd in (READ_ANA_CMD, READM_ANA_CMD, READV_ANA_CMD):
            ### Ensure input is correct type
            if not isinstance(gpio, analogio.AnalogIn):
                if gpio is not None:
                    gpio.deinit()
                gpio = analogio.AnalogIn(GPIO_PIN)

            if cmd == READ_ANA_CMD:
                value = get_sample_analogue(gpio)
            elif cmd == READM_ANA_CMD:
                #S# BEGIN
                _ = get_sample_analogue(gpio, samples=original_samples)
                value = ",".join([str(x) for x in original_samples])
                #S# END
                pass   ### pylint: disable=unnecessary-pass
            else:
                one_byte_buf[0] = COUNT_OFFSET
                serial.readinto(one_byte_buf)  ### a timeout should leave buffer alone...
                count = one_byte_buf[0] - COUNT_OFFSET
                ### Serial writes in a loop here as creating a large value string
                ### causes MemoryError on SAMD21
                if count > 0:
                    for _ in range(count - 1):
                        serial.write(str_to_bytes(f"{get_sample_analogue(gpio, iqrmean=False) >> SHIFT_BITS} "))
                    serial.write(str_to_bytes(f"{get_sample_analogue(gpio, iqrmean=False) >> SHIFT_BITS}\n"))
                else:
                    value = ""
#S# BEGIN
        elif cmd in (READ_DIG_CMD, READM_DIG_CMD, READV_DIG_CMD):
            ### Ensure input is correct type
            if not isinstance(gpio, digitalio.DigitalInOut):
                if gpio is not None:
                    gpio.deinit()
                gpio = digitalio.DigitalInOut(GPIO_PIN)

            if cmd == READ_DIG_CMD:
                value = get_digital(gpio)
            elif cmd == READM_DIG_CMD:
                value = ",".join([str(get_digital(gpio)) for _ in range(SAMPLE_COUNT)])
            else:
                one_byte_buf[0] = COUNT_OFFSET
                serial.readinto(one_byte_buf)  ### a timeout should leave buffer alone...
                count = one_byte_buf[0] - COUNT_OFFSET
                if count > 0:
                    for _ in range(count - 1):
                        serial.write(str_to_bytes(f"{get_digital(gpio)} "))
                    serial.write(str_to_bytes(f"{get_digital(gpio)}\n"))
                else:
                    value = ""
#S# END
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
