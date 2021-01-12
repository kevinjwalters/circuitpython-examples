### adc-test-collector v1.0
### Read data from multiple serial ports applying a timestamp
### Intended for use with adc-test-1

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

import serial
import sys

output_filename = "C:\\Windows\\Temp\\sampledata.txt"

verbose = 1

args = sys.argv[1:]
ports = args if args else ("COM14", "COM30", "COM31", "COM18")

if verbose:
    print("Opening:", ports)

serials = [serial.Serial(port=p, baudrate="115200", timeout=5) for p in ports]

synced = [False] * len(serials)

# The fixed number of characters for a line including CRLF
TOTAL_LINE_CHARS = 80

data = []

try:
    while True:
        for idx, ser in enumerate(serials):
            if not ser.in_waiting:
                continue
            line = ser.read(TOTAL_LINE_CHARS)
            if not synced[idx]:
                try:
                    lf_pos = line.index(b"\x0a")
                    if lf_pos != TOTAL_LINE_CHARS - 1:  ### read more unless lucky
                        line = line[lf_pos + 1:] + ser.read(lf_pos + 1)
                    synced[idx] = True
                except ValueError:
                    continue

            data.append(bytes(f'"{ports[idx]}",{time.time_ns()},', "ascii") + line)
            #print(ports[idx], time.time_ns(), line.decode("ascii"), end="")

except KeyboardInterrupt:
    with open(output_filename, "wb") as file:
        for line_bytes in data:
            file.write(line_bytes)
    if verbose:
        print("Written {:d} lines to".format(len(data)),
              output_filename)
