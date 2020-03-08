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

"""
`plotter`
================================================================================
CircuitPython library for the clue-plotter application's plotting facilties.
Not intended to be a truly general purpose plotter but perhaps could be
developed into one.

* Author(s): Kevin J. Walters

Implementation Notes
--------------------
**Hardware:**
* Adafruit CLUE <https://www.adafruit.com/product/4500>
**Software and Dependencies:**
* Adafruit's CLUE library: https://github.com/adafruit/Adafruit_CircuitPython_CLUE
"""

import time
import array
import random
import math

import board
import displayio
import terminalio

from adafruit_display_text.label import Label

### TODO - docs
### mention this does a bit more than simple raw plotting
### as its doing stats and holding original values


def mapf(value, in_min, in_max, out_min, out_max):
    return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


# This creates ('{.0f}', '{.1f}', '{.2f}', etc
_FMT_DEC_PLACES = tuple("{:." + str(x) + "f}" for x in range(10))

def format_width(nchars, value):
    """Simple attempt to generate a value within nchars characters.
       Return value can be too long, e.g. for nchars=5, bad things happen
       with values > 99999 or < -9999 or < -99.9."""
    neg_format = _FMT_DEC_PLACES[nchars - 3]
    pos_format = _FMT_DEC_PLACES[nchars - 2]
    if value <= -10.0:
        # this might overflow width
        text_value = neg_format.format(value)
    elif value < 0.0:
        text_value = neg_format.format(value)
    elif value >= 10.0:
        # this might overflow width
        text_value = pos_format.format(value)
    else:
        text_value = pos_format.format(value)  # 0.0 to 9.99999
    return text_value


class Plotter():
    _DEFAULT_SCALE_MODE = {"lines": "pixel",
                           "dots": "screen",
                           "minavgmax": "pixel"}
    
    # Palette for plotting, first one is set transparent
    PLOT_COLORS = [0x000000,
                   0x0000ff,
                   0x00ff00,
                   0x00ffff,
                   0xff0000,
                   0xff00ff,
                   0xffff00,
                   0xffffff,
                   0xff0080]

    POS_INF = float("inf")
    NEG_INF = float("-inf")

    def _display_manual(self):
        self._output.auto_refresh = False

    def _display_auto(self):
        self._output.auto_refresh = True

    def _display_refresh(self):
        self._output.refresh(minimum_frames_per_second=0)

    def __init__(self, output,
                 type="lines", mode="scroll", scale_mode=None,
                 width=240, height=240,
                 plot_width=200, plot_height=201,
                 x_divs=4, y_divs=4,
                 max_channels=3,
                 est_rate=50,
                 title="CLUE Plotter",
                 max_title_len=20,
                 mu_output=False,
                 debug=0):
        self._output = output
        self.change_mode(type, mode, scale_mode=scale_mode)
        self._width = width
        self._height = height
        self._plot_width = plot_width
        self._plot_height = plot_height
        self._x_divs = x_divs
        self._y_divs = y_divs
        self._max_channels = max_channels
        self._est_rate = est_rate
        self._title = title
        self._max_title_len = max_title_len

        # Initialise the arrays which hold data plus associated indexes
        self.clear_data()

        self._mu_output = mu_output
        self._debug = debug

        self._channels = None
        self._channel_colidx = []

        # The range the data source generates within
        self._abs_min = None
        self._abs_max = None
        
        # The current plot min/max
        self._plot_min = None
        self._plot_max = None

        self._font = terminalio.FONT
        self._y_axis_lab = ""
        self._y_lab_width = 5
        self._y_lab_color = 0xc0c0c0

        self._displayio_graph = None
        self._displayio_plot = None
        self._displayio_title = None
        self._displayio_y_labs = None
        self._displayio_y_axis_lab = None

    def get_colors(self):
        return self.PLOT_COLORS

    def clear_data(self):
        # Allocate arrays for each possible channel with plot_width elements
        self._data_min = None
        self._data_max = None
        
        self._data_y_pos = []
        self._data_value = []
        for _ in range(self._max_channels):
            # 'B' allows 0-255 which is ok for CLUE ...
            self._data_y_pos.append(array.array('B', [0] * self._plot_width))
            self._data_value.append(array.array('f', [0.0] * self._plot_width))

        # When in use the arrays in here are variable length
        self._datastats = [[] * self._max_channels]

        self._values = 0
        self._x_pos = 0
        self.data_idx = 0

    # Simple implementation here is to clear the screen on change...
    def change_mode(self, type, mode, scale_mode=None):
        if type not in ("lines", "dots", "heatmap"):
            raise ValueError("type not lines or dots")
        self._type = type
        if mode not in ("scroll", "wrap"):
            raise ValueError("mode not scroll or wrap")
        self._mode = mode
        if scale_mode is None:
            scale_mode = self._DEFAULT_SCALE_MODE[type]
        elif scale_mode not in ("pixel", "screen", "time"):
            raise ValueError("scale_mode not pixel, screen or time")
        self._scale_mode = scale_mode

        if self._mode == "scroll":
            self._display_auto()
        elif self_mode == "pixel":
            self._display_manual()

    def _make_empty_graph(self):
        ### TODO - cut size down here
        ### perhaps make grid in another method?
        grid_width  = self._plot_width + 1
        grid_height = self._plot_height
        plot_grid = displayio.Bitmap(grid_width, grid_height, 2)
        
        GRID_DOT_SPACING = 8  ### TODO - move this.

        # horizontal lines
        for x in range(0, grid_width, GRID_DOT_SPACING):
            for y in range(0, grid_height, 50):   ### TODO calc these 50 values or this range
                plot_grid[x, y] = 1

        # vertical lines
        for x in range(0, grid_width, 50):
            for y in range(0, grid_height, GRID_DOT_SPACING):
                plot_grid[x, y] = 1

        # grid colours
        grid_palette = displayio.Palette(2)
        grid_palette.make_transparent(0)
        grid_palette[0] = 0x000000
        grid_palette[1] = 0x308030

        self._displayio_plot = displayio.Bitmap(self._plot_width, self._plot_height, 8)
        # Create a colour palette for plot dots/lines
        plot_palette = displayio.Palette(9)

        for idx in range(len(self.PLOT_COLORS)):
           plot_palette[idx] = self.PLOT_COLORS[idx]
        plot_palette.make_transparent(0)

        # consider enlarging this for different intensities of the channel plots

        # Create a TileGrid using the Bitmap and Palette
        tg_plot_grid = displayio.TileGrid(plot_grid,
                                          pixel_shader=grid_palette)
        tg_plot_grid.x = 39
        tg_plot_grid.y = 30

        font_w, font_h = self._font.get_bounding_box()

        self._displayio_title = Label(self._font,
                                      text=self._title,
                                      max_glyphs=self._max_title_len,
                                      scale=2,
                                      line_spacing=1,
                                      color=self._y_lab_color)
        self._displayio_title.x = 40
        self._displayio_title.y = font_h // 2

        self._displayio_y_axis_lab = Label(self._font,
                                           text=self._y_axis_lab,
                                           max_glyphs=self._y_lab_width,
                                           line_spacing=1,
                                           color=self._y_lab_color)
        self._displayio_y_axis_lab.x = 0  # 0 works here because text is ""
        self._displayio_y_axis_lab.y = font_h // 2

        plot_y_labels = []
        # from top of screen to bottom
        ### TODO - try 6 chars
        for y_div in range(self._y_divs + 1):
            plot_y_labels.append(Label(self._font,
                                       text="-" * self._y_lab_width,
                                       max_glyphs=self._y_lab_width,
                                       line_spacing=1,
                                       color=self._y_lab_color))
            plot_y_labels[-1].x = 5 ### TODO THIS PROPERLY
            plot_y_labels[-1].y = y_div * 50 + 30 - 1  ### TODO THIS PROPERLY
        self._displayio_y_labs = plot_y_labels

        # three items (grid, axis label, title) plus the y tick labels
        g_background = displayio.Group(max_size=3+len(plot_y_labels))
        g_background.append(tg_plot_grid)
        for label in self._displayio_y_labs:
            g_background.append(label)
        g_background.append(self._displayio_y_axis_lab)
        g_background.append(self._displayio_title)

        tg_plot_data = displayio.TileGrid(self._displayio_plot,
                                          pixel_shader=plot_palette)
        tg_plot_data.x = 39
        tg_plot_data.y = 30

        # Create a Group
        main_group = displayio.Group(max_size=2)

        # Add the TileGrid to the Group
        main_group.append(g_background)
        main_group.append(tg_plot_data)
        return main_group

    def set_y_axis_tick_labels(self, y_min, y_max):
        px_per_div = (y_max - y_min) / self._y_divs
        for idx, tick_label in enumerate(self._displayio_y_labs):
            value = y_max - idx * px_per_div
            text_value = format_width(self._y_lab_width, value)
            tick_label.text = text_value[:self._y_lab_width]

    def display_on(self):
        if self._displayio_graph is None:
            self._displayio_graph = self._make_empty_graph()

        self._output.show(self._displayio_graph)

    def display_off(self):
        pass

    def data_add(self, values):
        for idx, value in enumerate(values):
            x_pos = self._x_pos
            self._data_value[idx][x_pos] = value
            y_pos = round(mapf(value,
                               self._plot_min, self._plot_max,
                               0, self._plot_height - 1))
            self._data_y_pos[idx][x_pos] = y_pos

            # TEMP PLOT - TODO REPLACE with line one
            self._displayio_plot[x_pos, y_pos] = self._channel_colidx[idx]

        new_x_pos = self._x_pos + 1
        if new_x_pos >= self._plot_width:
            # fallen off so wrap or leave position
            # on last column for scroll
            if self._mode == "wrap":
                self._x_pos = 0
        else:
            self._x_pos = new_x_pos

        self._values += 1

        if self._mu_output:
            print(values)
        if self._mode == "scroll":
            self._display_refresh()

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self._title = value[:self._max_title_len]  # does not show truncation
        self._displayio_title.text = self._title
        
    @property
    def channels(self):
        return self._channels

    @channels.setter
    def channels(self, value):
        if value > self._max_channels:
            raise ValueError("Exceeds max_channels")
        self._channels = value

    @property
    def y_range(self):
        return (self._plot_min, self._plot_max)
        
    @y_range.setter
    def y_range(self, minmax):
        changed = False
        if minmax[0] != self._plot_min:
            self._plot_min = minmax[0]
            changed = True
        if minmax[1] != self._plot_max:
            self._plot_max = minmax[1]
            changed = True

        if changed:
            self.set_y_axis_tick_labels(self._plot_min, self._plot_max)

    @property
    def y_axis_lab(self):
        return self._y_axis_lab
        
    @y_axis_lab.setter
    def y_axis_lab(self, text):
        self._y_axis_lab = text[:self._y_lab_width]
        font_w, font_h = self._font.get_bounding_box()
        x_pos = (40 - font_w * len(self._y_axis_lab)) // 2
        # max() used to prevent negative (off-screen) values
        self._displayio_y_axis_lab.x = max(0, x_pos)
        self._displayio_y_axis_lab.text = self._y_axis_lab

    @property
    def channel_colidx(self):
        return self._channel_colidx
        
    @channel_colidx.setter
    def channel_colidx(self, value):
        # tuple(0 ensures object has a local / read-only copy of data
        self._channel_colidx = tuple(value)
