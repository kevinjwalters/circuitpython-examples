### adctest-sg v1.0
### Test MCP4728 DAC against an ADS1115

### Tested on Cytron Maker Nano 2040 with Adafruit MCP4728 boards via ISO1540 isolator board
### and Seeedstudio Grove ADS1115 with CircuitPython 10.2.1

### copy this file to Cytron Maker Nano 2040 as code.py

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

### The DAC needs to be powered with a very stable power source for
### good accuracy


import gc
import time

import board
import busio

from adafruit_ads1x15 import ADS1115, ads1x15
from adafruit_ads1x15.analog_in import AnalogIn as ADSAnalogIn
import adafruit_mcp4728
import neopixel


### This needs to be set to the voltage for the DAC power supply
### 4 fully charged NiMH can produce 5.6V which is too high
### anything below 5.5V is okay, 5.1-5.2V is ideal
DAC_EST_V = 5.2
DAC_MAX_CODE = 4095   ### 12 bit max
DAC_CHANNELS = ("A", "B", "C", "D")

OUT_MIN = 0
OUT_MAX = DAC_MAX_CODE

SERIAL_TX_PIN = board.GP12
SERIAL_RX_PIN = board.GP13

### Maker port 0
I2C_SDA_PIN = board.GP1
I2C_SCL_PIN = board.GP0

SERIAL_BAUDRATE = 38400
RESPONSE_CHAR_WAIT_S = 0.5  ### very generous value!

MCP_OUTPUT_PIN = "A"
ADS1115_PIN = ads1x15.Pin.A0
ADS1115_RATE = 128

I2C_FREQUENCY = 400_000
MICROCONTROLLER_SUPPLY = 3.3
PIXEL_PIN = board.RGB
PIXEL_COUNT = 2

BLACK = 0x000000

if PIXEL_COUNT:
    pixels = neopixel.NeoPixel(PIXEL_PIN, PIXEL_COUNT, brightness=1.0)
    pixels.fill(BLACK)
else:
    pixels = None

i2c = busio.I2C(scl=board.GP1,
                sda=board.GP0,
                frequency=I2C_FREQUENCY)
mcp_dac = adafruit_mcp4728.MCP4728(i2c)

### mode changes are broken https://github.com/adafruit/Adafruit_CircuitPython_ADS1x15/issues/110
### creating object inside test_adc for now
## ads1115 = ADS1115(i2c, data_rate=128, mode=ads1x15.Mode.SINGLE)
## ads1115.gain = 2/3   ### for up to 6.144V
## ads1115_chan = ADSAnalogIn(ads1115, ADS1115_PIN)

### Set all outputs to 0 and save the settings in EEPROM
### TODO - document that code should be run once (before connecting a non 5V device)
for chan in DAC_CHANNELS:
    d_chan = getattr(mcp_dac, "channel_" + chan.lower())
    d_chan.raw_value = 0
mcp_dac.save_settings()


NOT_AVAIL = "NA"

### TODO - could use this to check baud rate and get adc details
### "INFO","Cytron Maker Nano RP2040 with rp2040", "rp2040", "CircuitPython", "10.2.1 on 2026-05-13","adc=12;aref=3.3"
INFO_CMD = "I"

READV_ANA_CMD = "C"
READV_DIG_CMD = "F"

serial = busio.UART(tx=SERIAL_TX_PIN, rx=SERIAL_RX_PIN,
                    baudrate=SERIAL_BAUDRATE,
                    timeout=RESPONSE_CHAR_WAIT_S)


def triangle_waveform(step):
    dc_value_fp = OUT_MIN
    direction_up = True

    while True:
        yield round(dc_value_fp)
        if direction_up:
            dc_value_fp += step
            if dc_value_fp > OUT_MAX:
                if dc_value_fp != OUT_MAX + 1 and round(dc_value_fp) == OUT_MAX + 1:
                    dc_value_fp = OUT_MAX
                else:
                    direction_up = False
                    dc_value_fp = OUT_MAX + 1 - step
        else:
            dc_value_fp -= step
            if dc_value_fp < OUT_MIN:
                if dc_value_fp != OUT_MIN - 1 and round(dc_value_fp) == OUT_MIN - 1:
                    dc_value_fp = OUT_MIN
                else:
                    break

DNL_SPIKES = [(512 * idx ) for idx in (1,3,5,7)]
def rp2040adcdnl():
    for _ in range(4):
        yield 0
    for spike in DNL_SPIKES:
        ### +/-50mV is no good, misses DNL spikes
        ### using 0mv to 150mV
        ##for half_step in range(-63, 63 + 1):
        for half_step in range(0, 63 * 3 + 1):
            value = (spike << 4) + (half_step << 3)
            if 0 <= value <= 65535:
                yield value
    for _ in range(4):
        yield 65535
    for step_down_to_zero in range(65536 - 8192, -1, -8192):
        yield step_down_to_zero


#print(list(triangle_waveform(8192)))
#print(list(rp2040adcdnl()))

def output(elems):
    print(",".join([NOT_AVAIL if x is None else (f'"{x}"' if isinstance(x, str) else str(x)) for x in elems]))


def test_adc(dac,
             dac_values,
             *,
             dac_pin=MCP_OUTPUT_PIN,
             adc_pin=ADS1115_PIN,
             adc_mode="S",
             dac_vref_mv="max",
             sample_count=1,
             runs=1,
             remote=True,
             reset_value=0):
    if adc_mode == "C":
        sample_mode = ads1x15.Mode.CONTINUOUS
        ads1115_wait = 2 / sample_rate
    else:
        sample_mode = ads1x15.Mode.SINGLE
        ads1115_wait = 0
    ### 2/3 gain required for up to 6.144V measurements
    ads1115 = ADS1115(i2c, data_rate=ADS1115_RATE, mode=sample_mode, gain=2/3)
    ads1115_chan = ADSAnalogIn(ads1115, adc_pin)

    dac_chan = getattr(dac, "channel_" + dac_pin.lower())

    max_v = None
    if dac_vref_mv=="max":
        dac_chan.vref = adafruit_mcp4728.Vref.VDD
        max_v = DAC_EST_V
    elif dac_vref_mv in (2048, 4096):
        dac_chan.vref = adafruit_mcp4728.Vref.INTERNAL
        dac_chan.gain = dac_vref_mv // 2048   ### gain is 1 or 2
        max_v = dac_vref_mv / 1000.0

    samples = [None] * sample_count
    cmd = READV_ANA_CMD.encode('utf-8') + bytes([sample_count + ord(" "),
                                                 ord("\n")])

    gc.collect()
    max_value = DAC_MAX_CODE
    ### Output the values, take ADC readings and print results
    for idx in range(runs):
        for value in dac_values:
            if value > max_value:
                continue

            est_voltage = max_v * value / 4096
            dac_chan.raw_value = value
            start_ns = time.monotonic_ns()
            if remote:
                serial.write(cmd)
                ### The timeout on the serial object does not work in all cases
                resp = serial.readline()
                try:
                    rars_str = resp.decode("utf-8").split(",")[0]
                    ### TODO finish parsing

                    ### TODO check for saturation or tiny nonsense values (beyond 20% error?)
                    ### to avoid testing a 3.3V at 5.1V
                    ### use m_voltage
                except (UnicodeError, ):
                    pass

            if ads1115_wait:
                adjusted_wait = ads1115_wait - (time.monotonic_ns() - start_ns) / 1e9
                if adjusted_wait > 0.0:
                    time.sleep(adjusted_wait)
            m_voltage = ads1115_chan.voltage

            output([dac_pin, adc_pin, adc_mode, dac_vref_mv,
                    idx, value, m_voltage] + samples)

    ### Switch back to single shot to minimise power consumption
    if ads1115.mode == ads1x15.Mode.CONTINUOUS:
        ads1115.mode = ads1x15.Mode.SINGLE

    if reset_value is not None:
        dac_chan.raw_value = reset_value


time.sleep(15)

test_dac = True
if test_dac:
    print("# Testing MCP4728 channnels")
    for chan in (MCP_OUTPUT_PIN,):
        for vref in ("max", 4096, 2048):
            for s_mode in ("S", "C"):
                #dac_values = triangle_waveform(512)
                values = triangle_waveform(1)
                test_adc(mcp_dac, values, dac_pin=chan, adc_mode=s_mode, dac_vref_mv=vref, remote=False)
                print()

        time.sleep(60)

    while True:
        pass
