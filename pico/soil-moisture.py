### soil-moisture.py v1.3
### Show soil moisture on SSD1306 screen using resistive and capacitive sensors

### Tested with Pi Pico and 6.2.0-beta.2-182-g24fdda038

### copy this file to Cytron Maker Pi Pico as code.py

### MIT License

### Copyright (c) 2021 Kevin J. Walters

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

### This displays the analogue outputs of a
### capacitive Grove moisture sensor (corrosion resistant) v1.0 on GP27 and a
### resistive generic moisture sensor on GP26 powered by GP16
### on an i2c SSD1306 LED screen on GP0 (SDA) and GP1 (SCL) marked Grove 1
### on the Maker Pi Pico board

import time
import random
import math
import gc

import board
import digitalio
import analogio
import displayio
import terminalio
import busio
import neopixel
import gamepad

import adafruit_displayio_ssd1306
import adafruit_display_shapes.polygon
import adafruit_display_shapes.triangle
import adafruit_display_shapes.rect
from adafruit_display_text.label import Label


debug = 1

### Time to wait after powering up the resistive sensor
### this is just a guess and may not even be needed

RES_SETTLE_TIME = 0.050  ### 50ms
LOOP_INTERVAL = 0.5  ### in seconds, used for sleep in loop
RESISTIVE_MEASURE = 20  ### Measure resistance every 20 loop iterations

SSD1306_ADDR = 0x3c
SSD1306_WIDTH = 128
SSD1306_HEIGHT = 64
SSD1306_SDA_PIN = board.GP0
SSD1306_SCL_PIN = board.GP1
SOIL_CAP_SIG_PIN = board.GP27
SOIL_RES_SIG_PIN = board.GP26
SOIL_RES_PWR_PIN = board.GP16

MPP_BUTTON_LEFT_PIN = board.GP20
MPP_BUTTON_MIDDLE_PIN = board.GP21
MPP_BUTTON_RIGHT_PIN = board.GP22
MPP_NEOPIXEL_PIN = board.GP28

### NeoPixel colours
BLACK = (0, 0, 0)


def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


def get_value(ain, samples=500):
    return sum([ain.value for _ in range(samples)]) / samples


class Moisture:
    VREF = 3.3
    GOOD_COLOUR = (0, 30, 0)     ### green
    DRY_COLOUR = (45, 18, 0)     ### orange
    TOODRY_COLOUR = (60, 0, 0)   ### red (used for flashing too)
    TOOWET_COLOUR = (40, 0, 40)  ### magneta

    def __init__(self, sensor_type, model="linear", vref=VREF):
        if sensor_type.lower() == "generic resistive":
            ### A generic resisitive pcb soil sensor measuring voltage
            ### across soil with 1k on upper half of potential divider
            self._arid = 65535.0    ### 3.3V
            self._sodden = 10000.0  ### 0.503V
            datafit1_rtp = self.dfs_res_raw_to_percent
        elif sensor_type.lower() == "grove capacitive":
            ### The Seeed Studio Grove Capacitive Soil Moisture Sensor v1.0
            self._arid = 38000.0    ### 1.913V
            self._sodden = 22000.0  ### 1.108V
            datafit1_rtp = self.dfs_cap_raw_to_percent
        else:
            raise ValueError("Unknown sensor_type: " + sensor_type)
        self.sensor_type = sensor_type

        self._lower = min(self._arid, self._sodden)
        self._range = abs(self._sodden - self._arid)
        self._inverted = (self._arid > self._sodden)
        self._vref = vref

        ### replace method
        if model == "linear":
            self.raw_to_percent = self.linear_raw_to_percent
        elif model == "datafit1":
            self.raw_to_percent = datafit1_rtp
        else:
            raise ValueError("Unknown model: " + model)
        self.model = model

    @classmethod
    def moisture_to_color(cls, percents):
        """Take multiple values and returns RGB colour and flashing boolean.
           The smallest percentage is used for dryness colour.
        """
        p_colour = cls.GOOD_COLOUR
        p_flash = False
        for percent in percents:
            if percent <= 35:
                p_colour = cls.TOODRY_COLOUR
            elif percent <= 45 and p_colour != cls.TOODRY_COLOUR:
                p_colour = cls.DRY_COLOUR
            elif percent >= 80:
                p_colour = cls.TOOWET_COLOUR

            if percent <= 20:
                p_flash = True

        return (p_colour, p_flash)


    def raw_to_percent(self, raw_adc):  ### pylint: disable=method-hidden
        raise NotImplementedError("This method is replaced in constructor...")

    def linear_raw_to_percent(self, raw_adc):
        fraction = (raw_adc - self._lower) / self._range
        if self._inverted:
            fraction = 1.0 - fraction
        return min(100.0, max(0.0, fraction * 100.0))

    def dfs_cap_raw_to_percent(self, raw_adc):
        """This is a formula from a crude manual approximate fit of two curves
           to the data from a simple and possibly flawed soil rehydration experiment.
           0:60 y=1.8579 - 0.00007*(ml^2))
           y=1.606 cutover
           60:280 y=11/(ml-31)+1.2266)
           """

        voltage = raw_adc / 65535.0 * self._vref
        if voltage > 1.606:
            try:
                ml = math.sqrt((1.8579 - voltage) / 0.00007)
            except ValueError:
                ml = 0.0
        else:
            ml = 11 / (1.60591 - 1.2266) + 31

        fraction = ml / 300.0

        return min(100.0, max(0.0, fraction  * 100.0))

    def dfs_res_raw_to_percent(self, raw_adc):
        """This is a formula from a crude manual approximate fit of two curves
           to the data from a simple and possibly flawed soil rehydration experiment.
           0:50 y=3.25 - 0.00036*(ml^2))
           y=2.35 cutover
           50:280 y= 2.7347 -  0.15 * log(ml-37)
           """

        voltage = raw_adc / 65535.0 * self._vref
        if voltage > 2.35:
            try:
                ml = math.sqrt((3.25 - voltage) / 0.00036)
            except ValueError:
                ml = 0.0
        else:
            ml = math.exp((2.7347 - voltage) / 0.15) + 37

        fraction = ml / 300.0

        return min(100.0, max(0.0, fraction  * 100.0))


class FakeGamePad:
    def __init__(self, *digins):
        self._digin = digins
        for digio in digins:
            digio.pull = digitalio.Pull.UP

    def get_pressed(self):
        """This is a poor emulation as does not indicate presses in the past."""
        pins_pressed = 0
        for digio in self._digin:
            pins_pressed <<= 1
            pins_pressed |= int(not digio.value)
        return pins_pressed


class Pot:
    def __init__(self, compartments=2, *, level=0, width=50, x=None, y=None):

        self._compartments = compartments
        self._width = width
        self._soil_height = 42
        self._soil_bottom_y = 46
        self._compartment_width = (width - 22) // 2
        self._disp_group = displayio.Group(max_size=1 + 2 * compartments)
        if x is not None:
            self._disp_group.x = x
        if y is not None:
            self._disp_group.y = y
        self._empty_pot = adafruit_display_shapes.polygon.Polygon([(0, 0),
                                                                   (10, 47),
                                                                   (width - 11, 47),
                                                                   (width - 1, 0),
                                                                   (width - 3, 4),
                                                                   (2, 4)],
                                                                  outline=0xffffff)
        self._disp_group.append(self._empty_pot)
        self._empty_compartment = [displayio.Group(max_size=2)
                                   for _ in range(compartments)]
        for comp in self._empty_compartment:
            self._disp_group.append(comp)

        self._level = [None] * compartments
        self._pixel_level = [None] * compartments
        if level is not None:
            for idx in range(compartments):
                self[idx] = level


    def _calc_pixel_level(self, level):
        return round(level / 100.0 * self._soil_height)


    def _draw_level(self, comp_idx, new_pix_level):
        ### Remove all displayio objects that were in the group
        group = self._disp_group[comp_idx + 1]
        while len(group) > 0:
            _ = group.pop()
        if new_pix_level == 0:
            return

        top = self._soil_bottom_y - new_pix_level + 1
        part1 = adafruit_display_shapes.rect.Rect(11 + self._compartment_width * comp_idx,
                                                  top,
                                                  self._compartment_width,
                                                  new_pix_level,
                                                  fill=0xffffff)
        group.append(part1)

        ### These triangles aren't quite perfectly aligned but it looks fine
        part2 = None
        if comp_idx == 0:  ### far left
            x_pos = 11
            part2 = adafruit_display_shapes.triangle.Triangle(x_pos - 1,
                                                              self._soil_bottom_y,
                                                              x_pos - 10 * new_pix_level // self._soil_height,
                                                              top,
                                                              x_pos - 1,
                                                              top,
                                                              fill=0xffffff)
        elif comp_idx == self._compartments - 1:  ### far right
            x_pos = 11 + self._compartment_width * self._compartments
            part2 = adafruit_display_shapes.triangle.Triangle(x_pos,
                                                              self._soil_bottom_y,
                                                              x_pos + 10 * new_pix_level // self._soil_height,
                                                              top,
                                                              x_pos,
                                                              top,
                                                              fill=0xffffff)
        if part2:
            group.append(part2)


    def __getitem__(self, idx):
        return self._level[idx]

    def __setitem__(self, idx, value):
        self._level[idx] = value
        new_pixel_level = self._calc_pixel_level(value)
        if self._pixel_level[idx] != new_pixel_level:
            self._draw_level(idx, new_pixel_level)
            self._pixel_level[idx] = new_pixel_level

    @property
    def group(self):
        return self._disp_group


class Anim:
    ### Data is 16 pixels wide
    _FRAMES = (((8, 19, 1),),
               ((7, 19, 1),),
               ((7, 18, 1),),
               ((8, 18, 1),),
               ((8, 17, 1),),
               ((7, 17, 1),),
               ((7, 16, 1),),
               ((8, 16, 1),),
               ((8, 15, 1),),
               ((7, 15, 1),),
               ((7, 14, 1),),
               ((8, 14, 1),),
               ((8, 13, 1),),
               ((7, 13, 1),),
               ((7, 12, 1), (8, 12, 1)),
               ((7, 11, 1), (8, 11, 1)),
               ((7, 10, 1), (8, 10, 1)),
               ((7, 9, 1), (8, 9, 1)),
               ((7, 8, 1), (8, 8, 1)),
               ((7, 7, 1), (8, 7, 1)),
               ((7, 7, 1), (8, 7, 1)),
               ((7, 6, 1), (8, 6, 1)),
               ((6, 6, 1), (9, 6, 1)),
               ((6, 5, 1), (9, 5, 1)),
               ((6, 5, 1), (9, 5, 1)),
               ((5, 5, 1), (10, 5, 1), (5, 4, 1), (10, 4, 1)),
               ((5, 3, 1), (10, 3, 1), (7, 5, 1), (8, 5, 1)),
               ((5, 2, 1), (10, 2, 1), (6, 4, 1), (9, 4, 1)),
               ((5, 1, 1), (10, 1, 1), (7, 4, 1), (8, 4, 1)),
               ((6, 2, 1), (9,  2, 1), (7, 3, 1), (8, 3, 1)),
               ((6, 1, 1), (9,  1, 1), (7, 2, 1), (8, 2, 1)),
               ((7, 1, 1), (8, 1, 1)),
               ((6, 10, 1), (9, 10, 1)),
               ((5, 10, 1), (10, 10, 1)),
               ((4, 10, 1), (11, 10, 1)),
               ((3, 10, 1), (12, 10, 1)),
               ((2, 10, 1), (13, 10, 1)),
               ((1, 9, 1), (1, 11, 1), (14, 9, 1), (14, 11, 1)),
               ((0, 9, 1), (0, 11, 1), (15, 9, 1), (15, 11, 1)),
               ((5, 0, 1),),
               ((7, 0, 1),),
               ((9, 0, 1),)
              )

    _LOOP = (((3, 10, 0), (12, 10, 0), (2, 10, 0), (13, 10, 0), (1, 9, 0), (1, 11, 0), (14, 9, 0), (14, 11, 0), (0, 9, 0), (0, 11, 0), (15, 9, 0), (15, 11, 0),
              (3, 9, 1), (12, 11, 1), (2, 9, 1), (13, 11, 1), (1, 8, 1), (1, 10, 1), (14, 10, 1), (14, 12, 1), (0, 8, 1), (0, 10, 1), (15, 10, 1), (15, 12, 1)),
             ((3, 9, 0), (12, 11, 0), (2, 9, 0), (13, 11, 0), (1, 8, 0), (1, 10, 0), (14, 10, 0), (14, 12, 0), (0, 8, 0), (0, 10, 0), (15, 10, 0), (15, 12, 0),
              (3, 10, 1), (12, 10, 1), (2, 10, 1), (13, 10, 1), (1, 9, 1), (1, 11, 1), (14, 9, 1), (14, 11, 1), (0, 9, 1), (0, 11, 1), (15, 9, 1), (15, 11, 1)),
             ((3, 10, 0), (12, 10, 0), (2, 10, 0), (13, 10, 0), (1, 9, 0), (1, 11, 0), (14, 9, 0), (14, 11, 0), (0, 9, 0), (0, 11, 0), (15, 9, 0), (15, 11, 0),
              (3, 11, 1), (12, 9, 1), (2, 11, 1), (13, 9, 1), (1, 10, 1), (1, 12, 1), (14, 8, 1), (14, 10, 1), (0, 10, 1), (0, 12, 1), (15, 8, 1), (15, 10, 1)),
             ((3, 11, 0), (12, 9, 0), (2, 11, 0), (13, 9, 0), (1, 10, 0), (1, 12, 0), (14, 8, 0), (14, 10, 0), (0, 10, 0), (0, 12, 0), (15, 8, 0), (15, 10, 0),
              (3, 10, 1), (12, 10, 1), (2, 10, 1), (13, 10, 1), (1, 9, 1), (1, 11, 1), (14, 9, 1), (14, 11, 1), (0, 9, 1), (0, 11, 1), (15, 9, 1), (15, 11, 1))
            )

    def __init__(self, x=None, y=None, loop=True):
        self._bitmap = displayio.Bitmap(36, 20, 2)
        self._palette = displayio.Palette(2)
        self._palette[0] = 0x000000
        self._palette[1] = 0xffffff

        self._tile_grid = displayio.TileGrid(self._bitmap,
                                             pixel_shader=self._palette)
        if x is not None:
            self._tile_grid.x = x
        if y is not None:
            self._tile_grid.y = y

        self._anim_offset_x = (self._bitmap.width - 16) // 2
        self._anim_offset_y = 0

        self._frame = 0
        self._frame_loop = 0
        self._loop = loop

    def nextFrame(self):
        if self._frame < len(self._FRAMES):
            pixel_list = self._FRAMES[self._frame]
            self._frame += 1
        elif self._loop:
            pixel_list = self._LOOP[self._frame_loop % len(self._LOOP)]
            self._frame_loop += 1
        else:
            return False

        for x, y, col_idx in pixel_list:
            self._bitmap[x + self._anim_offset_x,
                         y + self._anim_offset_y] = col_idx

        return True

    @property
    def tile_grid(self):
        return self._tile_grid


### CircuitPython will use an initalised display for a persistent console
### so release this if this has happened and re-initialise
displayio.release_displays()

### If screen is dead or not present
### ValueError: Unable to find I2C Display at 3c
### RuntimeError: No pull up found on SDA or SCL; check your wiring
try:
    i2c = busio.I2C(SSD1306_SCL_PIN, SSD1306_SDA_PIN, frequency=400 * 1000)
    display_bus = displayio.I2CDisplay(i2c, device_address=SSD1306_ADDR)
    display = adafruit_displayio_ssd1306.SSD1306(display_bus,
                                                 width=SSD1306_WIDTH,
                                                 height=SSD1306_HEIGHT)
except (ValueError, RuntimeError, OSError):
    display = None

if display:
    main_group = displayio.Group(max_size=7)
    display.show(main_group)

pixel = neopixel.NeoPixel(MPP_NEOPIXEL_PIN, 1)

d_print(1, "T-10")
time.sleep(10)

d_print(1, "GamePad launch")
### GamePad scans buttons constantly and provide debounce
LEFT, MIDDLE, RIGHT = ((1 << x) for x in range(2, 0 - 1, -1))

### https://github.com/adafruit/circuitpython/issues/4166
### GamePad currently kaput
##buttons = gamepad.GamePad(*[digitalio.DigitalInOut(p)
buttons = FakeGamePad(*[digitalio.DigitalInOut(p)
                        for p in (MPP_BUTTON_LEFT_PIN,
                                  MPP_BUTTON_MIDDLE_PIN,
                                  MPP_BUTTON_RIGHT_PIN)])
d_print(1, "GamePad has cleared the tower")

if display:
    pot = Pot(width=50,
              x=(display.width - 50) // 2,  ### centre
              y = 16   ### place in cyan section of screen
              )
    main_group.append(pot.group)


soil_res_type = "generic resistive"
soil_res = analogio.AnalogIn(SOIL_RES_SIG_PIN)
soil_res_pwr = digitalio.DigitalInOut(SOIL_RES_PWR_PIN)
soil_res_pwr.direction = digitalio.Direction.OUTPUT
soil_res_conv = (Moisture(soil_res_type,
                          model="linear",
                          vref=soil_res.reference_voltage),
                 Moisture(soil_res_type,
                          model="datafit1",
                          vref=soil_res.reference_voltage))

soil_cap_type = "grove capacitive"
soil_cap = analogio.AnalogIn(SOIL_CAP_SIG_PIN)
soil_cap_conv = (Moisture(soil_cap_type,
                          model="linear",
                          vref=soil_cap.reference_voltage),
                 Moisture(soil_cap_type,
                          model="datafit1",
                          vref=soil_cap.reference_voltage))

### Lower-case are risky due to descenders going from yellow
### into the cyan section of screen
### (yellow first 16, slight gap, cyan 48 remaining)
RAW_LEN = 5
if display:
    title = Label(terminalio.FONT, text="Res - Moisture - Cap", x=4, y=6)

    ### 5 digits for 16 bit raw values
    raw_blank = " " * RAW_LEN
    soil_res_raw_text = Label(terminalio.FONT,
                              text=raw_blank,
                              x=0, y=34)
    soil_cap_raw_text = Label(terminalio.FONT,
                              text=raw_blank,
                              x=display.width - len(raw_blank) * 1 * 6, y=34)

    soil_res_text = Label(terminalio.FONT,
                          text="--%",
                          x=0, y=54, scale=2)
    soil_cap_text = Label(terminalio.FONT,
                          text="--%",
                          x=display.width - 3 * 2 * 6, y=54, scale=2)

    ### Five items plus animation plus pot = 7
    main_group.append(title)
    main_group.append(soil_res_text)
    main_group.append(soil_cap_text)
    main_group.append(soil_res_raw_text)
    main_group.append(soil_cap_raw_text)
else:
    soil_res_raw_text = None
    soil_cap_raw_text = None

mu_output = True
raw_mode = False
anim = None
anim_enabled = True
anim_started = False
anim_start_ns = None
anim_complete = False
flash_toggle = False
res_raw = cap_raw = 0
### The index of the object use for
pct_conv_idx = 0
colour = BLACK
flash = False

count = 0
start_ns = time.monotonic_ns()
while True:
    count += 1
    now_ns = time.monotonic_ns()
    if display and anim_enabled:
        if anim_started and (now_ns - anim_start_ns) > 35e9:
            main_group.remove(anim.tile_grid)
            del anim
            anim_started = False
        elif (not anim_started
              and colour == Moisture.GOOD_COLOUR
              and random.random() < 0.01):
            anim = Anim(x=46, y=0)
            main_group.append(anim.tile_grid)
            anim_start_ns = now_ns
            anim_started = True

    presses = buttons.get_pressed()
    if presses & LEFT:
        pct_conv_idx = (pct_conv_idx + 1) % min(len(soil_res_conv),
                                                len(soil_cap_conv))
        ### Borrow the raw value text for name of the model
        s_model = soil_res_conv[pct_conv_idx].model
        if soil_res_raw_text and soil_cap_raw_text:
            soil_res_raw_text.text = s_model[0:RAW_LEN]
            soil_cap_raw_text.text = s_model[RAW_LEN:RAW_LEN * 2]
            time.sleep(1.0)
            soil_res_raw_text.text = raw_blank
            soil_cap_raw_text.text = raw_blank
    if presses & MIDDLE:
        mu_output = not mu_output
    if presses & RIGHT:
        raw_mode = not raw_mode
        if display and not raw_mode:
            soil_res_raw_text.text = raw_blank
            soil_cap_raw_text.text = raw_blank

    if count % RESISTIVE_MEASURE == 1:
        gc.collect()
        soil_res_pwr.value = True
        time.sleep(RES_SETTLE_TIME)
        res_raw = get_value(soil_res)
        soil_res_pwr.value = False

    cap_raw = get_value(soil_cap)

    if display and raw_mode:
        soil_res_raw_text.text = "{:5d}".format(round(res_raw))
        soil_cap_raw_text.text = "{:5d}".format(round(cap_raw))

    ##res_pctint = round(res_raw / 65535.0 * 100.0)
    ##cap_pctint = round(cap_raw / 65535.0 * 100.0)
    res_pctint = round(soil_res_conv[pct_conv_idx].raw_to_percent(res_raw))
    cap_pctint = round(soil_cap_conv[pct_conv_idx].raw_to_percent(cap_raw))

    if display:
        soil_res_text.text = "{:2d}%".format(min(99, res_pctint))
        soil_cap_text.text = "{:2d}%".format(min(99, cap_pctint))
        pot[0] = res_pctint
        pot[1] = cap_pctint

    if mu_output:
        if raw_mode:
            print((res_raw, cap_raw))
        else:
            print((res_pctint, cap_pctint))

    colour, flash = Moisture.moisture_to_color((res_pctint, cap_pctint))
    if flash:
        if flash_toggle:
            pixel[0] = colour
        else:
            pixel[0] = BLACK
        flash_toggle = not flash_toggle
    else:
        pixel[0] = colour

    if anim_started and not anim_complete:
        anim_complete = not anim.nextFrame()
    time.sleep(0.5)
