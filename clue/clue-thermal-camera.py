### clue-thermal-camera v0.6
### Thermal camera display on CLUE or PyPortal
### This plots an 8833 8x8 thermal infrared sensor on the CLUE
### using ulab to interpolate the image

### Tested with an Adafruit CLUE (Alpha) and CircuitPython and 5.3.0
### and PyPortal and 5.3.1

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
import terminalio
import displayio
import array

from adafruit_display_text.label import Label
import adafruit_amg88xx

### https://learn.adafruit.com/adafruit-amg8833-8x8-thermal-camera-sensor/python-circuitpython
### white  SDA
### yellow SCL

debug = 1

display = board.DISPLAY
DISPLAY_WIDTH = display.width
DISPLAY_HEIGHT = display.height

i2c = busio.I2C(board.SCL, board.SDA)
amg = adafruit_amg88xx.AMG88XX(i2c)


def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


def manual_screen_refresh(disp):
    """Refresh the screen as immediately as is currently possibly with refresh method."""
    refreshed = False
    while True:
        try:
            ### 1000fps is fastest library allows - this high value
            ### minimises any delays this refresh() method introduces
            refreshed = disp.refresh(minimum_frames_per_second=0,
                                     target_frames_per_second=1000)
        except RuntimeError:
            pass
        if refreshed:
            break


# # Create a bitmap with 16 colors
# bitmap = displayio.Bitmap(8, 8, 16)
 
# # Create a 16 color palette
# palette = displayio.Palette(16)
# palette[0] = 0x000000
# palette[1] = 0x202000
# palette[2] = 0x404000
# palette[3] = 0x585800
# palette[4] = 0x686800
# palette[5] = 0x707000
# palette[6] = 0x787800
# palette[7] = 0x808000
# palette[8] = 0x907000
# palette[9] = 0xa06000
# palette[10] = 0xb85000
# palette[11] = 0xc04000
# palette[12] = 0xd03000
# palette[13] = 0xe02000
# palette[14] = 0xf01000
# palette[15] = 0xff0000

# Create a bitmap with 256 colors
bitmap = displayio.Bitmap(8, 8, 256)

# Create a 256 color palette
palette = displayio.Palette(256)

### Last used in cpx/cpx-flameandsound.py
def hsvToRgb(h, s, v):
    if s == 0:
        return (v, v, v)

    i = int(h / 42.5);
    r = int((h - (i * 42.5)) * 6);

    p = (v * (255 - s)) >> 8;
    q = (v * (255 - ((s * r) >> 8))) >> 8;
    t = (v * (255 - ((s * (255 - r)) >> 8))) >> 8;

    i = i % 6
    if i == 0:
        return v, t, p
    if i == 1:
        return q, v, p
    if i == 2:
        return p, v, t
    if i == 3:
        return p, q, v
    if i == 4:
        return t, p, v
    if i == 5:
        return v, p, q


# for idx in range(256):
    # r = idx
    # g = round((idx / 255.0)**2 * 255)
    # b = round((idx / 255.0)**3 * 255)
    # palette[idx] = (r, g, b)

for idx in range(256):
    ### Want to start at 240 degrees blue (170)
    ### through to red 360 (255) then 
    ### And the around to 60 degress yellow (45)
    hh = round(170 + min(idx / 1.7, 130)) % 255
    if idx < 224:
        ss = 255 - round((idx/255)**2)
    else:
        ss = (255 - idx) * 8
    
    vv = round((idx/255) * 255)
    palette[idx] = hsvToRgb(hh, ss, vv)


# Create a TileGrid using the Bitmap and Palette
tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
 
# Scale 8 pixels 26x up to 208 pixels
scale = 26
b_group = displayio.Group(max_size=1, scale=scale)
b_group.x = DISPLAY_WIDTH - 8 * scale
b_group.y = round((DISPLAY_HEIGHT - 8 * scale) / 2)
# Add the TileGrid to the Group
b_group.append(tile_grid)


BLACK=0x000000
WHITE=0xffffff

sc_group = displayio.Group(max_size=2)
font_scale = 2

max_dob = Label(terminalio.FONT,
                text="    " "    ",  ### TODO HACK!
                scale=font_scale,
                background_color=BLACK,
                color=BLACK)
max_dob.y = round(DISPLAY_HEIGHT * 1/3)
min_dob = Label(terminalio.FONT,
                text="    " "    ",
                scale=font_scale,
                background_color=BLACK,
                color=BLACK)
min_dob.y = round(DISPLAY_HEIGHT * 2/3)
sc_group.append(max_dob)
sc_group.append(min_dob)


def setScale(min_t, max_t):
    col_min = min(max(round((min_t - 15.0) * 10), 0), 255)
    col_max = min(max(round((max_t - 15.0) * 10), 0), 255)

    min_dob.background_color = palette[col_min]
    min_dob.color = WHITE if col_min < 64 else BLACK
    max_dob.background_color = palette[col_max]
    max_dob.color = WHITE if col_max < 64 else BLACK
    ### TODO - needs more protection to stay within range
    min_dob.text = "{:.1f}".format(min_t)
    max_dob.text = "{:.1f}".format(max_t)


main_group = displayio.Group(max_size=2)
main_group.append(b_group)
main_group.append(sc_group)

# Add the Group to the Display
display.show(main_group)

display.auto_refresh = False

# 10 Hz
sample_time_ns = 1000 * 1000 * 1000 / 10


# 36.1ms
lut1 = tuple(min(max(round(temp / 1.6) - 11, 0), 15) for temp in range(0, 80 + 1))

# fractionally slow - 36.3ms
lut2 = array.array('i', lut1)


out_of_range = 0

### This updates at about 9Hz with 15 scale - 30 is very slow, maybe 3.2Hz
while True:
    start_ns = time.monotonic_ns()
    print(round((start_ns + 500000) // 1000000) / 1000.0, end=" ")
    
    try:
        ir_data = amg.pixels
    except OSError as oe:
        print("Exception:",repr(oe))
        continue
        
    min_temp = float("Inf")
    max_temp = float("-Inf")
    ## idx = 0
    for row_idx, row in enumerate(ir_data):
       for col_idx, temp in enumerate(row):
           ## bitmap[idx] = min(max(round(temp / 1.6) - 11, 0), 15)
           min_temp = min(min_temp, temp)
           max_temp = max(max_temp, temp)
           ## bitmap[idx] = lut1[round(temp)]
           bitmap[row_idx, col_idx] = min(max(round((temp - 15.0) * 10), 0), 255)
           ## idx += 1
    bitmap_updated_ns = time.monotonic_ns()

    if min_temp < -150 or max_temp > 150:
        out_of_range += 1
    else:
        setScale(min_temp, max_temp)

    if out_of_range >= 2:
        ### This does not help the problem I see with circa -500 values
        ### Power cycle of the sensor seems to be needed :(
        print("Making new amg", min_temp, max_temp)
        try:
            amg = adafruit_amg88xx.AMG88XX(i2c)
            out_of_range = 0
        except ex:
            print("Exception recreating amg object:", repr(ex))

    print("bitmap update", (bitmap_updated_ns - start_ns) / 1e9)
    manual_screen_refresh(display)

    # ensure for 1/10th to a second has passed to get a new reading from 8833
    while time.monotonic_ns() < start_ns + sample_time_ns:
        pass
