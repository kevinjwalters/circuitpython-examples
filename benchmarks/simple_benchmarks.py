### simple_benchmarks.py v1.0
### Some simple benchmarks

### DO NOT copy files to CIRCUITPY while this is running

### Tested with an Adafruit CLUE and Feather M4 Express using CircuitPython 5.3.1

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


### Discussion on this in https://forums.adafruit.com/viewtopic.php?f=60&t=170425  

import time
import gc
import sys

import board

### Turn off any screen as console output seriously messes up results
try:
    board.DISPLAY.auto_refresh = False
except Exception:
    pass


ITERATIONS = {}
OPS = {}
SEEDS = {}


def timeit(func):
    t1 = time.monotonic_ns()
    func()
    t2 = time.monotonic_ns()
    return (t2 - t1) / 1e9


### Floating point
### 1) avoid integers to avoid conversions and the long/big integer code
### 2) avoid repeated, unintentional calculations with 0.0/Inf/NaN 
ITERATIONS["bm_001AdditionA"] = 50_000
OPS["bm_001AdditionA"] = 10
def bm_001AdditionA(n):
    for idx in range(n):
        if idx % 50 == 0:
            a = 1.0
            b = 1.1
            c = 3.456789e-4
            d = 5.678901e4
            f = 1.5
        a += 1.01
        b = a + b
        c = c + a + a + a
        d = a + b + 0.9999
        e = a + b + c + d
    return (a,b,c,d,e)


ITERATIONS["bm_002MultiplicationA"] = 50_000
OPS["bm_002MultiplicationA"] = 10
def bm_002MultiplicationA(n):
    for idx in range(n):
        if idx % 50 == 0:
            a = 1.0
            b = 1.1
            c = 1.12345e-10
            d = 1.45678e10
            f = 1.5
        a *= 1.01
        b = a * b
        c = c * a * a * a
        d = a * b * 0.9999
        e = a * b * c * d
    return (a,b,c,d,e)


ITERATIONS["bm_003DivisionA"] = 50_000
OPS["bm_003DivisionA"] = 10
def bm_003DivisionA(n):
    for idx in range(n):
        if idx % 50 == 0:
            a = 1.0
            b = 1.1
            c = 1.12345e-10
            d = 1.45678e10
            f = 1.5
        a /= 1.01
        b = a / b
        c = c / a / a / a
        d = a / b / 0.9999
        e = a / b / c / d
    return (a,b,c,d,e)


local_funcs = locals()

def run(n=1, format="text", stats=False):
    for cond in ("platform", "version", "modules"):
        print(cond + ":", getattr(sys, cond))

    func_names = sorted([name for name, func in local_funcs.items() if name.startswith("bm_")])
    for f_n in func_names:
        pretty_name = f_n.lstrip("bm_")
        print(pretty_name, ": ", sep="", end="")
        count = ITERATIONS[f_n]
        gc.collect()
        duration = timeit(lambda : local_funcs[f_n](count))
        ops_per_func = OPS.get(f_n) if OPS.get(f_n) else 1
        print("{:f}s ({:f}Hz)".format(duration, ops_per_func * count / duration))
        time.sleep(0.1)
