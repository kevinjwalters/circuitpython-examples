### Input Demo - v1.0
### Read data over the USB serial connection
### This reads data over the serial connection demonstrating use of input()
### for simple communication between host computer and board running
### CircuitPython. Intended for Circuit Playground Express (CPX) but approach
### is applicable to all. input() waits for a command therefore code exhibits
### blocking behaviour.

### copy this file to CPX as code.py

# MIT License

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
import random
from adafruit_circuitplayground.express import cpx

### dictionary for permissible colours
colour = {
 "red"   : (0x20, 0, 0),
 "green" : (0, 0x20, 0),
 "blue"  : (0, 0, 0x20),
}

### Wait for a command like "glow red"
while True:
    command = input()
    try:
        [verb, noun] = command.split()
        if verb == "glow":
            cpx.pixels.fill(colour[noun])
            continue
    except:
        pass  ### fall through to error handling
    print("unknown command: " + command)
