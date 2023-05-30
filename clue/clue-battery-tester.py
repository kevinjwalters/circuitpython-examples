### clue-battery-tester v1.1

### A battery tester

### Tested with an Adafruit CLUE and CircuitPython and 8.0.5

### copy this file to CLUE board as code.py

### MIT License

### Copyright (c) 2023 Kevin J. Walters

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

### See https://www.instructables.com/member/kevinjwalters/ for the diagram
### showing the external circuit and connectivity

### If a battery is connected then the battery will be tested once
### for 10 seconds - this will have almost no effect on capacity.

### The left button starts a discharge test on the battery - this
### will FLATTEN the battery completely.

### The right button start a transistor voltage base sweep test - this
### puts a moderate load on the battery for about 25 minutes and will
### deplete a battery a little - this is intended for testing
### with power supplies

### https://www.onsemi.com/pdf/datasheet/bc337-d.pdf
### Ic maximum is 800 mA
### TPD 625 mW at Ta 25 Celsius


### TODO - set RGB led if present to indicate activity


import time
import os
import gc

import board
import analogio
import pwmio
import displayio
import terminalio
import digitalio
import neopixel

#from adafruit_display_text.label import Label


debug = 1

load_r1 = 47
load_r2 = 46.8
load_r = 1 / (1 / load_r1 + 1 / load_r2)

base_r1 = 2.172e3
base_r2 = 2.169e3
base_r = 1 / (1 / base_r1 + 1 / base_r2)
base_c = 470e-6  ### 454uF on multimeter  componen tester 435.4 437.6 436.3


REF_V = 3.3

### PWM duty cycle values
ZERO_DCS = 0
MAX_DCS = 65535

### Maximum number of samples used to detect a battery is connected
MAX_SAMPLES=2000


def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


### Left (a) and right (b) buttons
os_machine_uc = os.uname().machine.upper()
meowbit = os_machine_uc.find("MEOWBIT ") >= 0
clue = os_machine_uc.find("CLUE NRF52840 ") >= 0

if meowbit:
    pin_a = board.BTNA
    pin_b = board.BTNB
    output_internal_res = 140   ### What's STM like?
    status_led = None

    import array
    sample_store = array.array("H", [0] * MAX_SAMPLES)
elif clue:
    pin_a = board.BUTTON_A
    pin_b = board.BUTTON_B
    output_internal_res = 140   ### guestimate
    status_led = neopixel.NeoPixel(board.NEOPIXEL, 1)

    import ulab
    import ulab.numpy
    sample_store = ulab.numpy.zeros(MAX_SAMPLES, dtype=ulab.numpy.uint16)
else:
    raise RuntimeError("Unsupported board")


pin_but_a = digitalio.DigitalInOut(pin_a)
pin_but_a.switch_to_input(pull=digitalio.Pull.UP)
pin_but_b = digitalio.DigitalInOut(pin_b)
pin_but_b.switch_to_input(pull=digitalio.Pull.UP)
left_button = lambda: not pin_but_a.value
right_button = lambda: not pin_but_b.value

### The three LEDs all using 2.2k resistors
### Green is very dim, noticeably different to the rest
red_led = digitalio.DigitalInOut(board.P0)
red_led.switch_to_output()
amber_led = digitalio.DigitalInOut(board.P1)
amber_led.switch_to_output()
green_led = digitalio.DigitalInOut(board.P2)
green_led.switch_to_output()

### P12 for pwm voltage + P4/P10 for analogue read
### work on both the Adafruit Clue and the KittenBot Meowbit
### 2001 different outputs at 8kHz PWM on nRF52840 - 0V to 3.3V
tran_base_pwm = pwmio.PWMOut(board.P12, frequency=8 * 1000)

tran_coll_div2 = analogio.AnalogIn(board.P4)
battery_div2 = analogio.AnalogIn(board.P10)

display = board.DISPLAY
FONT_WIDTH, FONT_HEIGHT = terminalio.FONT.get_bounding_box()[:2]
DISPLAY_WIDTH, DISPLAY_HEIGHT = display.width, display.height
G_ORIGIN_X = DISPLAY_WIDTH // 2
G_ORIGIN_Y = DISPLAY_HEIGHT // 2

### Nothing on screen for now
group = displayio.Group()
display.show(group)
display.brightness = 0


resistor_to_gnd = (10 * 1000 * 2 ) / 2

base_capacitor = 470e-6


def sampleTwoPins(pin1, pin2, samples=500):
    total1 = total2 = 0
    for _ in range(samples):
        total1 += pin1.value
        total2 += pin2.value
    return (total1 / samples, total2 / samples)


def sampleConsistency(pin, samples=1000):
    for idx in range(samples):
        sample_store[idx] = pin.value
    mean_samples = ulab.numpy.mean(sample_store[:samples])
    sd_samples = ulab.numpy.std(sample_store[:samples])
    median_samples = ulab.numpy.median(sample_store[:samples])
    return (mean_samples, sd_samples, median_samples)



### TODO - make this a test with renamed BatteryTest as parent class
def transistorBaseCheck(steptime=4, steps=100, runs=("up", "down", "up", "down")):
    """This does a test of the transistor by sweeping from 0 to 3.3V
       by setting duty cycle on PWM output.
       The default settings are two up then down sweeps
       in 100 steps with 4 seconds per step."""

    step_ns = round(steptime * 1000 * 1000 * 1000)
    settle_ns = round(steptime * 0.8e9)

    for run in runs:
        is_step_up = run.lower() == "up"
        start_ns = time.monotonic_ns()
        for idx in range(steps + 1):
            t1 = time.monotonic_ns()
            dc = round((idx if is_step_up else steps - idx) * MAX_DCS / steps)
            tran_base_pwm.duty_cycle = dc

            while time.monotonic_ns() < start_ns + idx * step_ns + settle_ns:
                pass
            t2 = time.monotonic_ns()
            t_c_d2, b_d2 = sampleTwoPins(tran_coll_div2, battery_div2)
            t3 = time.monotonic_ns()

            print((t1, t2, t3, idx, dc, t_c_d2, b_d2))

            while time.monotonic_ns() < start_ns + (idx + 1) * step_ns:
                pass

    ### Ensure regardless of anything above that voltage goes back to 0
    tran_base_pwm.duty_cycle = 0


### Coefficients were based on voltage originally
### through a pair of 2.2k resistors in parralel (1105 ohms)

def bc337_ic(current_base):
    return -0.111176 + 0.172587 * (current_base * 1105)

def bc337_ib(current_coll):
    return (current_coll + 0.111176) / 0.172587 / 1105

### Approximate calibration for nRF52840 on CLUE based on one sample
def rawToVnRF52840(raw_value, count=1):
    return raw_value / count / 65535.0 * REF_V - 0.0014


def guessBattery(voltage):
    """Guess the battery type based on the unloaded voltage.
       Returns None if voltage is very low."""
    if voltage < 0.2:
        return None
    elif voltage <= 1.3:
        return "NiMH"
    elif voltage <= 1.55:
        return "Alkaline"
    elif voltage <= 3.35:
        return "LiButton"
    elif voltage <= 4.45:
        return "LiPo"
    return "UNKNOWN"


### Would be nice to load up AA batteries more but
### voltage and 47 ohm parallel pair won't allow this
DEFAULT_TARGET_LOAD_A = { "NiMH": 40/1000,
                           "Alkaline": 40/1000,
                           "LiButton": 5/1000,
                           "LiPo": 100/1000 }

DEFAULT_TARGET_LOAD_OHM = { "NiMH": 30,
                            "Alkaline": 35,
                            "LiButton": 300,
                            "LiPo": 40 }

DEFAULT_TARGET_POWER_W = { "NiMH": 45/1000,
                           "Alkaline": 45/1000,
                           "LiButton": 10/1000,
                           "LiPo": 350/1000 }

### Need to be more cautious here on the
### minimum voltage for rechargeable batteries
MIN_VOLTAGE = { "NiMH": 0.9,
                "Alkaline": 1.0,
                "LiButton": 2.0,
                "LiPo": 3.4 }



### TODO add anomlay voltages 0.2 and 6.4 - something has gone wrong
class BatteryTest:

    def __init__(self,
                 test,
                 base_v_pin,
                 base_res,
                 batt_v_pin,
                 load_res_v_pin,
                 load_res,
                 initial_voltage,
                 rc_s,
                 *,
                 batt_v_mult=2.0,
                 load_res_v_mult=2.0,
                 test_type="current",
                 target_value="default",
                 test_duration=None,
                 test_idx=None,
                 tran_linear_func=bc337_ib,
                 adc_to_v=None,
                 adc_store=sample_store,
                 vref=REF_V,
                 auto_adjust_ib=True,
                 output_data=None,
                 battery_type=None,
                 debug=0  ### pylint: disable=redefined-outer-name
                 ):
        if test not in ("capacity",
                        "discharge"):
            raise ValueError("Invalid test: " + test)
        self._test = test
        self._base_v_pin = base_v_pin
        self._base_res = base_res
        self._batt_v_pin = batt_v_pin
        self._batt_v_mult = batt_v_mult
        self._load_res_v_pin = load_res_v_pin
        self._load_res_v_mult = load_res_v_mult
        self._load_res = load_res
        ### A conservative value for the total resistance
        ### across battery when transistor is saturated
        self._est_total_resistance = max(self._load_res * 1.1,
                                         self._load_res + 2 + 2)
        if test_type in ("current", "resistance"):
            self._test_type = test_type
        else:
            raise ValueError("Invalid type: " + type)
        if (self._test_type == "resistance"
            and target_value != "default"
            and target_value < self._est_total_resistance):
            raise ValueError("Constant resitance value too low: " + target_value)

        start_sample_ns = time.monotonic_ns()
        if initial_voltage is None:
            voltage_now = self.batt_v()
            end_sample_ns = time.monotonic_ns()
        else:
            voltage_now = initial_voltage
            end_sample_ns = start_sample_ns
        self._mid_sample_ns = (start_sample_ns + end_sample_ns) // 2
        self.current_voltage = voltage_now

        if (self._test_type == "load"
            and target_value != "default"
            and target_value > voltage_now / self._est_total_resistance):
            raise ValueError("Constant current value too high: " + target_value)
        self._target_value = target_value
        if test_duration is None:
            self._test_duration = 3 * 24 * 60 * 60 if self._test == "discharge" else 10
        else:
            self._test_duration = test_duration
        self._test_idx = test_idx
        self._rc_s = rc_s
        self._tran_linear_func = tran_linear_func
        self._vref = vref
        self._auto_adjust_ib = auto_adjust_ib
        self._adc_to_v = adc_to_v if adc_to_v else lambda x, y: x / y / 65535.0 * vref
        self._adc_store = adc_store
        if output_data is None:
            self._output_data = self._test == "discharge"
        else:
            self._output_data = output_data
        self._output_data_lasttime_s = None
        self._battery_type = battery_type
        self._debug = debug

        self._firstguess_batt_type = None  ### __enter__ fills this in

        data_points = min(400, int(self._test_duration) + 1)
        self._test_voltage = [0] * data_points
        self._test_current = [0] * data_points
        self._test_time = [0] * data_points
        self._test_lastidx = -1
        self._test_lastreltime_s = -1

        self._current_current = self.batt_i(self.current_voltage)
        self._current_total = 0
        self._current_total_n = 0

        self._battery_capacity_guess = None  ### 0.0 to 1.0
        ### "good" 0.5 to 1.0
        ### "low"  0.25 to 0.5
        ### "replacerecharge" 0.0 to 0.25
        self._battery_state_guess = None
        self.completed = ""
        self._base_maxedout = False
        self._adjust_time_ns = None
        self._adjust_multipler = 1


    @classmethod
    def sampleMeanMedian(cls, pin, store, samples):

        for idx in range(samples):
            store[idx] = pin.value

        ### Discard lower and upper quartiles on assumption
        ### a few of these are outliers due to noisy sampling
        samples_view = sample_store[:samples]
        samples_view.sort()   ### TODO this will only work for ulab ndarray
        quarter = samples // 4
        return ulab.numpy.mean(sample_store[quarter:3*quarter])


    def batt_v(self, samples=400):
        sample = self.sampleMeanMedian(self._batt_v_pin,
                                       self._adc_store,
                                       samples)
        return self._adc_to_v(sample, 1) * self._batt_v_mult


    def tran_coll_v(self, samples=400):
        sample = self.sampleMeanMedian(self._load_res_v_pin,
                                       self._adc_store,
                                       samples)
        return self._adc_to_v(sample, 1) * self._load_res_v_mult


    def batt_v_simple(self, samples=400):
        ### TODO samples/median/whatever - MEDIAN TEMPTING FOR small samples??
        total = 0
        for _ in range(samples):
            total += self._batt_v_pin.value

        return self._adc_to_v(total, samples) * self._batt_v_mult


    def tran_coll_v_simple(self, samples=400):
        total = 0
        for _ in range(samples):
            total += self._load_res_v_pin.value

        return self._adc_to_v(total, samples) * self._load_res_v_mult


    def batt_i(self, batt_voltage=None, tran_coll_voltage=None):
        ba_v = self.batt_v() if batt_voltage is None else batt_voltage
        t_c_v = self.tran_coll_v() if tran_coll_voltage is None else tran_coll_voltage

        return (ba_v - t_c_v) / self._load_res


    def res_v(self):
        return self._res_v_pin.value * self._res_v_pin


    def __enter__(self):
        self.base_v(0)  ### should already be zero...

        self._test_time[0] = time.monotonic_ns()
        self._test_voltage[0] = self.current_voltage
        self._test_current[0] = self._current_current
        self._test_lastidx = 0
        self._test_lastreltime_s = 0

        if self._firstguess_batt_type is None:
            guess = guessBattery(self.current_voltage)
            if self._battery_type is None and guess is None:
                raise ValueError("Battery not connected or very dead")
            self._firstguess_batt_type = guess
            battery_type = self.battery_type
            if self._target_value == "default":
                if self._test_type == "current":
                    self._target_value = DEFAULT_TARGET_LOAD_A[battery_type]
                elif self._test_type == "resistance":
                    self._target_value = DEFAULT_TARGET_LOAD_OHM[battery_type]

        ### Load the battery if above minimum voltage
        if self.current_voltage <= MIN_VOLTAGE[self._firstguess_batt_type]:
            self.completed = "minimum voltage"
        else:
            if self._test_type == "current":
                self.base_ic(self._target_value)
            elif self._test_type == "resistance":
                self.base_ic(self._test_voltage[0] / self._target_value)

        return self  ### this is value returned to as part of with statement


    def testtick(self):

        adj_frac = 0
        time_remaining = 0

        if self.completed:
            return time_remaining

        start_sample_ns = time.monotonic_ns()
        self.current_voltage = self.batt_v()
        self._current_current = self.batt_i(self.current_voltage)
        end_sample_ns = time.monotonic_ns()
        self._mid_sample_ns = (start_sample_ns + end_sample_ns) // 2
        self._current_total += self._current_current
        self._current_total_n += 1

        ##print(self.current_voltage, " ", end="")

        ### Check to see if enough time has passed to record new values
        reltime_s = (self._mid_sample_ns - self._test_time[0]) / 1e9
        relinttime_s = int(reltime_s)
        newidx = self._test_lastidx + 1
        if (newidx < len(self._test_time)
            and relinttime_s > self._test_lastreltime_s):
            self._test_time[newidx] = self._mid_sample_ns
            self._test_voltage[newidx] = self.current_voltage
            self._test_current[newidx] = self._current_current
            self._test_lastidx = newidx
            self._test_lastreltime_s = relinttime_s

        if self.current_voltage <= MIN_VOLTAGE[self._firstguess_batt_type]:
            self.completed = "minimum voltage"
            self.base_v(0)
        else:
            time_remaining = self._test_duration - reltime_s
            if time_remaining < 0.0:
                self.completed = "test complete"
                self.base_v(0)
                time_remaining = 0
            else:
                if self._auto_adjust_ib:
                    adj_frac = self.adjustBase()

        if self._output_data:
            if (self._output_data_lasttime_s is None
                or relinttime_s > self._output_data_lasttime_s
                or self.completed):
                self._output_data_lasttime_s = relinttime_s

                ### TODO - do I want to log the voltage at tran_c too?
                optidx = () if self._test_idx is None else (self._test_idx,)
                print(optidx +
                      (self._test[0] + self._test_type[0],
                       relinttime_s,
                       self._mid_sample_ns,
                       self.current_voltage,
                       self._current_current,
                       adj_frac,
                       self.completed))
        return time_remaining


    def adjustBase(self):

        adjustment = 0
        now_ns = time.monotonic_ns()

        if self._test_type == "current":
            ratio = self._current_current / self._target_value
        elif self._test_type == "resistance":
            ratio = self._current_current / (self.current_voltage / self._target_value)

        duration_rc = (now_ns - self._test_time[0]) / 1e9 / self._rc_s

        ### Only try and adjust after three time constants,
        ### then every second after that
        ### (3 RC 95.0%, 4 RC 98.2%, 5 RC 99.3%)
        if duration_rc > 3.0:
            if (self._adjust_time_ns is None
                or now_ns - self._adjust_time_ns > 1000 * 1000 * 1000):
                self._adjust_time_ns = now_ns
                ### Algorithm here is based on an empirical iterative process
                ### (fiddling around semi-cluelessly)
                ### Reduce the ratio to stop dramatic changes and
                ### limit it to +/- 10% changes which decline over time
                reduction = 4
                swing_reduce_by_time = max(2.0,
                                           min(20.0,
                                               (now_ns - self._test_time[0]) / 1e9))

                max_swing = 0.2 / swing_reduce_by_time
                reduced_ratio = min(1 / (1 - max_swing),
                                    max(1 / (1 + max_swing),
                                        (ratio + reduction) / (1 + reduction)))
                new_mult = self._adjust_multipler / reduced_ratio
                adjustment = (new_mult - self._adjust_multipler) / self._adjust_multipler
                self._adjust_multipler = new_mult

                ### TODO review duplication of code, here vs __enter__
                if self._test_type == "current":
                    self.base_ic(self._target_value,
                                 multiplier=self._adjust_multipler)
                elif self._test_type == "resistance":
                    self.base_ic(self.current_voltage / self._target_value,
                                 multiplier=self._adjust_multipler)

        ## TODO DEL print("perc error", (ratio - 1) * 100.0, "d_rc", duration_rc)
        return adjustment


    def __exit__(self, ex_type, ex_value, ex_tb):
        self.base_v(0)


    def base_v(self, value):
        ##print("SETTING base_v", value)
        self._base_v_pin.duty_cycle = round(value * 65535 / self._vref)


    def base_ib(self, value):
        voltage = value * self._base_res
        c_voltage = max(0, min(self._vref, voltage))

        self.base_v(c_voltage)


    def base_ic(self, value, multiplier=1):
        ##print("SETTING base_ic", value, "x", multiplier)
        ib = self._tran_linear_func(value) * multiplier
        ## print("IC", value, "IB", ib)
        self.base_ib(ib)


    @property
    def mean_current(self):
        if self._current_total_n == 0:
            return 0
        return self._current_total / self._current_total_n


    @property
    def battery_type(self):
        return self._battery_type if self._battery_type else self._firstguess_batt_type


def runAlternatingDischargeCapacityTests(voltage_ulowload):
    """Run a series of short capacity tests and much longer discharge tests
       until the battery drops to minimum voltage."""

    cap_duration = 10
    dis_duration = 3600
    pause = 30
    discap_repeats = 5 * 24  ### approximately 5 days

    battery_type = None
    test_args = (tran_base_pwm,
                     base_r,
                     battery_div2,
                     tran_coll_div2,
                     load_r,
                     voltage_ulowload,
                     base_r * base_c)

    test_idx = 1
    with BatteryTest("capacity",
                     *test_args,
                     adc_to_v=rawToVnRF52840,
                     test_idx=test_idx,
                     test_duration=cap_duration,
                     output_data=True,
                     debug=debug) as lt:
        battery_type = lt.battery_type
        print("TEST", test_idx, battery_type)
        mean_current = 0
        while True:
            gc.collect()
            mem_free = gc.mem_free()
            if mem_free < 70 * 1000:
                print("MEMFREE", mem_free)
            time_left = lt.testtick()
            if not time_left:
                mean_current = lt.mean_current
                final_voltage = lt.current_voltage
                reason = lt.completed
                break
            time.sleep(0.01)
    print("Approximate mean current over test:", mean_current * 1000.0, "mA")
    print("Final voltage:", final_voltage)
    print("Completition reason:", reason)
    test_idx += 1

    if reason == "minimum voltage":
        return
    time.sleep(pause)

    for _ in range(discap_repeats):
        with BatteryTest("discharge",
                         *test_args,
                         adc_to_v=rawToVnRF52840,
                         test_idx=test_idx,
                         test_duration=dis_duration,
                         battery_type=battery_type,
                         debug=debug) as lt:
            print("TEST", test_idx, battery_type)
            mean_current = 0
            while True:
                gc.collect()
                mem_free = gc.mem_free()
                if mem_free < 70 * 1000:
                    print("MEMFREE", mem_free)
                time_left = lt.testtick()
                if not time_left:
                    mean_current = lt.mean_current
                    final_voltage = lt.current_voltage
                    reason = lt.completed
                    break
                time.sleep(0.01)

        ### Quick summary for now - TODO replace
        print("Approximate mean current over test:", mean_current * 1000.0, "mA")
        print("Final voltage:", final_voltage)
        print("Completition reason:", reason)
        test_idx += 1

        if reason == "minimum voltage":
            return
        time.sleep(pause)

        with BatteryTest("capacity",
                         *test_args,
                         adc_to_v=rawToVnRF52840,
                         test_idx=test_idx,
                         test_duration=10,
                         battery_type=battery_type,
                         output_data=True,
                         debug=debug) as lt:
            print("TEST", test_idx, battery_type)
            mean_current = 0
            while True:
                gc.collect()
                mem_free = gc.mem_free()
                if mem_free < 70 * 1000:
                    print("MEMFREE", mem_free)
                time_left = lt.testtick()
                if not time_left:
                    mean_current = lt.mean_current
                    final_voltage = lt.current_voltage
                    reason = lt.completed
                    break
                time.sleep(0.01)

        ### Quick summary for now - TODO replace
        print("Approximate mean current over test:", mean_current * 1000.0, "mA")
        print("Final voltage:", final_voltage)
        print("Completition reason:", reason)
        test_idx += 1

        if reason == "minimum voltage":
            return
        time.sleep(pause)


### Lamp test for the three LEDs
red_led.value = amber_led.value = green_led.value = True
time.sleep(1)
red_led.value = amber_led.value = green_led.value = False

gc.collect()
while True:
    if right_button():
        ### This sweeps full range which means care is required
        ### with battery current to avoid overloading BC337-25
        ### and/or load resistors
        gc.collect()
        transistorBaseCheck()

    ### Check voltage and check consistency (standard deviation) to ensure
    ### it is stable, i.e. properly connected
    bd2_raw_mean, bd2_raw_sd, _ = sampleConsistency(battery_div2)
    batt_v = rawToVnRF52840(bd2_raw_mean) * 2
    d_print(4, "Voltages (raw, raw_sd, cal_v)", bd2_raw_mean, bd2_raw_sd, batt_v)

    highVoltage = batt_v > 6.4
    batteryConnected = batt_v > 0.2
    if highVoltage:
        red_led.value = amber_led.value = True
        time.sleep(0.5)
        red_led.value = amber_led.value = False
        time.sleep(0.25)
    elif batteryConnected:
        if left_button():
            gc.collect()
            ### batteryTest(batt_v, "capacity")
            runAlternatingDischargeCapacityTests(batt_v)

    if debug >= 3:
        gc.collect()
        d_print(3, "GC MEM (end of main loop)", gc.mem_free())
