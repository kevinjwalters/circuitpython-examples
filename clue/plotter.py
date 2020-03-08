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

class Plotter():
    _DEFAULT_SCALE_MODE = {"lines": "pixel",
                           "dots": "screen",
                           "minavgmax": "pixel"}

    PLOT_COLORS = [0x000000,
                   0x0000ff,
                   0x00ff00,
                   0x00ffff,
                   0xff0000,
                   0xff00ff,
                   0xffff00,
                   0xffffff,
                   0xff0080]

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
        self._title = title
        self._max_title_len = max_title_len

        # Initialise the arrays which hold data plus associated indexes
        self.clear_data()

        self._mu_output = mu_output
        self._debug = debug

        self._min = None
        self._max = None
        self._abs_min = None
        self._abs_max = None
        self._plot_range = None
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

        plot_labels = []
        # from top of screen to bottom
        ### TODO - try 6 chars
        for y_div in range(self._y_divs + 1):
            plot_labels.append(Label(self._font,
                                     text="-" * self._y_lab_width,
                                     max_glyphs=self._y_lab_width,
                                     line_spacing=1,
                                     color=self._y_lab_color))
            plot_labels[-1].x = 5 ### TODO THIS PROPERLY
            plot_labels[-1].y = y_div * 50 + 30 - 1  ### TODO THIS PROPERLY
        self._displayio_y_labs = plot_labels

        g_background = displayio.Group(max_size=3+len(plot_labels))
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

    def display_on(self):
        if self._displayio_graph is None:
            self._displayio_graph = self._make_empty_graph()

        self._output.show(self._displayio_graph)

    def display_off(self):
        pass

    def data_add(self, values):
        for idx, value in enumerate(values):
            self._data_value[idx][self._x_pos] = value
            self._data_y_pos[idx][self._x_pos] = 00000  ### mapped value

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
