### cpx-ay-3-8912-qwertysynth v1.0
### CircuitPython (on CPX) proof of concept code for AY-3-8910 sound chip
### Wiring
### A0 not used (wary of this with possible capacitance issues)
### PSG A1 to BC1 and to BDIR via diode (rectifier 1N4001 working, shows good on SQ25, voltage just ok)
###     A2 to BDIR
###     A3 to CLK (2MHz)
### SR  A4 (SCL) to SRCLK
###     A5 (SDA) to SER
###     A6 not used (can I use this for half a UART?)
###     A7 to RCLK

### Tested with CPX and CircuitPython 3.1.2
### WILL NOT WORK WITH PREVIOUS VERSIONS DUE TO USE OF
### runtime.serial_bytes_available

### copy this file to CPX as code.py

### MIT License

### Copyright (c) 2019 Kevin J. Walters

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
import math

print("importing adafruit libs")

import busio
import board
import digitalio
import adafruit_74hc595
import pulseio

from supervisor import runtime
from sys import stdin

### CPX SCL is A4, SDA is A5
print("instantiating spi srlatchpin and sr")
spi = busio.SPI(board.SCL, board.SDA)
srlatchpin = digitalio.DigitalInOut(board.A7)
sr = adafruit_74hc595.ShiftRegister74HC595(spi, srlatchpin)
##sr.gpio = 0x00
##sr.gpio = 0x55
##sr.gpio = 0xaa
##sr.gpio = 0xff
##sr.gpio = 0x00

### TODO - turn this into a library
### TODO - look into MIDI over USB or over RX pin (I'm using TX!!)
### TODO - check behaviour/response of A0 to see if it's usable with speaker disabled
### TODO - look at manual envelope and modulation

### Using A3 for now - be wary of A0 as may have extra capacitance
twomeg = const(2*1000*1000)
clock2meg = pulseio.PWMOut(board.A3, duty_cycle=2**15, frequency=twomeg)

### BC2 does not need control, it's wired high
#bc1  = digitalio.DigitalInOut(board.A1)
#bc1.direction = digitalio.Direction.OUTPUT
#bdir = digitalio.DigitalInOut(board.A2)
#bdir.direction = digitalio.Direction.OUTPUT

### A1 is wired to BC1 and via diode to BDIR
### A2 is wired to BDIR
a1BDIRandBC1 = digitalio.DigitalInOut(board.A1)
a1BDIRandBC1.direction = digitalio.Direction.INPUT
a2BDIRonly = digitalio.DigitalInOut(board.A2)
a2BDIRonly.direction = digitalio.Direction.INPUT

### init for sound chip should ideally make sure
### the chip is reset in every way possible
### is half a register write a problem?

### bc1 and bdir are supposed to change with 50ns of each other
### and this is never going to happen with two interpreted instructions
### https://forums.adafruit.com/viewtopic.php?f=60&t=147642


### BDIR,BC1,BC2,BDIR = 1,1,1 = INTAK - LATCH ADDRESS
### this needs to pulse bdir and bc1 high near simultaneously
### REPL mode shows pulse width as 46 us
##
### BDIR,BC1,BC2,BDIR = 1,1,0 = DWS - WRITE TO PSG
### this needs to pulse bdir high while bc1 is low
def latchData(gpio):
    gpio.direction = digitalio.Direction.OUTPUT
    gpio.value = True   ### TODO - consider how to ensure pulse width here
    gpio.value = False
    gpio.direction = digitalio.Direction.INPUT

### TODO - this is not a good implementation with the output pin passed in    
def writeAddress(sr, a1BDIRandBC1, value):
    sr.gpio = value
    latchData(a1BDIRandBC1)
    
### TODO - this is not a good implementation with the output pin passed in    
def writeData(sr, a2BDIRonly, value):
    sr.gpio = value
    latchData(a2BDIRonly)
    
def writePSG(register, value, sr, a1BDIRandBC1, a2BDIRonly):
    writeAddress(sr, a1BDIRandBC1, register)
    writeData(sr, a2BDIRonly, value)

### clear the sixteen registers (R0 to R15)
for regidx in range(16):
    writePSG(regidx, 0, sr, a1BDIRandBC1, a2BDIRonly)
    
### Midi notes going beyond the A0-C8 (21-108) range
### 60 is C4 (middle C)
### 69 is A4 (440 Hz)
print("creating midinotes list")
midinotes = [round(twomeg / (16 * (440 * math.pow(2,x / 12.0)))) for x in range(-69,59)]

print("creating qwertytomidinote dictionary")
### a on keyboard starts the octave at C4 60
qwertytomidinote = {'a' : 60,  ### C4
                    'w' : 61,
                    's' : 62,
                    'e' : 63,
                    'd' : 64,
                    'f' : 65,
                    't' : 66,
                    'g' : 67,
                    'y' : 68,
                    'h' : 69,
                    'u' : 70,
                    'j' : 71,
                    'k' : 72,  ### C5
                    'o' : 73,
                    'l' : 74
                   }
print("post data structure assignment")
               
print("simple keyboard mode")

writePSG(7,  0xfe, sr, a1BDIRandBC1, a2BDIRonly)  ### Tone C,B,A enable, noise disable
writePSG(8,  0x00, sr, a1BDIRandBC1, a2BDIRonly)  ### A silent

keyboardmode = True
while keyboardmode:
    if runtime.serial_bytes_available:
        char = stdin.read(1)
        if char in qwertytomidinote:
            period = midinotes[qwertytomidinote[char]]
            writePSG(0, period & 0xff, sr, a1BDIRandBC1, a2BDIRonly)
            writePSG(1, period >> 8,   sr, a1BDIRandBC1, a2BDIRonly)
            writePSG(8,  0x0c, sr, a1BDIRandBC1, a2BDIRonly)
            time.sleep(0.25)
            writePSG(8,  0x00, sr, a1BDIRandBC1, a2BDIRonly)
        elif char == 'q':
            keyboardmode = False
           
               
### clear the sixteen registers (R0 to R15)
for regidx in range(16):
    writePSG(regidx, 0, sr, a1BDIRandBC1, a2BDIRonly)
    
writePSG(7,  0xf8, sr, a1BDIRandBC1, a2BDIRonly)  ### Tone C,B,A enable, noise disable
writePSG(8,  0x08, sr, a1BDIRandBC1, a2BDIRonly)  ### A half vol
writePSG(9,  0x08, sr, a1BDIRandBC1, a2BDIRonly)  ### B half vol
writePSG(10, 0x08, sr, a1BDIRandBC1, a2BDIRonly)  ### C half vol

### A3, A4, A5 for now
#notes=[int((2e6/(16*x))+0.5) for x in [220,440,880]]

### A4 - B5 in semitones
### 284 to 75 (how can this do high accurate notes??)
notes = [int(twomeg / (16 * (440 * math.pow(2,x/12.0)))+0.5) for x in range(24)]

### play some major chords
for i in range(4):
    for noteidx in [0,4,7]:
        writePSG(0, notes[noteidx] & 0xff, sr, a1BDIRandBC1, a2BDIRonly)
        writePSG(1, notes[noteidx] >> 8, sr, a1BDIRandBC1, a2BDIRonly)

        writePSG(2, notes[noteidx+4] >> 0xff, sr, a1BDIRandBC1, a2BDIRonly)
        writePSG(3, notes[noteidx+4] >> 8, sr, a1BDIRandBC1, a2BDIRonly)

        writePSG(4, notes[noteidx+7] >> 0xff, sr, a1BDIRandBC1, a2BDIRonly)
        writePSG(5, notes[noteidx+7] >> 8, sr, a1BDIRandBC1, a2BDIRonly)
        
        time.sleep(0.25)
