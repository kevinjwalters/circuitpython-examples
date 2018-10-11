### simple-analoguein v1.1
### Read analogue inputs on a Circuit Playground Express (CPX)
### Reads A1-A7 inputs and prints them to output

### copy this file to CPX as main.py

### MIT License

### Copyright (c) 2018 Kevin J. Walters

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

import board
from analogio import AnalogIn

pins = [ AnalogIn(board.A1),
         AnalogIn(board.A2),
         AnalogIn(board.A3),
         AnalogIn(board.A4),
         AnalogIn(board.A5),
         AnalogIn(board.A6),
         AnalogIn(board.A7) ]     

numpins = len(pins)
         
refvoltage = pins[0].reference_voltage
adcconvfactor = refvoltage / 65536

def getVoltage(pin):  # helper
    return pin.value * adcconvfactor

### 1000 is about 2.4s per loop iteration on a CPX
samples = 1000

while True:
    t1 = time.monotonic()
    total = [0] * numpins
    for repeat in range(samples):
        values = [pin.value for pin in pins]
        total = [sum(x) for x in zip(total, values)]
    avgs = list(map(lambda x: x / samples, total))
    t2 = time.monotonic()
    print("({:f},{:f},".format(t1,t2) + ",".join(str(avg) for avg in avgs) + ")")
    ##print("Analog Voltage: %f" % getVoltage(analogin))
    ##time.sleep(0.2)
