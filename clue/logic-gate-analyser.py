### logic-gate-analyser.py v1.1
### Displays matching logic gate and truth table based on inputs and outputs

### Tested with Adafruit CLUE and CircuitPython 9.0.4
### and Cytron EDU PICO and CircuitPython 9.0.4
### (9.0.0 to 9.0.2 are buggy for this program)

### copy this file to Adafruit CLUE / Cytron EDU PICO as code.py

### MIT License

### Copyright (c) 2024 Kevin J. Walters

### Permission is hereby granted, free of charge, to any person obtaining a copy
### of this software nd associated documentation files (the "Software"), to deal
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

### Instructables article
### TODO - add URL


import array
import math
import os
import time

import board
import analogio
import digitalio
import displayio
import terminalio
import bitmaptools
from adafruit_display_text.bitmap_label import Label

import ulab.numpy as np

from ymgp import YMGP


debug = 1

def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


### Left (a) and right (b) buttons for CLUE
### EDU PICO has A yellow (top) on GPO and B cyan (bottom) on GP1
clued_up = os.uname().machine.upper().find("CLUE") >= 0
if clued_up:
    pin_a = board.BUTTON_A
    pin_b = board.BUTTON_B

    input_pins = (board.P0, board.P1)
    output_pins = (board.P2,)

    display = board.DISPLAY

else:
    pin_a = board.GP0
    pin_b = board.GP1

    input_pins = (board.GP26, board.GP27)
    output_pins = (board.GP6,)

    import busio

    import adafruit_displayio_ssd1306   ### Not adafruit_ssd1306

    displayio.release_displays()
    i2c = busio.I2C(board.GP5, board.GP4, frequency=400 * 1000)
    SSD1306_WIDTH = 128
    SSD1306_HEIGHT = 64
    SSD1306_ADDR = 0x3c
    display_bus = displayio.I2CDisplay(i2c, device_address=SSD1306_ADDR)
    display = adafruit_displayio_ssd1306.SSD1306(display_bus,
                                                 width=SSD1306_WIDTH,
                                                 height=SSD1306_HEIGHT)

pin_but_a = digitalio.DigitalInOut(pin_a)
pin_but_a.switch_to_input(pull=digitalio.Pull.UP)
pin_but_b = digitalio.DigitalInOut(pin_b)
pin_but_b.switch_to_input(pull=digitalio.Pull.UP)
leftyellow_button_a = lambda: not pin_but_a.value
rightcyan_button_b = lambda: not pin_but_b.value


### This maps the truth table expressed as a string to the gate
### First value is number of inputs followed by output values
### for each row of the truth table with hypen as separator
gates = {"1-0-1": ("BUFFER",),
         "1-1-0": ("NOT",),

         "2-0-0-0-1": ("AND",),
         "2-0-1-1-1": ("OR",),
         "2-0-1-1-0": ("XOR",),
         "2-1-1-1-0": ("NAND",),
         "2-1-0-0-0": ("NOR",),
         "2-1-0-0-1": ("XNOR",)

         ## "2-1-1-0-1": (("NOT", None), "OR",)
        }


class InputReader:
    """Read a set of inputs repeatedly returing True or False for consistent values
       and None for inconsistent ones.
       It will perform analogue reads if possible applying a voltage threshold
       to determine a legitimate logic value."""
    def __init__(self,
                 pins,
                 sample_count=200,
                 *,
                 confidence=0.95,
                 low_threshold=1 / 5,
                 high_threshold=3.75 / 5):

        self._pins = tuple(pins)
        self._pin_count = len(pins)
        self._digitalin = [self._get_input(pin) for pin in pins]
        self._sample_count = sample_count
        self._samples = np.zeros((self._pin_count, self._sample_count),
                                 dtype=np.uint16)
        self._last_values = [None] * self._pin_count

        ### TODO - check this for small sizes like sample_count=8 confidence=0.75
        self._bottom_idx = math.floor(sample_count * (1.0 - confidence))
        self._top_idx = math.ceil(sample_count * confidence)
        self._low_threshold = round(65535 * low_threshold)
        ### A 4/5 threshold on high doesn't always work on 3.3V powered LogicBoard
        ### The NOT gates have slightly less oomph than XOR
        self._high_threshold = round(65535 * high_threshold)


    @classmethod
    def _get_input(cls, pin):
        try:
            adc_pin = analogio.AnalogIn(pin)
            return adc_pin
        except ValueError:
            ### Pin doesn't support analogue reads, revert to digital
            dig_pin = digitalio.DigitalInOut(pin)
            return dig_pin


    def _get_samples_digital(self):
        for s_idx in range(self._sample_count):
            for d_idx, dora_in in enumerate(self._digitalin):
                sample = dora_in.value
                self._samples[d_idx, s_idx] = (65535 if sample else 0) if isinstance(sample, bool) else sample


    ### This changes order of data in self._samples
    ### if ulab views of that are passed in
    def _distill_value(self, values):
        value = None
        values.sort()
        if values[self._bottom_idx] > self._high_threshold:
            value = True
        elif values[self._top_idx] < self._low_threshold:
            value = False
        return value


    def get_values(self):
        self._get_samples_digital()
        for d_idx in range(self._pin_count):
            self._last_values[d_idx] = self._distill_value(self._samples[d_idx])

        return self._last_values


class SingleGateBitmap:
    """Create a displayio Bitmap of a gate with optional connecting wires."""

    DEFAULT_WIRE_LEN=5
    NEGATE_RADIUS = 4

    ### Origin is top left
    gates = {"BUFFER": {"shape": ["poly", ((0, 5), (26, 20), (0, 35))],
                        "in": {"positions": ((0, 20),)},
                        "out": {"positions": ((26, 20),)},
                        "bb": (27, 36)
                       },

             "AND": {"shape": ["lines",((21, 40) , (0, 40), (0, 0), (21, 0)), "arc", ((21, 0), (21, 40), -20)],
                     "in": {"positions": ((0, 10), (0, 30))},
                     "out": {"positions": ((21+20, 20),)},
                     "bb": (42, 41)
                    },
             "OR": {"shape": ["lines",((0, 0), (9, 0)), "arc", ((9, 0), (41, 20), -50), "arc", ((41, 20), (9, 40), -50),
                              "lines", ((9, 40), (0, 40)), "arc", ((0, 40), (0, 0), 40)],
                    "in": {"positions": ((4, 10), (4, 30))},
                    "out": {"positions": ((41, 20),)},
                    "bb": (42, 41)
                    },
             "XOR": {"shape": ["lines",((0+5, 0), (9+5, 0)), "arc", ((9+5, 0), (41, 20), -50), "arc", ((41, 20), (9+5, 40), -50),
                               "lines", ((9+5, 40), (0+5, 40)), "arc", ((0+5, 40), (0+5, 0), 40),
                               "arc", ((0, 40), (0, 0), 40)],
                     "in": {"positions": ((4, 10), (4, 30))},
                     "out": {"positions": ((41, 20),)},
                     "bb": (42, 41)
                    }
            }

    ### Gates made from other gates with circle on output to negate it
    gates_negated = {"NOT": ["BUFFER", ("negate",)],
                     "NOR": ["OR", ("negate",)],
                     "NAND": ["AND", ("negate",)],
                     "XNOR": ["XOR", ("negate",)]
                     }

    def __init__(self,
                 gate_type,
                 *,
                 inout_length=DEFAULT_WIRE_LEN,
                 negate_radius=NEGATE_RADIUS,
                 orientation="E",
                 pal_idx_gate=1,
                 pal_idx_wire=2,
                 pal_idx_bg=0,
                 title=False,
                 wires=False,
                 labels=None,
                 cache=True
                 ):
        ### pylint: disable=too-many-locals

        self._type = gate_type
        self._negated_output = gate_type in self.gates_negated
        base_type = self.gates_negated.get(self._type)[0] if self._negated_output else self._type
        self._base_gate = self.gates.get(base_type)
        self._wires = wires

        if self._base_gate is None:
            raise ValueError("Unknown gate: " + self._type)

        bound_w, bound_h = self._base_gate["bb"]
        bound_w += negate_radius * 2 if self._negated_output else 0
        wx_off = 0
        if wires:
            bound_w += inout_length
            in_min_x = min([xy[0] for xy in self._base_gate["in"]["positions"]])
            ### Gate connections not at x=0 take up less space on left side
            wx_off = max(0, inout_length - in_min_x)
            bound_w += wx_off + inout_length

        self.width = bound_w
        self.height = bound_h
        self.bitmap = displayio.Bitmap(self.width, self.height,
                                       4 if pal_idx_gate != pal_idx_wire else 2)

        it_shape = iter(self._base_gate["shape"])
        for primitive in it_shape:
            args = next(it_shape)
            if primitive in ("lines", "poly"):
                bitmaptools.draw_polygon(self.bitmap,
                                         array.array("h", [xy[0] + wx_off for xy in args]),
                                         array.array("h", [xy[1] for xy in args]),
                                         pal_idx_gate,
                                         close=(primitive == "poly"))
            elif primitive == "arc":
                YMGP.draw_arc_points(self.bitmap,
                                     args[0][0] + wx_off, args[0][1],
                                     args[1][0] + wx_off, args[1][1],
                                     args[2],
                                     pal_idx_gate,
                                     segments=10)

        negx_off = 0
        if self._negated_output:
            output = self._base_gate["out"]
            pos = output["positions"][0]  ### first output (there's only one)
            bitmaptools.draw_circle(self.bitmap,
                                    wx_off + pos[0] + negate_radius,
                                    pos[1],
                                    negate_radius,
                                    pal_idx_gate)
            negx_off = negate_radius * 2

        if wires:
            for w_in_x, w_in_y in self._base_gate["in"]["positions"]:
                bitmaptools.draw_line(self.bitmap,
                                      wx_off + w_in_x - inout_length, w_in_y,
                                      wx_off + w_in_x - 1, w_in_y,
                                      pal_idx_gate)
            for w_in_x, w_in_y in self._base_gate["out"]["positions"]:
                bitmaptools.draw_line(self.bitmap,
                                      wx_off + w_in_x + negx_off + 1, w_in_y,
                                      wx_off + w_in_x + negx_off + inout_length, w_in_y,
                                      pal_idx_gate)


class GateDisplay:
    def __init__(self,
                 gate_type=None,
                 *,
                 title=True,
                 x=0,
                 y=0,
                 width=64,
                 height=64,
                 font=terminalio.FONT):

        self.group = displayio.Group()
        self.group.x = x
        self.group.y = y

        self._palette = displayio.Palette(4)
        self._palette[1] = 0xc0c000   ### TODO
        self._palette[2] = 0xc0c0c0
        self._font_fg = 0xc0c000
        self._font_bg = 0x000000
        self._width = width
        self._height = height

        self._font = font
        self._font_width = self._font.get_bounding_box()[0]
        font_height = self._font.get_bounding_box()[1]
        self._font_scale = 3 if self._height >= 128 else 2
        self._symbol_scale = 2 if self._height >= 128 else 1
        ### Text is position by midpoint for y
        ### The 10 // 14 is a crude way to squish capitals to top of screen
        squish_factor = 14 if self._height >= 128 else 10
        self._text_y_off = font_height * self._font_scale * squish_factor // 14 // 2

        self._gate_type = None
        self.gate_type = gate_type


    def _set_type(self, value):
        self._gate_type = value
        if self._gate_type is not None:
            gate_dio = SingleGateBitmap(self._gate_type, wires=True)
            gate_title = Label(font=self._font,
                               text=value,
                               color=self._font_fg,
                               background_color=self._font_bg,
                               scale=self._font_scale,
                               save_text=False)
            gate_title.x = (self._width - len(value) * self._font_width * self._font_scale) // 2
            gate_title.y = self._text_y_off

            tg_gate = displayio.TileGrid(bitmap=gate_dio.bitmap,
                                         pixel_shader=self._palette)
            tg_grp = displayio.Group()  ### Need this for scaling
            tg_grp.scale = self._symbol_scale
            tg_grp.x = (self._width - gate_dio.width * self._symbol_scale) // 2
            tg_grp.y = (self._text_y_off * 2
                        + max((self._height
                               - self._text_y_off * 2
                               - gate_dio.height * self._symbol_scale) // 2, 0))
            tg_grp.append(tg_gate)

            self.group.append(gate_title)
            self.group.append(tg_grp)


    @property
    def gate_type(self):
        return self._gate_type

    @gate_type.setter
    def gate_type(self, value):
        if value != self._gate_type:
            while len(self.group) > 0:
                self.group.pop()
            self._set_type(value)


class GraphicalTruthTable:

    def __init__(self,
                 inputs=2, outputs=1,
                 x=0,
                 y=0,
                 width=120,
                 height=240,
                 combinatorial=True):

        if isinstance(inputs, int):
            self._input_count = inputs
            self._input_names = tuple([chr(ord("A") + n) for n in range(self._input_count)])
        else:
            self._input_count = len(inputs)
            self._input_names = tuple(inputs)

        if isinstance(outputs, int):
            self._output_count = outputs
            self._output_names = tuple([chr(ord("X") + n) for n in range(self._output_count)])
        else:
            self._output_count = len(outputs)
            self._output_names = tuple(outputs)

        self._width = width
        self._height = height

        self._style = "numerical"  ### truefalse or highlow
        self._combinations = 2 ** self._input_count
        self._input_binfmt = "{0:0" + str(self._input_count) + "b}"
        self._columns = 1  ### For input count of 3 or more could go multi-column?
        self._rules = "hv"
        self._results = {}

        ### (From memory) this is 6x14 but 5x12 without whitespace and 5x9 for caps...
        self._font = terminalio.FONT
        font_width = self._font.get_bounding_box()[0]
        font_height = self._font.get_bounding_box()[1]
        self._row_y_space_px = font_height
        if height >= 240:
            self._font_scale = 3
        elif height < 128:
            self._font_scale = 1
            if height < 70:
                self._row_y_space_px -= 2
        else:
            self._font_scale = 2
        self._row_y_space_px *= self._font_scale

        self._font_width = font_width
        self._font_height = font_height
        self._font_fg = 0xb0b0b0
        self._font_bg = 0x000000
        self._rule_colour = 0x808080
        self._input_spacer = " "
        self._output_spacer = " "
        self._inout_sep = "  "

        self._header_y_space = min(self._row_y_space_px,
                                   height - (self._combinations + 1) * self._row_y_space_px)
        self._table_width = len(self._blank_text()) * self._font_scale * self._font_width
        self._table_height = (self._font_height * self._font_scale
                              + self._header_y_space
                              + self._combinations * self._row_y_space_px)

        self._init_empty_table(x, y)


    def _init_empty_table(self, x, y):
        grp = displayio.Group()
        grp.x = x + (self._width - self._table_width) // 2
        grp.y = y
        hdr_text = self._make_row(self._input_names, self._output_names)
        hdr = Label(font=self._font,
                    text=hdr_text,
                    color=self._font_fg,
                    background_color=self._font_bg,
                    scale=self._font_scale,
                    save_text=False)
        y_text = self._font_height * self._font_scale // 2
        hdr.y = y_text

        first_data_y = y_text + self._row_y_space_px + self._header_y_space
        y_text = first_data_y
        for _ in range(self._combinations):
            row = Label(font=self._font,
                        text=self._blank_text(),
                        color=self._font_fg,
                        background_color=self._font_bg,
                        scale=self._font_scale,
                        save_text=False)
            row.x = 0
            row.y = y_text
            grp.append(row)
            y_text += self._row_y_space_px

        ### Intentionally append other stuff after this to allow
        ### row indexing to find the corresponding Label line
        grp.append(hdr)

        if self._rules:
            pixel_bitmap = displayio.Bitmap(1, 1, 2)
            pixel_bitmap.fill(1)
            pixel_palette = displayio.Palette(2)
            pixel_palette[1] = self._rule_colour
            if "h" in self._rules:
                tg = displayio.TileGrid(pixel_bitmap,
                                        pixel_shader=pixel_palette,
                                        width=self._table_width,
                                        height=self._font_scale,
                                        default_tile=0)
                tg.y = self._font_height * self._font_scale + self._header_y_space // 2 - self._font_scale
                grp.append(tg)

            if "v" in self._rules:
                tg = displayio.TileGrid(pixel_bitmap,
                                        pixel_shader=pixel_palette,
                                        width=self._font_scale,
                                        height=self._table_height,
                                        default_tile=0)
                fw_px = self._font_width * self._font_scale
                tg.x = (len(self._make_row(self._input_names, [])) * fw_px
                        + len(self._inout_sep) * fw_px // 2) - self._font_scale
                grp.append(tg)

        self.group = grp


    @classmethod
    def normalise(cls, value):

        if value is None:
            return "?"
        elif isinstance(value, bool):
            return "1" if value else "0"
        elif value in ("0", "F"):
            return "0"
        elif value in ("1", "T"):
            return "1"

        return None


    def _blank_text(self):
        return self._make_row(["?"] * self._input_count, ["?"] * self._output_count)


    def _make_row(self, in_chars, out_chars):
        return (self._input_spacer.join(in_chars)
                + ((self._inout_sep + self._output_spacer.join(out_chars)) if out_chars else ""))


    def add(self, inputs, outputs):
        added = False
        different = False
        complete = False

        input_str = "".join([self.normalise(x) for x in inputs])
        output_str = "".join([self.normalise(x) for x in outputs])

        existing = self._results.get(input_str)
        if existing is None:
            self._results[input_str] = output_str
            added = True
        elif existing != output_str:
            self._results[input_str] = output_str
            different = True

        if added or different:
            self._update_dio(input_str=input_str)

        complete = len(self._results) == self._combinations
        return (added, different, complete)

    def clear(self):
        if len(self._results) > 0:
            self._results = {}
            self._update_dio(all_rows=True)


    def _update_row(self, row):
        input_str = self._input_binfmt.format(row)
        output_str = self._results.get(input_str)
        if output_str is not None:
            self.group[row].text = self._make_row(input_str, output_str)
        else:
            self.group[row].text = self._blank_text()
            self.group[row].text = self._blank_text()


    def _update_dio(self, input_str=None, all_rows=False):
        updated = False

        if all_rows:
            for row in range(self._combinations):
                self._update_row(row)
            updated = True

        elif input_str is not None:
            row = None
            try:
                row = int(input_str, 2)  ### convert base 2 (binary) string into row number
                self._update_row(row)
                updated = True
            except ValueError:
                pass

        return updated


    @property
    def result_summary(self):
        summary = ""
        if len(self._results) == self._combinations:
            output = [self._results.get(self._input_binfmt.format(r)) for r in range(self._combinations)]
            summary = "{:d}-{:s}".format(self._input_count, "-".join(output))

        return summary


    @property
    def input_count(self):
        return self._input_count


    @input_count.setter
    def input_count(self, value):
        pass
        ##raise NotImplementedError
        ##self._input_count = value


main_group = displayio.Group()
display.root_group = main_group

gtt = GraphicalTruthTable(outputs=["Z"],
                          width=display.width // 2,
                          height=display.height)
main_group.append(gtt.group)

#symbol_group = displayio.Group()
#symbol_group.x = display.width // 2
#symbol_group.scale = 2 if display.height >= 128 else 1
gate_disp = GateDisplay(x=display.width // 2,
                        width=display.width // 2,
                        height=display.height)
main_group.append(gate_disp.group)

observed_pins = InputReader(input_pins + output_pins)


left_button_lasttime = False
num_inputs = 2
shown_gate_type = None

while True:
    if rightcyan_button_b():
        gtt.clear()
        shown_gate_type = None
        gate_disp.gate_type = None
        time.sleep(1)
        continue

    ### Not yet implemented
    if False:
        if left_button_lasttime and leftyellow_button_a():
            ### Toggle between 2 and 1 inputs (not yet implemented)
            num_inputs = 3 - num_inputs
            gtt.input_count = num_inputs
        elif leftyellow_button_a():
            left_button_lasttime = True
            gtt.clear()
            time.sleep(1)
            continue
        left_button_lasttime = False

    in_and_out_values = observed_pins.get_values()
    if None not in in_and_out_values:
        ### Add inputs and outputs to truth table assuming 1 output
        gtt.add(in_and_out_values[:-1],
                in_and_out_values[-1:]
                )

    r_s = gtt.result_summary
    inf_gates = gates.get(r_s)
    ### Only works for simple single gates at the moment
    inf_gate_type = inf_gates[0] if inf_gates else None
    if inf_gate_type != shown_gate_type:
        print("Gate is:", inf_gate_type, "(based on", r_s + ")")
        gate_disp.gate_type = inf_gate_type
        shown_gate_type = inf_gate_type
