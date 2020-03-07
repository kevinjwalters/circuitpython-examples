### clue-plotter v1.3
### CircuitPython on CLUE sensor and input plotter
### This plots the sensors and analogue inputs in a style similar to
### an oscilloscope

### Tested with an Adafruit CLUE Alpha and CircuitPython and 5.0.0

### ANY CRITICAL NOTES ON LIBRARIES GO HERE

### copy this file to CLUE board as code.py
### needs companion plot_sensor.py file

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

from plot_source import *

### C/Arduino one https://github.com/adafruit/Adafruit_Arcada/blob/master/examples/full_board_tests/arcada_clue_sensorplotter/arcada_clue_sensorplotter.ino

# There's a form of on-demand instanitation for touch pads
# but analogio can be used if touch_0 - touch_3 have not been used
# https://github.com/adafruit/Adafruit_CircuitPython_CLUE
from adafruit_clue import clue
from adafruit_display_text import label

debug = 2

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


### TODO - got to solve the issue of reusing pins
### group by sensor?
sources = [#PinPlotSource(board.P0),
           #PinPlotSource(board.P1),
           #PinPlotSource(board.P2),
           TemperaturePlotSource(clue, type="C"),
           TemperaturePlotSource(clue, type="F"),
           PressurePlotSource(clue),
           HumidityPlotSource(clue),
           ColorPlotSource(clue),
           ProximityPlotSource(clue),
           IlluminatedColorPlotSource(clue, "Red"),
           IlluminatedColorPlotSource(clue, "Green"),
           IlluminatedColorPlotSource(clue, "Blue"),
           IlluminatedColorPlotSource(clue, "Clear"),
           VolumePlotSource(clue),
           AccelerometerPlotSource(clue),
           GyroPlotSource(clue),
           MagnetometerPlotSource(clue),
           PinPlotSource([board.P0, board.P1, board.P2])
          ]


#source = PinPlotSource(board.P2)
#source = ColorPlotSource(clue)
#source = ColorReflectedGreenPlotSource(clue)
current_source_idx = 0
source = sources[current_source_idx]   ### TODO - review where this is set

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
g_palette[1] = 0x308030

# Create a colour palette
# Eventually scope colours will be ch1 yellow, ch2 cyan, ch3 magenta
plot_palette = displayio.Palette(9)

plot_palette.make_transparent(0)
plot_palette[1] = 0x0000ff
plot_palette[2] = 0x00ff00
plot_palette[3] = 0x00ffff
plot_palette[4] = 0xff0000
plot_palette[5] = 0xff00ff
plot_palette[6] = 0xffff00
plot_palette[7] = 0xffffff
plot_palette[8] = 0xff0080

### TODO - this all needs a lot of work on colour names etc
#channel_colidx_default = (6, 8, 5)
channel_colidx_default = (6, 8, 5)

# Create a TileGrid using the Bitmap and Palette
tg_plot_grid = displayio.TileGrid(plot_grid, pixel_shader=g_palette)
tg_plot_grid.x = 39
tg_plot_grid.y = 30

font = terminalio.FONT
font_w, font_h = font.get_bounding_box()
### Text here is later changed to the source name
### TODO - max_glyphs here needs some enforcement
###        OR could write about that as a bug/risk
### Magic value of 45 in https://github.com/adafruit/Adafruit_CircuitPython_CLUE/blob/master/adafruit_clue.py#L128
### 240/45 = 5.333
### Could set this to max of the the name lengths?
### Could write about arbtriry text and truncations and ... UI feature

def plot_details(title="", ylab=""):
    source_label.text = title
    units_label.text = ylab
    ### center the text
    units_label.x = max(0, (40 - font_w * len(ylab))) // 2

text_colour=0xc0c0c0
initial_text = "CLUE Plotter"
max_text_len = max(len(initial_text), max([len(str(so)) for so in sources]))
source_label = label.Label(font, text=initial_text,
                           max_glyphs=max_text_len,
                           scale=2, line_spacing=1, color=text_colour)
source_label.x = 40
source_label.y = font_h // 2

initial_units=""
max_text_len = max(len(initial_units), max([len(so.units()) for so in sources]))
units_label = label.Label(font, text=initial_units,
                          max_glyphs=max_text_len,
                          line_spacing=1, color=text_colour)
units_label.x = 0
units_label.y = font_h // 2

X_DIVS = 4
Y_DIVS = 4
plot_labels = []

### from top to bottom
for ydiv in range(Y_DIVS + 1):
    plot_labels.append(label.Label(font, text="-----",
                       max_glyphs=5, line_spacing=1, color=text_colour))
    plot_labels[-1].x = 5
    plot_labels[-1].y = (ydiv) * 50 + 30 - 1  ### TODO THIS PROPERLY

### This is not needed as Label parent class is Group and scale works
#g_source = displayio.Group(scale=2, max_size=1)
#g_source.append(source_label)

g_background = displayio.Group(max_size=3+len(plot_labels))
g_background.append(tg_plot_grid)
for label in plot_labels:
    g_background.append(label)
g_background.append(units_label)
g_background.append(source_label)

tg_plot_data = displayio.TileGrid(plots, pixel_shader=plot_palette)
tg_plot_data.x = 39
tg_plot_data.y = 30

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

# # Draw even more pixels
# t1 = time.monotonic()
# for x in range(plot_width):
    # for y in range(plot_height):
        # plots[x, y] = 3
# t2 = time.monotonic()
# # The pixels have not necessarily all been shown at this point
# print("AUTO", t2 - t1)
# # 4.09s for 240x240, 3.00s for 200x200

# display.auto_refresh = False
# t1 = time.monotonic()
# for x in range(plot_width):
    # for y in range(plot_height):
        # plots[x, y] = 0
# display.refresh(minimum_frames_per_second=0)
# t2 = time.monotonic()
# print("MANUAL", t2 - t1)
# # 3.32s for 240x240, 2.45 for 200x200

print("DONT FORGET pylint")

MAX_CHANNELS = 3
plot_width = 200
points = [array.array('B', [0] * plot_width),
          array.array('B', [0] * plot_width),
          array.array('B', [0] * plot_width)]

data_cbuf = [array.array('f', [0] * plot_width),
             array.array('f', [0] * plot_width),
             array.array('f', [0] * plot_width)]


### TODO - looking to use button_b to select different plot modes
### TODO - look at scrolling like Arcada one does
modes = ("points",   # draws lines between points
         "lines",  # just points - slightly quicker
         "range",   # collects data for 1 second and displays min/avg/max
         "points scroll",
         "lines scroll",
         "range scroll",
       )

### Not sure if I'll use this or not ...
scale_mode = {"points": "screen",
              "lines": "column",
              "range", "column",
              "points scroll": "column",
              "lines scroll": "column",
              "range scroll": "column"}
       
       
current_mode = 0


display.auto_refresh = True

def set_grid_labels(p_labels, p_max, p_range):
    for idx, plot_label in enumerate(p_labels):
        value = p_max - idx * p_range / Y_DIVS
        ### Simple attempt to generate a value within 5 characters
        ### Bad things happen with values > 99999 or < -9999
        if value <= -10.0:
            text_value = "{:.2f}".format(value)[0:5]
        elif value < 0.0:
            text_value = "{:.2f}".format(value)
        elif value >= 10.0:
            text_value = "{:.3f}".format(value)[0:5]
        else:
            text_value = "{:.3f}".format(value)   ### 0.0 to 9.99999
        plot_label.text = text_value


def clear_plot_points(plts, pnts, channs):
    for x in range(len(pnts[0])):
        for ch in range(channs):
            plts[x, pnts[ch][x]] = transparent


while True:
    switch_source = False
    source = sources[current_source_idx]
    ### Put the description of the source on screen at the top
    source_name = str(source)
    if debug:
        print("Selecting source:", source_name)

    plot_details(title=source_name, ylab=source.units())
    source.start()
    channels_in_use = source.values()

    ### Use any requested colors that are found in palette
    ### otherwise use defaults
    channel_colidx = []
    palette = list(plot_palette)
    for idx, col in enumerate(source.colors()):
        try:
            channel_colidx.append(palette.index(col))
        except:
            channel_colidx.append(channel_colidx_default[idx])

    plot_initial_min = source.initial_min()
    plot_max = source.initial_max()
    plot_range = plot_max - plot_initial_min
    plot_scale = (plot_height - 1) / plot_range
    set_grid_labels(plot_labels, plot_max, plot_range)

    MINMAX_HISTORY = 5
    prior_data_min = [float("inf")] * MINMAX_HISTORY
    prior_data_max = [float("-inf")] * MINMAX_HISTORY
    transparent = 0
    off_scale = False
    scan = 1
    mode = modes[current_mode]
    cbuf_idx = 0
    
    while True:
        data_min = [float("inf")] * MAX_CHANNELS
        data_max = [float("-inf")] * MAX_CHANNELS
        t1 = time.monotonic()
        for x in range(plot_width):
            for ch in range(channels_in_use):
                if ch == 0:
                    all_data = source.data()
                if channels_in_use == 1:
                    data = all_data
                else:
                    data = all_data[ch]

                print("TODO", "replace this with undraws by drawing transparent line")
                plots[x, points[ch][x]] = transparent

                data_cbuf[ch][cbuf_idx] = data
                ypos = round((plot_max - data) * plot_scale)
                if ypos < 0:
                    data_max[ch] = data
                    off_scale = True  ### off the top
                elif ypos >= plot_height:
                    data_min[ch] = data
                    off_scale = True  ### off the bottom
                else:
                    points[ch][x] = ypos

                if mode == "points" and not off_scale:
                    plots[x, ypos] = channel_colidx[ch]
                elif mode == "lines":
                    if x == 0:
                        plots[x, ypos] = channel_colidx[ch]
                    else:
                        ### TODO - replace this with line drawing code

                        ### simplified line drawing with just verticals
                        if ypos == points[ch][x - 1]:
                            plots[x, ypos] = channel_colidx[ch]
                        else:
                            step = 1 if ypos > points[ch][x - 1] else -1
                            for lypos in range(points[ch][x - 1] + step,
                                               max(0, min(ypos + step,
                                                          plot_height - 1)),
                                               step):
                                plots[x, lypos] = channel_colidx[ch]

                elif mode == "range":
                    pass  ### TODO - implement!

                if data < data_min[ch]:
                    data_min[ch] = data
                if data > data_max[ch]:
                    data_max[ch] = data

            if clue.button_a:  ### change plot source
                ### Wait for release of button
                while clue.button_a:
                    pass
                ### Clear the screen
                clear_plot_points(plots, points, channels_in_use)

                ### Select the next source
                current_source_idx = (current_source_idx + 1) % len(sources)
                switch_source = True
                break

            if clue.button_b:  ### change plot mode
                ### Wait for release of button
                while clue.button_b:
                    pass
                current_mode = (current_mode + 1) % len(modes)
                mode = modes[current_mode]

            cbuf_idx += 1

        t2 = time.monotonic()

        if switch_source:
            break
        ### TODO - this needs to take into account min/max from source
        ### TODO - this needs a lot of refinement and testing
        ### test with flat line
        ### TODO - does this need a vertical shift without rescale?
        new_min = min(data_min)
        new_max = max(data_max)
        prior_data_min[scan % MINMAX_HISTORY] = new_min
        prior_data_max[scan % MINMAX_HISTORY] = new_max
        hist_min = min(prior_data_min)
        hist_max = max(prior_data_max)
        hist_range = hist_max - hist_min
        if hist_range > 0 and off_scale:
            print("ZOOM OUT / RECENTRE")
            ### Add 12.5% on top and bottom
            plot_max = hist_max + 0.125 * hist_range
            plot_range = 1.25 * hist_range
            plot_scale = (plot_height - 1) / plot_range
            clear_plot_points(plots, points, channels_in_use)
            set_grid_labels(plot_labels, plot_max, plot_range)
            off_scale = False

        ### Check to see if we should zoom in
        elif hist_range > 0 and plot_range * 0.5 > hist_range:
            print("ZOOM IN")
            plot_max = hist_max + 0.125 * hist_range
            plot_range = 1.25 * hist_range
            plot_scale = (plot_height - 1) / plot_range
            clear_plot_points(plots, points, channels_in_use)
            set_grid_labels(plot_labels, plot_max, plot_range)

        t3 = time.monotonic()
        print("LINEA", t2 - t1, t3 - t2)
        scan += 1

    source.stop()
    ### About 0.4s for clue.acceleration[0]
    ### About 8.4s for temperature !
    ### About 0.09-0.14 for analogio


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

### TODO REMOVE
print("sleeping 10 seconds")
time.sleep(10)
