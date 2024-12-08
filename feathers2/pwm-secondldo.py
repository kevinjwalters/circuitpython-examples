### pwm-secondldo2 v1.0
### PWM on FeatherS2 LDO2 enable for driving LEDs

### Tested on UM FeatherS2 with CircuitPython 9.2.1

### copy this file to UM FeatherS2  as code.py

### MIT License

### Copyright (c) 2024 Kevin J. Walters

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

### This program uses a PWM signal on the second LDO enable pin to provide
### PWM control over the LDO output - this is NOT necessarily advisable!!

### See Instructables articles for more detail


import random
import time

import board
##import analogio
import digitalio
import pwmio


global_brightness = 1
debug = 2

def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)

PWM_FREQUENCY = 200  ### above perception threshold
ldo2_pwm = pwmio.PWMOut(board.LDO2, frequency=PWM_FREQUENCY)

### Initialize the single onboard button
boot_btn_pin = digitalio.DigitalInOut(board.IO0)
boot_btn_pin.direction = digitalio.Direction.INPUT
boot_btn_pin.pull = digitalio.Pull.UP
boot_button = lambda: not boot_btn_pin.value



### Nothing much happens below about 1000
### 1300 is visible as dim brightness on LEDs
def brightness_to_ldoen_dc(bri):
    cap_bri = max(min(bri * global_brightness, 1.0), 0.0)
    return round(1000.0 + cap_bri * cap_bri * 64535.0)


mode = 0
MODE_COUNT = 2

min_loop_pause_ns = 25_000_000       ### 25ms

last_loop_ns = 0
last_stats_ns = 0

start_mode_ns = time.monotonic_ns()
light_level = None
loop_time_ms = 0
last_now_ns = 0
loop_count = 0
brightness = 0.0
last_brightness = brightness
ranflu_target = 0.0
ranflu_rate = 0.0


while True:
    ### Ensure loop only runs once every min_loop_pause_ns
    now_ns = time.monotonic_ns()
    loop_time_ms = (now_ns - last_now_ns) / 1e6
    last_now_ns = now_ns
    while True:
        if now_ns - last_loop_ns >= min_loop_pause_ns:
            break

        now_ns = time.monotonic_ns()

    if boot_button():
        mode = (mode + 1 ) % MODE_COUNT
        ### Tiny pause then wait for button release
        time.sleep(0.010)
        while boot_button():
            pass
        now_ns = time.monotonic_ns()
        start_mode_ns = now_ns

    time_diff_ns = now_ns - start_mode_ns

    if mode == 0:
        ### Ramp up then down
        brightness = (time_diff_ns % 4_000_000_000) / 2e9
        if brightness > 1.0:
            brightness = 2.0 - brightness  ### ramp down

    elif mode == 1:
        ### Random fluctuations
        if ranflu_rate == 0.0:
            ranflu_target = random.uniform(0.05, 1.0)
            ranflu_rate = random.uniform(0.05, 0.2)

        time_diff_s = (now_ns - last_loop_ns) / 1e9
        step = ranflu_rate * time_diff_s
        if ranflu_target > last_brightness:
            brightness = last_brightness + step
            if brightness > ranflu_target:
                brightness = ranflu_target
        else:
            brightness = last_brightness - step
            if brightness < ranflu_target:
                brightness = ranflu_target

        ### If we hit our target level then trigger a new one
        if brightness == ranflu_target:
            ranflu_rate = 0.0

    ldo2_pwm.duty_cycle = brightness_to_ldoen_dc(brightness)
    last_brightness = brightness
    last_loop_ns = now_ns
    loop_count += 1
