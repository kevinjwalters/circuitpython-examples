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
Internally this holds some values in a circular buffer to enable redrawing
and has some basic statistics on data.
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

import displayio
import terminalio

from adafruit_display_text.label import Label


def mapf(value, in_min, in_max, out_min, out_max):
    return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


### This creates ('{:.0f}', '{:.1f}', '{:.2f}', etc
_FMT_DEC_PLACES = tuple("{:." + str(x) + "f}" for x in range(10))

def format_width(nchars, value):
    """Simple attempt to generate a value within nchars characters.
       Return value can be too long, e.g. for nchars=5, bad things happen
       with values > 99999 or < -9999 or < -99.9."""
    neg_format = _FMT_DEC_PLACES[nchars - 3]
    pos_format = _FMT_DEC_PLACES[nchars - 2]
    if value <= -10.0:
        text_value = neg_format.format(value)  ### may overflow width
    elif value < 0.0:
        text_value = neg_format.format(value)
    elif value >= 10.0:
        text_value = pos_format.format(value)  ### may overflow width
    else:
        text_value = pos_format.format(value)  ### 0.0 to 9.99999
    return text_value


class Plotter():
    _DEFAULT_SCALE_MODE = {"lines": "scroll",
                           "dots": "screen",
                           "heatmap": "pixel"}

    ### Palette for plotting, first one is set transparent
    TRANSPARENT_IDX = 0
    ### Removed one colour to get number down to 8 for more efficient
    ### bit-packing in displayio's Bitmap
    _PLOT_COLORS = (0x000000,
                    0x0000ff,
                    0x00ff00,
                    0x00ffff,
                    0xff0000,
                    # 0xff00ff,
                    0xffff00,
                    0xffffff,
                    0xff0080)

    POS_INF = float("inf")
    NEG_INF = float("-inf")

    ### Approximate number of seconds to review data for zooming in
    ### and how often to do that check
    ZOOM_IN_TIME = 8
    ZOOM_IN_CHECK_TIME_NS = 5 * 1e9
    ### 20% headroom either side on zoom in/out
    ZOOM_HEADROOM = 20 / 100

    _GRID_COLOR = 0x308030
    _GRID_DOT_SPACING = 8

    _INFO_FG_COLOR = 0x000080
    _INFO_BG_COLOR = 0xc0c000
    _LABEL_COLOR = 0xc0c0c0

    def _display_manual(self):
        """Intention was to disable auto_refresh here but this needs a
           simple displayio refresh to work well."""
        self._output.auto_refresh = True

    def _display_auto(self):
        self._output.auto_refresh = True

    def _display_refresh(self):
        """Intention was to call self._output.refresh() but this does not work well
           as current implementation is designed with a fixed frame rate in mind."""
        if self._output.auto_refresh:
            return True
        else:
            return True

    def __init__(self, output,
                 style="lines", mode="scroll", scale_mode=None,
                 screen_width=240, screen_height=240,
                 plot_width=200, plot_height=201,
                 x_divs=4, y_divs=4,
                 scroll_px=50,
                 max_channels=3,
                 est_rate=50,
                 title="CLUE Plotter",
                 max_title_len=20,
                 mu_output=False,
                 debug=0):
        """scroll_px of greater than 1 gives a jump scroll."""
        # pylint: disable=too-many-locals,too-many-statements
        self._output = output
        self.change_stylemode(style, mode, scale_mode=scale_mode, clear=False)
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

        # These arrays are used to provide a circular buffer
        # with _data_values valid values - this needs to be sized
        # one larger than screen width to retrieve prior y position
        # for line undrawing in wrap mode
        self._data_size = self._plot_width + 1
        self._data_y_pos = []
        self._data_value = []
        for _ in range(self._max_channels):
            # 'i' is 32 bit signed integer
            self._data_y_pos.append(array.array('i', [0] * self._data_size))
            self._data_value.append(array.array('f', [0.0] * self._data_size))

        ### begin-keep-pylint-happy
        self._data_min = None
        self._data_max = None
        self._data_mins = None
        self._data_maxs = None
        self._data_stats_maxlen = None
        self._data_stats = None
        self._values = None
        self._data_values = None
        self._x_pos = None
        self._data_idx = None
        self._offscreen = None
        self._plot_offyscale = None
        self._plot_lastzoom_ns = None
        ### end-keep-pylint-happy
        self._init_data()

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
        self._plot_min_range = None  ### Used partly to prevent div by zero

        self._plot_dirty = False  ### flag indicate some data has been plotted
        self._suppress_one_redraw = False  ### flag used to incr. efficiency

        self._font = terminalio.FONT
        self._y_axis_lab = ""
        self._y_lab_width = 5  # maximum characters for y axis label
        self._y_lab_color = self._LABEL_COLOR

        self._displayio_graph = None
        self._displayio_plot = None
        self._displayio_title = None
        self._displayio_info = None
        self._displayio_y_labs = None
        self._displayio_y_axis_lab = None
        self._last_manual_refresh = None

    def _init_data(self):
        # Allocate arrays for each possible channel with plot_width elements
        self._data_min = self.POS_INF
        self._data_max = self.NEG_INF
        self._data_mins = [self.POS_INF]
        self._data_maxs = [self.NEG_INF]
        self._data_start_ns = [time.monotonic_ns()]
        self._data_stats_maxlen = 10

        # When in use the arrays in here are variable length
        self._data_stats = [[] * self._max_channels]

        self._values = 0  ### total data processed
        self._data_values = 0  ### valid elements in data_y_pos and data_value
        self._x_pos = 0
        self._data_idx = 0
        self._offscreen = False
        self._plot_offyscale = False
        self._plot_lastzoom_ns = 0  ### monotonic_ns() for last zoom in

    def _recalc_y_pos(self):
        """Recalculates _data_y_pos based on _data_value for changes in y scale."""
        # Check if nothing to do - important since _plot_min _plot_max not yet set
        if self._data_values == 0:
            return

        for ch_idx in range(self._channels):
            # intentional use of negative array indexing
            for data_idx in range(self._data_idx - 1,
                                  self._data_idx - 1 - self._data_values,
                                  -1):
                self._data_y_pos[ch_idx][data_idx] = round(mapf(self._data_value[ch_idx][data_idx],
                                                                self._plot_min,
                                                                self._plot_max,
                                                                self._plot_height_m1,
                                                                0))

    def get_colors(self):
        return self._PLOT_COLORS

    def clear_all(self):
        if self._values != 0:
            self._undraw_bitmap()
        self._init_data()

    # Simple implementation here is to clear the screen on change...
    def change_stylemode(self, style, mode, scale_mode=None, clear=True):
        if style not in ("lines", "dots", "heatmap"):
            raise ValueError("style not lines or dots")
        if mode not in ("scroll", "wrap"):
            raise ValueError("mode not scroll or wrap")
        if scale_mode is None:
            scale_mode = self._DEFAULT_SCALE_MODE[style]
        elif scale_mode not in ("pixel", "screen", "time"):
            raise ValueError("scale_mode not pixel, screen or time")

        # Clearing everything on screen and everything stored in variables
        # is simplest approach here - clearing involves undrawing
        # which uses the self._style so must not change that beforehand
        if clear:
            self.clear_all()

        self._style = style
        self._mode = mode
        self._scale_mode = scale_mode

        if self._mode == "wrap":
            self._display_auto()
        elif self._mode == "scroll":
            self._display_manual()

    def _make_empty_tg_plot_bitmap(self):
        plot_bitmap = displayio.Bitmap(self._plot_width, self._plot_height,
                                       len(self._PLOT_COLORS))
        # Create a colour palette for plot dots/lines
        plot_palette = displayio.Palette(len(self._PLOT_COLORS))

        for idx in range(len(self._PLOT_COLORS)):
            plot_palette[idx] = self._PLOT_COLORS[idx]
        plot_palette.make_transparent(0)
        tg_plot_data = displayio.TileGrid(plot_bitmap,
                                          pixel_shader=plot_palette)
        tg_plot_data.x = 39
        tg_plot_data.y = 30
        return (tg_plot_data, plot_bitmap)

    def _make_tg_grid(self):
        grid_width  = self._plot_width + 1
        grid_height = self._plot_height
        grid_height = self._plot_height // 2  ## QUICK HACK FOR TESTING - UNDO TODO
        plot_grid = displayio.Bitmap(grid_width, grid_height, 2)

        # horizontal lines
        if self._y_divs:
            for x in range(0, grid_width, self._GRID_DOT_SPACING):
                for y in range(0, grid_height, grid_height // self._y_divs):
                    plot_grid[x, y] = 1

        # vertical lines
        if self._x_divs:
            for x in range(0, grid_width, grid_width // self._x_divs):
                for y in range(0, grid_height, self._GRID_DOT_SPACING):
                    plot_grid[x, y] = 1

        # grid colours
        grid_palette = displayio.Palette(2)
        grid_palette.make_transparent(0)
        grid_palette[0] = 0x000000
        grid_palette[1] = self._GRID_COLOR

        # Create a TileGrid using the Bitmap and Palette
        tg_plot_grid = displayio.TileGrid(plot_grid,
                                          pixel_shader=grid_palette)
        tg_plot_grid.x = 39
        tg_plot_grid.y = 30
        return tg_plot_grid

    def _make_empty_graph(self, tg_and_plot=None):
        _, font_h = self._font.get_bounding_box()

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
        self._displayio_y_axis_lab.x = 0  ### 0 works here because text is ""
        self._displayio_y_axis_lab.y = font_h // 2

        plot_y_labels = []
        ### y increases top to bottom of screen
        for y_div in range(self._y_divs + 1):
            plot_y_labels.append(Label(self._font,
                                       text="-" * self._y_lab_width,
                                       max_glyphs=self._y_lab_width,
                                       line_spacing=1,
                                       color=self._y_lab_color))
            plot_y_labels[-1].x = 5
            plot_y_labels[-1].y = (round(y_div * self._plot_height / self._y_divs)
                                   + 30 - 1)
        self._displayio_y_labs = plot_y_labels

        # three items (grid, axis label, title) plus the y tick labels
        g_background = displayio.Group(max_size=3+len(plot_y_labels))
        g_background.append(self._make_tg_grid())
        for label in self._displayio_y_labs:
            g_background.append(label)
        g_background.append(self._displayio_y_axis_lab)
        g_background.append(self._displayio_title)

        if tg_and_plot is not None:
            (tg_plot, plot) = tg_and_plot
        else:
            (tg_plot, plot) = self._make_empty_tg_plot_bitmap()

        self._displayio_plot = plot

        # Create the main Group for display with one spare slot for
        # popup informational text
        main_group = displayio.Group(max_size=3)
        main_group.append(g_background)
        main_group.append(tg_plot)
        self._displayio_info = None

        return main_group

    def set_y_axis_tick_labels(self, y_min, y_max):
        px_per_div = (y_max - y_min) / self._y_divs
        for idx, tick_label in enumerate(self._displayio_y_labs):
            value = y_max - idx * px_per_div
            text_value = format_width(self._y_lab_width, value)
            tick_label.text = text_value[:self._y_lab_width]

    def display_on(self, tg_and_plot=None):
        if self._displayio_graph is None:
            self._displayio_graph = self._make_empty_graph(tg_and_plot=tg_and_plot)

        self._output.show(self._displayio_graph)

    def display_off(self):
        pass

    def _draw_vline(self, x1, y1, y2, colidx):
        """Draw a clipped vertical line at x1 from pixel one along from y1 to y2.
           """
        # Same vertical position as previous point
        # print("VLINE", x1, y1, y2, colidx)
        if y2 == y1:
            if 0 <= y2 <= self._plot_height_m1:
                self._displayio_plot[x1, y2] = colidx
            return

        # y2 above y1, on screen this translates to being below
        step = 1 if y2 > y1 else -1

        for line_y_pos in range(max(0, min(y1 + step, self._plot_height_m1)),
                                max(0, min(y2, self._plot_height_m1)) + step,
                                step):
            self._displayio_plot[x1, line_y_pos] = colidx

    def _clear_plot_bitmap(self):
        if not self._plot_dirty:
            return
        t1 = time.monotonic_ns()
        # This approach gave
        # "MemoryError: memory allocation failed, allocating 20100 bytes"
        #(tg_plot, plot) = self._make_empty_tg_plot_bitmap()
        #self._displayio_plot = plot
        #self._displayio_graph[1] = tg_plot
        #self._displayio_plot[:] = self._transparent_array

        # probably a fraction quicker with a single for loop?
        for yy in range(self._plot_height):
            for xx in range(self._plot_width):
                self._displayio_plot[xx, yy] = self.TRANSPARENT_IDX

        if self._debug >= 4:
            print("Clear plot bitmap", (time.monotonic_ns() - t1) * 1e-9)
        self._plot_dirty = False

    # This is almost always going to be quicker
    # than the slow _clear_plot_bitmap
    def _undraw_bitmap(self):
        if not self._plot_dirty:
            return
        x_cols = min(self._data_values, self._plot_width)
        wrapMode = self._mode == "wrap"
        if wrapMode:
            x_data_idx = (self._data_idx - self._x_pos) % self._data_size
        else:
            x_data_idx = (self._data_idx - x_cols) % self._data_size

        colidx = self.TRANSPARENT_IDX
        for ch_idx in range(self._channels):
            data_idx = x_data_idx
            for x_pos in range(x_cols):
                # "jump" the gap in the circular buffer for wrap mode
                if wrapMode and x_pos == self._x_pos:
                    data_idx = (data_idx + self._data_size - self._plot_width) % self._data_size
                    # TODO - inhibit line drawing in BOTH VERSIONS

                y_pos = self._data_y_pos[ch_idx][data_idx]
                if self._style == "lines" and x_pos != 0:
                    # Python supports negative array index
                    prev_y_pos = self._data_y_pos[ch_idx][data_idx - 1]
                    self._draw_vline(x_pos, prev_y_pos, y_pos, colidx)
                else:
                    if 0 <= y_pos <= self._plot_height_m1:
                        self._displayio_plot[x_pos, y_pos] = colidx
                data_idx += 1
                if data_idx >= self._data_size:
                    data_idx = 0

        self._plot_dirty = False

    def _undraw_column(self, x_pos, data_idx):
        colidx = self.TRANSPARENT_IDX
        for ch_idx in range(self._channels):
            y_pos = self._data_y_pos[ch_idx][data_idx]
            if self._style == "lines" and x_pos != 0:
                # Python supports negative array index
                prev_y_pos = self._data_y_pos[ch_idx][data_idx - 1]
                self._draw_vline(x_pos, prev_y_pos, y_pos, colidx)
            else:
                if 0 <= y_pos <= self._plot_height_m1:
                    self._displayio_plot[x_pos, y_pos] = colidx

    # TODO - This is a cut and paste from _undraw_bitmap()
        # TODO - This is a cut and paste from _undraw_bitmap()
            # TODO - This is a cut and paste from _undraw_bitmap()
                # TODO - This is a cut and paste from _undraw_bitmap()

    # TODO - time to clean this up and review _data_redraw()
    def _data_redraw_all(self):
        x_cols = min(self._data_values, self._plot_width)
        wrapMode = self._mode == "wrap"
        if wrapMode:
            x_data_idx = (self._data_idx - self._x_pos) % self._data_size
        else:
            x_data_idx = (self._data_idx - x_cols) % self._data_size

        for ch_idx in range(self._channels):
            colidx = self._channel_colidx[ch_idx]
            data_idx = x_data_idx
            for x_pos in range(x_cols):
                # "jump" the gap in the circular buffer for wrap mode
                if wrapMode and x_pos == self._x_pos:
                    data_idx = (data_idx + self._data_size - self._plot_width) % self._data_size
                    # TODO - inhibit line drawing in BOTH VERSIONS

                y_pos = self._data_y_pos[ch_idx][data_idx]
                if self._style == "lines" and x_pos != 0:
                    # Python supports negative array index
                    prev_y_pos = self._data_y_pos[ch_idx][data_idx - 1]
                    self._draw_vline(x_pos, prev_y_pos, y_pos, colidx)
                else:
                    if 0 <= y_pos <= self._plot_height_m1:
                        self._displayio_plot[x_pos, y_pos] = colidx
                data_idx += 1
                if data_idx >= self._data_size:
                    data_idx = 0

        self._plot_dirty = True

    # TODO - very similar code to _undraw_bitmap although that is now
    # more sophisticated as it support wrap mode
    def _data_redraw(self, x1, x2, x1_data_idx):
        """Redraw data from x1 to x2 inclusive."""
        for ch_idx in range(self._channels):
            colidx = self._channel_colidx[ch_idx]
            data_idx = x1_data_idx
            for x_pos in range(x1, x2 + 1):
                y_pos = self._data_y_pos[ch_idx][data_idx]
                if self._style == "lines" and x_pos != 0:
                    # Python supports negative array index
                    prev_y_pos = self._data_y_pos[ch_idx][data_idx - 1]
                    self._draw_vline(x_pos, prev_y_pos, y_pos, colidx)
                else:
                    if 0 <= y_pos <= self._plot_height_m1:
                        self._displayio_plot[x_pos, y_pos] = colidx
                data_idx += 1
                if data_idx >= self._data_size:
                    data_idx = 0

        self._plot_dirty = True

    def _update_stats(self, value):
        """Update the statistics for minimum and maximum."""
        if value < self._data_min:
            self._data_min = value
        if value > self._data_max:
            self._data_max = value

        ### Occasionally check if we need to add a new bucket to stats
        no_new_bucket = True
        if self._values & 0xf == 0:
            now_ns = time.monotonic_ns()
            if  now_ns - self._data_start_ns[-1] > 1e9:
                self._data_start_ns.append(now_ns)
                self._data_mins.append(value)
                self._data_maxs.append(value)
                no_new_bucket = False
                ### Remove the first elements if too long
                if len(self._data_start_ns) > self._data_stats_maxlen:
                    self._data_start_ns.pop(0)
                    self._data_mins.pop(0)
                    self._data_maxs.pop(0)

        if no_new_bucket:
            if value < self._data_mins[-1]:
                self._data_mins[-1] = value
            if value > self._data_maxs[-1]:
                self._data_maxs[-1] = value

    def _check_zoom_in(self, values):
        """Check if recent data warrants zooming in on y axis scale based on checking
           minimum and maximum times which are recorded in approximate 1 second buckets.
           Returns two element tuple with (min, max) or empty tuple for no zoom required.
           Caution is required with min == max."""
        start_idx = len(self._data_start_ns) - self.ZOOM_IN_TIME
        if start_idx < 0:
            return ()

        now_ns = time.monotonic_ns()
        if now_ns < self._plot_lastzoom_ns + self.ZOOM_IN_CHECK_TIME_NS:
            return ()
        self._plot_lastzoom_ns = now_ns

        recent_min = min(min(self._data_mins[start_idx:]), *values)
        recent_max = max(max(self._data_maxs[start_idx:]), *values)
        recent_range = recent_max - recent_min
        headroom = recent_range * self.ZOOM_HEADROOM

        ### No zoom if the range of data is near the plot range
        if (self._plot_min > recent_min - headroom
                and self._plot_max < recent_max + headroom):
            return ()

        new_plot_min = max(recent_min - headroom, self._abs_min)
        new_plot_max = min(recent_max + headroom, self._abs_max)
        return (new_plot_min, new_plot_max)

    def _data_store(self, values, data_idx):
        for ch_idx, value in enumerate(values):
            # store value and update min/max as required
            self._data_value[ch_idx][data_idx] = value
            self._update_stats(value)

    def _data_draw(self, values, x_pos, data_idx):
        offscale = False
        rescale_not_needed = True

        for ch_idx, value in enumerate(values):
            # last two parameters appear "swapped" - this deals with the
            # displayio screen y coordinate increasing downwards
            y_pos = round(mapf(value,
                               self._plot_min, self._plot_max,
                               self._plot_height_m1, 0))

            if y_pos < 0 or y_pos >= self._plot_height:
                offscale = True
                self._plot_offyscale = offscale
                if self._scale_mode == "pixel":
                    rescale_not_needed = False

            if rescale_not_needed:
                self._data_y_pos[ch_idx][data_idx] = y_pos

                if self._style == "lines" and self._x_pos != 0:
                    # Python supports negative array index
                    prev_y_pos = self._data_y_pos[ch_idx][data_idx - 1]
                    self._draw_vline(x_pos, prev_y_pos, y_pos,
                                     self._channel_colidx[ch_idx])
                    self._plot_dirty = True  # bit wrong if whole line is off screen
                else:
                    if not offscale:
                        self._displayio_plot[x_pos, y_pos] = self._channel_colidx[ch_idx]
                        self._plot_dirty = True

        return rescale_not_needed

    def _auto_plot_range(self):
        ### TODO - this MAKES NO SENSE ANY MORE AS IT IS USING EXTREMES OF DATA
        changed = False
        plot_range = self._data_max - self._data_min
        headroom = plot_range * self.ZOOM_HEADROOM
        new_plot_min = max(self._data_min - headroom, self._abs_min)
        new_plot_max = min(self._data_max + headroom, self._abs_max)

        if (new_plot_min != self._plot_min or new_plot_max != self._plot_max):
            # set new range which will also redo y tick labels if necessary
            self.y_range = (new_plot_min, new_plot_max)
            changed = True

        self._plot_offyscale = False
        return changed

    def data_add(self, values):
        # pylint: disable=too-many-branches
        data_idx = self._data_idx
        rescaled = False

        # This first check could be improved to check data in values too
        if self._x_pos == 0 and self._mode == "wrap" and self._plot_offyscale:
            rescaled = self._auto_plot_range()

        if self._offscreen and self._mode == "scroll":
            # Clear and redraw the bitmap to scroll it leftward
            #self._clear_plot_bitmap()  # 2.3 seconds at 200x201
            self._undraw_bitmap()
            if self._plot_offyscale:
                self._suppress_one_redraw = True
                rescaled = self._auto_plot_range()
            sc_data_idx = ((data_idx + self._scroll_px - self._plot_width)
                           % self._data_size)
            self._data_values -= self._scroll_px
            self._data_redraw(0, self._plot_width - 1 - self._scroll_px,
                              sc_data_idx)

            self._x_pos = self._plot_width - self._scroll_px
            self._offscreen = False

        elif (self._data_values >= self._plot_width
              and self._values >= self._plot_width and self._mode == "wrap"):
            self._undraw_column(self._x_pos, data_idx - self._plot_width)

        x_pos = self._x_pos

        ### Add the data and draw it unless a y axis is going to be rescaled
        self._data_store(values, data_idx)
        if not rescaled and self._scale_mode != "TODOFIXPIXELpixel" and self._values & 0xf == 0:
            rescale_zoom_range = self._check_zoom_in(values)
            if rescale_zoom_range:
                self.y_range = rescale_zoom_range

        rescale_needed = not self._data_draw(values, x_pos, data_idx)
        if rescale_needed:
            self._auto_plot_range()        # rescale y range
            self._data_draw(values, x_pos, data_idx)

        ### finally store the values in circular buffer
        self._data_store(values, data_idx)

        # increment the data index wrapping around
        self._data_idx += 1
        if self._data_idx >= self._data_size:
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
                self._offscreen = True
        else:
            self._x_pos = new_x_pos

        if self._data_values < self._data_size:
            self._data_values += 1

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
    def info(self):
        if self._displayio_info is None:
            return None
        return self._displayio_info.text

    @info.setter
    def info(self, value):
        """Place some text on the screen.
           Multiple lines are supported with newline character.
           Font will be 3x standard terminalio font or 2x if that does not fit."""
        if self._displayio_info is not None:
            self._displayio_graph.pop()

        if value is not None and value != "":
            font_scale = 3
            line_spacing = 1.25

            font_w, font_h = self._font.get_bounding_box()
            text_lines = value.split("\n")
            max_word_chars = max([len(word) for word in text_lines])
            ### If too large reduce the scale
            if (max_word_chars * font_scale * font_w > self._screen_width
                    or len(text_lines) * font_scale * font_h * line_spacing > self._screen_height):
                font_scale -= 1

            self._displayio_info = Label(self._font, text=value,
                                         line_spacing=line_spacing,
                                         scale=font_scale,
                                         background_color=self._INFO_FG_COLOR,
                                         color=self._INFO_BG_COLOR)
            ### centre the (left justified) text
            self._displayio_info.x = (self._screen_width
                                      - font_scale * font_w * max_word_chars) // 2
            self._displayio_info.y = self._screen_height // 2
            self._displayio_graph.append(self._displayio_info)

        else:
            self._displayio_info = None

        if self._mode == "scroll":
            self._display_refresh()

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
        y_min, y_max = minmax

        ### if values reduce range below the minimum then widen the range
        ### but keep it within the absolute min/max values
        if self._plot_min_range is not None:
            range_extend = self._plot_min_range - (y_max - y_min)
            if range_extend > 0:
                y_max += range_extend / 2
                y_min -= range_extend / 2
                if y_min < self._abs_min:
                    y_min = self._abs_min
                    y_max = y_min + self._plot_min_range
                elif y_max > self._abs_max:
                    y_max = self._abs_max
                    y_min = y_max - self._plot_min_range

        changed = False
        if minmax[0] != self._plot_min:
            self._plot_min = y_min
            changed = True
        if minmax[1] != self._plot_max:
            self._plot_max = y_max
            changed = True

        if changed:
            self.set_y_axis_tick_labels(self._plot_min, self._plot_max)
            if self._values:
                self._undraw_bitmap()
            self._recalc_y_pos()  ## calculates new y positions
            if self._values:
                if self._suppress_one_redraw:
                    self._suppress_one_redraw = False
                else:
                    self._data_redraw_all()

    @property
    def y_full_range(self):
        return (self._plot_min, self._plot_max)

    @y_full_range.setter
    def y_full_range(self, minmax):
        self._abs_min = minmax[0]
        self._abs_max = minmax[1]

    @property
    def y_min_range(self):
        return self._plot_min_range

    @y_min_range.setter
    def y_min_range(self, value):
        self._plot_min_range = value

    @property
    def y_axis_lab(self):
        return self._y_axis_lab

    @y_axis_lab.setter
    def y_axis_lab(self, text):
        self._y_axis_lab = text[:self._y_lab_width]
        font_w, _ = self._font.get_bounding_box()
        x_pos = (40 - font_w * len(self._y_axis_lab)) // 2
        ### max() used to prevent negative (off-screen) values
        self._displayio_y_axis_lab.x = max(0, x_pos)
        self._displayio_y_axis_lab.text = self._y_axis_lab

    @property
    def channel_colidx(self):
        return self._channel_colidx

    @channel_colidx.setter
    def channel_colidx(self, value):
        ### tuple() ensures object has a local / read-only copy of data
        self._channel_colidx = tuple(value)

    @property
    def mu_output(self):
        return self._mu_output

    @mu_output.setter
    def mu_output(self, value):
        self._mu_output = value
