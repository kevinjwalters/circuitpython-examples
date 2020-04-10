### data-rep-calc v0.11
### A calculator which also shows the floating point data representation

### Tested with an Adafruit CLUE (Alpha) and CircuitPython and 5.1.0

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

import time
import math
import struct

import board
import displayio
import terminalio

### TODO negative number
### TODO flip between op1 / op2
### TODO show operator
### TODO change operator
### TODO calculate result using CP's FP

### TODO make this work for bluefruit + gizmo too
### And PyGamer / any Arcade device which runs CircuitPython
from adafruit_clue import clue
from adafruit_display_text.label import Label

debug = 1


### TODO is looking for board.DISPLAY a reasonable way to work out if we are on CPB+Gizmo
display = board.DISPLAY


def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)

RAD_TO_DEG = 180.0 / math.pi


digit = 5

changed = False

### lilac, pale green and beige inspired bytearray
### https://www.h-schmidt.net/FloatConverter/IEEE754.html
### first set are actual values, second set tweaked for CLUE
### signbg = (211, 211, 232)
### exponentbg = (194, 222, 195)
### mantissabg = (222, 209, 197)
signbg_col = (211, 211, 232)
exponentbg_col = (194, 232, 195)
mantissabg_col = (232, 209, 187)

cursor_col = (255, 0, 0)  ### Red cursor


def get_tilt_angle():
    """ 0 degrees for flat on a desk, 90 for upright """
    (ax, ay, az) = clue.acceleration
    return math.atan2(ay, -az) * RAD_TO_DEG


def get_tilt_angles():
    """0 degrees for flat, -90 for left side down to stand on its side.
       0 degrees for flat on a desk, 90 for upright """
    (ax, ay, az) = clue.acceleration
    return (math.atan2(ax, -az) * RAD_TO_DEG,
            math.atan2(ay, -az) * RAD_TO_DEG)


# gyro based on first reading with magnitude 20 and rate
# limited with 0.25s pause does not work that well

start_angle = None
start_digit = None
digit_idx = 0


### display is 8 wide for decimal mantissa, 7sf plus .
### 123456.0
### 000004  but do something with leading zeros to hide them - maybe dark grey
###   3.14
### 1.2345
### 1.234567 x 10^-123

### digits which are 1.234567 with dec_exp is 0
digits = [1, 2, 3, 4, 5, 6, 7]
### the decimail exponent
dec_exp = 0


### TODO - check exponent ranges wrt
### 5 degree on acceleromter works pretty well and could be used on Arcade


# >>> 9e-44
# 8.96831e-44
# >>> 1e-45
# 0.0

# >>> 2e38
# 2e+38
# >>> 3e38
# 3e+38
# >>> 4e38
# inf

# from 1.40129846432e-45 to 3.40282346639e+38 (max binary exponent is NaN)

class DecimalFP():

    MIN_EXPONENT = -45
    MAX_EXPONENT = 38

    def __init__(self, number=None, *, mantissa=None, exponent=None, precision=7):
        self._negative = False
        self._precision = 7
        self._mantissa = list(range(1, precision + 1))  # 1.234567 equivalent
        self._exponent = 0
        self._nan = False
        self._inf = False
        self._cursor = 0
        self._fp30bit = None
        self._recalc_fp()

    def __str__(self):
        """Returns the value in scientific notation."""
        return self.text_repr()

    def text_repr(self, scientific=True):
        man_str = str(self._mantissa[0]) + "." + "".join(map(str, self._mantissa[1:]))
        sci_not = ("-" if self._negative else "") + man_str + " x 10^" + str(self._exponent)
        return sci_not

    def decimal_fp(self):
        """Returns tuples of tuples, sign, mantissa and exponent."""
        sign = (1,) if self._negative else (0,)
        mantissa = tuple(self._mantissa)
        exponent = tuple(str(self._exponent))
        return (sign, mantissa, exponent)

    def binary_fp_str(self):
        return "".join(["{0:{fill}8b}".format(b, fill='0')
                        for b in struct.pack('>f', self._fp30bit)])

    def binary_fp_comp(self, implicit=False):
        """Returns a three tuples sign, exponent and mantissa
           each of which is a tupple of 1 and 0s."""
        bits = []
        for fp_byte in struct.pack('>f', self._fp30bit):
            for _ in range(8):
                bits.append(1 if fp_byte & 0x80 else 0)
                fp_byte <<= 1

        sign = (bits[0],)
        exponent = tuple(bits[1:9])
        mantissa = tuple(([1] if implicit else []) + bits[9:32])
        return (sign, exponent, mantissa)

    def _recalc_fp(self):
        """Recalculate the floating point version of the number using
           CircuitPython's float() with a string made from the authoritative data."""
        self._fp30bit = float(str(self._mantissa[0]) + "."
                              + "".join(map(str, self._mantissa[1:]))
                              + "e" + str(self._exponent))

    def cursor_right(self):
        self._cursor = (self._cursor + 1) % self._precision

    @property
    def cursor(self):
        return self._cursor

    @cursor.setter
    def cursor(self, value):
        self._cursor = value

    @property
    def cursor_digit(self):
        return self._mantissa[self._cursor]

    @cursor_digit.setter
    def cursor_digit(self, value):
        if not isinstance(value, int) or not 0 <= value <= 9:
            raise ValueError("Not 0-9 int")
        self._mantissa[self._cursor] = value
        self._recalc_fp()

    @property
    def exponent(self):
        return self._exponent

    @exponent.setter
    def exponent(self, value):
        self._exponent = value
        self._recalc_fp()


class ScreenFP():
    zeros_and_ones = None  ### initialised in constructor
    z_a_o_palette = None  ### initialised in constructor
    _cursors = {}

    _COLORS = 7

    BIT_WIDTH = 7
    BIT_HEIGHT = 8

    SIGN_0 = 0
    SIGN_1 = 1
    EXPONENT_0 = 2
    EXPONENT_1 = 3
    MANTISSA_0 = 4
    MANTISSA_1 = 5

    _FONT = terminalio.FONT
    _FONT_W = _FONT.get_bounding_box()[0]
    _FONT_H = _FONT.get_bounding_box()[1]

    @classmethod
    def _make_cursor_line(cls, size):
        """Make a simple line cursor in Bitmap form assuming it will be scaled
           like the decimal text field is scaled."""
        width = (cls._FONT_W - 1) * size
        height = 2 * size
        cursor_line = displayio.Bitmap(width, height, cls._COLORS)

        for pix_idx in range(width * height):
            cursor_line[pix_idx] = 6  ### TODO

        return cursor_line

    @classmethod
    def _make_cursor(cls, cursor_type, size):
        """Create a new cursor if required, otherwise just return an existing one."""
        cursor = cls._cursors.get((cursor_type, size))
        if cursor is None:
            if cursor_type == "line":
                cursor = cls._make_cursor_line(size)
            else:
                return ValueError("cursor_type must be line")
            cls._cursors[(cursor_type, size)] = cursor

        return cursor

    @classmethod
    def _make_zeros_and_ones(cls):
        """A bitmap with six cls.BIT_WIDTHs in three 0 and 1 pairs, the three pairs having
           background colours of lilac, pale green and beige."""
        zeros_and_ones = displayio.Bitmap(6 * cls.BIT_WIDTH,
                                          cls.BIT_HEIGHT, cls._COLORS)

        ### Draw background colours but leave right column blank for gap
        col_idx = (3, 4, 5)
        x_offset = 0
        for col_idx in col_idx:
            for x in range(x_offset, x_offset + 2 * cls.BIT_WIDTH):
                ### if not the last column draw in the chosen colour
                if x % cls.BIT_WIDTH != cls.BIT_WIDTH - 1:
                    for y in range(cls.BIT_HEIGHT):
                        zeros_and_ones[x, y] = col_idx
            x_offset += 2 * cls.BIT_WIDTH

        ### Draw black 0s
        black_idx = 1
        for x_offset in range(0, 6 * cls.BIT_WIDTH,
                              2 * cls.BIT_WIDTH):
            zeros_and_ones[x_offset + 2, 1] = black_idx
            zeros_and_ones[x_offset + 3, 1] = black_idx
            zeros_and_ones[x_offset + 2, cls.BIT_HEIGHT - 2] = black_idx
            zeros_and_ones[x_offset + 3, cls.BIT_HEIGHT - 2] = black_idx
            for y in range(2, cls.BIT_HEIGHT -2):
                zeros_and_ones[x_offset + 1, y] = black_idx
                zeros_and_ones[x_offset + 4, y] = black_idx

        ### Draw black 1s
        for x_offset in range(cls.BIT_WIDTH, (6 + 1) * cls.BIT_WIDTH,
                              2 * cls.BIT_WIDTH):
            zeros_and_ones[x_offset + 1, 2] = black_idx
            for y in range(1, cls.BIT_HEIGHT - 1):
                zeros_and_ones[x_offset + 2, y] = black_idx
                zeros_and_ones[x_offset + 3, y] = black_idx

        return zeros_and_ones

    @classmethod
    def _make_z_a_o_palette(cls):
        z_a_o_palette = displayio.Palette(cls._COLORS)
        z_a_o_palette.make_transparent(0)
        z_a_o_palette[1] = 0x000000
        z_a_o_palette[2] = 0xffffff
        z_a_o_palette[3] = signbg_col
        z_a_o_palette[4] = exponentbg_col
        z_a_o_palette[5] = mantissabg_col
        z_a_o_palette[6] = cursor_col
        return z_a_o_palette

    def __init__(self, *, x=20, y=6, size="tiny", bits=32, cursor_type="line"):
        ### Must use class here for LHS assignment
        if ScreenFP.zeros_and_ones is None:
            ScreenFP.zeros_and_ones = ScreenFP._make_zeros_and_ones()
        if ScreenFP.z_a_o_palette is None:
            ScreenFP.z_a_o_palette = ScreenFP._make_z_a_o_palette()

        if size=="tiny":
            cols = bits
            rows = 1
            scale = 1
        elif size=="small":
            cols = bits // 2
            rows = 2
            scale = 2
        else:
            raise ValueError("size must be tiny or small")

        self._x = x   ### TODO - ponder this as it's currently indented from the binary representation
        self._y = y
        
        ### TODO magic number
        self._decimal = Label(font=self._FONT,
                              text="-" * 20, color=0xc0c0c0,
                              scale=scale)
        # Set the location
        self._decimal.x = self._x
        self._decimal.y = self._y + self._FONT_H * scale // 2

        self._binary_chunk_width = cols
        self._binary_chunks = []

        y_start_pos = self._y + round(1.25 * self._FONT_H * scale)
        
        for row in range(rows):
            bin_digits = displayio.TileGrid(self.zeros_and_ones,
                                            pixel_shader=self.z_a_o_palette,
                                            width=cols,
                                            height=1,
                                            tile_width=self.BIT_WIDTH,
                                            tile_height=self.BIT_HEIGHT)
            bin_digits.x = self._x // 2 // scale
            bin_digits.y = y_start_pos // scale
            y_start_pos += self.BIT_HEIGHT * scale + 4  ### magic value
            self._binary_chunks.append(bin_digits)

        self._cursor_spacing = self._FONT_W * scale
        self._cursor_visible = True

        ### Get a shared cursor, TileGrid allows custom positioning
        ### to allow for x/y positioning
        cursor = ScreenFP._make_cursor(cursor_type, 2)
        cursor_tilegrid = displayio.TileGrid(cursor,
                                             pixel_shader=self.z_a_o_palette)
        cursor_tilegrid.x = self._decimal.x
        cursor_tilegrid.y = self._decimal.y + self._FONT_H // 2 + 5

        ### The binary row(s) need to go in as a second Group to allow them
        ### to have their own scale factor
        main_group = displayio.Group(max_size=3)
        bin_group = displayio.Group(max_size=len(self._binary_chunks), scale=scale)
        main_group.append(self._decimal)
        main_group.append(bin_group)
        main_group.append(cursor_tilegrid)

        for binary_chunk in self._binary_chunks:
            bin_group.append(binary_chunk)

        self._cursor_tilegrid = cursor_tilegrid
        self._group = main_group

        self._set_binary([0] * bits)

        ### An optional on-screen representation of a cursor
        ### None or 0
        self._cursor = 0 if cursor_type else None

    def _set_binary(self, bits):
        for src_bit_idx in range(32):
            if src_bit_idx % self._binary_chunk_width == 0:
                bin_idx = 0
                binary_chunk = self._binary_chunks[src_bit_idx // self._binary_chunk_width]

            bit = bits[src_bit_idx]
            if src_bit_idx == 0:
                value = self.SIGN_1 if bit else self.SIGN_0
            elif 1 <= src_bit_idx <= 8:
                value = self.EXPONENT_1 if bit else self.EXPONENT_0
            else:  ### 9 to 31 inclusive
                value = self.MANTISSA_1 if bit else self.MANTISSA_0
            binary_chunk[bin_idx] = value
            bin_idx += 1

    def update_value(self, text, bits):
        if text is not None:
            self._decimal.text = text
        if bits is not None:
            self._set_binary(bits)

    def displayio_group(self):
        return self._group

    def _cursor_set_x_pos(self):
        """."""
        if self._cursor is None:
            return

        ### skip the decimal point
        cursor_pos = self._cursor if self._cursor == 0 else self._cursor + 1
        self._cursor_tilegrid.x = 20 + cursor_pos * self._cursor_spacing  ### TODO

    @property
    def cursor(self):
        return self._cursor

    @cursor.setter
    def cursor(self, value):
        self._cursor = value
        self._cursor_set_x_pos()

    @property
    def cursor_visible(self):
        return self._cursor_visible

    @cursor_visible.setter
    def cursor_visible(self, value):
        """If the value has changed store it and then hide or show it by removing it
           from the main displayio Group."""
        if self._cursor_visible != value:
            self._cursor_visible = value
            if self._cursor_visible:
                self._group.append(self._cursor_tilegrid)
            else:
                self._group.pop()


operators = ("+", "-", "*", "/", "^")

### default is tiny which is a challenge to read for oldsters!
operand1_gob = ScreenFP(y=00, size="small")
operand2_gob = ScreenFP(y=85, size="small")
result_gob = ScreenFP(y=170, size="small")

operand1 = DecimalFP()
operand2 = DecimalFP()
operator = operators[0]
result = DecimalFP()


screen_group = displayio.Group(max_size=3)
screen_group.append(operand1_gob.displayio_group())
screen_group.append(operand2_gob.displayio_group())
screen_group.append(result_gob.displayio_group())

display.show(screen_group)


### TODO draw a cursor with colour showing whether in edit mode
### or could do this as a flashing inversion or could do it as a brighter character?

while True:
    #text_area.text = str(digit)
    ### TODO only set this if value has changed (maybe)
    ##text_area.text = "".join(map(str, digits))
    ##text_area.text = str(operand1)
    si, ex, ma = operand1.binary_fp_comp()
    operand1_gob.update_value(str(operand1), si + ex + ma)

    ### TODO - replace this
    operand2_gob.update_value(str(operand1), si + ex + ma)
    result_gob.update_value(str(operand1), si + ex + ma)

    if changed:
        changed = False
        time.sleep(0.25)

    if clue.button_a and not clue.button_b:
        timeout = False
        start_ns = time.monotonic_ns()
        while clue.button_a:
            if time.monotonic_ns() - start_ns >= 500000000:
                timeout = True
                break

        if timeout:
            ### TODO visual indication exponent is being changed
            start_tr_angle, _ = get_tilt_angles()
            start_exponent = operand1.exponent
            operand1_gob.cursor_visible = False
            while clue.button_a:
                tr_angle, _ = get_tilt_angles()
                offset = int((tr_angle - start_tr_angle) / 5.0)
                ### TODO 38 / -38
                operand1.exponent = max(min(start_exponent + offset,
                                            operand1.MAX_EXPONENT),
                                        operand1.MIN_EXPONENT)
                ### Need to decide where/when to update text in all of this mess
                ##text_area.text = str(operand1)
                si, ex, ma = operand1.binary_fp_comp()
                operand1_gob.update_value(str(operand1), si + ex + ma)
            operand1_gob.cursor_visible = True
        else:
            ### Move the cursor on the held by the data representation
            ### then update the screen version
            operand1.cursor_right()
            operand1_gob.cursor = operand1.cursor

    if clue.button_b:
        ## (gx, _, _) = clue.gyro
        if start_angle is None:
            start_angle = get_tilt_angle()
            ##start_digit = digits[digit_idx]
            start_digit = operand1.cursor_digit
        else:
            angle = get_tilt_angle()
            offset = int((angle - start_angle) / 5.0)
            ## digits[digit_idx] = max(min(start_digit + offset, 9), 0)
            operand1.cursor_digit = max(min(start_digit + offset, 9), 0)
            #if digit > 0 and gx > 20:
            #    digit -= 1
            #    changed = True
            #elif digit < 9 and gx < -20:
            #    digit += 1
            #    changed = True
    elif start_angle is not None:
        start_angle = None
        start_digit = None
