### dotstar-racer v1.0
### CircuitPython (on Gemma M0) example for Dotstar RGB LEDs
### This makes a growing group of pixels move along the strip.

### The code breaks the object encapsulation in its quest for
### performance over good OO practice

### Tested with Gemma M0 and CircuitPython 2.2.0

### copy this file to Gemma M0 as main.py

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

### For very simple example see
### https://learn.adafruit.com/adafruit-gemma-m0/circuitpython-dotstar

### A few performance tweaks as original code isn't great on
### long (144) led chains
     
import board
import digitalio
import adafruit_dotstar
import time
     
### 1m strip of 144 per m = 144
### 5m strip of  60 per m = 300
### 5m strip of  30 per m = 150
numpix = 144

### first arg - C or D?
### second arg - C or D?
### image shows output 2 to CI (2nd one down) and output 0 to DI (3rd one down)
### warning cable colours may be confusing on APA102 strips
### (D2,D0) according to online docs gives hardware SPI (i.e. efficient)
### https://circuitpython.readthedocs.io/projects/dotstar/en/latest/api.html
oclock=board.D2
odata=board.D0
##bright=0.2
bright=1.0
strip = adafruit_dotstar.DotStar(oclock, odata, numpix, bright, False)
##strip = adafruit_dotstar.DotStar(oclock, odata, numpix, bright)

boardled = digitalio.DigitalInOut(board.D13)
boardled.direction = digitalio.Direction.OUTPUT

black=(0,0,0)
red=(255,0,0)
green=(0,255,0)
blue=(0,0,255)
magenta=(255,0,255)
cyan=(0,255,255)
yellow=(255,255,0)

def wheel(pos):
    # Input a value 0 to 255 to get a color value.
    # The colours are a transition r - g - b - back to r.
    if (pos < 0) or (pos > 255):
        return (0, 0, 0)
    tripos = int(pos*3)
##    tripos = pos*3
    if (pos < 85):
        return (tripos, 255 - tripos, 0)
    elif (pos < 170):
        tripos -= 255
        return (255 - tripos, 0, tripos)
    else:
        tripos -= 510
        return (0, tripos, 255 - tripos)

### This appears very slow for 144 leds
### 18.6s on Gemma M0 with auto_write=True
### 0.40s with auto_write=False
### 0.35s with reduced calculations and less fp
### wait is problematic because for a few ms
### the loop before sleep takes most of the time
### with large strip
### added steps to make this invariant with len(strip)
def rainbow_cycle(wait, steps=20):
    scale = 256 / len(strip)
    adjsteps = int(steps / len(strip) * 144)
    steplist = [int(x * (255.0/adjsteps) + 0.5) for x in range(adjsteps)]
    for j in steplist:
        t1 = time.monotonic()
        bufidx = strip.start_header_size + 1
        for i in range(len(strip)):
            idx = int(i * scale) + j
            (r,g,b) = wheel(idx & 255)
            ### breaking encapsulation to test performance
            strip.buf[bufidx] = b
            bufidx += 1
            strip.buf[bufidx] = g
            bufidx += 1
            strip.buf[bufidx] = r
            bufidx += 2
        t2 = time.monotonic()
        strip.show()
        t3 = time.monotonic()
        ### 122 ms breaking encapsulation, otherwise 230ms, ~400ms with pointless auto show
        print('rainbow change start {:f}, for assign {:f}, show {:f}'.format(t1,t2-t1,t3-t2))
        time.sleep(wait)

### race a group of pixels along the strip
### this version uses normal array assignment to strip
def race(bg,fg,width):
    length = len(strip)
    cwidth = min(length,width)
    cwidthplusone = cwidth+1

    for i in range(length+cwidth):
        pos=i
        for w in range(cwidthplusone):
            pos=i-w
            if pos >= 0 and pos < length:
                if w == cwidth:
                    strip[pos] = bg
                else:
                    strip[pos] = fg
        strip.show()

### race a group of pixels along the strip
### this version breaks the encapsulation of the strip
### object and assigns directly to the underlying buffer
### for better performance
def racefast(bg,fg,width):
    length = len(strip)
    cwidth = min(length,width)
    cwidthplusone = cwidth+1

    for i in range(length+cwidth):
        pos=i
        for w in range(cwidthplusone):
            pos=i-w
            if pos >= 0 and pos < length:
                ### calculate position of bgr triplet
                bufidx = (pos << 2) + strip.start_header_size + 1
                if w == cwidth:
                    (r,g,b) = bg
                else:
                    (r,g,b) = fg
                ### breaking object encapsulation
                ### print('bufidx {:d}'.format(bufidx))
                strip.buf[bufidx] = b
                strip.buf[bufidx+1] = g
                strip.buf[bufidx+2] = r

        strip.show()
        
strip.fill(black)
strip.show()
time.sleep(1)

strip.fill(red)
strip.show()
time.sleep(1)
   
strip.fill(green)
strip.show()
time.sleep(1)
     
strip.fill(blue)
strip.show()
time.sleep(1)

### TODO - remove the cut and paste coding going on here!
while True:
    boardled.value = not boardled.value
    for width in range(1,13):
        ##print('race width {:f} begin at {:f}'.format(width,time.monotonic()))
        race(black,red,width)
        ##print('race width {:f} end at {:f}'.format(width,time.monotonic()))

    for width in range(1,13):
        ##print('race width {:f} begin at {:f}'.format(width,time.monotonic()))
        race(black,green,width)
        ##print('race width {:f} end at {:f}'.format(width,time.monotonic()))

    for width in range(1,13):
        ##print('race width {:f} begin at {:f}'.format(width,time.monotonic()))
        race(black,blue,width)
        ##print('race width {:f} end at {:f}'.format(width,time.monotonic()))

    for width in range(1,13):
        ##print('race width {:f} begin at {:f}'.format(width,time.monotonic()))
        racefast(black,magenta,width)
        ##print('race width {:f} end at {:f}'.format(width,time.monotonic()))

    for width in range(1,13):
        ##print('race width {:f} begin at {:f}'.format(width,time.monotonic()))
        racefast(black,cyan,width)
        ##print('race width {:f} end at {:f}'.format(width,time.monotonic()))

    for width in range(1,13):
        ##print('race width {:f} begin at {:f}'.format(width,time.monotonic()))
        racefast(black,yellow,width)
        ##print('race width {:f} end at {:f}'.format(width,time.monotonic()))  
       
