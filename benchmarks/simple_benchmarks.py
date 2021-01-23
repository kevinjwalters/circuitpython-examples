### simple_benchmarks.py v1.4
### Some simple benchmarks

### DO NOT copy files to CIRCUITPY while this is running

### Tested with an Adafruit CLUE and Feather M4 Express using CircuitPython 5.3.1
### And Microbit V1 using MicroPython v1.9.2-34-gd64154c73

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
import os
import sys

import math

### Turn off any screen as console output seriously messes up results
try:
    import board
    board.DISPLAY.auto_refresh = False
except Exception:
    pass

### sys.platform not present on FeatherS2 with 6.0.0
try:
    PLATFORM = sys.platform
except AttributeError:
    PLATFORM = None

ITERATIONS = {}
OPS = {}
SEEDS = {}


def timeit_cp(func):
    t1 = t2 = time.monotonic_ns()
    func()
    t2 = time.monotonic_ns()
    return (t2 - t1) / 1e9


def timeit_mb(func):
    t1 = t2 = time.ticks_us()
    func()
    t2 = time.ticks_us()
    return (t2 - t1) / 1e6

def timeit_bp(func):
    t1 = t2 = time.monotonic()
    func()
    t2 = time.monotonic()
    return (t2 - t1) / 1.0

### Could switch to execute and look
### for exceptions (AttributeError, NotImplementedError)?
if PLATFORM in ("linux", "win32"):
    timeit = timeit_bp
elif PLATFORM in ("microbit", "rp2"):
    timeit = timeit_mb
else:
    timeit = timeit_cp


### pylint: disable=invalid-name

### Floating point
### 1) avoid integers to avoid conversions and the long/big integer code
### 2) avoid repeated, unintentional calculations with 0.0/Inf/NaN
ITERATIONS["bm_001AdditionA"] = 50 * 1000
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
    return (a, b, c, d, e)


ITERATIONS["bm_002MultiplicationA"] = 50 * 1000
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
    return (a, b, c, d, e)


ITERATIONS["bm_003DivisionA"] = 50 * 1000
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
    return (a, b, c, d, e)

ITERATIONS["bm_004ArchimedesPiA"] = 5 * 1000
OPS["bm_004ArchimedesPiA"] = 1
def bm_004ArchimedesPiA(n):
    for idx in range(n):
        x = 4
        y = 2 * math.sqrt(2)

        count = 0
        ### Conventional approach is to iterate until x - y is small
        while count < 10:
            x_new = 2.0 * x * y / (x + y)
            y = math.sqrt(x_new * y)
            x = x_new
            count += 1
        my_pi = (x + y) / 2.0

    return (my_pi, count)

### calculation with extremely large numbers are likely to prevent critical
### periodic background tasks running in the interpreter
ITERATIONS["bm_005MixedBigIntA"] = 3 * 1000
OPS["bm_005MixedBigIntA"] = 30
def bm_005MixedBigIntA(n):
    big_num1 = 987654321987654321987654321987654321
    for idx in range(n):
        num = 1
        num *= 1000
        num = 2 * num * num * num
        num = 12345 * num
        num = num * 12345678901234567890000 * big_num1 * big_num1
        num *= 3
        num *= 31415
        num += 987654321 + num + num + num
        num -= 100000000
        num -= 800000000
        num -= 87654321
        num = -num
        num //= 4  ### undo the addition of three extra num
        num = num // 12345 // big_num1
        num = -num
        num //= 123456789012345678900
        num = num // 100 // 3 // big_num1
        num //= 31415
        num = num // 1000
        num -= 500 * 1000
        num = num - 500000 - 500000 - 499999
        assert num == 1

    return (num,)


local_funcs = locals()

def run(runs=5, fmt="text", stats=False):
    for cond in ("platform", "version", "modules"):
        if hasattr(sys, cond):
            print("sys." + cond + ":", getattr(sys, cond))
    for cond in ("sysname", "nodename", "release", "version", "machine"):
        if hasattr(os.uname(), cond):
            print("os." + cond + ":", getattr(os.uname(), cond))

    func_names = sorted([name for name, func in local_funcs.items() if name.startswith("bm_")])
    for f_n in func_names:
        pretty_name = f_n.lstrip("bm_")
        print(pretty_name, ": ", sep="", end="")
        count = ITERATIONS[f_n]
        gc.collect()
        durations = []
        for _ in range(runs):
            durations.append(timeit(lambda: local_funcs[f_n](count)))
            time.sleep(0.1)

        ops_per_func = OPS.get(f_n) if OPS.get(f_n) else 1
        ops_per_sec_mean = ops_per_func * count / sum(durations) / runs

        print(",".join(["{:.4f}s".format(d) for d in durations]),
              "({:.0f}Hz)".format(ops_per_sec_mean))
        time.sleep(0.1)


if __name__ == "__main__":
    run()
