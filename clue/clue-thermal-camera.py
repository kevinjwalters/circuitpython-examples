### clue-thermal-camera v0.8
### Thermal camera display on CLUE or PyPortal

### This plots the output from two thermal infrared sensors (cameras)
### the AMG8833 8x8 and the MLX90640 32x24

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

### Originally tested with an Adafruit CLUE (Alpha) and CircuitPython
### and 5.3.0 and PyPortal and 5.3.1 for v0.6

### v0.7 tested on CircuitPython 7.3.3, v0.8 tested on CircuitPython 8.1.1, both PyPortal

### If PyPortal hangs at startup is likely to be due to 5V on 4 pin connector rather than 3.3V
### Very carefully cutting and soldering the 3.3V enable pad can fix this.


import time
import array

import board
import busio
import terminalio
import displayio

from micropython import const
from adafruit_display_text.label import Label

### https://learn.adafruit.com/adafruit-amg8833-8x8-thermal-camera-sensor/python-circuitpython
### white  SDA
### yellow SCL

MLX90640_I2C_ADDR = 0x33
AMG8833_I2C_ADDR = 0x69  ### can also be 0x68

quiet = True
debug = 1

display = board.DISPLAY
DISPLAY_WIDTH = display.width
DISPLAY_HEIGHT = display.height

### Keep searching for a thermal sensor
time.sleep(3)
i2c = busio.I2C(board.SCL, board.SDA)
found = False
while True:
    while i2c.try_lock():
        pass
    device_addrs = i2c.scan()
    i2c.unlock()
    for addr in (MLX90640_I2C_ADDR, AMG8833_I2C_ADDR):
        if addr in device_addrs:
            found = True
    if found:
        break
    print("Still waiting for thermal sensor")
    time.sleep(3)


class ThermalSensorMLX():

    def __init__(self, i2c_):
        self.width = 32
        self.height = 24
        self.min_temp_c = -150
        self.max_temp_c = 150
        self._frame_data = [0] * (self.width * self.height)
        self._mlx = adafruit_mlx90640.MLX90640(i2c_)
        self._mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_4_HZ
        self._exception_count = 0

    def getFrame(self):
        no_data = True
        ### Retries only here to work around library issue
        for attempt in range(3):
            try:
                ### This is buggy and can throw math domain error exceptions in sqrt
                ### https://github.com/adafruit/Adafruit_CircuitPython_MLX90640/issues/34
                self._mlx.getFrame(self._frame_data)
                no_data = False
                break
            except ValueError:
                self._exception_count += 1
                time.sleep(0.2)   ### Pause for prayer

        if no_data:
            raise ValueError("Too many ValueError from MLX90640 library")

        for offset in range(self.width - 1, -1, -1):
            yield self.oneSomething(offset)


    def oneSomething(self, offset):
        for d_idx in range(len(self._frame_data) + offset - self.width,
                             -1,
                             0 - self.width):
            yield self._frame_data[d_idx]


class ThermalSensorAMG():

    def __init__(self, i2c_):
        self.width = 8
        self.height = 8
        self.min_temp_c = -150
        self.max_temp_c = 150
        self._ir_data = [[]]
        self._amg = adafruit_amg88xx.AMG88XX(i2c_)


    def getFrame(self):
        self._ir_data = self._amg.pixels
        return self._ir_data


if MLX90640_I2C_ADDR in device_addrs:
    import adafruit_mlx90640
    i2c.deinit()
    i2c = busio.I2C(board.SCL, board.SDA, frequency=400*1000)
    sensor = ThermalSensorMLX(i2c)
    target_rate = 2
else:
    import adafruit_amg88xx
    sensor = ThermalSensorAMG(i2c)
    target_rate = 10


def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


def manual_screen_refresh(disp):
    """Refresh the screen immediately.
       This is trivial in CircuitPython 7 compared to odd-looking workaround used for 5."""
    return disp.refresh()


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
PALETTE_SIZE = const(256)
PALETTE_THIRD = const(85)
MAX_PALETTE = const(255)
bitmap = displayio.Bitmap(sensor.width, sensor.height, PALETTE_SIZE)
if not quiet:
    print("BWH", bitmap.width, bitmap.height)

# Create a 256 color palette
palette = displayio.Palette(PALETTE_SIZE)

### Last used in cpx/cpx-flameandsound.py
def hsvToRgb(h, s, v):
    if s == 0:
        return (v, v, v)

    i = int(h / 42.5)
    r = int((h - (i * 42.5)) * 6)

    p = (v * (255 - s)) >> 8
    q = (v * (255 - ((s * r) >> 8))) >> 8
    t = (v * (255 - ((s * (255 - r)) >> 8))) >> 8

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


for idx in range(PALETTE_SIZE):
    ### Want to start at 240 degrees blue (170)
    ### through to red 360 (255) then
    ### And the around to 60 degress yellow (45)
    hh = round(170 + min(idx / 1.7, 130)) % 256
    norm_idx = idx / MAX_PALETTE
    if norm_idx < 0.875:
        ss = 255 - round(norm_idx**2)
    else:
        ss = round((1 - norm_idx) * MAX_PALETTE * 8)

    vv = round(norm_idx**0.75 * 255)
    palette[idx] = hsvToRgb(hh, ss, vv)


### Create a TileGrid using the Bitmap and Palette
tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)

### Need 32 pixels for text on the left
### Calculate the scale up value
plot_width = DISPLAY_WIDTH - 32
plot_height = DISPLAY_HEIGHT
size_x = plot_width / sensor.width
size_y = plot_height / sensor.height
scale = int(min(size_x, size_y))


### TODO
scale = scale - 2

b_group = displayio.Group(scale=scale)
b_group.x = DISPLAY_WIDTH - sensor.width * scale
b_group.y = round((DISPLAY_HEIGHT - sensor.height * scale) / 2)
# Add the TileGrid to the Group
b_group.append(tile_grid)

### For 256 palette 15 to 79 Celsius
TEMP_OFFSET = const(-15)
TEMP_COEFF = const(4)

BLACK = 0x000000
WHITE = 0xffffff

sc_group = displayio.Group()
font_scale = 2

### Bit of a hack for PyPortals with plastic face on obscuring 0
x_pos = 10 if DISPLAY_WIDTH > DISPLAY_HEIGHT else 0

max_dob = Label(terminalio.FONT,
                text="___.__",  ### TODO HACK!
                scale=font_scale,
                background_color=BLACK,
                color=BLACK)
max_dob.x = x_pos
max_dob.y = round(DISPLAY_HEIGHT * 1/3)
min_dob = Label(terminalio.FONT,
                text="___.__",
                scale=font_scale,
                background_color=BLACK,
                color=BLACK)
min_dob.x = x_pos
min_dob.y = round(DISPLAY_HEIGHT * 2/3)
sc_group.append(max_dob)
sc_group.append(min_dob)


def setDisplayedScale(min_t, max_t):
    col_min = min(max(round((min_t + TEMP_OFFSET) * TEMP_COEFF), 0), MAX_PALETTE)
    col_max = min(max(round((max_t + TEMP_OFFSET) * TEMP_COEFF), 0), MAX_PALETTE)

    min_dob.background_color = palette[col_min]
    min_dob.color = WHITE if col_min < PALETTE_THIRD else BLACK
    max_dob.background_color = palette[col_max]
    max_dob.color = WHITE if col_max < PALETTE_THIRD else BLACK
    ### TODO - needs more protection to stay within range
    min_dob.text = "{:.1f}".format(min_t)
    max_dob.text = "{:.1f}".format(max_t)


main_group = displayio.Group()
main_group.append(b_group)
main_group.append(sc_group)

# Add the Group to the Display
##display.show(main_group)
display.root_group = main_group

display.auto_refresh = False

sample_time_ns = int(1000 * 1000 * 1000 / target_rate)

### 36.1ms
lut1 = tuple(min(max(round((temp + TEMP_OFFSET) * TEMP_COEFF), 0), MAX_PALETTE) for temp in range(0, 200 + 1))

### fractionally slow - 36.3ms
lut2 = array.array('i', lut1)


out_of_range = 0
width_m1 = sensor.width - 1
frame = 1

### AMG8833 This updates at about 9Hz with 15 scale - 30 is very slow, maybe 3.2Hz
while True:
    start_ns = time.monotonic_ns()
    if not quiet:
        print(round((start_ns + 500000) // 1000000) / 1000.0, end=" ")

    try:
        ir_data = sensor.getFrame()
    except OSError as oe:
        print("Exception:", repr(oe))
        continue

    min_temp = float("Inf")
    max_temp = float("-Inf")


    for col_idx, col in enumerate(ir_data):
        for row_idx, temp in enumerate(col):
            min_temp = min(min_temp, temp)
            max_temp = max(max_temp, temp)
            bitmap[width_m1 - col_idx, row_idx] = min(max(round((temp + TEMP_OFFSET) * TEMP_COEFF), 0), MAX_PALETTE)
            #bitmap[width_m1 - col_idx, row_idx] = lut1[round(temp)]
    bitmap_updated_ns = time.monotonic_ns()

    if min_temp < sensor.min_temp_c or max_temp > sensor.max_temp_c:
        out_of_range += 1
    else:
        if frame % 5 == 1:
            setDisplayedScale(min_temp, max_temp)

##    if out_of_range >= 2:
##        ### This does not help the problem I see with circa -500 values
##        ### Power cycle of the sensor seems to be needed :(
##        print("Making new amg", min_temp, max_temp)
##        try:
##            amg = adafruit_amg88xx.AMG88XX(i2c)
##            out_of_range = 0
##        except ex:
##            print("Exception recreating amg object:", repr(ex))

    if not quiet:
        print("bitmap update", (bitmap_updated_ns - start_ns) / 1e9)
    manual_screen_refresh(display)

    # ensure for 1/10th to a second has passed to get a new reading from 8833
    while time.monotonic_ns() < start_ns + sample_time_ns:
        pass

    frame += 1
