### clue-mutlitemplogger.py v1.2
### Measure temperature from multiple sensors and log to CIRCUITPY

### This now writes every 6 minutes to REDUCE THE WEAR on the flash chip
### (replacing this involves SMD soldering!)
### See https://forums.adafruit.com/viewtopic.php?f=65&t=175527

### Tested with Adafruit CLUE and CircuitPython 6.1.0

### MIT License

### Copyright (c) 2021 Kevin J. Walters

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
import math
from collections import OrderedDict

import microcontroller
import board
from adafruit_onewire.bus import OneWireBus
import adafruit_ds18x20
import adafruit_bmp280
import adafruit_sht31d
import neopixel
from analogio import AnalogIn


### Avoid P0-P2 as they have 1M resistors to facilitate capacitive touch
### Avoid P5/P11 which also have pull resistors for buttons
NTC_PIN = board.P4
DS18X20_PIN = board.P7
TMP36_PIN = board.P10
LM35_PIN = board.P12

MAX_AIN = 2**16 - 1

VERBOSE = False

### Measure every 10 seconds but do not write to CIRCUITPY at this
### rate as the flash does not have wear-levelling and
count = 3
interval = 10
interval_ns = interval * 1000 * 1000 * 1000
write_buffer_lines = 108  ### 8640 bytes every 108/3*10=360 seconds
pending_writes = []

console = True


### CIRCUITPY will only be writeable if boot.py has made it so
try:
    data_file = open("/t1.txt", "ab")
except OSError as ose:
    data_file = None

### NeoPixel colour during measurement
### Bright values may be useful if powered from a
### USB power bank with low-current auto off
RECORDING = 0xff0000
READING = 0x00ff00 + (0x0000ff if data_file else 0)
BLACK = 0x000000


### First value might be questionable with a high impedance source
### due to input multiplexing
def get_voltage(ain, samples=500):
    return sum([ain.value for _ in range(samples)]) / (samples * MAX_AIN) * vref


def set_backlight(level):
    board.DISPLAY.brightness = level


def find_DS18X20(bus, verbose=True):
    """This assumes it is the only thing connected.
       Do not forget the 4.7k pullup resistor!"""
    devices = bus.scan()
    if verbose:
        for dev in devices:
            print("ROM = {}\tFamily = 0x{:02x}".format([hex(i) for i in dev.rom],
                                                       dev.family_code))
    return devices[0] if devices else None


def measure_temps(sensor_list=None):
    names = sensors.keys() if sensor_list is None else sensor_list
    readings = OrderedDict()
    pixel[0] = READING
    for s_name in names:
        readings[s_name] = sensors[s_name]()
    pixel[0] = BLACK
    return readings


i2c = board.I2C()
ow_bus = OneWireBus(DS18X20_PIN)
bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(i2c)
sht31d = adafruit_sht31d.SHT31D(i2c)
ds18b20 = adafruit_ds18x20.DS18X20(ow_bus,
                                   find_DS18X20(ow_bus, verbose=VERBOSE))
pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)

ntc_ain = AnalogIn(NTC_PIN)
tmp36_ain = AnalogIn(TMP36_PIN)
lm35_ain = AnalogIn(LM35_PIN)

vref = ntc_ain.reference_voltage


### Review PAD_TO_LEN if extending this dict
sensors = OrderedDict([("bmp280", lambda: bmp280.temperature),
                       ("sht31d", lambda: sht31d.temperature),
                       ("cpu", lambda: microcontroller.cpu.temperature),
                       ("ds18b20", lambda: ds18b20.temperature),
                       ("tmp36", lambda: get_voltage(tmp36_ain) * 100.0 - 50.0),
                       ("lm35", lambda: get_voltage(lm35_ain) * 100.0),
                       ("ntc", lambda: get_voltage(ntc_ain))])


def output(text, *, pad=" ", pad_len=0, end=b"\x0d\x0a", encoding="ascii"):
    if pad and pad_len:
        out_text = text + " " * (pad_len - len(text) - len(end))
    else:
        out_text = text

    if console:
        print(out_text)
    if data_file:
        pending_writes.append(out_text.encode(encoding) + end)
        if len(pending_writes) >= write_buffer_lines:
            pixel[0] = RECORDING
            for line in pending_writes:
                data_file.write(line)
            data_file.flush()
            pending_writes.clear()
            pixel[0] = BLACK


### 80 chars minus CRLF
### THIS IS A BIT TIGHT - EXTEND IF MORE MEASUREMENTS ARE ADDED
FIXED_WIDTH = 80
HEADER = "# time,backlight," + ",".join(sensors.keys())

for _ in range(3):
    output(HEADER, pad_len=FIXED_WIDTH)


last_loop_ns = 0

backlight_cycle_dur_ns = 7200e9
backlight_cycle = [1.0, 0.0, 0.0, 0.125, 0.25, 0.5]

start_loop_ns = time.monotonic_ns()
while True:
    while True:
        now_ns = time.monotonic_ns()
        if now_ns > last_loop_ns + interval_ns:
            break
    last_loop_ns = now_ns

    ### Cycle the backlight through the brightness values stored in list
    phase, _ = math.modf((now_ns - start_loop_ns) / backlight_cycle_dur_ns)
    backlight = backlight_cycle[min(int(phase * len(backlight_cycle)),
                                    len(backlight_cycle) - 1)]
    set_backlight(backlight)

    ### Take a few measurements and print / log them
    for _ in range(count):
        in_start_ns = time.monotonic_ns()
        temps = measure_temps()
        data_as_text = ("{:d},{:.3f},".format(in_start_ns, backlight)
                        + ",".join([str(temp) for temp in temps.values()]))
        output(data_as_text, pad_len=FIXED_WIDTH)
