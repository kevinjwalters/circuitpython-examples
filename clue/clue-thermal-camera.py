### clue-thermal-camera v0.5
### Thermal camera display on CLUE
### This plots an 8833 8x8 thermal infrared sensor on the CLUE
### using ulab to interpolate the image
### the sensors and three of the analogue inputs on

### Tested with an Adafruit CLUE (Alpha) and CircuitPython and 5.1.0

### copy this file to CLUE board as code.py

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
import busio
import displayio
import array

import adafruit_amg88xx

### https://learn.adafruit.com/adafruit-amg8833-8x8-thermal-camera-sensor/python-circuitpython
### white  SDA
### yellow SCL

debug = 1

display = board.DISPLAY
i2c = busio.I2C(board.SCL, board.SDA)
amg = adafruit_amg88xx.AMG88XX(i2c)


def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


# Create a bitmap with two colors
bitmap = displayio.Bitmap(8, 8, 16)
 
# Create a two color palette
palette = displayio.Palette(16)
palette[0] = 0x000000
palette[1] = 0x202000
palette[2] = 0x404000
palette[3] = 0x585800
palette[4] = 0x686800
palette[5] = 0x707000
palette[6] = 0x787800
palette[7] = 0x808000
palette[8] = 0x907000
palette[9] = 0xa06000
palette[10] = 0xb85000
palette[11] = 0xc04000
palette[12] = 0xd03000
palette[13] = 0xe02000
palette[14] = 0xf01000
palette[15] = 0xff0000

# Create a TileGrid using the Bitmap and Palette
tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
 
# Scale 8 30x up to 240 pixels
group = displayio.Group(scale=30)
 
# Add the TileGrid to the Group
group.append(tile_grid)

# Add the Group to the Display
display.show(group)

display.auto_refresh = False

# 10 Hz
sample_time_ns = 1000 * 1000 / 10


# 36.1ms
lut1 = tuple(min(max(round(temp / 1.6) - 11, 0), 15) for temp in range(0, 80 + 1))

# fractionally slow - 36.3ms
lut2 = array.array('i', lut1)

### This updates at about 9Hz with 15 scale - 30 is very slow, maybe 3.2Hz
while True:
    start_ns = time.monotonic_ns()
    print(round((start_ns + 500000) // 1000000) / 1000.0, end=" ")
    idx = 0
    for row_idx, row in enumerate(amg.pixels):
       for col_idx, temp in enumerate(row):
           ## bitmap[idx] = min(max(round(temp / 1.6) - 11, 0), 15)
           bitmap[idx] = lut1[round(temp)]
           idx += 1
    bitmap_updated_ns = time.monotonic_ns()

    print("bitmap update", (bitmap_updated_ns - start_ns) / 1e9)
    
    ### This blocks until 2/25th second have passsed since
    ### last screen update
    while not display.refresh(target_frames_per_second=500, minimum_frames_per_second=0):
        pass

    # ensure for 1/10th to a second has passed to get a new reading from 8833
    while time.monotonic_ns() < start_ns + sample_time_ns:
        pass
