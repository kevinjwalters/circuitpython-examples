# The MIT License (MIT)
#
# Copyright (c) 2020 Kevin J. Walters
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import unittest
from unittest.mock import Mock, MagicMock, call

import array
import numpy
import os
verbose = int(os.getenv('TESTVERBOSE', '2'))

import sys
# Mocking libraries which are about to be import'd by Plotter
sys.modules['board'] = MagicMock()
sys.modules['displayio'] = MagicMock()
sys.modules['terminalio'] = MagicMock()
sys.modules['adafruit_display_text.label'] = MagicMock()

# Borrowing the dhalbert/tannewt technique from adafruit/Adafruit_CircuitPython_Motor
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# import what we are testing
from plotter import Plotter

import terminalio  # mocked
terminalio.FONT = Mock()
terminalio.FONT.get_bounding_box = Mock(return_value=(6, 14))


# TODO use setup() and tearDown() - https://docs.python.org/3/library/unittest.html#unittest.TestCase.tearDown

class Test_Plotter(unittest.TestCase):

    _SCROLL_PX = 25

    def make_a_Plotter(self, style, mode):
        mocked_display = Mock()

        plotter = Plotter(mocked_display,
                  style=style,
                  mode=mode,
                  scroll_px=self._SCROLL_PX,
                  title="Debugging",
                  max_title_len=99,
                  mu_output=False,
                  debug=0)

        return plotter

    def ready_plot_source(self, plttr, source):
        #source_name = str(source)

        plttr.clear_all()
        #plttr.title = source_name
        #plttr.y_axis_lab = source.units()
        plttr.y_range = (source.initial_min(), source.initial_max())
        plttr.y_full_range = (source.min(), source.max())
        channels_from_source = source.values()
        plttr.channels = channels_from_source
        plttr.channel_colidx = (1, 2, 3)
        source.start()
        return (source, channels_from_source)

    def make_a_PlotSource(self, channels = 1):
        ps = Mock()
        ps.initial_min = Mock(return_value=-100.0)
        ps.initial_max = Mock(return_value=100.0)
        ps.min = Mock(return_value=-100.0)
        ps.max = Mock(return_value=100.0)
        if channels == 1:
            ps.values = Mock(return_value=channels)
            ps.data = Mock(side_effect=list(range(10,90)) * 100)
        elif channels == 3:
            ps.values = Mock(return_value=channels)
            ps.data = Mock(side_effect=list(zip(list(range(10,90)),
                                           list(range(15,95)),
                                           list(range(40,60)) * 4)) * 100)
        return ps

    def make_a_PlotSource_onespike(self):
        ps = Mock()
        ps.initial_min = Mock(return_value=-100.0)
        ps.initial_max = Mock(return_value=100.0)
        ps.min = Mock(return_value=-100.0)
        ps.max = Mock(return_value=100.0)

        ps.values = Mock(return_value=1)
        ps.data = Mock(side_effect=[0]*95 + [5,10,20,50,80,90,70,30,20,10]
                                   + [0] * 95 + [1] * 1000)

        return ps

    def make_a_PlotSource_bilevel(self, first_v=60, second_v=700):
        ps = Mock()
        ps.initial_min = Mock(return_value=-100.0)
        ps.initial_max = Mock(return_value=100.0)
        ps.min = Mock(return_value=-1000.0)
        ps.max = Mock(return_value=1000.0)

        ps.values = Mock(return_value=1)
        ps.data = Mock(side_effect=[first_v] * 199 + [second_v] * 1001)

        return ps
        
    def test_spike_after_wrap_and_overwrite_one_channel(self):
        """A specific test to check that a spike that appears in wrap mode is
           correctly cleared by subsequent flat data."""
        plotter = self.make_a_Plotter("lines", "wrap")
        (tg, plot) = (Mock(), numpy.zeros((200, 201), numpy.uint8))
        plotter.display_on(tg_and_plot=(tg, plot))
        test_source1 = self.make_a_PlotSource_onespike()
        self.ready_plot_source(plotter, test_source1)

        unique, counts = numpy.unique(plot, return_counts=True)
        self.assertTrue(numpy.alltrue(unique == [0]),
                        "Checking all pixels start as 0")

        # Fill screen
        for d_idx in range(200):
            plotter.data_add((test_source1.data(),))

        unique, counts = numpy.unique(plot, return_counts=True)
        self.assertTrue(numpy.alltrue(unique == [0, 1]),
                        "Checking pixels are now a mix of 0 and 1")

        # Rewrite whole screen with new data as we are in wrap mode
        for d_idx in range(190):
            plotter.data_add((test_source1.data(),))

        non_zero_rows = []
        for y_pos in range(0, 201):
            count = 0
            for x_pos in range(0, 200):
                if plot[x_pos, y_pos] != 0:
                    count += 1
            if count > 0:
                non_zero_rows.append(y_pos)

        if verbose >= 4:
            print("y=99", plot[:, 99])
            print("y=100", plot[:, 100])

        self.assertTrue(9 not in non_zero_rows,
                        "Check nothing is just above 90 which plots at 10")
        self.assertEqual(non_zero_rows, [99, 100],
                        "Only pixels left plotted should be from values 0 and 1 being plotted at 99 and 100")
        self.assertTrue(numpy.alltrue(plot[:, 99] == [1] * 190 + [0] * 10),
                        "Checking row 99 precisely")
        self.assertTrue(numpy.alltrue(plot[:, 100] == [0] * 190 + [1] * 10),
                        "Checking row 100 precisely")

        plotter.display_off()


    def test_clearmode_from_lines_wrap_to_dots_scroll(self):
        """A specific test to check that a spike that appears in lines wrap mode is
           correctly cleared by a change to dots scroll."""
        plotter = self.make_a_Plotter("lines", "wrap")
        (tg, plot) = (Mock(), numpy.zeros((200, 201), numpy.uint8))
        plotter.display_on(tg_and_plot=(tg, plot))
        test_source1 = self.make_a_PlotSource_onespike()
        self.ready_plot_source(plotter, test_source1)

        unique, counts = numpy.unique(plot, return_counts=True)
        self.assertTrue(numpy.alltrue(unique == [0]),
                        "Checking all pixels start as 0")

        # Fill screen then wrap to write another 20 values
        for d_idx in range(200 + 20):
            plotter.data_add((test_source1.data(),))

        unique, counts = numpy.unique(plot, return_counts=True)
        self.assertTrue(numpy.alltrue(unique == [0, 1]),
                        "Checking pixels are now a mix of 0 and 1")

        plotter.change_stylemode("dots", "scroll")
        unique, counts = numpy.unique(plot, return_counts=True)
        self.assertTrue(numpy.alltrue(unique == [0]),
                        "Checking all pixels are now 0 after change_stylemode")

        plotter.display_off()


    def test_clear_after_scrolling_one_channel(self):
        """A specific test to check screen clears after a scroll to help
           investigate a bug with that failing to happen in most cases."""
        plotter = self.make_a_Plotter("lines", "scroll")
        (tg, plot) = (Mock(), numpy.zeros((200, 201), numpy.uint8))
        plotter.display_on(tg_and_plot=(tg, plot))
        test_source1 = self.make_a_PlotSource()
        self.ready_plot_source(plotter, test_source1)

        unique, counts = numpy.unique(plot, return_counts=True)
        self.assertTrue(numpy.alltrue(unique == [0]),
                        "Checking all pixels start as 0")

        # Fill screen
        for d_idx in range(200):
            plotter.data_add((test_source1.data(),))

        unique, counts = numpy.unique(plot, return_counts=True)
        self.assertTrue(numpy.alltrue(unique == [0, 1]),
                        "Checking pixels are now a mix of 0 and 1")
        self.assertEqual(plotter._values, 200)
        self.assertEqual(plotter._data_values, 200)

        # Force a single scroll of the data
        for d_idx in range(10):
            plotter.data_add((test_source1.data(),))

        self.assertEqual(plotter._values, 200 + 10)
        self.assertEqual(plotter._data_values, 200 + 10 - self._SCROLL_PX)

        # This should clear all data and the screen
        if verbose >= 3:
            print("change_stylemode() to a new mode which will clear screen")
        plotter.change_stylemode("dots", "wrap")
        unique, counts = numpy.unique(plot, return_counts=True)
        self.assertTrue(numpy.alltrue(unique == [0]),
                        "Checking all pixels are now 0")

        plotter.display_off()

    def test_check_internal_data_three_channels(self):
        width = 200
        plotter = self.make_a_Plotter("lines", "scroll")
        (tg, plot) = (Mock(), numpy.zeros((width, 201), numpy.uint8))
        plotter.display_on(tg_and_plot=(tg, plot))
        test_triplesource1 = self.make_a_PlotSource(channels=3)

        self.ready_plot_source(plotter, test_triplesource1)

        unique, counts = numpy.unique(plot, return_counts=True)
        self.assertTrue(numpy.alltrue(unique == [0]),
                        "Checking all pixels start as 0")

        # Three data samples
        all_data = []
        for d_idx in range(3):
            all_data.append(test_triplesource1.data())
            plotter.data_add(all_data[-1])

        # all_data is now [(10, 15, 40), (11, 16, 41), (12, 17, 42)]
        self.assertEqual(plotter._data_y_pos[0][0:3],
                         array.array('i', [90, 89, 88]),
                         "channel 0 plotted y positions")
        self.assertEqual(plotter._data_y_pos[1][0:3],
                         array.array('i', [85, 84, 83]),
                         "channel 1 plotted y positions")
        self.assertEqual(plotter._data_y_pos[2][0:3],
                         array.array('i', [60, 59, 58]),
                         "channel 2 plotted y positions")

        # Fill rest of screen
        for d_idx in range(197):
            all_data.append(test_triplesource1.data())
            plotter.data_add(all_data[-1])

        # Three values more values to force a scroll
        for d_idx in range(3):
            all_data.append(test_triplesource1.data())
            plotter.data_add(all_data[-1])

        # all_data[-4] is (49, 54, 59)
        # all_data[-3:0] is [(50, 55, 40) (51, 56, 41) (52, 57, 42)]
        expected_data_size = width - self._SCROLL_PX + 3
        st_x_pos = width - self._SCROLL_PX
        d_idx = plotter._data_idx - 3

        self.assertTrue(3 < self._SCROLL_PX, "Ensure no recent scrolling")
        # the data_idx here is 2 because the size is now plot_width + 1
        self.assertEqual(plotter._data_idx, 2)
        self.assertEqual(plotter._x_pos, st_x_pos + 3)
        self.assertEqual(plotter._data_values, expected_data_size)
        self.assertEqual(plotter._values, len(all_data))

        if verbose >= 4:
            print("YP",d_idx, plotter._data_y_pos[0][d_idx:d_idx+3])
            print("Y POS", [str(plotter._data_y_pos[ch_idx][d_idx:d_idx+3])
                            for ch_idx in [0, 1, 2]])
        ch0_ypos = [50, 49, 48]
        self.assertEqual([plotter._data_y_pos[0][idx] for idx in range(d_idx, d_idx + 3)],
                         ch0_ypos,
                         "channel 0 plotted y positions")
        ch1_ypos = [45, 44, 43]
        self.assertEqual([plotter._data_y_pos[1][idx] for idx in range(d_idx, d_idx + 3)],
                         ch1_ypos,
                         "channel 1 plotted y positions")
        ch2_ypos = [60, 59, 58]
        self.assertEqual([plotter._data_y_pos[2][idx] for idx in range(d_idx, d_idx + 3)],
                         ch2_ypos,
                         "channel 2 plotted y positions")

        # Check for plot points - fortunately none overlap
        total_pixel_matches = 0
        for ch_idx, ch_ypos in enumerate((ch0_ypos, ch1_ypos, ch2_ypos)):
            expected = plotter.channel_colidx[ch_idx]
            for idx, y_pos in enumerate(ch_ypos):
                actual = plot[st_x_pos+idx, y_pos]
                if actual == expected:
                    total_pixel_matches += 1
                else:
                    if verbose >= 4:
                        print("Pixel value for channel",
                              "{:d}, naive expectation {:d},".format(ch_idx,
                                                                     expected),
                              "actual {:d} at {:d}, {:d}".format(idx, actual,
                                                                 st_x_pos+idx,
                                                                 y_pos))
        # Only 7 out of 9 will match because channel 2 put a vertical
        # line at x position 175 over-writing ch0 and ch1
        self.assertEqual(total_pixel_matches, 7, "plotted pixels check")
        # Check for that line from pixel positions 42 to 60
        for y_pos in range(42, 60 + 1):
            self.assertEqual(plot[st_x_pos, y_pos],
                             plotter.channel_colidx[2],
                             "channel 2 (over-writing) vertical line")

        plotter.display_off()

    def test_clear_after_scrolling_three_channels(self):
        """A specific test to check screen clears after a scroll with
           multiple channels being plotted (three) to help
           investigate a bug with that failing to happen in most cases
           for the second and third channels."""
        plotter = self.make_a_Plotter("lines", "scroll")
        (tg, plot) = (Mock(), numpy.zeros((200, 201), numpy.uint8))
        plotter.display_on(tg_and_plot=(tg, plot))
        test_triplesource1 = self.make_a_PlotSource(channels=3)

        self.ready_plot_source(plotter, test_triplesource1)

        unique, counts = numpy.unique(plot, return_counts=True)
        self.assertTrue(numpy.alltrue(unique == [0]),
                        "Checking all pixels start as 0")

        # Fill screen
        for d_idx in range(200):
            plotter.data_add(test_triplesource1.data())

        unique, counts = numpy.unique(plot, return_counts=True)
        self.assertTrue(numpy.alltrue(unique == [0, 1, 2, 3]),
                        "Checking pixels are now a mix of 0, 1, 2, 3")
        # Force a single scroll of the data
        for d_idx in range(10):
            plotter.data_add(test_triplesource1.data())

        # This should clear all data and the screen
        if verbose >= 3:
            print("change_stylemode() to a new mode which will clear screen")
        plotter.change_stylemode("dots", "wrap")
        unique, counts = numpy.unique(plot, return_counts=True)
        self.assertTrue(numpy.alltrue(unique == [0]),
                        "Checking all pixels are now 0")

        plotter.display_off()

    def test_auto_rescale_wrap_mode(self):
        """Ensure the auto-scaling is working and not leaving any remnants of previous plot."""
        plotter = self.make_a_Plotter("lines", "wrap")
        (tg, plot) = (Mock(), numpy.zeros((200, 201), numpy.uint8))
        plotter.display_on(tg_and_plot=(tg, plot))
        test_source1 = self.make_a_PlotSource_bilevel(first_v=60, second_v=900)

        self.ready_plot_source(plotter, test_source1)

        unique, counts = numpy.unique(plot, return_counts=True)
        self.assertTrue(numpy.alltrue(unique == [0]),
                        "Checking all pixels start as 0")

        # Fill screen with first 200
        for d_idx in range(200):
            plotter.data_add((test_source1.data(),))

        non_zero_rows = []
        for y_pos in range(0, 201):
            count = 0
            for x_pos in range(0, 200):
                if plot[x_pos, y_pos] != 0:
                    count += 1
            if count > 0:
                non_zero_rows.append(y_pos)

        self.assertEqual(non_zero_rows, list(range(0, 40 + 1)),
                        "From value 60 being plotted at 40 but also upward line at end")

        # Rewrite screen with next 200 but these should force an internal
        # rescaling of y axis
        for d_idx in range(200):
            plotter.data_add((test_source1.data(),))

        self.assertEqual(plotter.y_range, (-108.0, 1000.0),
                         "Check rescaled y range")

        non_zero_rows = []
        for y_pos in range(0, 201):
            count = 0
            for x_pos in range(0, 200):
                if plot[x_pos, y_pos] != 0:
                    count += 1
            if count > 0:
                non_zero_rows.append(y_pos)

        self.assertEqual(non_zero_rows, [18],
                        "Only pixels now should be from value 900 being plotted at 18")

        plotter.display_off()


if __name__ == '__main__':
    unittest.main(verbosity=verbose)
