### cpx-ir-shutter-remote v0.2
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
##from adafruit_circuitplayground.express import cpx


CARRIER_IRFREQ_SONY = 40 * 1000
### 40kHz modulation (for Sony)
### with 20% duty cycle (13107 out of 65535)
pwm = pulseio.PWMOut(board.IR_TX,
                     frequency=CARRIER_IRFREQ_SONY,
                     duty_cycle=13107)
pulseout = pulseio.PulseOut(pwm)


### Sony values based on ones in
### https://github.com/z3t0/Arduino-IRremote/blob/master/src/ir_Sony.cpp
#encoder = adafruit_irremote.GenericTransmit(header=[2320, 10],
#                                            one=   [1175, 650],
#                                            zero=  [575,  650],
#                                            trail=0)

encoder = adafruit_irremote.GenericTransmit(header=[2400, 600],
                                            one=   [1200, 600],
                                            zero=  [600,  600],
                                            trail=None, debug=True)


### loop asking the user to type name of button they wish to send
### pre-empty any ValueError exceptions with in test                 
while True:
    name = input("Press return to send")
    ### Testing enhancement to transmit()
    
    print("sending x3")
    print(time.monotonic())
    encoder.transmit(pulseout, [0xB4, 0xB8, 0xF0], repeat=3, delay=0.005, nbits=20)  ### shutter
    ##encoder.transmit(pulseout, [0x12, 0xB8, 0xF0], nbits=20)  ### start video
    ##time.sleep(0.005)
