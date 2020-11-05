### cpx-ir-shutter-remote v1.0
### Circuit Playground Express (CPX) shutter remote using infrared for Sony Cameras
### TODO - describe in more detail

### copy this file to CPX as code.py

### MIT License

### Copyright (c) 2020 Kevin J. Walters

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

import pulseio
import board
import adafruit_irremote
from adafruit_circuitplayground import cp


debug = 1

def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


### 40kHz modulation (for Sony)
### with 20% duty cycle (13107 out of 65535)
CARRIER_IRFREQ_SONY = 40 * 1000
ir_carrier_pwm = pulseio.PWMOut(board.IR_TX,
                                frequency=CARRIER_IRFREQ_SONY,
                                duty_cycle=13107)
ir_pulseout = pulseio.PulseOut(ir_carrier_pwm)


### Sony timing values (in us) based on the ones in
### https://github.com/z3t0/Arduino-IRremote/blob/master/src/ir_Sony.cpp
### Disabling the addition of trail value is required to make this work
### trail=0 does not work
ir_encoder = adafruit_irremote.GenericTransmit(header=[2400, 600],
                                               one=   [1200, 600],
                                               zero=  [600,  600],
                                               trail=None)

SHUTTER_CMD_COLOUR = (16, 0, 0)
BLACK = (0, 0, 0)

S_TO_NS = 1000 * 1000 * 1000
ADJ_NS = 20 * 1000 * 1000
intervals = [5, 10, 15, 20, 25, 30, 60,
             120, 180, 240, 300, 600, 1800, 3600]
interval_idx = intervals.index(30)  ### default is 30 seconds
intervalometer = False
last_cmd_ns = None
first_cmd_ns = None

###encoder.transmit(pulseout, [0x12, 0xB8, 0xF0], nbits=20)  ### start video   
while True:
    if cp.switch:  ### switch to left
        intervalometer = False
        if cp.button_a:  ### left button_a
            cp.pixels.fill(SHUTTER_CMD_COLOUR)
            last_cmd_ns = time.monotonic_ns()
            ir_encoder.transmit(ir_pulseout, [0xB4, 0xB8, 0xF0],
                                repeat=3, delay=0.005, nbits=20)  ### shutter
            if first_cmd_ns is None:
                first_cmd_ns = last_cmd_ns
            print("Manual", "shutter release at", (last_cmd_ns - first_cmd_ns) / S_TO_NS)
            cp.pixels.fill(BLACK)
            while cp.button_a:
                pass  ### wait for button release
    
    else:  ### switch to right
        if cp.button_a and interval_idx > 0:
            interval_idx -= 1
            while cp.button_a:
                pass  ### wait for button release
        elif cp.button_b and interval_idx < len(intervals) - 1:
            interval_idx += 1
            while cp.button_b:
                pass  ### wait for button release
        
        now_ns = time.monotonic_ns()
        if (not intervalometer
            or now_ns - last_cmd_ns >= intervals[interval_idx] * S_TO_NS - ADJ_NS):
            intervalometer = True
            
            cp.pixels.fill(SHUTTER_CMD_COLOUR)
            last_cmd_ns = time.monotonic_ns()
            ir_encoder.transmit(ir_pulseout, [0xB4, 0xB8, 0xF0],
                                repeat=3, delay=0.005, nbits=20)  ### shutter
            if first_cmd_ns is None:
                first_cmd_ns = last_cmd_ns
            print("Timer", "shutter release at", (last_cmd_ns - first_cmd_ns) / S_TO_NS)
            cp.pixels.fill(BLACK)
