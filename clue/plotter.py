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


# This creates ('{:.0f}', '{:.1f}', '{:.2f}', etc
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
    _DEFAULT_SCALE_MODE = {"lines": "scroll",
                           "dots": "screen",
                           "heatmap": "pixel"}

    # Palette for plotting, first one is set transparent
    TRANSPARENT_IDX = 0
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
        # TODO re-enable self._output.auto_refresh = False
        # _display_refresh doesn't seem to work possibly if called very freq.
        # Trying False again - simple test of Label/Bitmap shows this is ok... odd...
        #self._output.auto_refresh = False
        
        # DISABLING manual for now by not setting this to False
        self._output.auto_refresh = True

    def _display_auto(self):
        self._output.auto_refresh = True

    def _display_refresh(self):
        return True
        # This is a hack to work around how refresh() works
        # as it is designed for constant frame rate updates and
        # blocks accordingly based on duration of a frame
        # there's currently no simple "refresh now"
        # HACK needs more research 
        if self._last_manual_refresh is not None:
            # using int() to round down
            tfps = int(1000.0 / (time.monotonic() - self._last_manual_refresh))
        else:
            tfps = 60
        if self._debug >= 5:
            t1 = time.monotonic()
            updated = self._output.refresh(target_frames_per_second=tfps,
                                           minimum_frames_per_second=0)
            print("Manual screen refresh time", time.monotonic() - t1, updated)
        else:
            updated = self._output.refresh(target_frames_per_second=tfps,
                                           minimum_frames_per_second=0)
        if updated:
            self._last_manual_refresh = time.monotonic() # Perhaps this should be pre-refresh
        return updated

    def __init__(self, output,
                 type="lines", mode="scroll", scale_mode=None,
                 screen_width=240, screen_height=240,
                 plot_width=200, plot_height=201,
                 x_divs=4, y_divs=4,
                 scroll_px=25,
                 max_channels=3,
                 est_rate=50,
                 title="CLUE Plotter",
                 max_title_len=20,
                 mu_output=False,
                 debug=0):
        """scroll_px of greater than 1 gives a jump scroll."""
        self._output = output
        self.change_typemode(type, mode, scale_mode=scale_mode, clear=False)
        self._screen_width = screen_width
        self._screen_height = screen_height
        self._plot_width = plot_width
        self._plot_height = plot_height
        self._plot_height_m1 = plot_height - 1
        self._x_divs = x_divs
        self._y_divs = y_divs
        self._scroll_px = scroll_px
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
        self._plot_offscale = False

        self._font = terminalio.FONT
        self._y_axis_lab = ""
        self._y_lab_width = 5
        self._y_lab_color = 0xc0c0c0

        self._displayio_graph = None
        self._displayio_plot = None
        self._displayio_title = None
        self._displayio_y_labs = None
        self._displayio_y_axis_lab = None
        self._last_manual_refresh = None 

    def get_colors(self):
        return self.PLOT_COLORS

    def clear_all(self):
        if self._values != 0:
            self._undraw_bitmap()
        self.clear_data()

    def clear_data(self):
        # Allocate arrays for each possible channel with plot_width elements
        self._data_min = self.POS_INF
        self._data_max = self.NEG_INF

        self._data_y_pos = []
        self._data_value = []
        for _ in range(self._max_channels):
            # 'i' is 32 bit signed integer
            self._data_y_pos.append(array.array('i', [0] * self._plot_width))
            self._data_value.append(array.array('f', [0.0] * self._plot_width))

        # When in use the arrays in here are variable length
        self._datastats = [[] * self._max_channels]

        self._values = 0
        self._x_pos = 0
        self._data_idx = 0
        self._lastcolumn = False
        self._plot_offscale = False

        # This is created to facilitate fast clear of the plot Bitmap
        #self._transparent_array = array.array('B')
        #self._row_of_zeros = array.array('B', [0] * self._plot_width)
        #for row in range(self._plot_height):
        #    self._transparent_array.extend(row_of_zeros)

    # Simple implementation here is to clear the screen on change...
    def change_typemode(self, type, mode, scale_mode=None, clear=True):
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

        # Clearing everything on screen and stored in variables
        # is simplest approach here
        if clear:
            self.clear_all()

        if self._mode == "wrap":
            self._display_auto()
        elif self._mode == "scroll":
            self._display_manual()

    def _make_empty_tg_plot_bitmap(self):
        plot_bitmap = displayio.Bitmap(self._plot_width, self._plot_height, 9)
        # Create a colour palette for plot dots/lines
        plot_palette = displayio.Palette(9)

        for idx in range(len(self.PLOT_COLORS)):
            plot_palette[idx] = self.PLOT_COLORS[idx]
        plot_palette.make_transparent(0)
        tg_plot_data = displayio.TileGrid(plot_bitmap,
                                          pixel_shader=plot_palette)
        tg_plot_data.x = 39
        tg_plot_data.y = 30
        return (tg_plot_data, plot_bitmap)
        
    def _make_empty_graph(self):
        ### TODO - cut size down here
        ### perhaps make grid in another method?
        grid_width  = self._plot_width + 1
        grid_height = self._plot_height
        #plot_grid = displayio.Bitmap(grid_width, grid_height, 2)
        
        GRID_DOT_SPACING = 8  ### TODO - move this.

        # horizontal lines
        #for x in range(0, grid_width, GRID_DOT_SPACING):
        #    for y in range(0, grid_height, 50):   ### TODO calc these 50 values or this range
        #        plot_grid[x, y] = 1

        # vertical lines
        #for x in range(0, grid_width, 50):
        #    for y in range(0, grid_height, GRID_DOT_SPACING):
        #        plot_grid[x, y] = 1

        # grid colours
        #grid_palette = displayio.Palette(2)
        #grid_palette.make_transparent(0)
        #grid_palette[0] = 0x000000
        #grid_palette[1] = 0x308030

        # consider enlarging this for different intensities of the channel plots

        # Create a TileGrid using the Bitmap and Palette
        #tg_plot_grid = displayio.TileGrid(plot_grid,
        #                                  pixel_shader=grid_palette)
        #tg_plot_grid.x = 39
        #tg_plot_grid.y = 30

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
        #temp# g_background.append(tg_plot_grid)
        for label in self._displayio_y_labs:
            g_background.append(label)
        g_background.append(self._displayio_y_axis_lab)
        g_background.append(self._displayio_title)

        (tg_plot, plot) = self._make_empty_tg_plot_bitmap()

        self._displayio_plot = plot

        # Create a Group
        main_group = displayio.Group(max_size=2)

        # Add the TileGrid to the Group
        main_group.append(g_background)
        main_group.append(tg_plot)
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

    def _draw_vline(self, x1, y1, y2, colidx):
        """Draw a clipped vertical line at x1 from pixel one along from y1 to y2.
           """
        # Same vertical position as previous point
        if y2 == y1:
            if (y2 >= 0 and y2 <= self._plot_height_m1):
                self._displayio_plot[x1, y2] = colidx
            return

        if y2 > y1:
            step = 1  # y2 above y1, on screen this translates to being below
        else:
            step = -1
        for line_y_pos in range(max(0, min(y1 + step, self._plot_height_m1)),
                                max(0, min(y2, self._plot_height_m1)) + step,
                                step):
            self._displayio_plot[x1, line_y_pos] = colidx

    def _clear_plot_bitmap(self):
        t1 = time.monotonic()
        # This approach gave
        # "MemoryError: memory allocation failed, allocating 20100 bytes"
        #(tg_plot, plot) = self._make_empty_tg_plot_bitmap()
        #self._displayio_plot = plot
        #self._displayio_graph[1] = tg_plot
        
        #self._displayio_plot[:] = self._transparent_array
        
        # Probably a bit quicker to do 
        # for val in self._displayio_plot: val=0
        offset = 0
        for yy in range(self._plot_height):
            for xx in range(self._plot_width):
                self._displayio_plot[xx, yy] = self.TRANSPARENT_IDX

        if self._debug >= 4:
            print("Clear plot bitmap", time.monotonic() - t1)

    # This is almost always going to be quicker
    # than the slow _clear_plot_bitmap
    def _undraw_bitmap(self):
        if self._values < self._plot_width:
            data_idx = 0
        else:
            data_idx = self._data_idx

        for ch_idx in range(self._channels):
            colidx = self.TRANSPARENT_IDX
            for x_pos in range(min(self._plot_width, self._values)):
                y_pos = self._data_y_pos[ch_idx][data_idx]
                if self._type == "lines" and x_pos != 0:
                    # Python supports negative array index
                    prev_y_pos = self._data_y_pos[ch_idx][data_idx - 1]
                    self._draw_vline(x_pos, prev_y_pos, y_pos, colidx)
                else:
                    if y_pos >= 0 and y_pos <= self._plot_height_m1:
                        self._displayio_plot[x_pos, y_pos] = colidx
                data_idx += 1
                if data_idx >= self._plot_width:
                    data_idx = 0

    def _undraw_column(self, x_pos, data_idx):
        for ch_idx in range(self._channels):
            y_pos = self._data_y_pos[ch_idx][data_idx]
            if self._type == "lines" and x_pos != 0:
                # Python supports negative array index
                prev_y_pos = self._data_y_pos[ch_idx][data_idx - 1]
                self._draw_vline(x_pos, prev_y_pos, y_pos,
                                 self.TRANSPARENT_IDX)
            else:
                if y_pos >= 0 and y_pos <= self._plot_height_m1:
                    self._displayio_plot[x_pos, y_pos] = self.TRANSPARENT_IDX   

    # TODO - very similar code to _undraw_bitmap ...
    def _data_redraw(self, x1, x2, data_idx):
        """Redraw data from x1 to x2 inclusive."""
        for ch_idx in range(self._channels):
            colidx = self._channel_colidx[ch_idx]
            for x_pos in range(x1, x2 + 1):
                y_pos = self._data_y_pos[ch_idx][data_idx]
                if self._type == "lines" and x_pos != 0:
                    # Python supports negative array index
                    prev_y_pos = self._data_y_pos[ch_idx][data_idx - 1]
                    self._draw_vline(x_pos, prev_y_pos, y_pos, colidx)                                     
                else:
                    if y_pos >= 0 and y_pos <= self._plot_height_m1:
                        self._displayio_plot[x_pos, y_pos] = colidx
                data_idx += 1
                if data_idx >= self._plot_width:
                    data_idx = 0

    def _data_store_draw(self, values, x_pos, data_idx):
        offscale = False
        rescale_not_needed = True
        for ch_idx, value in enumerate(values):    
            # store value and update min/max as required
            self._data_value[ch_idx][data_idx] = value
            if value < self._data_min:
                self._data_min = value
            if value > self._data_max:
                self._data_max = value

            # last two parameters appear "swapped" - this deals with the
            # displayio screen y coordinate increasing downwards
            y_pos = round(mapf(value,
                               self._plot_min, self._plot_max,
                               self._plot_height_m1, 0))
            
            if y_pos < 0 or y_pos >= self._plot_height:
                offscale = True
                self._plot_offscale = offscale
                if self._scale_mode == "pixel":
                    rescale_not_needed = False
                
            if rescale_not_needed:
                self._data_y_pos[ch_idx][data_idx] = y_pos

                if self._type == "lines" and self._values != 0:
                    # Python supports negative array index
                    prev_y_pos = self._data_y_pos[ch_idx][data_idx - 1]
                    self._draw_vline(x_pos, prev_y_pos, y_pos,
                                     self._channel_colidx[ch_idx])
                else:
                    if not offscale:
                        self._displayio_plot[x_pos, y_pos] = self._channel_colidx[ch_idx]

            return rescale_not_needed

    def _auto_plot_range(self):
        changed = False
        range = self._data_max - self._data_min
        headroom = range * 0.2
        new_plot_min = max(self._data_min - headroom, self._abs_min)
        new_plot_max = min(self._data_max + headroom, self._abs_max)

        # set new range which will also redo y tick labels if necessary
        self.y_range = (new_plot_min, new_plot_max)
        self._offscale = False

    def data_add(self, values):
        data_idx = self._data_idx

        ### TODO - ponder this
        ###        as it will not catch the first reading being off scale
        if self._x_pos == 0 and self._mode == "wrap" and self._plot_offscale:
            self._auto_plot_range()

        if self._lastcolumn and self._mode == "scroll":
            # Clear and redraw the bitmap to scroll it leftward
            #self._clear_plot_bitmap()  # 2.3 seconds at 200x201
            self._undraw_bitmap()
            if self._plot_offscale:
                self._auto_plot_range()
            self._data_redraw(0, self._plot_width - 1 - self._scroll_px,
                              (data_idx + self._scroll_px) % self._plot_width)
            self._x_pos = self._plot_width - self._scroll_px
            self._lastcolumn = False

        x_pos = self._x_pos

        if self._values >= self._plot_width and self._mode == "wrap":
            self._undraw_column(x_pos, data_idx)

        # add the data and draw it unless a y axis is going to be rescaled
        if not self._data_store_draw(values, x_pos, data_idx):
            self._auto_plot_range()        # rescale y range
            # draw with new range
            self._data_store_draw(values, x_pos, data_idx)

        # increment the data index wrapping around
        self._data_idx += 1
        if self._data_idx >= self._plot_width:
            self._data_idx = 0

        # increment x position dealing with wrap/scroll
        new_x_pos = x_pos + 1
        if new_x_pos >= self._plot_width:
            # fallen off edge so wrap or leave position
            # on last column for scroll
            if self._mode == "wrap":
                self._x_pos = 0
            else:
                self._x_pos = new_x_pos  # this is off screen
                self._lastcolumn = True
        else:
            self._x_pos = new_x_pos

        self._values += 1

        if self._mu_output:
            print(values)

        # scrolling mode has automatic refresh in background turned off
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
    def y_full_range(self):
        return (self._plot_min, self._plot_max)
        
    @y_full_range.setter
    def y_full_range(self, minmax):
        self._abs_min = minmax[0]
        self._abs_max = minmax[1]

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
