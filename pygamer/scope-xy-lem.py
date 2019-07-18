### scope-xy-lem v0.9
### Output simple vector image of a Lunar Excursion Module to oscilloscope
### Needs X-Y mode and an Adafruit M4 board like Feather M4
### or PyGamer (best to disconnect headphones)

### copy this file to PyGamer (or other M4 board) as code.py

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
import array

import board
import busio
import audioio
import analogio

### TODO - split up parts of image to tell addpoints not to put in
###        extra points - could just use (None, None) or perhaps a
###        better data structure to give more flexibility later??

### TODO - some animation - could use controls on the PyGamer

### TODO - detect and dim screen

### PyGamer voltage limit to around 2.5V
### https://forums.adafruit.com/viewtopic.php?f=24&t=153703

### SAMD51 (M4) boards are steppy on the up
### https://forums.adafruit.com/viewtopic.php?f=24&t=153707

### centered
### 22 high
### 32 width
### TODO - add thruster cone
###      - more detail on legs

### centered
### 22 high
### 32 width
### TODO - add thruster cone
###      - more detail on legs
lem = [[(-8, -2), (-9, -3), (-9, -9), (-7, -11), (7, -11), (9, -9), (9, -3), (8, -2)],  ### top
       [(-10, 6), (-10, -1), (10, -1), (10, 6), (-9, 6), ],  ### bottom
       [(-10, 2),  (-15, 10)],  ### left leg
       [(-14, 11), (-16, 11)],  ### left pad
       [ (10, 2),  (15, 10)],   ### right leg
       [ (14, 11), (16, 11)],   ### right pad
      ]


### add extra points to any lines if length is greater than min_dist
def addpoints(points, min_dist):
    newpoints = []
    original_len = len(points)
    for idx in range(original_len):
        x1, y1 = points[idx]
        x2, y2 = points[(idx + 1) % original_len]

        ### Always keep the original point
        newpoints.append((x1, y1))

        diff_x = x2 - x1
        diff_y = y2 - y1
        dist = math.sqrt(diff_x ** 2 + diff_y ** 2)
        if dist > min_dist:
            ### Calculate extra intermediate points plus one
            extrasp1 = int(dist // min_dist) + 1
            for extra_idx in range(1, extrasp1):
                ratio = extra_idx / extrasp1
                newpoints.append((x1 + diff_x * ratio,
                                  y1 + diff_y * ratio))
        ### Two points define a straight line
        ### so no need to connect final point back to first
        if original_len == 2:
            break

    return newpoints

data = lem

### get the range of logo points
### extra points from linear interpolation will not change this
min_x, min_y = max_x, max_y = data[0][0]
for part in data:
    for point in part:
       min_x = min(min_x, point[0])
       max_x = max(max_x, point[0])
       min_y = min(min_y, point[1])
       max_y = max(max_y, point[1])

### PyPortal DACs seem to stop around 53000 and there's 2 100 ohm resistors
### on output
### 32768 and 32000 exhibit this bug but 25000 so far appears to be a
### workaround, albeit a mysterious one
### https://github.com/adafruit/circuitpython/issues/1992
dac_x_min = 0
dac_y_min = 0
dac_x_max = 25000
dac_y_max = 25000
dac_x_mid = dac_x_max // 2
dac_y_mid = dac_y_max // 2

### Convert the points into format suitable for audio library
### and scale to the DAC range used by the library
### INTENTIONALLY using "h" here as libraries will make a copy of
### rawdata which is useful to allow animating code to modify rawdata
### without affecting output

range_x = max_x - min_x
range_y = max_y - min_y
halfrange_x = range_x / 2
halfrange_y = range_y / 2
mid_x = halfrange_x + min_x
mid_y = halfrange_y + min_y

use_wav = True
rubbish_wav_bug_workaround = False
leave_wav_looping = True

### A0 will be x, A1 will be y
if use_wav:
    print("Using audioio.RawSample for DACs")
    dacs = audioio.AudioOut(board.A0, right_channel=board.A1)
else:
    print("Using analogio.AnalogOut for DACs")
    a0 = analogio.AnalogOut(board.A0)
    a1 = analogio.AnalogOut(board.A1)

### Demonstration of different intermediate point spacing on vectors
intermediates = [100, 10, 7, 5, 4, 3, 2, 1.5, 1, 0.5, 0.25]

### 0.8 gives a border and allows for data to be slightly off centre
mult_x = dac_x_max / max(range_x, range_y) * 0.8
mult_y = dac_x_max / max(range_x, range_y) * 0.8

### 10Hz is ok for AudioOut, optimistic for AnalogOut
frame_t = 1/1
prev_t = time.monotonic()
frame = 1
while True:
    ### Add intermediate points to make line segments for each part
    ### look like continuous lines on x-y oscilloscope output
    spacing = intermediates[(frame - 1) % len(intermediates)]
    display_data = []
    for part in data:
        display_data.extend(addpoints(part, spacing))

    rawdata = array.array("h", (2 * len(display_data)) * [0])
    idx = 0
    for px, py in display_data:
        rawdata[idx] = round(px * mult_x)
        rawdata[idx + 1] = 0 - round(py * mult_y)
        idx += 2

    if use_wav:
        ### 200k (maybe 166.667k) seems to be practical limit
        ### 1M permissible but seems same as around 200k
        output_wave = audioio.RawSample(rawdata,
                                        channel_count=2,
                                        sample_rate=50 * 1000)

        ### The image may "warp" sometimes with loop=True due to a strange bug
        ### https://github.com/adafruit/circuitpython/issues/1992
        if rubbish_wav_bug_workaround:
            while True:
                dacs.play(output_wave)
                if time.monotonic() - prev_t >= frame_t:
                    break
        else:
            dacs.play(output_wave, loop=True)
            while time.monotonic() - prev_t < frame_t:
                pass
            if not leave_wav_looping:
                dacs.stop()
    else:
        while True:
            ### This gives a very flickery image with 4932 points
            ### slight flicker at 2552
            ### might be ok for 1000
            for idx in range(0, len(rawdata), 2):
                a0.value = rawdata[idx]
                a1.value = rawdata[idx + 1]
            if time.monotonic() - prev_t >= frame_t:
                break
    prev_t = time.monotonic()
    #angle += math.pi / 180 * 3 ### 72 degrees per frame
    frame += 1
