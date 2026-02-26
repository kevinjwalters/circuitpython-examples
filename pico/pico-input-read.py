### pico-gpio-read v1.0
### Respond to simple serial commands with digital or analogue gpio

### Tested on Pi Pico W vs Pi Pico 2 W both running CircuitPython 10.1.3

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

### Relevant Errata: RP2350-9 and RP2040-E11


import time

import analogio
import board
import busio
import digitalio

SERIAL_TX_PIN = board.GP16
SERIAL_RX_PIN = board.GP17
GPIO_PIN = board.GP26
SERIAL_BAUDRATE = 38400
CMD_READ_TIMEOUT_S = 1.0

serial = busio.UART(tx=SERIAL_TX_PIN, rx=SERIAL_RX_PIN,
                    baudrate=SERIAL_BAUDRATE, timeout=CMD_READ_TIMEOUT_S)

READ_ANA_CMD = "A"
READ_DIG_CMD = "D"

gpio = None


SAMPLE_COUNT = 32
samples = [0] * SAMPLE_COUNT
def get_sample_analogue(ana):
    for idx in range(SAMPLE_COUNT):
        samples[idx] = ana.value
    samples.sort()
    total = 0
    ### Discard bottom two and top two for IQR style arithmetic mean
    for idx in range(2, SAMPLE_COUNT - 2):
        total += samples[idx]
    return total / (SAMPLE_COUNT - 4)

def get_digital(dig):
    return 1 if dig.value else 0

time.sleep(5)


while True:
    serial_request = serial.readline()
    try:
        cmds = serial_request.decode("utf-8").split()
    except (AttributeError, UnicodeError):
        cmds = []

    for cmd in cmds:
        if cmd == READ_ANA_CMD:
            ### Ensure input is correct type
            if not isinstance(gpio, analogio.AnalogIn):
                if gpio is not None:
                    gpio.deinit()
                gpio = analogio.AnalogIn(GPIO_PIN)

            value = get_sample_analogue(gpio)
            serial.write(f"{value}\n".encode("utf-8"))
        elif cmd == READ_DIG_CMD:
            ### Ensure input is correct type
            if not isinstance(gpio, digitalio.DigitalInOut):
                if gpio is not None:
                    gpio.deinit()
                gpio = digitalio.DigitalInOut(GPIO_PIN)

            value = get_digital(gpio)
            serial.write(f"{value}\n".encode("utf-8"))
        elif len(cmd) > 0:
            serial.write("\n".encode("utf-8"))
