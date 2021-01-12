### adc-test-1 v1.0
### Print values from ADC to compare between boards
### Reads from A5, sets A0 on SAMD21 only

### Tested with various Feather boards and CircuitPython 6.x verisons

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

import board
import analogio
import os

SYSNAME = os.uname().sysname

def iterjoin(*iterables):
   for iter in iterables:
       yield from iter

def inf_num():
    while True:
        yield -1

def repeat(value, cnt):
    for _ in range(cnt):
        yield value


input_pin = board.A5
output_pin = board.A0 if SYSNAME == "samd21" else None
OUTPUT_DAC_BITS = 10

input = analogio.AnalogIn(input_pin)
output = analogio.AnalogOut(output_pin) if output_pin else None

try:
    _ = time.monotonic_ns()
    time_fn = time.monotonic_ns
    time_mul = 1e-9
except (AttributeError, NotImplementedError):
    time_fn = time.monotonic
    time_mul = 1

SAMPLE_SIZES = (1, 8, 50)

output_step = 1 << (16 - OUTPUT_DAC_BITS)

### The SAMD21 is about 22ms for the loop anyway
interval = 0.025

time.sleep(30)

### 80 chars minus CRLF minus standard print space between arguments
PAD_TO_LEN = 80 - 2 - 1
HEADER = "# time,samples,output,input"

for _ in range(3):
    print(HEADER, " " * (PAD_TO_LEN - len(HEADER)))

last_loop = 0

while True:
    if output:
        loop_data = iterjoin(range(0, 2**16, output_step),
                             range(2**16 - output_step, -output_step, -output_step),
                             repeat(65535, 50),
                             repeat(32768, 50),
                             repeat(0,50),
                             repeat(65535, 25),
                             repeat(0,25),
                             repeat(65535,25))
    else:
        loop_data = inf_num()

    for out_value in loop_data:
        if output:
            output.value = out_value

        while True:
            now = time_fn() * time_mul
            if now > last_loop + interval:
                break
        last_loop = now

        for sample_size in SAMPLE_SIZES:
            in_start_t = time_fn()
            if sample_size == 1:
                in_value = input.value
            else:
                in_value = sum([input.value for _ in range(sample_size)]) / sample_size
            data_as_text = "{:f},{:d},{:d},{:f}".format(in_start_t * time_mul,
                                                        out_value,
                                                        sample_size,
                                                        in_value)
            print(data_as_text, " " * (PAD_TO_LEN - len(data_as_text)))
