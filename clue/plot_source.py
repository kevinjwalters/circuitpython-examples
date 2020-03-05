### plot_source v1.0
### Library for sensorCircuitPython on CLUE sensor and input plotter
### This plots the sensors and analogue inputs in a style similar to
### an oscilloscope

### Tested with an Adafruit CLUE Alpha and CircuitPython and 5.0.0

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

import math

import board
import analogio

# There's a form of on-demand instanitation for touch pads
# but analogio can be used if touch_0 - touch_3 have not been used
from adafruit_clue import clue

# debug = 2

# remember this was a p3.reference_voltage which is 3.3
# p3 = analogio.AnalogIn(board.P3)

### if clue.touch_3 has not been used then it doesn't instantiate
### the TouchIn object so there's no problem with creating an AnalogIn

### TODO - lots of documentation on meaning/use of all these parameters
class PlotSource():   
    DEFAULT_COLORS = (0xffff00, 0x00ffff, 0xff0080)
    RGB_COLORS = (0xff0000, 0x00ff00, 0x0000ff)

    def __init__(self, values, name, units="",
                 min=0, max=65535, initial_min=None, initial_max=None,
                 rate=None, colors=None):
        self._name = name
        self._values = values
        self._units = units
        self._min = min
        self._max = max
        if initial_min is not None:
            self._initial_min = initial_min
        else:
            self._initial_min = min
        if initial_max is not None:
            self._initial_max = initial_max
        else:
            self._initial_max = max
        self._rate = rate
        if colors is not None:
            self._colors = colors
        else:
            self._colors = self.DEFAULT_COLORS[:values]

    def __str__(self):
        return self._name

    def data(self):
        return None

    def min(self):
        return self._min

    def max(self):
        return self._max

    def initial_min(self):
        return self._initial_min

    def initial_max(self):
        return self._initial_max

    def start(self):
        pass

    def stop(self):
        pass

    def values(self):
        return self._values

    def units(self):
        return self._units

    def rate(self):
        return self._rate

    def colors(self):
        return self._colors


### This over-reads presumably due to electronics warming boards update
### plus it looks odd on close inspection as it climbs about 0.1 as being read
class TemperaturePlotSource(PlotSource):
    def _convert(self, value):
        return value * self._scale + self._offset

    def __init__(self, clue, type="C"):
        self._clue = clue
        if type[0] == "F":
            type_name = "Fahrenheit"
            self._scale = 1.8
            self._offset = 32.0
        elif type[0] == "K":
            type_name = "Kelvin"
            self._scale = 1.0
            self._offset = -273.15
        else:
            type_name = "Celsius"
            self._scale = 1.0
            self._offset = 0.0
        super().__init__(1, "Temperature (" + type_name[0] + ")",
                         min=self._convert(0),
                         max=self._convert(100),
                         initial_min=self._convert(10),
                         initial_max=self._convert(40),
                         rate=24)

    def data(self):
        return self._convert(self._clue.temperature)


### The 300, 1100 values are in adafruit_bmp280 but are private variables
class PressurePlotSource(PlotSource):
    def __init__(self, clue):
        self._clue = clue
        super().__init__(1, "Pressure (hPa)",
                         min=300, max=1100, initial_min=980, initial_max=1040,
                         rate=22)

    def data(self):
        return self._clue.pressure


class ProximityPlotSource(PlotSource):
    def __init__(self, clue):
        self._clue = clue
        super().__init__(1, "Proximity",
                         min=0, max=255,
                         rate=720)

    def data(self):
        return self._clue.proximity


class HumidityPlotSource(PlotSource):
    def __init__(self, clue):
        self._clue = clue
        super().__init__(1, "Rel. Humidity (%)",
                         min=0, max=100, initial_min=20, initial_max=60,
                         rate=54)

    def data(self):
        return self._clue.humidity


class PinPlotSource(PlotSource):
    def __init__(self, pin):
        try:
            pins = [p for p in pin]
        except:
            pins = [pin]

        self._pins = pins
        self._analogin = [analogio.AnalogIn(p) for p in pins]
        super().__init__(len(pins),
                         "Pad: " + ", ".join([str(p).split('.')[-1] for p in pins]),
                         rate=10000)

    def data(self):
        if len(self._pins) == 1:
            return self._analogin[0].value
        else:
            return [ana.value for ana in self._analogin]

    def pins(self):
        return self._pins


### TODO - consider returning colour hints or alternative colours
class ColorPlotSource(PlotSource):
    def __init__(self, clue):
        self._clue = clue
        super().__init__(3, "Color: R, G, B",
                         min=0, max=8000,  ### 7169 looks like max
                         colors=self.RGB_COLORS,
                         rate=100)

    def data(self):
        (r, g, b, c) = self._clue.color
        return (r, g, b)

    def start(self):
        ### These values will affect the maximum return value
        ### Set APDS9660 to sample every (256 - 249 ) * 2.78 = 19.46ms
        self._clue._sensor.integration_time = 249 # 19.46ms, ~ 50Hz
        self._clue._sensor.color_gain = 0x02 # 16x (library default is 4x)


class IlluminatedColorPlotSource(PlotSource):
    def __init__(self, clue, colour):
        self._clue = clue
        if colour[0] == "R":
            self._channel = "R"
            rgb_idx = 0
        elif colour[0] == "G":
            self._channel = "G"
            rgb_idx = 1
        elif colour[0] == "B":
            self._channel = "B"
            rgb_idx = 2
        else:
            raise ValueError("colour must be Red, Green or Blue")

        super().__init__(1, "Ilum. color: " + self._channel,
                         min=0, max=8000,
                         initial_min=100, initial_max=700,
                         colors=(self.RGB_COLORS[rgb_idx],),
                         rate=100)

    ### for VALUE of 1, returns int or float
    ### for VALUE > 1, returns tuple of aforementioned
    def data(self):
        (r, g, b, c) = self._clue.color
        if self._channel == "R":
            return r
        elif self._channel == "G":
            return g
        elif self._channel == "B":
            return b
        else:
            return None  ### This should never happen

    def start(self):
        ### Set APDS9660 to sample every (256 - 249 ) * 2.78 = 19.46ms
        self._clue._sensor.integration_time = 249 # 19.46ms, ~ 50Hz
        self._clue._sensor.color_gain = 0x03 # 64x (library default is 4x)

        self._clue.white_leds = True

    def stop(self):
        self._clue.white_leds = False


class VolumePlotSource(PlotSource):
    def __init__(self, clue):
        self._clue = clue
        super().__init__(1, "Volume (dB)",
                         min=0, max=97+3,   ### 97dB is 16bit dynamic range
                         initial_min=10, initial_max=60,
                         rate=41)

    _LN_CONVERSION_FACTOR = 20 / math.log(10)

    def data(self):
        return (math.log(self._clue.sound_level + 1)
                * self._LN_CONVERSION_FACTOR)


### TODO - this is not a blocking read for new data,
###        data comes back faster (500Hz) than it changes
###        if read in a tight loop
class GyroPlotSource(PlotSource):
    def __init__(self, clue):
        self._clue = clue
        super().__init__(3, "Gyro (dps?)",
                         min=-287-13, max=287+13,  ### 286.703 appears to be max
                         initial_min=-100, initial_max=100,
                         colors=self.RGB_COLORS,
                         rate=500)

    def data(self):
        return clue.gyro


class AccelerometerPlotSource(PlotSource):
    def __init__(self, clue):
        self._clue = clue
        super().__init__(3, "Accelerometer (g)",
                         min=-40, max=40,  ### 39.1992 approx max
                         initial_min=-20, initial_max=20,
                         colors=self.RGB_COLORS,
                         rate=500)

    def data(self):
        return clue.acceleration


class MagnetometerPlotSource(PlotSource):
    def __init__(self, clue):
        self._clue = clue
        super().__init__(3, "Magnetometer (uT)",
                         min=-479-21, max=479+21,  ### 478.866 approx max
                         initial_min=-80, initial_max=80,  ### Earth around 60uT
                         colors=self.RGB_COLORS,
                         rate=500)

    def data(self):
        return clue.magnetic


