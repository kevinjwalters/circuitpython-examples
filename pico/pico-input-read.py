### pico-input-read v1.2
### Respond to simple serial commands with digital or analogue gpio

### Tested on Pi Pico W vs Pi Pico 2 W both running CircuitPython 10.1.3
### Tested on Pi Pico W vs Pimoroni Tiny 2350 both running CircuitPython 10.1.3

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

### Responses to commands sent over a serial/UART connection
### with digital or adc value from GP26
### Multiple read commands addded for noise analysis

### Relevant Errata: RP2350-9 and RP2040-E11


import os
import time

import analogio
import board
import busio
import digitalio


### TX pin must be even-numbered on RPxxxx
machine = os.uname().machine
if machine.find("Pimoroni Tiny") >= 0:
    SERIAL_TX_PIN = board.GP6
    SERIAL_RX_PIN = board.GP5
else:
    SERIAL_TX_PIN = board.GP16
    SERIAL_RX_PIN = board.GP17

### This is marked A0 on Tiny 2350
GPIO_PIN = board.GP26

SERIAL_BAUDRATE = 38400
CMD_READ_TIMEOUT_S = 1.0

serial = busio.UART(tx=SERIAL_TX_PIN, rx=SERIAL_RX_PIN,
                    baudrate=SERIAL_BAUDRATE, timeout=CMD_READ_TIMEOUT_S)

READ_ANA_CMD = "A"
READM_ANA_CMD = "B"

READ_DIG_CMD = "D"
READM_DIG_CMD = "E"

gpio = None


SAMPLE_COUNT = 32
sample_store = [0] * SAMPLE_COUNT
def get_sample_analogue(ana, samples=None):
    for idx in range(SAMPLE_COUNT):
        sample_store[idx] = ana.value

    ### Make a copy of samples before sorting if requested
    if samples is not None:
        samples[:] = sample_store

    sample_store.sort()
    total = 0
    ### Discard bottom two and top two for IQR style arithmetic mean
    for idx in range(2, SAMPLE_COUNT - 2):
        total += sample_store[idx]
    return total / (SAMPLE_COUNT - 4)


def get_digital(dig):
    return 1 if dig.value else 0


time.sleep(5)

original_samples = [0] * SAMPLE_COUNT
while True:
    serial_request = serial.readline()
    try:
        cmds = serial_request.decode("utf-8").split()
    except (AttributeError, UnicodeError):
        cmds = []

    for cmd in cmds:
        value = None
        if cmd in (READ_ANA_CMD, READM_ANA_CMD):
            ### Ensure input is correct type
            if not isinstance(gpio, analogio.AnalogIn):
                if gpio is not None:
                    gpio.deinit()
                gpio = analogio.AnalogIn(GPIO_PIN)

            if cmd == READ_ANA_CMD:
                value = get_sample_analogue(gpio)
            else:
                _ = get_sample_analogue(gpio, original_samples)
                value = ",".join([str(x) for x in original_samples])
        elif cmd in (READ_DIG_CMD, READM_DIG_CMD):
            ### Ensure input is correct type
            if not isinstance(gpio, digitalio.DigitalInOut):
                if gpio is not None:
                    gpio.deinit()
                gpio = digitalio.DigitalInOut(GPIO_PIN)

            if cmd == READ_DIG_CMD:
                value = get_digital(gpio)
            else:
                value = ",".join([str(get_digital(gpio)) for _ in range(SAMPLE_COUNT)])
        elif len(cmd) > 0:
            value = ""
        if value is not None:
            serial.write(f"{value}\n".encode("utf-8"))
