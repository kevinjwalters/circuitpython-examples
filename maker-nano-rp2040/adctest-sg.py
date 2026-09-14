### adctest-sg v1.1
### Test another microcontroller's ADC using an MCP4728 DAC and an ADS1115

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
### good accuracy, batteries and a good linear regulator work well

### See https://www.instructables.com/member/kevinjwalters for article on how to set
### up the circuit for the testing - two 100 ohm resistors are used to combined
### the output for two DAC channels for slightly finer resolution

### TODO - document in article that my branch needs to be used for library if PR not
### yet integrated and distributed in release file


import array
import gc
import time
from collections import OrderedDict

import board
import busio
import microcontroller
import pwmio


### neopixel and simpleio are frozen modules for Maker Nano RP2040
import neopixel
##import simpleio

from adafruit_ads1x15 import ADS1115, ads1x15
from adafruit_ads1x15.analog_in import AnalogIn as ADSAnalogIn
import adafruit_mcp4728


SOFTWARE_NAME = "adctest-sg"
SOFTWARE_VERSION = "1.1"


### Going from 125MHz to 250MHz
### Code for finding pairs of DAC codes to match
### voltage gaps is slow (and a bit inefficient!)
microcontroller.cpu.frequency = 250_000_000

debug = 3

### This needs to be set to the voltage for the DAC power supply
### 4 fully charged NiMH can produce 5.6V which is too high
### anything below 5.5V is okay, 5.1-5.2V is ideal
### A regulator is needed to get a stable voltage for the best data
### when the external Vdd reference is used
DAC_EST_V = 5.2
MCP_OUTPUT_PIN_PAIR = ("B", "C")
DAC_PD_500K = (530.9e3, 529.9e3, 528.5e3, 529.5e3)
DAC_EXT_POTDIV = (None, 98.4, 98.5, None)
DAC_LOAD = 98.86e3
DAC_IMPEDANCE = 1   ### only at low currents!

### Board Under Test
BUT_ADC_OVER_V = 0.1   ### the voltage to go beyond ADC detected maximum

ADC_NOISE_SAMPLES = 200
NOISE_VOLTAGES = (0.0, 0.050, 0.1, 0.2, 0.3, 0.4, 0.5, 0.60, 0.65, 0.70,
                  1.0, 1.225, 1.650,
                  2.0, 2.5,
                  3.0, 3.1, 3.2, 3.250, 3.3,
                  4.0, 4.7, 4.8, 4.9, 4.950,
                  5.0)

START_PAUSE_S = 10

TEST_VREFS = ("max", 4096, 2048)
TEST_VREFS_ASC = (2048, 4096, "max")

### Single-shot (S) still seems to affect MCP 4728 output with more noise
### and strangely lower voltage
### Better data from continuous mode, C mode also aligns with multimeter values
TEST_ADC_MODES = ("C",)

ADS1115_PIN = ads1x15.Pin.A0
ADS1115_RATE = 128
ADS1115_POSBITS = 16 - 1   ### bits representing positive values
ADS1115_POSCODES = 2**ADS1115_POSBITS
### 2/3 gain (lowest setting) is required for up to 6.144V measurements
ADS1115_GAIN = 2 / 3
ADS1115_RAW_TO_V = 4.096 / ADS1115_GAIN / ADS1115_POSCODES   ### 187.5 uV

SERIAL_TX_PIN = board.GP12  ### green
SERIAL_RX_PIN = board.GP13  ### blue

### Maker port 0
I2C_SDA_PIN = board.GP1
I2C_SCL_PIN = board.GP0

DAC_BITS = 12
DAC_CODES = 2**DAC_BITS
DAC_MAX_CODE = DAC_CODES - 1  ### 4095 is 12 bit max
DAC_CHANNELS = ("A", "B", "C", "D")
DAC_CHANNEL_IDX = {c:i for i, c in enumerate(DAC_CHANNELS)}
### This is a magic value to put a channel in
### the power down state with 1k to GND to get 0V
DAC_GND_MAGIC_CODE = -1

OUT_MIN = 0
OUT_MAX = DAC_MAX_CODE

SERIAL_BAUDRATE = 38400
RESPONSE_CHAR_WAIT_S = 2.5  ### extremely generous value to accommodate slow info command
RESPONSE_CHAR_WAIT_NS = int(RESPONSE_CHAR_WAIT_S * 1e9)


##SPEAKER_PIN = board.GP22
I2C_FREQUENCY = 400_000
MICROCONTROLLER_SUPPLY = 3.3
PIXEL_PIN = board.RGB
PIXEL_COUNT = 2

BLACK  = 0x000000
GREEN  = 0x001800
BLUE   = 0x000020   ### used to indicate 3.3V testing
RED    = 0x1c0000
YELLOW = 0x181400   ### used to indicate 5.0V testing


def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


if PIXEL_COUNT:
    pixels = neopixel.NeoPixel(PIXEL_PIN, PIXEL_COUNT, brightness=1.0)
    pixels[0] = GREEN
    pixels[1] = BLACK
else:
    pixels = None

### GPIO with blue leds are used to indicate which test is running
PWM_FLASH_FREQ = 8  ### minimum is 7
gpio_leds = tuple(pwmio.PWMOut(p, frequency=PWM_FLASH_FREQ)
                  for p in (board.GP8, board.GP7, board.GP6, board.GP5, board.GP4, board.GP3, board.GP2))
LED_TEST_RUNNING = 32768
LED_TEST_ON = 65535
LED_TEST_COMPLETE = 65535


i2c = busio.I2C(scl=board.GP1,
                sda=board.GP0,
                frequency=I2C_FREQUENCY)
mcp_dac = adafruit_mcp4728.MCP4728(i2c)

### mode changes are broken https://github.com/adafruit/Adafruit_CircuitPython_ADS1x15/issues/110
### creating object inside test_adc for now
## ads1115 = ADS1115(i2c, data_rate=128, mode=ads1x15.Mode.SINGLE)
## ads1115.gain = 2/3   ### for up to 6.144V
## ads1115_chan = ADSAnalogIn(ads1115, ADS1115_PIN)

### Set all outputs to 0 using 500k pull down and save the settings in EEPROM
### TODO - document in the article that code should be run once (before connecting a non 5V device)
def dac_pd(dac, *,
           channel_list=DAC_CHANNELS,
           pull_down=adafruit_mcp4728.PowerState.PD500K):
    ### Step through the pull downs from high to low
    ### This means if a subsequent channel was left with a high voltage it won't
    ### get a 1k to ground due to the external circuitry
    for ps_pd_value in (adafruit_mcp4728.PowerState.PD500K,
                        adafruit_mcp4728.PowerState.PD100K,
                        adafruit_mcp4728.PowerState.PD1K):
        for chan_char in channel_list:
            d_chan = getattr(dac, "channel_" + chan_char.lower())
            d_chan.power_state = ps_pd_value
        if ps_pd_value == pull_down:
            break

dac_pd(mcp_dac)
mcp_dac.save_settings()


NOT_AVAIL = "NA"

### TODO - could use this to check baud rate and get adc details
### "INFO","Cytron Maker Nano RP2040 with rp2040", "rp2040", "CircuitPython", "10.2.1 on 2026-05-13","adc=12;aref=3.3"
INFO_CMD = "I"

READV_ANA_CMD = "C"
READV_DIG_CMD = "F"

serial = busio.UART(tx=SERIAL_TX_PIN, rx=SERIAL_RX_PIN,
                    baudrate=SERIAL_BAUDRATE,
                    ##receiver_buffer_size=100,
                    timeout=RESPONSE_CHAR_WAIT_S)

##discard_count = serial.in_waiting
##_ = serial.read(discard_count)
##print("Serial discard", discard_count)

def triangle_waveform(step_size, wave_min=OUT_MIN, wave_max=OUT_MAX):
    dc_value_fp = wave_min
    direction_up = True

    while True:
        yield round(dc_value_fp)
        if direction_up:
            dc_value_fp += step_size
            if dc_value_fp > wave_max:
                if dc_value_fp != wave_max + 1 and round(dc_value_fp) == wave_max + 1:
                    dc_value_fp = wave_max
                else:
                    direction_up = False
                    dc_value_fp = wave_max + 1 - step_size
        else:
            dc_value_fp -= step_size
            if dc_value_fp < wave_min:
                if dc_value_fp != wave_min - 1 and round(dc_value_fp) == wave_min - 1:
                    dc_value_fp = wave_min
                else:
                    break


def triangle_waveform_v(max_v,
                        dac_code_count,
                        dac_vref_v):
    return triangle_waveform(1, wave_max=min(int(dac_code_count * max_v / dac_vref_v), dac_code_count - 1))


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


### TODO - remove this later as it appears not to be needed
### perhaps the issue I was thinking of was UART with floating input and
### strange stuff (NULs?) appearing on RX?
SERIAL_TIMEOUT_NS = round(RESPONSE_CHAR_WAIT_S * 1e9)
def readLineTimeout(ser):
    ### The timeout on the serial object does not work in all cases
    start_ns = time.monotonic_ns()
    data = ser.readline()
    if data is not None:
        return data
    while time.monotonic_ns() - start_ns < SERIAL_TIMEOUT_NS:
        data = ser.readline()
        if data is not None:
            break
    return data


#print(list(triangle_waveform(8192)))
#print(list(rp2040adcdnl()))

def output(elems):
    print(",".join([NOT_AVAIL if x is None else (f'"{x}"' if isinstance(x, str) else str(x)) for x in elems]))


def test_adc(dac,
             dac_values,
             short_name,
             *,
             dac_pins=None,
             adc_pin=ADS1115_PIN,
             adc_mode="S",
             adc_sample_rate=ADS1115_RATE,
             dac_limit_v=None,
             dac_vref_mv="max",
             dac_v=5.0,
             sample_count=1,
             runs=1,
             remote=True,
             reset_value=None,
             return_refadc=None,
             value_count=None):
    ### pylint: disable=too-many-statements,too-many-locals,too-many-return-statements,too-many-branches
    if sample_count > 255 - ord(" "):
        raise ValueError("too many samples")

    if dac_limit_v is None:
        raise ValueError("dac_limit_v must be set")

    if adc_mode == "C":
        sample_mode = ads1x15.Mode.CONTINUOUS
        ads1115_wait = 2 / adc_sample_rate
    else:
        sample_mode = ads1x15.Mode.SINGLE
        ads1115_wait = 0

    ### Object is (re)created here due to
    ### https://github.com/adafruit/Adafruit_CircuitPython_ADS1x15/issues/110
    ads1115 = ADS1115(i2c, data_rate=adc_sample_rate,
                      mode=sample_mode, gain=ADS1115_GAIN)
    ads1115_chan = ADSAnalogIn(ads1115, adc_pin)

    dac_pintxt = ";".join(dac_pins)
    dac_chans = tuple(getattr(dac, "channel_" + dp.lower()) for dp in dac_pins)

    max_v = None
    for dac_chan in dac_chans:
        if dac_vref_mv=="max":
            dac_chan.vref = adafruit_mcp4728.Vref.VDD
            max_v = dac_v
        elif dac_vref_mv in (2048, 4096):
            dac_chan.vref = adafruit_mcp4728.Vref.INTERNAL
            dac_chan.gain = dac_vref_mv // 2048   ### gain is 1 or 2
            max_v = dac_vref_mv / 1000.0

    ### Storage for values that come back from remote
    samples = [None] * (sample_count if remote else 0)
    cmd = READV_ANA_CMD.encode('utf-8') + bytes([sample_count + ord(" ")])

    max_value = min(DAC_MAX_CODE, int(DAC_CODES * dac_limit_v / max_v))
    ### Output the values, take ADC readings and print results
    for r_idx in range(runs):
        gc.collect()  ### just an attempt to get less jitter in readings
        for v_idx, val_list in enumerate(zip(*dac_values)):
            if value_count is not None and v_idx >= value_count:
                break

            if any(v > max_value for v in val_list):
                continue

            ### Set voltage by setting one or more channel outputs
            for c_idx in range(len(dac_chans)):
                dac_chan = dac_chans[c_idx]
                value = val_list[c_idx]
                ##est_voltage = max_v * value / 4096
                if value == DAC_GND_MAGIC_CODE:
                    if dac_chan.power_state != adafruit_mcp4728.PowerState.PD1K:
                        dac_chan.power_state = adafruit_mcp4728.PowerState.PD1K
                else:
                    if dac_chan.power_state != adafruit_mcp4728.PowerState.NORMAL:
                        dac_chan.power_state = adafruit_mcp4728.PowerState.NORMAL
                    dac_chan.raw_value = value

            start_ns = time.monotonic_ns()
            if remote:
                serial.write(cmd)
                resp = serial.readline()
                try:
                    samples_str = resp.decode("utf-8").strip()
                    for s_idx, sample in enumerate(samples_str.split()):
                        samples[s_idx] = int(sample)
                except (UnicodeError, ValueError):
                    pass

            if ads1115_wait:
                adjusted_wait = ads1115_wait - (time.monotonic_ns() - start_ns) / 1e9
                if adjusted_wait > 0.0:
                    time.sleep(adjusted_wait)

            m_raw = ads1115_chan.value
            m_voltage = m_raw * ADS1115_RAW_TO_V

            values_str = ",".join(str(s) for s in val_list)
            samples_str = ",".join(str(s) for s in samples)
            output([start_ns,
                    short_name,
                    dac_pintxt, adc_pin, adc_mode, str(dac_vref_mv),
                    r_idx, f"[{values_str:s}]", m_voltage,
                    f"[{samples_str:s}]" if samples_str else None])

            if return_refadc is not None and v_idx < len(return_refadc):
                ### Put a floor at 0V as an ADS1115 can measure negative values
                ### and noise/circuity issues could create legitimate -1 value
                return_refadc[v_idx] = max(0, m_raw)

    ### Switch back to single shot to minimise power consumption
    if ads1115.mode == ads1x15.Mode.CONTINUOUS:
        ads1115.mode = ads1x15.Mode.SINGLE

    if reset_value is not None:
        for dac_chan in dac_chans:
            dac_chan.raw_value = reset_value

    return None  ### what should I return TODO


### Parses something like
### "INFO","ana-dig-reader","1.2","Arduino","UNO R4 WiFi","Renesas RA4M1","Arduino","adc_bits=14;aref=5.0;input_pin=19" (plus CR LF)
def get_board_info():
    fields = {}
    serial.write(INFO_CMD.encode('utf-8'))
    resp = serial.readline()
    try:
        ### For a timeout resp will be None and cause an AttributeError
        raw_fields = resp.decode("utf-8").strip().split(",")
    except (UnicodeError, AttributeError):
        raw_fields = []

    try:
        ### String parsing is hacky here with double quote stripping
        resp_type = raw_fields[0].replace('"', "")
        if resp_type == "INFO":
            for idx, d_name in enumerate(("software_name", "software_version",
                                          "board_manu", "board_name", "board_mcu",
                                          "language")):
                fields[d_name] = raw_fields[idx + 1].replace('"', "")
            data = {}
            for n_v in raw_fields[7].replace('"', "").split(";"):
                (name, value) = n_v.split("=", 1)
                data[name] = value
            fields["data"] = data
    except IndexError:
        pass
    return fields


def get_dac_code_v(target_v, adc_meas, *,
                   dac_pin=None, dac_vref_mv=None, dac_max_v=None):
    if target_v > dac_max_v:
        return None
    t_adc_code = max(0, round(target_v / ADS1115_RAW_TO_V))
    return get_dac_code(t_adc_code, adc_meas,
                        dac_pin=dac_pin, dac_vref_mv=dac_vref_mv, dac_max_v=dac_max_v)


def get_dac_code(t_adc_code, adc_meas, *,
                 dac_pin=None, dac_vref_mv=None, dac_max_v=None):
    """ Return the closest dac code based on a target voltage and ADS measurements of them.
        Assumes monotonically increasing adc_meas."""
    adc_meas_chvr = adc_meas[(dac_pin, dac_vref_mv)]

    ### ulab would be quicker here but will allocate temporary variables...
    ### (Python for leaves idx as last value, i.e. range(10) would be 9)
    for idx in range(len(adc_meas_chvr)):
        if adc_meas_chvr[idx] >= t_adc_code:
            break

    if idx != 0:
        before_err = abs(adc_meas_chvr[idx - 1] - t_adc_code)
        here_err = abs(adc_meas_chvr[idx] - t_adc_code)
        ### Go back to previous one if it's closer
        if before_err <= here_err:
            idx = idx - 1

    return idx


dc_pair_max_dist = 101

def get_second_dac_code_v(target_v, adc_meas, *,
                          dac_code1=None, dac_pin1=None,
                          dac_pin2=None,
                          dac_vref_mv=None, dac_max_v=None):
    """ Search for nearby DAC codes on a second channel which will produce
        a voltage close to target_v given the potential divider in use
        and lack of internal pull down resistors.

        Assumes DAC channels are within a few mV of each other."""

    adc_meas_pin1 = adc_meas[(dac_pin1, dac_vref_mv)]
    adc_meas_pin2 = adc_meas[(dac_pin2, dac_vref_mv)]

    out_res1 = DAC_EXT_POTDIV[DAC_CHANNEL_IDX[dac_pin1]]
    out_res2 = DAC_EXT_POTDIV[DAC_CHANNEL_IDX[dac_pin2]]
    ### Total pull-down, internal pull-down plus the external DAC_LOAD (100k resistor)
    tot_pd_res1 = 1 / (1 / DAC_PD_500K[DAC_CHANNEL_IDX[dac_pin1]] + 1 / DAC_LOAD)
    tot_pd_res2 = 1 / (1 / DAC_PD_500K[DAC_CHANNEL_IDX[dac_pin2]] + 1 / DAC_LOAD)
    dac_loaded_to_unloaded1 = (out_res2 + tot_pd_res2 + out_res1 + DAC_IMPEDANCE) / (out_res2 + tot_pd_res2)
    dac_loaded_to_unloaded2 = (out_res1 + tot_pd_res1 + out_res2 + DAC_IMPEDANCE) / (out_res1 + tot_pd_res1)
    ## print("CONV", dac_loaded_to_unloaded1, dac_loaded_to_unloaded2)  ### TODO
    dac_p1_pulldown_v = adc_meas_pin1[dac_code1] * ADS1115_RAW_TO_V
    dac_p1_int_v = dac_p1_pulldown_v * dac_loaded_to_unloaded1
    ### The three values are use to calculate the combined, loaded output voltage
    total_res = 1 / (1 / (out_res1 + DAC_IMPEDANCE) + 1 / (out_res2 + DAC_IMPEDANCE) + 1 / DAC_LOAD)
    v_p1 = dac_p1_int_v / (out_res1 + DAC_IMPEDANCE) * total_res
    scale2_div = total_res / (out_res2 + DAC_IMPEDANCE)
    ###
    raw_to_pdcorr_v = ADS1115_RAW_TO_V * dac_loaded_to_unloaded2
    ### Use the pin1 dac code as a starting point for search
    mid_code2 = dac_code1
    dc_search_size = dc_pair_max_dist * 3 // 2
    dc_start = max(0, mid_code2 - dc_search_size // 2)
    dc_endex = min(DAC_MAX_CODE + 1, dc_start + dc_search_size)

    best_dac_code = None
    best_v = None
    last_abserr = float("Inf")
    min_abserr = float("Inf")
    rise_count = 0
    ### TODO - the search here could be improved based on the linearity of adc_meas_pin2
    for dac_code2 in range(dc_start, dc_endex):
        ### Convert from raw value to voltage then pull-down correction in one multiply
        dac_p2_int_v = adc_meas_pin2[dac_code2] * raw_to_pdcorr_v

        ### Calculate the combined voltage output taking int account the external load
        ### (application of Kirchoff's current law)
        calc_combined_v = v_p1 + dac_p2_int_v * scale2_div
        ##print("VOLTAGES", target_v, dac_p1_int_v, dac_p2_int_v, calc_combined_v, v_p1)  ### TODO
        abserr = abs(calc_combined_v - target_v)
        if abserr < min_abserr:
            best_dac_code = dac_code2
            best_v = calc_combined_v
            min_abserr = abserr

        if abserr > last_abserr:
            rise_count += 1
            ### give up if trend is definitely upward
            if rise_count >= 2:
                break
        else:
            rise_count = 0

        last_abserr = abserr

    return (best_dac_code, best_v)


def get_dac_code_pair(adc_code, adc_meas, *,
                      dac_pins=None, dac_vref_mv=None, dac_max_v=None):
    """Look for an optimal pair of dac_codes which will produce a voltage nearest to
       adc_code equvalent voltage when output on the two dac_pins."""

    target_v = adc_code * ADS1115_RAW_TO_V
    if target_v > dac_max_v:
        return (None, None)

    coarse_pin, fine_pin = dac_pins

    coarse_dac_code = get_dac_code(adc_code, adc_meas,
                                   dac_pin=coarse_pin, dac_vref_mv=dac_vref_mv, dac_max_v=dac_max_v)
    adc_meas_coarse = adc_meas[(coarse_pin, dac_vref_mv)]
    if adc_meas_coarse[coarse_dac_code] == adc_code:
        print("TODO", "requesting existing code in first pin - this should not happen given use")
        return (coarse_dac_code, None)

    fine_dac_code = get_dac_code(adc_code, adc_meas,
                                 dac_pin=fine_pin, dac_vref_mv=dac_vref_mv, dac_max_v=dac_max_v)
    adc_meas_fine = adc_meas[(fine_pin, dac_vref_mv)]
    if adc_meas_fine[fine_dac_code] == adc_code:
        print("TODO", "requesting existing code in second pin - this should not happen given use")
        return (None, fine_dac_code)

    ### Build a list of coarse, fine dac codes and calculate combined
    ### voltage for each pair then look for minimum error
    c_start = max(0, coarse_dac_code - dc_pair_max_dist // 2)
    c_endex = min(DAC_MAX_CODE + 1, c_start + dc_pair_max_dist)

    min_abserr = float("Inf")
    matched_coarse_dac_code = None
    matched_fine_dac_code = None
    good_enough_error = 0.08 * ADS1115_RAW_TO_V   ### 0.08 LSB = 0.015mV
    ### the sort here makes the search start with some values
    ### that cover the whole search range
    for coarse_dac_code in sorted(range(c_start, c_endex),
                                  key=lambda x: x % 13 * 13 + x // 13):
        fine_dac_code, c_v = get_second_dac_code_v(target_v, adc_meas,
                                                   dac_code1=coarse_dac_code, dac_pin1=coarse_pin,
                                                   dac_pin2=fine_pin,
                                                   dac_vref_mv=dac_vref_mv, dac_max_v=dac_max_v)

        abserr = abs(c_v - target_v)
        if abserr < min_abserr:
            min_abserr = abserr
            matched_coarse_dac_code = coarse_dac_code
            matched_fine_dac_code = fine_dac_code
            if abserr < good_enough_error:
                break

    if not 0 <= matched_coarse_dac_code <= DAC_MAX_CODE or not 0 <= matched_fine_dac_code <= DAC_MAX_CODE:
        print("INTERNAL ERROR: something went very wrong, DAC code out of range:", matched_coarse_dac_code, matched_fine_dac_code)
        return (None, None)

    if abs(matched_coarse_dac_code - matched_fine_dac_code) > 120:
        print("INTERNAL ERROR: something went very wrong and DAC voltages are not close:", matched_coarse_dac_code, matched_fine_dac_code)
        return (None, None)

    ### Not worth trying if more than, say, +/- 0.6 LSB
    if min_abserr > 0.6 * ADS1115_RAW_TO_V:
        print(f"INFO: no match with +/- 0.6LSB for {target_v:.f} (abs err {min_abserr*1000:.3f}mV")
        return (None, None)

    return (matched_coarse_dac_code, matched_fine_dac_code)


def b_set(bitset, value):
    bitset[value // 8] |= 1 << (value % 8)


def b_check(bitset, value):
    return bool(bitset[value // 8] & 1 << (value % 8))


def announce_start(t_idx, t_desc):
    now_ns = time.monotonic_ns()
    print(f"### BEGIN {t_desc:s} at {now_ns * 1e-9:.3f}s ###")
    gpio_leds[t_idx].duty_cycle = LED_TEST_RUNNING
    ##for freq in (440, 880, 1760):
    ##    simpleio.tone(SPEAKER_PIN, freq, 0.2)
    return now_ns


def announce_end(t_idx, t_desc, s_ns):
    now_ns = time.monotonic_ns()
    dur_ns = now_ns - s_ns
    print(f"### END {t_desc:s} at {now_ns * 1e-9:.3f}s duration {dur_ns * 1e-9:.3f}s cputemp {microcontroller.cpu.temperature:.1f} ###")
    print()
    gpio_leds[t_idx].duty_cycle = LED_TEST_COMPLETE
    ##for freq in reversed((440, 880, 1760)):
    ##    simpleio.tone(SPEAKER_PIN, freq, 0.2)
    time.sleep(2.0 - 0.2 * 3)


SOME_ZEROES = (tuple(DAC_GND_MAGIC_CODE for _ in range(5)),)

### 15s pause to allow operator to setup serial console collection, abort testing, etc
start_pause_ns = time.monotonic_ns()
while time.monotonic_ns() - start_pause_ns < START_PAUSE_S * 1e9:
    for dc in triangle_waveform(LED_TEST_ON // 50, wave_max=LED_TEST_ON):
        for pwm in gpio_leds:
            pwm.duty_cycle = dc
            time.sleep(0.010)

test_idx = 0
test_desc = "board informtion"
test_start_ns = announce_start(test_idx, test_desc)
test_name = "info"
remote_info = get_board_info()
print("### Board:", remote_info, "###")
announce_end(test_idx, test_desc, test_start_ns)

remote_adc_vref = float(remote_info["data"]["aref"])
if abs(remote_adc_vref - 5.0) < 1e-4:  ### generous tolerance for floating point
    pixels[1] = YELLOW
elif abs(remote_adc_vref - 3.3) < 1e-4:
    pixels[1] = BLUE
else:
    raise ValueError("Unexpected remote ADC voltage reference: " + remote_info["data"]["aref"])



test_limit_v = remote_adc_vref + BUT_ADC_OVER_V
print(f"### Board under test ADC range 0V to {remote_adc_vref:.1f}V - testing up to {test_limit_v:.3f}V ###")
print()

##test_limit_v = 0.333  ### TODO - remove - just for testing


test_idx = 1
test_desc = "bug workaround for https://github.com/adafruit/Adafruit_CircuitPython_ADS1x15/issues/112"
test_start_ns = announce_start(test_idx, test_desc)
test_name = "bugw1"

vref="max"
s_mode = "S"  ### do one single-shot read to workaround bug in CircuitPython library
test_adc(mcp_dac, SOME_ZEROES, test_name,
         dac_pins=(MCP_OUTPUT_PIN_PAIR[0],), dac_v=DAC_EST_V, adc_mode=s_mode, dac_vref_mv=vref, dac_limit_v=test_limit_v,
                   remote=False)

announce_end(test_idx, test_desc, test_start_ns)

time.sleep(60)
print("### 60 second pause ###")


### This is similar to the test from mcp7428-ads1115-test
ads1115_measurements = {}
test_idx = 2
test_desc = "testing MCP4728 channnels"
test_name = "dac"
test_start_ns = announce_start(test_idx, test_desc)
ads1115_raw_bitset = array.array("B", [0]) * (ADS1115_POSCODES // 8)
for chan in MCP_OUTPUT_PIN_PAIR:
    ### very important not to leave one channel with an output value while other is being tested
    dac_pd(mcp_dac)
    chan_tuple = (chan,)
    for vref in TEST_VREFS:
        for s_mode in TEST_ADC_MODES:
            #dac_values = triangle_waveform(512)
            values = (triangle_waveform(1),)
            ### ADS1115 values are signed, hence "h" rather than "H"
            ads1115_values = array.array("h", [0]) * DAC_CODES  ### ramp-up only
            ### -1 is a special value to produce 0.000V by putting
            #### the MCP4728 channel in power down state with 1K to ground
            test_adc(mcp_dac, SOME_ZEROES, test_name,
                     dac_pins=chan_tuple, dac_v=DAC_EST_V, adc_mode=s_mode, dac_vref_mv=vref, dac_limit_v=test_limit_v, remote=False)
            test_adc(mcp_dac, values, test_name,
                     dac_pins=chan_tuple, dac_v=DAC_EST_V, adc_mode=s_mode, dac_vref_mv=vref, dac_limit_v=test_limit_v, remote=False,
                     return_refadc=ads1115_values)
            test_adc(mcp_dac, SOME_ZEROES, test_name,
                     dac_pins=chan_tuple, dac_v=DAC_EST_V, adc_mode=s_mode, dac_vref_mv=vref, dac_limit_v=test_limit_v, remote=False)

            ### TODO - ponder whether i should set all these values from the remote tests lower down
            ### In theory they are very similar but there will be some DAC values on the boundary of ads1115 values
            for covered_adc_code in ads1115_values:
                if covered_adc_code >= 0:
                    b_set(ads1115_raw_bitset, covered_adc_code)
            if s_mode == TEST_ADC_MODES[0]:  ### only store the first one
                ads1115_measurements[(chan, vref)] = ads1115_values

del ads1115_values
dac_pd(mcp_dac)
announce_end(test_idx, test_desc, test_start_ns)



### Do a test in 0.05 volt steps to see when ADC hits its limitation
### When boards are powered "properly"
### This will be 3.25 / 3.30 / 3.35 for 3.3V
###              4.95 / 5.00 / 5.05 for 5V
### For board tests take them to this voltage plus 0.1V on the triangle wave.
##but_adc_approx_upper_v = None
##but_adc_upper_v = but_adc_approx_upper_v + ADC_OVER_V

### Set first pixel to a colour to indicate top voltage
### blue for 2.5V and 5.0V red with magenta in between
### RESERVE RED for errors??
### TODO

### Ramp tests - do S and C in case there's an accuracy or noise difference I haven't noticed
###
adc_triangle_test = True
ADC_TRIANGLE_SAMPLES = 40
if adc_triangle_test:
    test_idx = 3
    test_desc = "testing remote ADC with each MCP4728 channnel"
    test_name = "triangle"
    test_start_ns = announce_start(test_idx, test_desc)
    ### -1 is a special value to produce 0.000V by putting
    #### the MCP4728 channel in power down state with 1K to ground
    for chan in MCP_OUTPUT_PIN_PAIR:
        dac_pd(mcp_dac)
        chan_tuple = (chan,)
        for vref in TEST_VREFS:
            for s_mode in TEST_ADC_MODES:
                #dac_values = triangle_waveform(512)
                values = (triangle_waveform(1),)
                test_adc(mcp_dac, SOME_ZEROES, test_name,
                         dac_pins=chan_tuple, dac_v=DAC_EST_V, adc_mode=s_mode, dac_vref_mv=vref, dac_limit_v=test_limit_v,
                         remote=True, sample_count=ADC_TRIANGLE_SAMPLES)
                test_adc(mcp_dac, values, test_name,
                         dac_pins=chan_tuple, dac_v=DAC_EST_V, adc_mode=s_mode, dac_vref_mv=vref, dac_limit_v=test_limit_v,
                         remote=True, sample_count=ADC_TRIANGLE_SAMPLES)
                test_adc(mcp_dac, SOME_ZEROES, test_name,
                         dac_pins=chan_tuple, dac_v=DAC_EST_V, adc_mode=s_mode, dac_vref_mv=vref, dac_limit_v=test_limit_v,
                         remote=True, sample_count=ADC_TRIANGLE_SAMPLES)

    dac_pd(mcp_dac)
    announce_end(test_idx, test_desc, test_start_ns)


adc_gap_test = True
GAP_SAMPLES = ADC_TRIANGLE_SAMPLES
if adc_gap_test and len(MCP_OUTPUT_PIN_PAIR) == 2:
    test_idx = 4
    test_desc = "testing remote ADC with combined MCP4728 channnels (gap coverage)"
    test_name = "gaps"
    test_start_ns = announce_start(test_idx, test_desc)

    last_ads1115_code = min(round(test_limit_v / ADS1115_RAW_TO_V) + 1,
                                  ADS1115_POSCODES - 1)
    gap_count_before = 0
    for covered_adc_code in range(last_ads1115_code):
        if not b_check(ads1115_raw_bitset, covered_adc_code):
            gap_count_before += 1
    print("GAP COUNT", gap_count_before, "LAC", last_ads1115_code)

    ### Deal with gaps in chunks of 1000 to avoid running out of memory
    GAP_CHUNK_SIZE = 1000
    gap_dac_code_1 = array.array("h", [0]) * GAP_CHUNK_SIZE
    gap_dac_code_2 = array.array("h", [0]) * GAP_CHUNK_SIZE
    ads1115_new_values = array.array("h", [0]) * GAP_CHUNK_SIZE

    gap_dac_count = 0
    ### TODO - ponder whether i want to do this with 2.048 and 4.096 internal vrefs for below 1.9V and 3.95V?
    ### the lower voltage references will have finer granularity...
    vref = "max"
    d_max_v = DAC_EST_V

    gap_adc_code = 0
    while gap_adc_code < last_ads1115_code:
        this_chunk_len = 0
        while this_chunk_len < len(gap_dac_code_1) and gap_adc_code < last_ads1115_code:
            if b_check(ads1115_raw_bitset, gap_adc_code):
                gap_adc_code += 1
                continue   ### not a gap

            (c1, c2) = get_dac_code_pair(gap_adc_code, ads1115_measurements,
                                         dac_pins=MCP_OUTPUT_PIN_PAIR, dac_vref_mv=vref, dac_max_v=d_max_v)
            if c1 is not None and c2 is not None:
                gap_dac_code_1[this_chunk_len] = c1
                gap_dac_code_2[this_chunk_len] = c2
                #print("DC pair", c1, c2, "for", gap_adc_code)
                this_chunk_len += 1
            gap_adc_code += 1

        if this_chunk_len > 0:
            print("CHUNK LEN", this_chunk_len)
            for s_mode in TEST_ADC_MODES:
                ### Bring outputs back to very near 0V by using reset_value
                ### This is useful as the "finding gap value" code takes time
                ### and outputs could be left a bit high
                ### e.g. 5.05V on a USB powered Arduino R4 WiFi running at 4.64V
                test_adc(mcp_dac, (gap_dac_code_1, gap_dac_code_2), test_name,
                         value_count=this_chunk_len, dac_pins=MCP_OUTPUT_PIN_PAIR,
                         dac_v=DAC_EST_V, adc_mode=s_mode, dac_vref_mv=vref, dac_limit_v=test_limit_v, remote=True,
                         sample_count=GAP_SAMPLES,
                         return_refadc=ads1115_new_values,
                         reset_value=0)

            dac_pd(mcp_dac)

        for covered_adc_code in ads1115_new_values:
            if covered_adc_code >= 0:
                b_set(ads1115_raw_bitset, covered_adc_code)

    gap_count_after = 0
    for covered_adc_code in range(last_ads1115_code):
        if not b_check(ads1115_raw_bitset, covered_adc_code):
            gap_count_after += 1

    print(f"### TODO STATUS STANDARD before={gap_count_before:d} after={gap_count_after:d}")

    dac_pd(mcp_dac)
    announce_end(test_idx, test_desc, test_start_ns)

    del gap_dac_code_1, gap_dac_code_2, ads1115_new_values


### Very short voltage test to try and get a bit more coverage of the 0-5mV range
VERYLOW_SAMPLES = ADC_TRIANGLE_SAMPLES
verylow_test = True
if verylow_test:
    test_idx = 5
    test_desc = "testing remote ADC with each MCP4728 channnel with low voltages and 1k pull down"
    test_name = "verylow"
    test_start_ns = announce_start(test_idx, test_desc)
    for chan in MCP_OUTPUT_PIN_PAIR:
        dac_pd(mcp_dac, pull_down=adafruit_mcp4728.PowerState.PD1K)
        ### Theoretically 2.048 internal is the only one needed
        ### but zero offsets can be different per voltage referance
        ### so give all three a go
        chan_tuple = (chan,)
        for vref in TEST_VREFS:
            for s_mode in TEST_ADC_MODES:
                values = (triangle_waveform(1, wave_max=20),)
                test_adc(mcp_dac, values, test_name,
                         dac_pins=chan_tuple, dac_v=DAC_EST_V, adc_mode=s_mode, dac_vref_mv=vref, dac_limit_v=test_limit_v,
                         remote=True, sample_count=VERYLOW_SAMPLES)

    dac_pd(mcp_dac)
    announce_end(test_idx, test_desc, test_start_ns)


### Noise test
NOISE_TEST_RUNS = 5
noise_test = True
if noise_test:
    test_idx = 6
    test_desc = "testing remote ADC with first MCP4728 channnel and lots of samples"
    test_name = "noise"
    test_start_ns = announce_start(test_idx, test_desc)
    for chan in MCP_OUTPUT_PIN_PAIR[0]:
        ### Python allow keys to be different types, int and str here
        vref_voltages = OrderedDict([(2048, []),
                                     (4096, []),
                                     ("max", [])])
        chan_tuple = (chan,)
        for nv in NOISE_VOLTAGES:
            if nv == 0.0:
                vref_voltages[2048].append(DAC_GND_MAGIC_CODE)
            elif nv > test_limit_v:
                pass
            else:
                vref = None
                d_max_v = None
                ### Select the best voltage reference
                if nv < 2.02:
                    vref = 2048
                    d_max_v = vref / 1000.0
                elif nv < 4.04:
                    vref = 4096
                    d_max_v = vref / 1000.0
                elif nv < DAC_EST_V:
                    vref = "max"
                    d_max_v = DAC_EST_V

                if vref is not None:
                    vref_voltages[vref].append(get_dac_code_v(nv, ads1115_measurements,
                                                              dac_pin=chan, dac_vref_mv=vref, dac_max_v=d_max_v))

        for vref, noisev_values in vref_voltages.items():
            for s_mode in TEST_ADC_MODES:
                test_adc(mcp_dac, (noisev_values,), test_name,
                         dac_pins=chan_tuple, dac_v=DAC_EST_V, adc_mode=s_mode, dac_vref_mv=vref, dac_limit_v=test_limit_v,
                         remote=True, sample_count=ADC_NOISE_SAMPLES,
                         runs=NOISE_TEST_RUNS)

    dac_pd(mcp_dac)
    announce_end(test_idx, test_desc, test_start_ns)

dac_pd(mcp_dac)   ### just in case

### Indicate done
pixels[0] = BLACK


while True:
    pass
