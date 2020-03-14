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

from plotter import Plotter

import terminalio  # mocked

def t_f_gbb():
    return (6, 14)

terminalio.FONT = Mock()
terminalio.FONT.get_bounding_box = t_f_gbb


class Test_Plotter(unittest.TestCase):

    def make_a_Plotter(self, style, mode):
        mocked_display = Mock()
        
        plotter = Plotter(mocked_display,
                  style=style,
                  mode=mode,
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

    def make_a_PlotSource(self):
        ps = Mock()
        ps.initial_min = Mock(return_value=0)
        ps.initial_max = Mock(return_value=100)
        ps.min = Mock(return_value=0.0)
        ps.max = Mock(return_value=100.0)
        ps.values = Mock(return_value=1)
        ps.data = Mock(side_effect=list(range(10,90)) * 100)
        return ps

    def test_scrolling(self):
        plotter = self.make_a_Plotter("lines", "scroll")
        (tg, plot) = (Mock(), numpy.zeros((200, 201), numpy.uint8))
        plotter.display_on(tg_and_plot=(tg, plot))
        test_source1 = self.make_a_PlotSource()
        self.ready_plot_source(plotter, test_source1)
        
        print("")
        unique, counts = numpy.unique(plot, return_counts=True)
        print(unique, counts)
        
        # Fill screen
        for d_idx in range(200):
            plotter.data_add((test_source1.data(),))

        unique, counts = numpy.unique(plot, return_counts=True)
        print(unique, counts)
        
        # Force a single scroll of the data
        for d_idx in range(10):
            plotter.data_add((test_source1.data(),))
        
        # This should clear all data
        plotter.change_stylemode("lines", "scroll")
        unique, counts = numpy.unique(plot, return_counts=True)
        print(unique, counts)
        self.assertTrue(numpy.alltrue(unique == [0]),
                        "Checking all pixels are now 0")
        
        plotter.display_off()
        
        woohoo = True  # interested in getting to here
        self.assertTrue(woohoo)


if __name__ == '__main__':
    unittest.main(verbosity=verbose)
