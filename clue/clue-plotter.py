### clue-plotter v1.8
### CircuitPython on CLUE sensor and input plotter
### This plots the sensors and analogue inputs in a style similar to
### an oscilloscope

### Tested with an Adafruit CLUE (Alpha) and CircuitPython and 5.0.0

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
from plotter import Plotter

### C/Arduino one https://github.com/adafruit/Adafruit_Arcada/blob/master/examples/full_board_tests/arcada_clue_sensorplotter/arcada_clue_sensorplotter.ino

# There's a form of on-demand instanitation for touch pads
# but analogio can be used if touch_0 - touch_3 have not been used
# https://github.com/adafruit/Adafruit_CircuitPython_CLUE
from adafruit_clue import clue

debug = 4

### TODO - work out how/if to use this in libraries
def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


### TODO - got to solve the issue of reusing pins
### group by sensor or leave this as an enhancement?
# No attempt to graph/represent clue.gesture
sources = [#PinPlotSource(board.P0),
           #PinPlotSource(board.P1),
           #PinPlotSource(board.P2),
           TemperaturePlotSource(clue, mode="Celsius"),
           TemperaturePlotSource(clue, mode="Fahrenheit"),
           PressurePlotSource(clue, mode="Metric"),
           PressurePlotSource(clue, mode="Imperial"),
           HumidityPlotSource(clue),
           ColorPlotSource(clue),
           ProximityPlotSource(clue),
           IlluminatedColorPlotSource(clue, mode="Red"),
           IlluminatedColorPlotSource(clue, mode="Green"),
           IlluminatedColorPlotSource(clue, mode="Blue"),
           IlluminatedColorPlotSource(clue, mode="Clear"),
           VolumePlotSource(clue),
           AccelerometerPlotSource(clue),
           GyroPlotSource(clue),
           MagnetometerPlotSource(clue),
           PinPlotSource([board.P0, board.P1, board.P2])
          ]

current_source_idx = 0

stylemodes = (("lines", "scroll"),   # draws lines between points
              ("lines", "wrap"),
              ("dots", "scroll"),    # just points - slightly quicker
              ("dots", "wrap")
             )
## Not implemented yet
##              ("heatmap", "scroll"), # collects data for 1 second and displays min/avg/max
##              ("heatmap", "wrap"))

current_sm_idx = 0


def select_colors(plttr, src, def_palette):
    # Use any requested colors that are found in palette
    # otherwise use defaults
    channel_colidx = []
    palette = plttr.get_colors()
    colors = PlotSource.DEFAULT_COLORS if def_palette else src.colors()
    for idx, col in enumerate(colors):
        try:
            channel_colidx.append(palette.index(col))
        except:
            channel_colidx.append(PlotSource.DEFAULT_COLORS.index(col))
    return channel_colidx


def ready_plot_source(plttr, srcs, def_palette, index=0):
    source = srcs[index]
    ### Put the description of the source on screen at the top
    source_name = str(source)
    if debug:
        print("Selecting source:", source_name)

    plttr.clear_all()
    plttr.title = source_name
    plttr.y_axis_lab = source.units()
    plttr.y_range = (source.initial_min(), source.initial_max())
    plttr.y_full_range = (source.min(), source.max())
    channels_from_source = source.values()
    plttr.channels = channels_from_source
    plttr.channel_colidx = select_colors(plttr, source, def_palette)

    source.start()
    return (source, channels_from_source)


def print_data_rate(source):
    """Print data read rate for debugging and setting PlotSource rates."""
    for trial in range(5):
        t1 = time.monotonic()
        for i in range(100):
            _ = source.data()
        t2 = time.monotonic()
        print("Read rate", trial, "at", 100.0 / (t2 - t1), "Hz")


def wait_for_release(func):
   t1 = time.monotonic()
   while func():
       pass
   return (time.monotonic() - t1)


def popup_text(plttr, text, duration=1.0):
    plttr.info = text
    time.sleep(duration)
    plttr.info = None


# TODO - add user interface to change colours
# TODO - add user interface to toggle MU output
mu_plotter_output = False

initial_title = "CLUE Plotter"
max_title_len = max(len(initial_title), max([len(str(so)) for so in sources]))
plotter = Plotter(board.DISPLAY,
                  style=stylemodes[current_sm_idx][0],
                  mode=stylemodes[current_sm_idx][1],
                  title=initial_title,
                  max_title_len=max_title_len,
                  mu_output=mu_plotter_output,
                  debug=debug)

# If set to true this forces use of colour blindness friendly colours
default_palette = False

clue.pixel[0] = (0, 0, 0)  # turn off the NeoPixel on the back of CLUE board

plotter.display_on()

while True:
    # set the source and start items
    (source, channels) = ready_plot_source(plotter, sources,
                                           default_palette, current_source_idx)
    if debug >= 5:
        print_data_rate(source)

    while True:
        # read data
        all_data = source.data()

        # check for left (A) and right (B) button presses
        if clue.button_a:  # change plot source
            release_time = wait_for_release(lambda: clue.button_a)
            if release_time > 3.0:
                mu_plotter_output = not mu_plotter_output
                plotter.mu_output = mu_plotter_output
                popup_text(plotter,
                           "Mu output "
                           + ("on" if mu_plotter_output else "off"))
            elif release_time > 1.0:
                default_palette = not default_palette
                popup_text(plotter,
                           ("default" if default_palette else "source")
                           + "\npalette")

                plotter.channel_colidx = select_colors(plotter, source,
                                                       default_palette)
            else:
                current_source_idx = (current_source_idx + 1) % len(sources)
                break  # to select the new source

        if clue.button_b:  # change plot style and mode
            current_sm_idx = (current_sm_idx + 1) % len(stylemodes)
            (new_style, new_mode) = stylemodes[current_sm_idx]
            plotter.info = new_style + "\n" + new_mode
            release_time = wait_for_release(lambda: clue.button_b)
            plotter.info = ""
            d_print(1, "Graph change", new_style, new_mode)
            plotter.change_stylemode(new_style, new_mode)

        # display it
        if channels == 1:
            plotter.data_add((all_data,))
        else:
            plotter.data_add(all_data)

    source.stop()

plotter.display_off()
