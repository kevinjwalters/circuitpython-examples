### dotstar-twinkle v1.0
### CircuitPython (on Gemma M0) example for Dotstar RGB LEDs
### This animates randomly placed twinkling "stars".

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

import board
import digitalio
import adafruit_dotstar
import time
import random
     
### 1m strip of 144 per m = 144
### 5m strip of  60 per m = 300
### 5m strip of  30 per m = 150
numpix = 144

### Warning: cable colours may be confusing on APA102 strips, e.g.
###          red and black are not always +5v and ground

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

black   = (0,0,0)
red     = (255,0,0)
green   = (0,0xff,0)
blue    = (0,0,0b11111111)
magenta = (255,0,255)
cyan =    (0,255,255)
yellow =  (255,255,0)

### Do red, green, blue then leave on black
def striptest(strip):
    for col in [red,green,blue,black]:
        strip.fill(col)
        strip.show()
        time.sleep(1)


### test at each end of strip
def twinkletest(strip):
    for pos in [3,2,1,0,numpix-4,numpix-3,numpix-2,numpix-1]:
        twinkle(strip, yellow, pos, 5, 1.0)


### clips any values
### expects values to be length of width currently
### UNTIL adafruit_dotstar is fixed use arrayassign
def safeassign(array, index, width, values):
    length = len(array)
    
    ### check off left side of list
    if index < 0:
        newwidth = width + index  ### shorten width
        if (newwidth <= 0):
            return  ### completely off
        ### trim left on values[]
        newwidth = min(newwidth,length)
        #array[0:width] = values[-index:-index+width]
        arrayassign(array, 0, newwidth, values[-index:-index+newwidth])

    ### check completely off right side of list
    elif index >= length:
        return

    ### partially off right side
    elif (index + width > length):
        newwidth = length - index
        #array[index:length] = values[0:newwidth]
        arrayassign(array, index, length, values[0:newwidth])
    else:
        #array[index:index+width] = values
        arrayassign(array, index, index+width, values)


### temporary workaround for bug in adafruit_dotstar        
def arrayassign(l, start, finish, r):
    ##print('assign start={:d} finish={:d} lenl={:d} lenr={:d}'.format(start, finish, len(l), len(r)))
    ri=0
    for li in range(start, finish):
        l[li] = r[ri]
        ri += 1


def twinkle(strip, colour, position, width, duration, iteration=0):
    ##print('twinkle p={:d} w={:d} d={:f}'.format(position, width, duration))

    mididx = width // 2
    leftidx = position - mididx
    frames = 16   ### -7 to 7 plus final black

    ### If length of an iteration (frame) is not specified
    ### measure it by setting black
    if iteration == 0:
        t1 = time.monotonic()
        safeassign(strip, leftidx, width, [black] * width)
        strip.show()
        iteration = time.monotonic() - t1
        frames += 1

    ### Calculate the time per frame and if this is higher
    ### than the time to write data and show the pixels
    ### the calculate the time to pause
    timeperframe = duration / frames
    if (timeperframe > (iteration + 0.001)):
        sleeptime = timeperframe - (iteration + 0.001)
    else:
        sleeptime = 0

    ### Create the varying brightness sparkle as array of arrays
    colours = []
    for colidx in range(width):
        col = [i >> abs(mididx - colidx) * 2 for i in colour]
        colours.append(col)

    for shiftvalue in list(range(7,0,-1))+list(range(0,8)):
        t1 = time.monotonic()
        ##print('twinkling sv={:d} s={:f} at {:f}'.format(shiftvalue, sleeptime, time.monotonic()))
        ### safeassign takes array of colours in tuple representation
        safeassign(strip, leftidx, width, [tuple(map(lambda x: x >> shiftvalue,col)) for col in colours])
        strip.show()
        if sleeptime != 0:
            time.sleep(sleeptime)

    ### Back to black
    safeassign(strip, leftidx, width, [black] * width)
    strip.show()


### frame 1 is black but is usually skipped, last frame is black
class star:
    brightnessshift = list(range(7,0,-1))+list(range(0,8))

    ### startframe of 2 skips black frame 1
    def __init__(self, colour, width, frames = 17, startframe=2):
        self.colours = []  ### array of rgb array
        mididx = width // 2
        for colidx in range(width):
            col = [i >> abs(mididx - colidx) * 2 for i in colour]
            self.colours.append(col)
        self.width = width
        self.frames = frames
        self.framenum = startframe

    ### Returns whether the star still burns
    def render(self, strip, leftidx):
        ##print('twinkling li={:d} fr={:d} at {:f}'.format(leftidx, self.framenum, time.monotonic()))
        ### safeassign takes array of colours in tuple representation
        atlastframe = self.framenum >= self.frames
        if self.framenum == 1 or atlastframe:
            coloursthisframe = [black] * self.width
        else:
            ### following statement appears to be running out of memory
            coloursthisframe = [tuple(map(lambda x: x >> self.brightnessshift[self.framenum - 2],col)) for col in self.colours]
        safeassign(strip, leftidx, self.width, coloursthisframe)

        if not atlastframe:
            self.framenum += 1
        return not atlastframe


class stars:
    def __init__(self, strip):
        self.strip = strip
        self.stars = []
        self.framenum = 1
        self.count = 0

    def add(self, star, midposition, width):
        ### TODO - add code to check for overlaps
        ### and crop to be in bound
        leftidx = midposition - (width // 2)
        starandpos = (star, leftidx)
        self.stars.append(starandpos)
        self.count += 1

    ### write values to LED array
    ### returns array indices of any stars which needs to be removed
    ### in ascending order
    def render(self):
        burntout = []
        for i in range(len(self.stars)):
            (s,li) = self.stars[i]
            burns = s.render(self.strip, li)
            if (not burns):
                burntout.append(i)
        return burntout
        ##list(map(lambda x:x.render(self.strip),stars))   ### this needs to implement burnout

    ### takes a list of indixes to remove in ascending order
    ### and deletes them
    def prune(self, delidxs):
        for i in sorted(delidxs, reverse=True):
            del self.stars[i]
            self.count -= 1


striptest(strip)
##twinkletest(strip)

stars = stars(strip)

frametime = 1 / 10

### Twinkle multiple stars
while True:
    boardled.value = not boardled.value

    ### Add a star randomly
    rnd = random.random()
    if rnd < 0.2:
        midposition = random.randrange(numpix)
        width = random.randrange(3,11,2)  ### odd between 3 and 9
        colour = [128,128,128]
        colour[random.randrange(3)] = 255
        ### TODO - work out how to do variable duration
        astar = star(colour, width)
        ### TODO - check for overlap??
        ##print('adding star width={:d} midposition={:d}'.format(width, midposition))
        stars.add(astar, midposition, width)

    ### render all stars - assigns all values to strip
    burntout = stars.render()

    ### send to the dotstar LED strip
    strip.show()

    ### remove any burnt out stars
    if len(burntout) > 0:
        stars.prune(burntout)

    ### pause as required
    ### TODO - calculate this dynamically
    time.sleep(0.050)
