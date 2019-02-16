### cpx-ay-3-8912-poc v1.3
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

### Tested with CPX and CircuitPython 3.1.1

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

import busio
import board
import digitalio
import adafruit_74hc595
import pulseio

### CPX SCL is A4, SDA is A5
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
for i in range(10):
    for noteidx in [0,4,7]:
        writePSG(0, notes[noteidx] & 0xff, sr, a1BDIRandBC1, a2BDIRonly)
        writePSG(1, notes[noteidx] >> 8, sr, a1BDIRandBC1, a2BDIRonly)

        writePSG(2, notes[noteidx+4] >> 0xff, sr, a1BDIRandBC1, a2BDIRonly)
        writePSG(3, notes[noteidx+4] >> 8, sr, a1BDIRandBC1, a2BDIRonly)

        writePSG(4, notes[noteidx+7] >> 0xff, sr, a1BDIRandBC1, a2BDIRonly)
        writePSG(5, notes[noteidx+7] >> 8, sr, a1BDIRandBC1, a2BDIRonly)
        
        time.sleep(0.25)

### clear the sixteen registers (R0 to R15)
for regidx in range(16):
    writePSG(regidx, 0, sr, a1BDIRandBC1, a2BDIRonly) 

time.sleep(3)   

writePSG(7,  0xf8, sr, a1BDIRandBC1, a2BDIRonly)  ### Tone C,B,A enable, rest disable
writePSG(8,  0x00, sr, a1BDIRandBC1, a2BDIRonly)  ### A silent for now
writePSG(9,  0x00, sr, a1BDIRandBC1, a2BDIRonly)  ### B silent for now
writePSG(10,  0x00, sr, a1BDIRandBC1, a2BDIRonly) ### C silent for now

### Midi notes going beyond the A0-C8 (21-108) range
### 60 is C4 (middle C)
### 69 is A4 (440 Hz)
midinotes = [round(twomeg / (16 * (440 * math.pow(2,x / 12.0)))) for x in range(-69,59)]

bpm = 90
notegap = 0.05
barlength = 60 / bpm * 4

### 1977 tune for a 1978 chip
tune1 = [(69, 10, 0.25,   0),  ### tone,
         (71, 12, 0.25,   0),  ### up a full tone,
         (67, 10, 0.25,   0),  ### down a major third,
         (55, 11, 0.25,   0),  ### now drop an octave,
         (62, 10, 1.25, -12),  ### up a perfect fifth.
         ( 0,  0, 0.75,   0)   ### (rest, wait for arrival)
        ]

### Envelope generator uses a divide by 256 counter
EGenable = 0x10
### temp trebbling
EGtime = round(0.1 * (twomeg / 256))   ### 100ms rise time
### Continue, Alternate, Attack, Hold
EGmode = 0b1101   ### CAAH 
writePSG(11, EGtime & 0xff, sr, a1BDIRandBC1, a2BDIRonly)  ### EG timer low
writePSG(12, EGtime >> 8  , sr, a1BDIRandBC1, a2BDIRonly)  ### EG timer high
writePSG(13, EGmode, sr, a1BDIRandBC1, a2BDIRonly)

### Loop currently ignores overheard of code and bus writes with the musical timing
### Needs a bit of work to get it to the ARP 2500 standard
### B is slightly detuned from A - subtraction is crude/wrong but sounds ok
### C is being used for chords/unison and is a little quieter if not using EG
for i in range(4):
    for (noteidx, volume, length, subosc) in tune1:
        ### TODO review low/high order if volume != 0
        
        ### Trying this here to see if this is what triggers (starts) envelope
        if volume > 0:
            writePSG(13, EGmode, sr, a1BDIRandBC1, a2BDIRonly)
        
        writePSG(0, midinotes[noteidx] & 0xff, sr, a1BDIRandBC1, a2BDIRonly)
        writePSG(1, midinotes[noteidx] >> 8,   sr, a1BDIRandBC1, a2BDIRonly)
        writePSG(2, (midinotes[noteidx] - 1) & 0xff, sr, a1BDIRandBC1, a2BDIRonly)
        writePSG(3, (midinotes[noteidx] - 1) >> 8,   sr, a1BDIRandBC1, a2BDIRonly)
        if subosc != 0:
            writePSG(4, midinotes[noteidx + subosc] & 0xff, sr, a1BDIRandBC1, a2BDIRonly)
            writePSG(5, midinotes[noteidx + subosc] >> 8,   sr, a1BDIRandBC1, a2BDIRonly)
        ### volume appear to have no effect if EG is used - bit of a shame
        EGonoff = EGenable if volume > 0 else 0
        writePSG(8, volume | EGonoff, sr, a1BDIRandBC1, a2BDIRonly)
        writePSG(9, volume | EGonoff, sr, a1BDIRandBC1, a2BDIRonly)
        if subosc != 0:
            writePSG(10, round(volume/1.3) | EGonoff, sr, a1BDIRandBC1, a2BDIRonly)
        noteontime = length * barlength - notegap
        time.sleep(noteontime)
        writePSG(8, 0, sr, a1BDIRandBC1, a2BDIRonly)
        writePSG(9, 0, sr, a1BDIRandBC1, a2BDIRonly)
        if subosc != 0:
            writePSG(10, 0, sr, a1BDIRandBC1, a2BDIRonly)
        time.sleep(notegap)

### clear the sixteen registers
### registers 0 to 15, original data sheet calls these R0-R7 R10-R15 (no R8/R9, octal!)
for regidx in range(16):
    writePSG(regidx, 0, sr, a1BDIRandBC1, a2BDIRonly) 
