### simple-analoguein v1.2
### Read analogue inputs on a Circuit Playground Express (CPX)
### Reads A0-A7 inputs and prints them to output

### copy this file to CPX as code.py

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

### All eight pins on CPX board
pins = [ AnalogIn(board.A0),
         AnalogIn(board.A1),
         AnalogIn(board.A2),
         AnalogIn(board.A3),
         AnalogIn(board.A4),
         AnalogIn(board.A5),
         AnalogIn(board.A6),
         AnalogIn(board.A7) ]     

numpins = len(pins)
refvoltage = pins[0].reference_voltage
adcconvfactor = refvoltage / 65536

### Convert value from pin.value to voltage
def getVoltage(pin):
    return pin.value * adcconvfactor

### 1000 is about 2.4s per loop iteration for 7 pins on a CPX
### 370 is about 1s for 8 pins on CPX
samples = 370

### Print two relative timestamps in seconds plus an unweighted average of
### many samples for each pin in python tuple style which can be read
### directly graphed by the Mu editor - values are raw (0-65535)
while True:
    total = [0] * numpins
    t1 = time.monotonic()
    for repeat in range(samples):
        values = [pin.value for pin in pins]
        total = [sum(x) for x in zip(total, values)]
    t2 = time.monotonic()
    avgs = list(map(lambda x: x / samples, total))
    print("({:f},{:f},".format(t1,t2) + ",".join(str(avg) for avg in avgs) + ")")
