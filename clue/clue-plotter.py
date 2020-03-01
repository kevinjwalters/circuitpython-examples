### clue-plotter v0.6
### CircuitPython on CLUE sensor and input plotter
### This plots the sensors and analogue inputs in a style similar to
### an oscilloscope

### Tested with an Adafruit CLUE Alpha and CircuitPython and 5.0.0-beta.5

### ANY CRITICAL NOTES ON LIBRARIES GO HERE

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
import array
import random
import math

import board
import displayio
import terminalio
import analogio

# There's a form of on-demand instanitation for touch pads
# but analogio can be used if touch_0 - touch_3 have not been used
from adafruit_clue import clue
from adafruit_display_text import label

# remember this was a p3.reference_voltage which is 3.3
# p3 = analogio.AnalogIn(board.P3)

# On main screen
# Temp
# Baro
# Humid
# Light
# Accel (ms-2)
# Gyro (??)
# Mag ?
# Mic ? (maybe 0-255)


### from https://github.com/adafruit/Adafruit_CircuitPython_CLUE
# from adafruit_clue import clue

# clue.sea_level_pressure = 1020

# clue_data = clue.display_clue_data(title="CLUE Sensor Data!", title_scale=2, num_lines=15)

# while True:
    # clue_data[0].text = "Acceleration: {:.2f} {:.2f} {:.2f}".format(*clue.acceleration)
    # clue_data[1].text = "Gyro: {:.2f} {:.2f} {:.2f}".format(*clue.gyro)
    # clue_data[2].text = "Magnetic: {:.3f} {:.3f} {:.3f}".format(*clue.magnetic)
    # clue_data[3].text = "Pressure: {:.3f}hPa".format(clue.pressure)
    # clue_data[4].text = "Altitude: {:.1f}m".format(clue.altitude)
    # clue_data[5].text = "Temperature: {:.1f}C".format(clue.temperature)
    # clue_data[6].text = "Humidity: {:.1f}%".format(clue.humidity)
    # clue_data[7].text = "Proximity: {}".format(clue.proximity)
    # clue_data[8].text = "Gesture: {}".format(clue.gesture)
    # clue_data[9].text = "Color: R: {} G: {} B: {} C: {}".format(*clue.color)
    # clue_data[10].text = "Button A: {}".format(clue.button_a)
    # clue_data[11].text = "Button B: {}".format(clue.button_b)
    # clue_data[12].text = "Touch 0: {}".format(clue.touch_0)
    # clue_data[13].text = "Touch 1: {}".format(clue.touch_1)
    # clue_data[14].text = "Touch 2: {}".format(clue.touch_2)
    # clue_data.show()


### if clue.touch_3 has not been used then it doesn't instantiate
### the TouchIn object so there's no problem with creating an AnalogIn

class PlotSource():
    MIN = 0 
    MAX = 65535
    SCALE_MIN = 0
    SCALE_MAX = 65535
    # practical maximum read rate per second on CLUE hardware
    RATE = 0
    UNIT = None
    VALUES = 0
    
    def __init__(self):
        self._name = ""

    def __str__(self):
        return self._name
        
    def data(self):
        return None

    def start(self):
        pass
        
    def stop(self):
        pass


class PinPlotSource(PlotSource):
    def __init__(self, pin):
        self._pin = pin
        self._analogin = analogio.AnalogIn(pin)
        self._name = ("Pad", str(board.P3).split('.')[-1])
        
    MIN = 0 
    MAX = 65535
    SCALE_MIN = 0
    SCALE_MAX = 65535
    # practical maximum read rate per second on CLUE hardware
    RATE = 10000
    UNIT = "NOT VOLTS!"
    VALUES = 1
    
    ### for VALUE of 1, returns int or float
    ### for VALUE > 1, returns tuple of aforementioned
    def data(self):
        return self._analogin.value


### TODO - consider returning colour hints or alternative colours
class ColorPlotSource(PlotSource):
    def __init__(self, clue):
        self._clue = clue
        self._name = ("Color: R, G, B")
        
    MIN = 0 
    MAX = 65535
    SCALE_MIN = 0
    SCALE_MAX = 65535
    # practical maximum read rate per second on CLUE hardware
    RATE = 10000
    UNIT = "NOT VOLTS!"
    VALUES = 3
    
    ### for VALUE of 1, returns int or float
    ### for VALUE > 1, returns tuple of aforementioned
    def data(self):
        (r, g, b, c) = self._clue.color
        return (r, g, b)

    def start(self):
        ### Set APDS9660 to sample every (256 - 249 ) * 2.78 = 19.46ms
        self._clue._sensor.integration_time = 249 # 19.46ms, ~ 50Hz
        self._clue._sensor.color_gain = 0x02 # 16x (library default is 4x)


class ColorReflectedGreenPlotSource(PlotSource):
    def __init__(self, clue):
        self._clue = clue
        self._name = ("Color: G")
        
    MIN = 0 
    MAX = 65535
    SCALE_MIN = 0
    SCALE_MAX = 65535
    # practical maximum read rate per second on CLUE hardware
    RATE = 10000
    UNIT = "NOT VOLTS!"
    VALUES = 1

    ### for VALUE of 1, returns int or float
    ### for VALUE > 1, returns tuple of aforementioned
    def data(self):
        (r, g, b, c) = self._clue.color
        return g

    def start(self):
        ### Set APDS9660 to sample every (256 - 249 ) * 2.78 = 19.46ms
        self._clue._sensor.integration_time = 249 # 19.46ms, ~ 50Hz
        self._clue._sensor.color_gain = 0x02 # 16x (library default is 4x)
      
        self._clue.white_leds = True
        
    def stop(self):
        self._clue.white_leds = False


class VolumePlotSource(PlotSource):
    def __init__(self, clue):
        self._clue = clue
        self._name = ("Volume (dB)")
        
    MIN = 0 
    MAX = 97 + 3
    SCALE_MIN = 0
    SCALE_MAX = 97 + 3
    # practical maximum read rate per second on CLUE hardware
    RATE = 10000
    UNIT = "dB"
    VALUES = 1

    _LN_CONVERSION_FACTOR = 20 / math.log(10)

    def data(self):
        return (math.log(self._clue.sound_level + 1)
                * self._LN_CONVERSION_FACTOR)


#source = PinPlotSource(board.P3)
#source = ColorPlotSource(clue)
#source = ColorReflectedGreenPlotSource(clue)
source = VolumePlotSource(clue)

display = board.DISPLAY

# Create a bitmap with two colors

plot_width  = 200
grid_width  = plot_width + 1
plot_height = 201
grid_height = plot_height

### TODO - separate palette for plot_grid ?
plot_grid = displayio.Bitmap(grid_width, grid_height, 2)
plots = displayio.Bitmap(plot_width, plot_height, 8)

g_palette = displayio.Palette(2)
g_palette.make_transparent(0)
g_palette[0] = 0x000000
g_palette[1] = 0x40c040

# Create a colour palette
# Eventually scope colours will be ch1 yellow, ch2 cyan, ch3 magenta
palette = displayio.Palette(9)

palette.make_transparent(0)
palette[1] = 0x0000ff
palette[2] = 0x00ff00
palette[3] = 0x00ffff
palette[4] = 0xff0000
palette[5] = 0xff00ff
palette[6] = 0xffff00
palette[7] = 0xffffff

### TODO - this all needs a lot of work on colour names etc
###
channel_colidx = (6, 3, 5)

# Create a TileGrid using the Bitmap and Palette
tg_plot_grid = displayio.TileGrid(plot_grid, pixel_shader=g_palette)
tg_plot_grid.x = 39
tg_plot_grid.y = 20

source_description = str(source)

font = terminalio.FONT
font_w, font_h = font.get_bounding_box()
source_label = label.Label(font, text=source_description,
                           scale=2, line_spacing=1, color=0xc0c0c0)
source_label.y = font_h // 2  ### TODO this doesn't look quite right

### This is not needed as Label parent class is Group and scale works
#g_source = displayio.Group(scale=2, max_size=1)
#g_source.append(source_label)

g_background = displayio.Group(max_size=2)
g_background.append(tg_plot_grid)
g_background.append(source_label)

tg_plot_data = displayio.TileGrid(plots, pixel_shader=palette)
tg_plot_data.x = 39
tg_plot_data.y = 20

# Create a Group
main_group = displayio.Group(max_size=2)
 
# Add the TileGrid to the Group
main_group.append(g_background)
main_group.append(tg_plot_data)
 
# Add the Group to the Display
display.show(main_group)

GRID_DOT_SPACING = 8

# horizontal lines
for x in range(0, grid_width, GRID_DOT_SPACING):
    for y in range(0, grid_height, 50):
        plot_grid[x, y] = 1  ### TODO - this is green review this

# vertical lines
for x in range(0, grid_width, 50):
    for y in range(0, grid_height, GRID_DOT_SPACING):
        plot_grid[x, y] = 1  ### TODO - this is green review this

# Get some data on read rates on CLUE
for trial in range(5):
    t1 = time.monotonic()
    for i in range(100):
        _ = source.data()
    t2 = time.monotonic()
    print("Read rate", trial, "at", 100.0 / (t2 - t1), "Hz")

# Draw even more pixels
t1 = time.monotonic()
for x in range(plot_width):
    for y in range(plot_height):
        plots[x, y] = 3
t2 = time.monotonic()
# The pixels have not necessarily all been shown at this point
print("AUTO", t2 - t1)
# 4.09s for 240x240, 3.00s for 200x200

display.auto_refresh = False
t1 = time.monotonic()
for x in range(plot_width):
    for y in range(plot_height):
        plots[x, y] = 0
display.refresh(minimum_frames_per_second=0)
t2 = time.monotonic()
print("MANUAL", t2 - t1)
# 3.32s for 240x240, 2.45 for 200x200

MAX_CHANNELS = 3
plot_width = 200
points = [array.array('B', [0] * plot_width),
          array.array('B', [0] * plot_width),
          array.array('B', [0] * plot_width)]

display.auto_refresh = True

source.start()
channels_in_use = source.VALUES
plot_initial_min = 0
plot_max = 300
plot_range = plot_max - plot_initial_min
plot_scale = (plot_height - 1) / plot_range
data_min = [float("inf")] * MAX_CHANNELS
data_max = [float("-inf")] * MAX_CHANNELS
MINMAX_HISTORY = 5
prior_data_min = [float("inf")] * MINMAX_HISTORY 
prior_data_max = [float("-inf")] * MINMAX_HISTORY
transparent = 0
off_scale = False

for scan in range(200):
    t1 = time.monotonic()
    for x in range(plot_width):
        data = source.data()
        if channels_in_use > 1:
            data = source.data()
            for ch in range(channels_in_use):
                plots[x, points[ch][x]] = transparent
                #points[0][x] = round(clue.acceleration[0] * 6.0) + 100
                #points[0][x] = round((clue.temperature - 20.0) * 15)
                #points[0][x] = random.randint(50, 150)
                ypos = round((plot_max - data[ch]) * plot_scale)
                if ypos < 0:
                    data_max[ch] = data[ch]
                    off_scale = True
                elif ypos >= plot_height:
                    data_min[ch] = data[ch]                   
                    off_scale = True
                else:                
                    plots[x, ypos] = channel_colidx[ch]
                    points[ch][x] = ypos
                    
                if data[ch] < data_min[ch]:
                    data_min[ch] = data[ch]
                if data[ch] > data_max[ch]:
                    data_max[ch] = data[ch]
        else:
            data = source.data()
            plots[x, points[0][x]] = transparent
            #points[0][x] = round(clue.acceleration[0] * 6.0) + 100
            #points[0][x] = round((clue.temperature - 20.0) * 15)
            #points[0][x] = random.randint(50, 150)
            ypos = round((plot_max - data) * plot_scale)
            if ypos < 0:
                off_scale = True
            elif ypos >= plot_height:
                off_scale = True
            else:
                plots[x, ypos] = channel_colidx[0]
                points[0][x] = ypos

            if data < data_min[0]:
                data_min[0] = data
            if data > data_max[0]:
                data_max[0] = data

    t2 = time.monotonic()
    print("LINEA", t2 - t1) 

    ### TODO - this needs a lot of refinement and testing
    ### test with flat line
    ### TODO - does this need a vertical shift without rescale?
    new_min = min(data_min)
    new_max = max(data_max)
    prior_data_min[scan % MINMAX_HISTORY] = new_min
    prior_data_max[scan % MINMAX_HISTORY] = new_max
    current_range = new_max - new_min
    if current_range > 0 and off_scale:
        print("ZOOM OUT / RECENTRE")
        ### Add 12.5% on top and bottom
        plot_max = new_max + 0.125 * current_range
        plot_range = 1.25 * current_range
        plot_scale = (plot_height - 1) / plot_range
        ### TODO - redraw grid and labels
        off_scale = False
    else:
        hist_min = min(prior_data_min)
        hist_max = max(prior_data_max)
        historical_range = hist_max - hist_min
        if historical_range > 0 and plot_range * 0.8 > historical_range:
            print("ZOOM IN")
            ### TODO - needs to look at more historical data for min/max
            ### Check to see if we should zoom in
            plot_max = new_max + 0.125 * historical_range
            plot_range = 1.25 * historical_range
            plot_scale = (plot_height - 1) / plot_range

    data_min = [float("inf")] * MAX_CHANNELS
    data_max = [float("-inf")] * MAX_CHANNELS
    
### About 0.4s for clue.acceleration[0]
### About 8.4s for temperature !
### About 0.09-0.14 for analogio

source.stop()

# display.auto_refresh = False
# for scans in range(20):
    # t1 = time.monotonic()
    # for x in range(plot_width):
        # plots[x, points[0][x]] = 0
        # #points[0][x] = round(clue.acceleration[0] * 6.0) + 100
        # #points[0][x] = round((clue.temperature - 20.0) * 15)
        # #points[0][x] = random.randint(50, 150)
        # points[0][x] = round(source.data() / 328)
        # plots[x, points[0][x]] = 1
    # display.refresh(minimum_frames_per_second=0)
    # t2 = time.monotonic()
    # print("LINEM", t2 - t1)
### About 0.04 for analogio

# display.auto_refresh = False
# for scans in range(20):
    # t1 = time.monotonic()
    # for x in range(plot_width):
        # plots[x, points[0][x]] = 0
        # #points[0][x] = round(clue.acceleration[0] * 6.0) + 100
        # #points[0][x] = round((clue.temperature - 20.0) * 15)
        # #points[0][x] = random.randint(50, 150)
        # points[0][x] = round(source.data() / 328)
        # plots[x, points[0][x]] = 1
        # if x % 50 == 49:
            # display.refresh(minimum_frames_per_second=0)
    # t2 = time.monotonic()
    # print("LINEM4", t2 - t1)
### About 0.12-0.15 for analogio

print("sleeping 10 seconds")
time.sleep(10)
