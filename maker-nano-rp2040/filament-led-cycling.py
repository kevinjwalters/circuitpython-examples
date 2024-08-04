### filament-led-cycling v1.1
### Basic test patterns using pwm for six channel constant current LED driver circuit

### Tested on Cytron Maker Nano RP2040 with CircuitPython 9.0.5

### copy this file to Cytron Maker Nano RP2040 as code.py

### MIT License

### Copyright (c) 2024 Kevin J. Walters

### Permission is hereby granted, free of charge, to any person obtaining a copy
### of this software nd associated documentation files (the "Software"), to deal
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

### See Instructables articles for more detail

### TODO - auto-adjust using ambient light sensor
### TODO - add current estimate in code based
###        on RP2040 base usage plus LED brightness levels, speaker use and RGB pixels
### TODO - add one_by_one mode for checking current on each channel

import random
import time

import board
import analogio
import digitalio
import pwmio
from ulab import numpy as np
##from audiopwmio import PWMAudioOut as AudioOut
##from audiocore import WaveFile

### neopixel and simpleio are frozen modules for Maker Nano RP2040
import neopixel
import simpleio

### pylint: disable=global-statement


global_brightness = 1
resistance_e = 1 / (1/10 + 1/27)   ### parallel 10R and 27R = 7.30 ohms
vbe_std = 0.618  ### at 25 Celsius
debug = 2


current_est = (vbe_std / resistance_e)
### This is just a guess fit based on the chart a datasheet
## leddriver_vbe_temp_coef = (-2.34 + current_est**0.5 * 1.6) / 1e3
feedback_vbe_temp_coef = -2.35 / 1e3  ### for 1.6mA


def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


adc_vals = np.zeros(16, dtype=np.uint16)
def read_adc(ain):
    global adc_vals
    for idx in range(adc_vals.size):
        adc_vals[idx] = ain.value
    adc_vals.sort()  ### in-place sort
    return np.mean(adc_vals[2:-2])


### Initialise the six pins use to driver filament LEDs using different
### frequencies to try to spread the on times to lower aggregate peak current
### RP2040 PWM architecture dictates they must match per GPIO pair
BASE_FREQUENCY = 1907  ### rounded 125MHz / 2**16
pwms = (pwmio.PWMOut(board.GP9, frequency=BASE_FREQUENCY),
        pwmio.PWMOut(board.GP8, frequency=BASE_FREQUENCY),

        pwmio.PWMOut(board.GP5, frequency=BASE_FREQUENCY + 79),
        pwmio.PWMOut(board.GP4, frequency=BASE_FREQUENCY + 79),

        pwmio.PWMOut(board.GP1, frequency=BASE_FREQUENCY + 127),
        pwmio.PWMOut(board.GP0, frequency=BASE_FREQUENCY + 127)
        )
LED_COUNT = len(pwms)

### Initialize Neopixel RGB LEDs
pixels = neopixel.NeoPixel(board.GP11, 2)
pixels.fill(0)

PIXEL_BE = 0   ### top of board (near RESET button)
PIXEL_SV = 1   ### bottom of board (near BOOT button)

BLACK  = 0x000000
YELLOW = 0x0c0c00
ORANGE = 0x0f0700
RED    = 0x0f0000
CYAN   = 0x000c0c
BLUE   = 0x00000f

### Define pin connected to tiny speaker
SPEAKER_PIN = board.GP22

##audio_out = AudioOut(SPEAKER_PIN, quiescent_value=0)
####scanner_file = open("scanner-mono-16k.wav", "rb")
##scanner_file = open("one-drip-16k.wav", "rb")
##scanner_sample = WaveFile(scanner_file)

### Initialize the single onboard button
btn_pin = digitalio.DigitalInOut(board.GP20)
btn_pin.direction = digitalio.Direction.INPUT
btn_pin.pull = digitalio.Pull.UP
button = lambda: not btn_pin.value

### Analogue pins for the constant current driver board
### A0 is output from potential divider using LDR and 10k resistor
### A1 is output from 2x10k potential divider for 5V pin
### A2 is Vbe for board.GP5 (led 2)
### A3 is Vbe for board.GP1 (led 4)
light_level_adc = analogio.AnalogIn(board.A0)
supply_voltage_adc = analogio.AnalogIn(board.A1)
led2_vbe_adc = analogio.AnalogIn(board.A2)
led4_vbe_adc = analogio.AnalogIn(board.A3)
adc_offset = (read_adc(led2_vbe_adc) + read_adc(led4_vbe_adc)) / 2

ALMOST_100_DC = round(0.995 * 65535)  ### Only take Vbe measurements above this

ADC_REF = light_level_adc.reference_voltage   ### This will be 3.3
ADC_CONV = ADC_REF / 65535.0

REF_A4 = 440
MIDI_A4 = 69
def midi_to_freq(midi_note):
    return REF_A4 * 2**((midi_note - MIDI_A4) / 12)


simple_pulsing_test = True

if simple_pulsing_test:
    simpleio.tone(SPEAKER_PIN, midi_to_freq(MIDI_A4) / 4.0, 0.1)
    simpleio.tone(SPEAKER_PIN, midi_to_freq(MIDI_A4) / 2.0, 0.1)
    simpleio.tone(SPEAKER_PIN, midi_to_freq(MIDI_A4), 0.1)
    time.sleep(0.5)


def brightness_to_dc(brightness):
    cap_bri = max(min(brightness * global_brightness, 1.0), 0.0)
    return round(cap_bri * cap_bri * 65535.0)


def brightness_to_dc_looks_bad(brightness):
    cap_bri = max(min(brightness * global_brightness, 1.0), 0.0)
    if cap_bri > 0.08:
        return round((cap_bri + 0.16 ) * 56495.69)
    else:
        return round(cap_bri * 169487.07)

for bri_level in range(20 + 1):
    b = bri_level / 20.0
    print(b, brightness_to_dc(b))


def random_fluctuations(time_ns, state):
    if len(state) == 0:
        state["target"] = []
        state["rate"] = []
        state["last"] = []
        state["last_ns"] = 0

    if len(state["target"]) == 0:
        state["target"] = [random.uniform(0.03, 0.8) for x in range(LED_COUNT)]
        state["rate"] = [random.uniform(0.1, 0.4) for x in range(LED_COUNT)]

    if len(state["last"]) == 0:
        ### Initialise LEDS, all off
        for idx, pwm in enumerate(pwms):
            pwm.duty_cycle = brightness_to_dc(0.0)
        state["last"] = [0.0] * LED_COUNT
    else:
        time_diff_s = (time_ns - state["last_ns"]) / 1e9
        for idx, pwm in enumerate(pwms):
            last_val = state["last"][idx]
            target_val = state["target"][idx]
            step = state["rate"][idx] * time_diff_s
            if target_val > last_val:
                new_val = last_val + step
                if new_val > target_val:
                    new_val = target_val
            else:
                new_val = last_val - step
                if new_val < target_val:
                    new_val = target_val

            pwm.duty_cycle = brightness_to_dc(new_val)
            state["last"][idx] = new_val
            ### If we hit our target level then make a new one
            if new_val == target_val:
                state["target"][idx] = random.uniform(0.03, 0.8)
                state["rate"][idx] = random.uniform(0.1, 0.4)

    state["last_ns"] = time_ns


def rotating_pulsing(time_ns,
                     state  ### pylint: disable=unused-argument
                     ):
    cycle_time_ns = time_ns % 12_000_000_000

    peak_pos = cycle_time_ns / 2_000_000_000 - 0.5

    for idx, pwm in enumerate(pwms):
        distance1 = abs((idx - LED_COUNT) - peak_pos)
        distance2 = abs(idx - peak_pos)
        distance3 = abs((idx + LED_COUNT) - peak_pos)
        distance = min(distance1, distance2, distance3)
        brightness = (distance / (LED_COUNT / 2)) ** 3

        pwm.duty_cycle = brightness_to_dc(brightness)


def all_pulsing(time_ns,
                state  ### pylint: disable=unused-argument
                ):
    """Ramp brightness on all LEDs up over 3 seconds, then down for 3s, then pause for 1s.
       This currently has a beeping chromatic scale which jars after a few repeats.
    """

    cycle_time_ns = time_ns % 7_000_000_000

    if cycle_time_ns <= 3_000_000_000:
        brightness = cycle_time_ns / 3_000_000_000
    elif cycle_time_ns <= 6_000_000_000:
        brightness = (6_000_000_000 - cycle_time_ns) / 3_000_000_000
    else:
        brightness = 0

    for pwm in pwms:
        pwm.duty_cycle = brightness_to_dc(brightness)

    if brightness != 0:
        simpleio.tone(SPEAKER_PIN, midi_to_freq(48 + int(brightness * 4 * 12 )), 0.028)


def larson_scanner(time_ns,
                   state  ### pylint: disable=unused-argument
                   ):
    """A basic larson scanner."""
    cycle_time_ns = time_ns % (15 * 200_000_000)

    direction = -1  ### moving right
    peak_intpos = int(cycle_time_ns / 200_000_000) - 1
    if peak_intpos >= LED_COUNT + 1:
        direction = 1  ### moving left
        peak_intpos = 2 * LED_COUNT + 1 - peak_intpos

    for idx, pwm in enumerate(pwms):
        brightness = 0
        if idx == peak_intpos:
            brightness = 1.0
        elif idx == peak_intpos + direction:
            brightness = 0.3
        elif idx == peak_intpos + 2 * direction:
            brightness = 0.1

        pwm.duty_cycle = brightness_to_dc(brightness)

    ##if (direction > 0 and peak_intpos == LED_COUNT - 1) or (direction < 0 and peak_intpos == 0):
    ##    audio_out.play(scanner_sample)  ### this sounds terrible


tune1 = [( 0, 1.0, [(0, 0.1), (1, 0.1), (2, 0.1), (3, 0.1), (4, 0.1)]),
         (69, 0.25, [(4, 0.7)]),  ### tone,
         (71, 0.25, [(3, 0.7)]),  ### up a full tone,
         (67, 0.25, [(2, 0.7)]),  ### down a major third,
         (55, 0.25, [(0, 0.7)]),  ### now drop an octave,
         (62, 1.25, [(1, 0.7)]),  ### up a perfect fifth.
         ( 0, 0.75, [(0, 0.4), (1, 0.4), (2, 0.4), (3, 0.4), (4, 0.4)])   ### (rest, wait for arrival)
        ]
tune1_len = sum([note[1] for note in tune1])
def some_notes(time_ns,
               state  ### pylint: disable=unused-argument
               ):
    """This turns them all off for 2 seconds, then adds one every 2 seconds.
       This is intended to facilitate current measurement from slow meters.
    """
    if len(state) == 0:
        state["start_ns"] = time_ns
        state["barlength"] = 60 / 90 * 4
        state["notegap"] = 0.05
        state["length_ns"] = round(tune1_len * state["barlength"] * 1e9)
        state["next_note"] = 0

    reltime_ns = (time_ns - state["start_ns"]) % state["length_ns"]

    note_start = 0.0
    for idx, (midi_note, length, pwm_changes) in enumerate(tune1):
        note_len = length * state["barlength"]
        note_end = note_start + note_len
        if idx == state["next_note"] and note_start <= reltime_ns / 1e9 < note_end:
            state["next_note"] = (idx + 1) % len(tune1)
            for pwm_idx, brightness in pwm_changes:
                pwms[pwm_idx].duty_cycle = brightness_to_dc(brightness)
            if midi_note > 0:
                simpleio.tone(SPEAKER_PIN,
                              midi_to_freq(midi_note),
                              note_len - state["notegap"])
            break
        note_start = note_end


def staggered_on(time_ns,
                 state  ### pylint: disable=unused-argument
                 ):
    """This turns them all off for 2 seconds, then adds one every 2 seconds.
       This is intended to facilitate current measurement from slow meters.
    """
    cycle_time_ns = time_ns % 14_000_000_000

    on_count = int(cycle_time_ns / 2_000_000_000)
    for idx, pwm in enumerate(pwms):
        pwm.duty_cycle = 65535 if idx < on_count else 0


sv_badness_history = np.zeros(125, dtype=np.uint8)
sv_badness_idx = 0
def set_supply_voltage_status(sv):
    """The supply voltage is normally 4.7 but will decrease with load.
       Below 3.6 it's shown as red as this is when it will lower the output
       from the 3.3V regulator.
       Low microcontroller voltages will unfortunately also mess up ADC
       readings as VCC is the voltage reference value.
    """
    global sv_badness_idx, sv_badness_history

    badness = 0
    if sv < 3.6:
        badness = 3
    elif sv < 3.8:
        badness = 2
    elif sv < 4.0:
        badness = 1

    ### Using maximum of history provides a hold feature with less flicker
    sv_badness_history[sv_badness_idx] = badness
    sv_badness_idx = (sv_badness_idx + 1) % sv_badness_history.size

    pixels[PIXEL_SV] = (BLACK, YELLOW, ORANGE, RED)[np.max(sv_badness_history)]


def set_vbe_status(vbes):
    """Indicate issues with Vbe on an RGB pixel,
       red for suspicious difference between transistors,
       orange for very hot or low supply voltage,
       yellow for hot, cyan for cold, blue for very cold."""
    colour = BLACK
    if len(vbes) > 0 and max(vbes) - min(vbes) > 0.050:
        colour = RED  ### Suspicious difference beyond 50mV
    else:
        for vbe in vbes:
            if vbe < 0.500:
                colour = ORANGE  ### either very hot or low supply voltage or high led resistance
            elif vbe < 0.580:
                colour = YELLOW  ### hot
            elif vbe > 0.730:
                colour = BLUE    ### very cold
            elif vbe > 0.670:
                colour = CYAN    ### cold

    pixels[PIXEL_BE] = colour


def calc_temperature(vbes, temp_coef):
    if len(vbes) == 0:
        return None

    mean_v = sum(vbes) / len(vbes)
    return 25 + (mean_v - vbe_std) / temp_coef


mode = 0
MODE_COUNT = 6

### Loop is currently 8-10ms
min_loop_pause_ns = 5_000_000        ### 5ms
debug_print_time_ns = 1_000_000_000  ### each second

last_loop_ns = 0
last_stats_ns = 0

start_mode_ns = time.monotonic_ns()
anim_state = {}
light_level = None
supply_voltage = None
led2_vbe = None
led4_vbe = None
temp = None
pausing = None
loop_time_ms = 0
last_now_ns = 0
loop_count = 0

while True:
    light_level = read_adc(light_level_adc) - adc_offset
    supply_voltage = (read_adc(supply_voltage_adc) - adc_offset) * 2 * ADC_CONV
    set_supply_voltage_status(supply_voltage)

    if debug >= 1 and last_loop_ns - last_stats_ns >= debug_print_time_ns:
        d_print(1,
                light_level, supply_voltage, led2_vbe, led4_vbe, temp,
                round(loop_time_ms, 2), pausing)
        last_stats_ns = time.monotonic_ns()

    ### Ensure loop only runs once every min_loop_pause_ns
    pausing = False

    now_ns = time.monotonic_ns()
    loop_time_ms = (now_ns - last_now_ns) / 1e6
    last_now_ns = now_ns
    while True:
        if now_ns - last_loop_ns >= min_loop_pause_ns:
            break
        pausing = True
        now_ns = time.monotonic_ns()

    ### Only check vbe for simple case of 100% duty cycle
    if pwms[2].duty_cycle >= ALMOST_100_DC:
        led2_vbe = (read_adc(led2_vbe_adc) - adc_offset) * ADC_CONV
    if pwms[4].duty_cycle >= ALMOST_100_DC:
        led4_vbe = (read_adc(led4_vbe_adc) - adc_offset) * ADC_CONV
    pukka_vbe = [v for v in [led2_vbe, led4_vbe] if v is not None]
    set_vbe_status(pukka_vbe)
    temp = calc_temperature(pukka_vbe, feedback_vbe_temp_coef)

    if button():
        anim_state = {}   ### reset state
        mode = (mode + 1 ) % MODE_COUNT
        ### tiny pause then wait for button release
        time.sleep(0.010)
        while button():
            pass
        now_ns = time.monotonic_ns()
        start_mode_ns = now_ns

    time_diff_ns = now_ns - start_mode_ns
    if mode == 0:
        random_fluctuations(time_diff_ns, anim_state)
    elif mode == 1:
        rotating_pulsing(time_diff_ns, anim_state)
    elif mode == 2:
        all_pulsing(time_diff_ns, anim_state)
    elif mode == 3:
        larson_scanner(time_diff_ns, anim_state)
    elif mode == 4:
        some_notes(time_diff_ns, anim_state)
    elif mode == 5:
        staggered_on(time_diff_ns, anim_state)

    last_loop_ns = now_ns
    loop_count += 1
