### pico-input-tester v2.0
### Measure RP2350 Errata 9 leakage flaw with smoother PWM output and ADC reads including ADS1115

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

### Output triangle wave using PWM output
### then read voltage values to determine any
### drop across a resistor connected to input
### on another Pi Pico 2

### Relevant Errata: RP2350-9 and RP2040-E11

import gc
import time

import analogio
import board
import busio
import microcontroller
import pwmio

from adafruit_ads1x15 import ADS1115, ads1x15
from adafruit_ads1x15.analog_in import AnalogIn as ADSAnalogIn

PWM_OUT_PIN = board.GP10
SERIAL_TX_PIN = board.GP16
SERIAL_RX_PIN = board.GP17
I2C_SDA_PIN = board.GP14
I2C_SCL_PIN = board.GP15
ADC_SMOUT_PIN = board.GP26      ### RC smoothed output
ADC_RES_SMOUT_PIN = board.GP27  ### voltage the other side of large resistor
SERIAL_BAUDRATE = 38400
RESPONSE_CHAR_WAIT_S = 0.5      ### very generous value!

PWM_RANGE = round(3.3 * 1_000)  ### number of PWM values

### CircuitPython's duty_cycle range is always 0 to 65535
OUT_MIN = 0
OUT_MAX = 65535
### duty cycle increment/decrement value for triangle wave
### must be 1.0 or larger
TRIANGLE_STEPS = [1024,
                  ##1000,
                  ##65535 / 3.3 / 100,
                  65535 / 3.3 / 1000
                  ]

NOT_AVAIL = "NA"

### 5 RC time constants for guess at internal GPIO output impedance
### plus external 220ohm pair in parallel times capacitance
IMP_GPIO = 123
RCF_R = 220 / 2
RCF_C = 470e-6
### Resistance value around 10k-20k should be viable here to observe the flaw,
### below about 7-8k the problem should disappear...
#IMP_RES = 10e3
IMP_RES = 9.91e3
SETTLE_TIME_S = 5 * (IMP_GPIO + RCF_R) * RCF_C

READ_ANA_CMD = "A"
READ_DIG_CMD = "D"

serial = busio.UART(tx=SERIAL_TX_PIN, rx=SERIAL_RX_PIN,
                    baudrate=SERIAL_BAUDRATE, timeout=RESPONSE_CHAR_WAIT_S)

cpu_freq = microcontroller.cpus[0].frequency

def pwm_init(dc):
    return pwmio.PWMOut(PWM_OUT_PIN,
                        duty_cycle=dc,
                        frequency=round(cpu_freq / PWM_RANGE))


adc_smout = analogio.AnalogIn(ADC_SMOUT_PIN)
adc_res_smout = analogio.AnalogIn(ADC_RES_SMOUT_PIN)

### TI ADS1x15 can go way faster for i2c but use 100kHz to cater
### for long dangling cables
### ADS1x15 has a differential mode but not using it here
DEF_ADS1115_ADDR = 0x48
tiads = tiads_smout = tiads_res_smout = None
try:
    i2c = busio.I2C(scl=I2C_SCL_PIN, sda=I2C_SDA_PIN,
                    frequency=100_000)

    while i2c.try_lock():
        pass
    device_addrs = i2c.scan()
    i2c.unlock()

    if device_addrs.count(DEF_ADS1115_ADDR) > 0:
        tiads = ADS1115(i2c)  ### defaults to data_rate of 128 samples per second
        tiads_smout = ADSAnalogIn(tiads, ads1x15.Pin.A0)
        tiads_res_smout = ADSAnalogIn(tiads, ads1x15.Pin.A1)
except RuntimeError:
    ### "RuntimeError: No pull up found on SDA or SCL; check your wiring" will happen
    ### if nothing is connected
    pass

SAMPLE_COUNT = 32
samples = [0] * SAMPLE_COUNT
def get_sample(ana):
    for idx in range(SAMPLE_COUNT):
        samples[idx] = ana.value
    samples.sort()
    total = 0
    ### Discard bottom few and top few for IQR style arithmetic mean
    for idx in range(2, SAMPLE_COUNT - 2):
        total += samples[idx]
    return total / (SAMPLE_COUNT - 4)


def triangle_waveform(step):
    dc_value_fp = OUT_MIN
    direction_up = True

    while True:
        yield round(dc_value_fp)
        if direction_up:
            dc_value_fp += step
            if dc_value_fp > OUT_MAX:
                if round(dc_value_fp) == OUT_MAX + 1:
                    dc_value_fp = OUT_MAX
                else:
                    direction_up = False
                    dc_value_fp = OUT_MAX + 1 - step
        else:
            dc_value_fp -= step
            if dc_value_fp < OUT_MIN:
                if round(dc_value_fp) == OUT_MIN - 1:
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


time.sleep(15)
### Print header
print(",".join(["start_ns",
                "test_idx",
                "dc_value",
                "int_adc_smout",
                "ext_adc_smout",
                "int_adc_res_smout",
                "ext_adc_res_smout",
                "input",
                "rem_adc_res_smout",
                "c_pwm"]))

cycle_count = 0
while True:
    for continuous_pwm in (True, False):
        pwm_out = pwm_init(0) if continuous_pwm else None
        for cmd in (READ_DIG_CMD, READ_ANA_CMD):
            for step_gen in [rp2040adcdnl()] + [triangle_waveform(s) for s in TRIANGLE_STEPS]:
                gc.collect()
                cycle_count += 1
                cmd_b = cmd.encode('utf-8') + bytes([ord("\n")])
                for dc_value in step_gen:
                    if continuous_pwm:
                        pwm_out.duty_cycle = dc_value
                        time.sleep(SETTLE_TIME_S)
                    else:
                        ### This is only appropriate for large capacitors like 470uF
                        pwm_out = pwm_init(dc_value)
                        time.sleep(SETTLE_TIME_S)
                        pwm_out.deinit()  ### return to high impedance input

                    ### Issues read ADC or read digital input command
                    ### to remote Pi Pico 2 then
                    ### do local reads while that's being sent/processed
                    serial.write(cmd_b)

                    start_ns = time.monotonic_ns()
                    int_adc_smout = get_sample(adc_smout)
                    ### Voltage is used for ADS1115 as it has variable gain and
                    ### an internal voltage reference
                    ext_adc_smout = tiads_smout.voltage if tiads_smout else NOT_AVAIL
                    int_adc_res_smout = get_sample(adc_res_smout)
                    ext_adc_res_smout = tiads_res_smout.voltage if tiads_res_smout else NOT_AVAIL

                    ### The timeout on the serial object does not work in all cases
                    resp = serial.readline()
                    try:
                        rars_str = resp.decode("utf-8").split(",")[0]
                        ### Digital value comes back as integer 0 or 1
                        rem_adc_res_smout = (int(rars_str) if cmd == READ_DIG_CMD
                                             else float(rars_str))
                    except (AttributeError, UnicodeError, ValueError):
                        rem_adc_res_smout = NOT_AVAIL
                    c_pwm = "T" if continuous_pwm else "F"
                    print(f"{start_ns},{cycle_count},{dc_value},{int_adc_smout},{ext_adc_smout},{int_adc_res_smout},{ext_adc_res_smout},{cmd},{rem_adc_res_smout},{c_pwm}")
