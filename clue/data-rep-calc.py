### data-rep-calc v0.13
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
### TODO option to show implicit bit

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


def get_tilt_angles():
    """0 degrees for flat, -90 for left side down to stand on its side.
       0 degrees for flat on a desk, 90 for upright """
    (ax, ay, az) = clue.acceleration
    return (math.atan2(ax, -az) * RAD_TO_DEG,
            math.atan2(ay, -az) * RAD_TO_DEG)


# gyro based on first reading with magnitude 20 and rate
# limited with 0.25s pause does not work that well

start_fb_angle = None
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
        """Returns the value in scientific notation
           of the form [-]N.NNNNNNN x 10^[-]N."""
        return self.text_repr()

    def __float__(self):
        """Returns the value as a float."""
        return self._fp30bit


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
        self._fp30bit = float(("-" if self._negative else "")
                              + str(self._mantissa[0]) + "."
                              + "".join(map(str, self._mantissa[1:]))
                              + "e" + str(self._exponent))

    def cursor_right(self):
        self._cursor = (self._cursor + 1) % self._precision

    def set_fp(self, value):
        """Use format to convert a float to the internal representation."""
        mant_str, exp_str = '{:.e}'.format(value).split("e")
        mant_idx = 0
        dot_idx = None
        new_negative = False
        new_mantissa = []
        for idx, mant_char in enumerate(mant_str):
            if mant_char.isdigit():
                new_mantissa.append(int(mant_char))
            elif mant_char == ".":
                dot_idx = idx
            elif idx == 0 and mant_char == "-":
                new_negative = True
            else:
                return ValueError("Cannot parse: " + value)

        self._negative = new_negative
        ### dot_idx expected to be 1 for positive, 2 for negative
        self._exponent = int(exp_str) + dot_idx - 1 - (1 if new_negative else 0)
        self._mantissa = new_mantissa[:self._precision]
        self._recalc_fp()
        if self._fp30bit != value:
            d_print(0, "WARNING", "set_fp mismatch {:.e} {:.e}".format(value, self._fp30bit))

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


_cursors = {}

def make_cursor_line(size):
    """Make a simple line cursor in Bitmap form assuming it will be scaled
       like the decimal text field is scaled."""
    ### TODO - work out how (and where) to do this elegantly
    font_w = 6
    width = (font_w - 1) * size
    height = 2 * size
    cursor_line = displayio.Bitmap(width, height, 8)  ### TODO ...

    for pix_idx in range(width * height):
        cursor_line[pix_idx] = 6  ### TODO

    return cursor_line

def make_cursor(cursor_type, size):
    """Create a new cursor if required, otherwise just return an existing one."""
    cursor = _cursors.get((cursor_type, size))
    if cursor is None:
        if cursor_type == "line":
            cursor = make_cursor_line(size)
        else:
            return ValueError("cursor_type must be line")
        _cursors[(cursor_type, size)] = cursor

    return cursor


class ScreenFP():
    zeros_and_ones = None  ### initialised in constructor
    z_a_o_palette = None  ### initialised in constructor


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
        self._decimal.x = self._x + 6
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
            ### TODO - this x calc works but is nonsense
            bin_digits.x = self._x // 2 // scale
            bin_digits.y = y_start_pos // scale
            y_start_pos += self.BIT_HEIGHT * scale + 4  ### magic value
            self._binary_chunks.append(bin_digits)

        self._cursor_spacing = self._FONT_W * scale
        self._cursor_visible = False

        ### Get a shared cursor, TileGrid allows custom positioning
        ### to allow for x/y positioning
        cursor = make_cursor(cursor_type, 2)
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
        if self._cursor_visible:
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
        self._cursor_tilegrid.x = self._decimal.x + cursor_pos * self._cursor_spacing

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


class ScreenOperator():
   # needs to do a cursor
   # need to show one character, possibly two

    def __init__(self, symbol):
        self._cursor_visible = False
        self._symbol = symbol

        symbol_gob = Label(font=terminalio.FONT,
                           text=symbol,
                           max_glyphs=2,
                           color=0xc0c000,
                           scale=2)

        # Set the location TODO re-think how this is done
        symbol_gob.x = 0
        symbol_gob.y = 84
        self._symbol_gob = symbol_gob
        self._group = displayio.Group(max_size=2)
        self._group.append(self._symbol_gob)
        if self._cursor_visible:
            pass  ### TODO

    def displayio_group(self):
        return self._group

    @property
    def symbol(self):
        return self._symbol

    @symbol.setter
    def symbol(self, value):
        self._symbol = value
        self._symbol_gob.text = value[:2]

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
                pass
                ### self._group.append(self._CURSORWHENIDOIT)  TODO
            else:
                pass
                ### self._group.pop()  TODO


class Operator():
    def __init__(self, func, symbol):
        self._func = func
        self._symbol = symbol

    def __str__(self):
        return self._symbol

    def apply(self, op1, op2):
        return self._func(op1, op2)

class OperatorAdd(Operator):
    def __init__(self):
        super().__init__(lambda arg1, arg2: arg1 + arg2, "+")

class OperatorSubtract(Operator):
    def __init__(self):
        super().__init__(lambda arg1, arg2: arg1 - arg2, "-")

class OperatorMultiply(Operator):
    def __init__(self):
        super().__init__(lambda arg1, arg2: arg1 * arg2, "*")

class OperatorDivide(Operator):
    def __init__(self):
        super().__init__(lambda arg1, arg2: arg1 / arg2, "/")


operators = (OperatorAdd(),
             OperatorSubtract(),
             OperatorMultiply(),
             OperatorDivide())
selected_operator_idx = 0
operator_num = len(operators)

operand1 = DecimalFP()
operand2 = DecimalFP()
operator = operators[selected_operator_idx]
result = DecimalFP()

ops = [operand1, operand2, operator]
selected_op_idx = 0
op_num = 3

### default is tiny which is a challenge to read for oldsters!
operand1_gob = ScreenFP(y=00, size="small")
operand2_gob = ScreenFP(y=85, size="small")
op_str = str(operator)
operator_gob = ScreenOperator(op_str)
result_gob = ScreenFP(y=170, size="small")

screen_ops = [operand1_gob, operand2_gob, operator_gob]

screen_group = displayio.Group(max_size=4)
screen_group.append(operand1_gob.displayio_group())
screen_group.append(operand2_gob.displayio_group())
screen_group.append(operator_gob.displayio_group())
screen_group.append(result_gob.displayio_group())

screen_ops[selected_op_idx].cursor_visible = True

display.show(screen_group)


def update_result_duo(op1, oper, op2, res, res_gob):
    """Do the calculation and updates the result and its graphical representation."""
    ### CircuitPython does not currently allow/translate float()
    ### for a class
    new_float = oper.apply(op1.__float__(), op2.__float__())
    res.set_fp(new_float)
    si, ex, ma = res.binary_fp_comp()
    res_gob.update_value(str(res), si + ex + ma)

for op, screen_op in ((operand1, operand1_gob),
                      (operand2, operand2_gob),
                      (result, result_gob)):
    si, ex, ma = op.binary_fp_comp()
    screen_op.update_value(str(op), si + ex + ma)

update_result_duo(operand1, operators[selected_operator_idx], operand2,
                  result, result_gob)


### TODO - there's a bug where start angle isn't registered for a digital change
### on second operand under some circumstances
while True:
    #text_area.text = str(digit)
    ### TODO only set this if value has changed (maybe)
    ##text_area.text = "".join(map(str, digits))
    ##text_area.text = str(operand1)
    if changed:
        update_result_duo(operand1,
                          operators[selected_operator_idx],
                          operand2,
                          result, result_gob)
        changed = False

    if clue.button_a and not clue.button_b:
        timeout1 = False
        timeout2 = False
        start_ns = time.monotonic_ns()
        while clue.button_a:
            if time.monotonic_ns() - start_ns >= 500000000:
                timeout1 = True
                break

        if timeout1:
            screen_ops[selected_op_idx].cursor_visible = False
            selected_op_idx = (selected_op_idx + 1 ) % op_num
            screen_ops[selected_op_idx].cursor_visible = True

        while clue.button_a:
            if time.monotonic_ns() - start_ns >= 1000000000:
                timeout2 = True
                break

        if timeout2:
            ### TODO visual indication exponent is being changed

            ### Undo the cursor move from first timeout as we now know that's
            ### not what the user wants
            screen_ops[selected_op_idx].cursor_visible = False
            selected_op_idx = (selected_op_idx - 1 ) % op_num

            start_tr_angle, _ = get_tilt_angles()
            if not isinstance(ops[selected_op_idx], Operator):
                start_exponent = ops[selected_op_idx].exponent

            while clue.button_a:
                tr_angle, _ = get_tilt_angles()
                offset = int((tr_angle - start_tr_angle) / 5.0)

                if not isinstance(ops[selected_op_idx], Operator):
                    ### TODO 38 / -38
                    ops[selected_op_idx].exponent = max(min(start_exponent + offset,
                                                            operand1.MAX_EXPONENT),
                                                        operand1.MIN_EXPONENT)
                    ### Need to decide where/when to update text in all of this mess
                    ##text_area.text = str(operand1)
                    si, ex, ma = ops[selected_op_idx].binary_fp_comp()
                    screen_ops[selected_op_idx].update_value(str(ops[selected_op_idx]),
                                                             si + ex + ma)
                    changed = True

            screen_ops[selected_op_idx].cursor_visible = True
        else:
            ### Move the cursor on the held by the data representation
            ### then update the screen version
            if not isinstance(ops[selected_op_idx], Operator):
                ops[selected_op_idx].cursor_right()
                screen_ops[selected_op_idx].cursor = ops[selected_op_idx].cursor

    if clue.button_b:
        ## (gx, _, _) = clue.gyro
        if start_fb_angle is None:
            _, start_fb_angle = get_tilt_angles()
            ##start_digit = digits[digit_idx]
            if isinstance(ops[selected_op_idx], Operator):
                start_operator_idx = selected_operator_idx
            else:
                start_digit = operand1.cursor_digit
        else:
            _, angle = get_tilt_angles()
            offset = int((angle - start_fb_angle) / 5.0)
            ## digits[digit_idx] = max(min(start_digit + offset, 9), 0)

            if isinstance(ops[selected_op_idx], Operator):
                selected_operator_idx = ( start_operator_idx + offset ) % operator_num
                operator_gob.symbol = str(operators[selected_operator_idx])
                if selected_operator_idx != start_operator_idx:
                    changed = True
            else:
                new_digit = max(min(start_digit + offset, 9), 0)
                if ops[selected_op_idx].cursor_digit != new_digit:
                    ops[selected_op_idx].cursor_digit = new_digit

                    si, ex, ma = ops[selected_op_idx].binary_fp_comp()
                    screen_ops[selected_op_idx].update_value(str(ops[selected_op_idx]),
                                                             si + ex + ma)
                    changed = True
    elif start_fb_angle is not None:
        start_fb_angle = None
