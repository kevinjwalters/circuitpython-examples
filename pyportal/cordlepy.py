### cordlepy 1.5
### A port of Wordle word game

### Tested with an Adafruit PyPortal and an Adafruit CLUE
### on CircuitPython 7.1.1

### make a secrets.py including the timezone
### copy a file with five character words on each line to gamewords.txt
### copy this file to PyPortal board as code.py

### MIT License

### Copyright (c) 2022 Kevin J. Walters

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

### TODO - mark keys with yellow / green guesses
### TODO - PyPortal top left / bottom right press for calibration at start
###        or auto calibration based on keypresses if keen
### TODO - statistics at end of round
### TODO - Adafruit IO integration of some sort? A misused heatmap?
### TODO - a few sound effects?

### TODO - fix up CLUE positioning
### TODO - add left button on CLUE for extra enter key
### TODO - increase word scroll step on CLUE and re-evaluate word grid size
### TODO - add a date setter when needed with 2022 epoch

### TODO - add in-app purchase with proof-of-work cryptocurrency of hints to
###        unlevel the playing field, unvetted adverts, lootboxes,
###        undeclared product placement, selling users' data and
###        low-latency trading of word lists and somehow squeeze in NFTs


import time
import os
import gc
import random
import re

import board
import displayio
import terminalio

from adafruit_bitmap_font import bitmap_font
from adafruit_button import Button
from adafruit_display_text.bitmap_label import Label

gc.collect()
debug = 3

def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


### Left (a) and right (b) buttons
os_machine_uc = os.uname().machine.upper()
clue = os_machine_uc.find("CLUE NRF52840 ") >= 0


display = board.DISPLAY

DISPLAY_WIDTH, DISPLAY_HEIGHT = display.width, display.height
##display.auto_refresh = False
### Colours
WHITE = 0xe0e0e0
BLACK = 0x000000
LIGHTGREY = 0xb0b0b0
LIGHTYELLOW = 0xe0e040
LIGHTGREEN = 0x40d040
BLUE = 0x0000d0

ROUNDS = 1
MAX_GUESSES = 6
### Whether the guess has to be from words - this is set
### to False later for < 100 words
GRADE_TEXT = ["Genius",
              "Magnificent",
              "Impressive",
              "Splendid",
              "Great",
              "Phew"]


ORD_a, ORD_z, ORD_A, ORD_Z = ord("a"), ord("z"), ord("A"), ord("Z")
def lc_rot13(text):
    return "".join(chr((ord(c) - ORD_a + 13) % 26 + ORD_a)
                   if ORD_a <= ord(c) <= ORD_z else c for c in text)


### Would be more elegant if sub-classed but probably less memory efficient
class GameWords:
    DISK = 1
    MEM_RAW_LIST = 2

    ONE_A_DAY = 101
    RANDOM = 102
    RANDOM_NO_REPEAT = 103
    INORDER = 104

    def __init__(self, url="file:///gamewords.txt", threshold=2000):
        self._raw_words = None
        self._word_count = 0
        self._src = None  ### DISK, MEM_RAW_LIST
        self._selector = self.RANDOM
        self._selector_value = None
        self._dictionary_rule = False
        self._decode = lambda t: t
        self._threshold = threshold
        self._first_line_off = 0
        self._fh = None
        self._initWords(url)

    def _initWords(self, url):
        fileurl = re.match(r"file:///(.+)", url)
        if fileurl:
            filename = fileurl.group(1)
            file_len = os.stat(filename)[6]
            self._src = self.MEM_RAW_LIST if file_len <= self._threshold else self.DISK
            fh = open(filename)  ### defaults to text read mode
            first_line = fh.readline()
            comment = re.match(r"^#+(\s*.*)?", first_line)
            if comment:
                self._first_line_off = fh.tell()
                tokens = comment.group(1).strip().split()
                while True:
                    try:
                        token = tokens.pop(0)
                        if token == "rot13":
                            self._decode = lc_rot13
                        elif token == "one_a_day":
                            start_date = tokens.pop(0)
                            ### Relying on int() to filter out any dodgy data...
                            parsed_date = [int(x) for x in start_date.split("-")]
                            self._selector_value = tuple(parsed_date)
                            self._selector = self.ONE_A_DAY
                        elif token == "dictionary":
                            self._dictionary_rule = True
                    except IndexError:
                        break
            else:
                fh.seek(0)

            if self._src == self.MEM_RAW_LIST:
                self._raw_words = fh.readlines()
                self._word_count = len(self._raw_words)
            elif self._src == self.DISK:
                self._fh = fh
                while True:
                    line = self._fh.readline()
                    if line:
                        self._word_count += 1
                    else:
                        break


    def __len__(self):
        return self._word_count


    def _read_file_line(self, idx):
        self._fh.seek(self._first_line_off)
        line = idx
        while line > 0:
            _ = self._fh.readline()
            line -= 1
        return self._fh.readline()


    def getNextWord(self):
        if self._selector == self.ONE_A_DAY:
            w_idx = self._selector_value
            self._selector_value += 1
        elif self._selector == self.RANDOM:
            w_idx = random.randrange(self._word_count)
        elif self._selector == self.RANDOM_NO_REPEAT:
            raise NotImplementedError("yet!")
        elif self._selector == self.INORDER:
            w_idx = self._selector_value
            self._selector_value += 1

        return self.getWord(w_idx)


    def getWord(self, idx):
        wrd = None
        w_idx = idx % self._word_count

        if self._src == self.MEM_RAW_LIST:
            wrd = self._raw_words[w_idx]
        elif self._src == self.DISK:
            wrd = self._read_file_line(w_idx)

        return self._decode(wrd.rstrip())


    def isOkay(self, wrd):
        return self.isPresent(wrd) if self._dictionary_rule else True


    def isPresent(self, wrd):
        if self._src == self.MEM_RAW_LIST:
            for raw_wrd in self._raw_words:
                wrd2 = self._decode(raw_wrd.rstrip())
                if wrd == wrd2:
                    return True
        elif self._src == self.DISK:
            self._fh.seek(self._first_line_off)
            while True:
                raw_wrd = self._fh.readline()
                if raw_wrd:
                    wrd2 = self._decode(raw_wrd.rstrip())
                    if wrd == wrd2:
                        return True
                else:
                    break  ### EOF

        return False


    @property
    def selector(self):
        return self._selector


    @property
    def selector_value(self):
        return self._selector_value


    @selector_value.setter
    def selector_value(self, new_value):
        self._selector_value = new_value


def fetchDate(wrds):
    word_idx = None

    ### alarm.sleep_memory isn't present on PyPortal
    ### Storing the word_idx in a register on the temperature sensor - niishhh!
    import adafruit_adt7410
    adafruit_adt7410.ADT7410.reset = lambda self: self  ### nobble the reset
    adt = adafruit_adt7410.ADT7410(board.I2C(), address=0x48)
    ### Look for a value (well) below default of 10 degrees
    if adt.low_temperature < 0.0:
        word_idx = round((0.0 - adt.low_temperature) * 128)
        wrds.selector_value = word_idx
        d_print(1, "Retrieved word_idx", word_idx)

    ### If word_idx isn't set need to fetch the data from t'Internet
    if word_idx is None:
        import supervisor
        import adafruit_datetime
        from adafruit_pyportal import PyPortal
        pyportal = PyPortal(status_neopixel=board.NEOPIXEL)
        pyportal.get_local_time()
        wordle_oday = adafruit_datetime.date(*wrds.selector_value).toordinal()
        now_oday = adafruit_datetime.datetime.now().toordinal()
        word_idx = now_oday - wordle_oday
        d_print(1, "Saving word_idx", word_idx)
        adt.low_temperature = (0 - word_idx ) / 128
        time.sleep(10)
        supervisor.reload()


words = GameWords()
gc.collect()
d_print(3, "GC after retrieveWords", gc.mem_free())

if not clue and words.selector == GameWords.ONE_A_DAY:
    d_print(1, "Fetch the time over Wi-Fi and set the word of the day")
    fetchDate(words)


if clue:
    import math
    import digitalio
    from adafruit_lsm6ds.lsm6ds33 import LSM6DS33
    pin_a = board.BUTTON_A
    pin_b = board.BUTTON_B
    pin_but_a = digitalio.DigitalInOut(pin_a)
    pin_but_a.switch_to_input(pull=digitalio.Pull.UP)
    pin_but_b = digitalio.DigitalInOut(pin_b)
    pin_but_b.switch_to_input(pull=digitalio.Pull.UP)
    left_button = lambda: not pin_but_a.value
    right_button = lambda: not pin_but_b.value
    keyboard_device = [LSM6DS33(board.I2C()),
                       right_button,
                       ((0, -2),   ### x -z
                        (1, -2))]  ### y -z
    default_font = terminalio.FONT
    default_font_scale = 2
else:
    left_button = right_button = None  ### Assume PyPortal
    from adafruit_touchscreen import Touchscreen
    ### These numbers borrowed from
    ### https://learn.adafruit.com/pyportal-calculator-using-the-displayio-ui-elements
    PYPORTAL_TSCAL_X = (5800, 59000)
    PYPORTAL_TSCAL_Y = (5800, 57000)
    accel = None  ### Present but not used
    keyboard_device = Touchscreen(board.TOUCH_XL, board.TOUCH_XR,
                                  board.TOUCH_YD, board.TOUCH_YU,
                                  calibration=(PYPORTAL_TSCAL_X,
                                               PYPORTAL_TSCAL_Y),
                                  size=(DISPLAY_WIDTH, DISPLAY_HEIGHT))
    default_font = bitmap_font.load_font("/fonts/Arial-12.bdf")
    default_font_scale = 1


FONT_WIDTH, FONT_HEIGHT = default_font.get_bounding_box()[:2]
G_ORIGIN_X = DISPLAY_WIDTH // 2
G_ORIGIN_Y = DISPLAY_HEIGHT // 2


class WordGrid():
    DEFAULT = LIGHTGREY
    PRESENT = LIGHTYELLOW
    CORRECT_POSITION = LIGHTGREEN
    square_palette = None   ### Initialised in WordSquare
    COL_IDX = {DEFAULT: 0, PRESENT: 1, CORRECT_POSITION: 2}

    BLANK = " "

    def __init__(self, word_len=5, num_words=6,
                 WordLabel=Label,
                 font=terminalio.FONT, font_scale=2, hpad=4):
        dio_words = displayio.Group()

        x_spacing = 34
        y_spacing = 34
        for w_idx in range(num_words):
            dio_chars = displayio.Group()

            for c_idx in range(word_len):
                char = WordLabel(font, scale=font_scale, text=self.BLANK,
                                 color=BLACK, background_color=self.DEFAULT,
                                 padding_left=hpad, padding_right=hpad)
                char.x = c_idx * x_spacing
                char.y = w_idx * y_spacing   ### TODO height correction for weird coord scheme
                dio_chars.append(char)
            dio_words.append(dio_chars)

        self._dio_words = dio_words

        self._dio_group = displayio.Group()
        self._dio_group.x = 86  ### TODO properly
        self._dio_group.y = 18   ### TODO properly
        self._dio_group.append(self._dio_words)

    @classmethod
    def WordSquare(cls, width, height, color=DEFAULT):
        if cls.square_palette is None:
            cls.square_palette = displayio.Palette(3)
            for colour, idx in cls.COL_IDX.items():
                cls.square_palette[idx] = colour
        if True:
            square_bitmap = displayio.Bitmap(width, height, len(cls.square_palette))
            tg = displayio.TileGrid(square_bitmap, pixel_shader=cls.square_palette)
        else:
            square_bitmap = displayio.Bitmap(1, 1, len(cls.square_palette))
            tg = displayio.TileGrid(square_bitmap,
                                    pixel_shader=cls.square_palette,
                                    width=width,
                                    height=height,
                                    default_tile=0)
        square_bitmap.fill(cls.COL_IDX[color])
        return tg


    def set(self, widx, cidx, letter, bg):
        if letter is not None:
            self._dio_words[widx][cidx].text = letter
        if bg is not None:
            self._dio_words[widx][cidx].background_color = bg

    def get(self, widx, cidx):
        return (self._dio_words[widx][cidx].text,
                self._dio_words[widx][cidx].background_color)

    @property
    def group(self):
        return self._dio_group

    @property
    def y(self):
        return self._dio_group.y

    @y.setter
    def y(self, value):
        self._dio_group.y = value


class Keyboard():
    BACKSPACE = 8
    ENTER = 13
    OFF_KEYBOARD = -1

    _ALPHA_LAYOUT = {"QUERTY": [["qwertyuiop",0],
                                ["asdfghjkl", 0.4],
                                ["zxcvbnm", 0.8]]}

    def __init__(self,
                 input_device,
                 layout="QUERTY",
                 numbers=False,
                 keycaps_upper=True, shift=False, control=False, symbols=False,
                 enter=True, backspace=True, space=False,
                 keycap_fg=0xd0d0d0,
                 keycap_bg=0x404040,
                 keycap_font=terminalio.FONT,
                 min_press_time=0.08,  ### 80ms plus library delay required for a press
                 max_width=None,
                 max_height=None,
                 cb=None,
                 cb_kwargs={},
                 blank_char=" "
                 ):
        self._keys = []
        self._dio_keyboard = displayio.Group()
        ### TODO - sizing code still needs some cleaning
        self._dio_keyboard.x = int(max_width / 40) if max_width else 8
        self._dio_keyboard.y = 132   ### TODO set this properly
        self._key_width = int(max_width / 12) if max_width else 26
        self._key_height = int(max_width / 12) if max_width else 26
        self._key_x_space = int(self._key_width / 5)
        self._key_y_space = self._key_x_space + 2
        
        self._keycap_fg = keycap_fg
        self._keycap_bg = keycap_bg
        self._keycap_font = keycap_font
        self._initKeys(layout,
                       enter=enter, backspace=backspace, space=space,
                       numbers=numbers, keycaps_upper=keycaps_upper,
                       shift=shift, control=control, symbols=False)
        self._dio_group = displayio.Group()

        self._touch_screen = None
        self._off_time = 0.05

        self._accel = None
        self._accel_lr_ud = None
        self._button = None
        self._keycursor_home = (1, 4)  ### row, column
        self._keycursor = None

        self._min_press_time = min_press_time
        self._cb = cb
        self._cb_kwargs = cb_kwargs
        self._blank_char = blank_char
        try:
            _ = input_device.touch_point
            self._touch_screen = input_device
        except AttributeError:
            pass

        try:
            _ = input_device[0].acceleration
            _ = input_device[1]()
            _ = input_device[2][:2]
            self._accel = input_device[0]
            self._button = input_device[1]
            self._accel_lr_ud = input_device[2][:2]
        except (AttributeError, TypeError):
            pass

        if self._touch_screen is None and self._accel is None:
            raise ValueError("Need an input_device which supports touch_point"
                             "or array with accelerometer, callable button and axis spec")


    def _makeButton(self, x, y, text, width=None, height=None):
        button = Button(x=x,
                        y=y,
                        width=self._key_width if width is None else width,
                        height=self._key_width if height is None else height,
                        label=text,
                        label_font=self._keycap_font,
                        label_color=self._keycap_fg,
                        fill_color=self._keycap_bg,
                        style=Button.ROUNDRECT)
        return button


    def _initKeys(self, layout,
                  enter=True, backspace=True, space=False,
                  numbers=False, keycaps_upper=True,
                  shift=False, control=False, symbols=False):
        try:
            layout = self._ALPHA_LAYOUT[layout]
        except KeyError:
            raise ValueError("Unknown layout " + layout)
        for row_idx, (line, offset) in enumerate(layout):
            button_row = displayio.Group()
            self._dio_keyboard.append(button_row)
            key_row = []
            self._keys.append(key_row)

            x_pos = int(offset * (self._key_width + self._key_x_space))
            col_idx = 0
            on_last_row = row_idx == len(layout) - 1
            y_pos = row_idx * (self._key_height + self._key_y_space)
            if enter and on_last_row:
                x_pos = 0  ### remove offset
                wide_width = int(1.333 * self._key_width)
                butt = self._makeButton(x_pos, y_pos,
                                        "EN",
                                        width=wide_width)
                button_row.append(butt)
                key_row.append(self.ENTER)
                x_pos += wide_width + self._key_x_space
                col_idx += 1

            for char in line:
                butt = self._makeButton(x_pos, y_pos,
                                        char.upper() if keycaps_upper else char)
                button_row.append(butt)
                key_row.append(char)
                x_pos += self._key_width + self._key_x_space
                col_idx += 1

            if backspace and on_last_row:
                wide_width = int(1.333 * self._key_width)
                butt = self._makeButton(x_pos, y_pos,
                                        "BS",
                                        width=wide_width)
                button_row.append(butt)
                key_row.append(self.BACKSPACE)
                x_pos += wide_width + self._key_x_space
                col_idx += 1


    def showKeyboard(self):
        if len(self._dio_group) == 0:
            self._dio_group.append(self._dio_keyboard)


    def hideKeyboard(self):
        if len(self._dio_group) > 0:
            _ = self._dio_group.pop()


    def _decodePresses(self, press_list, lift_time_ns):
        """Takes a list of [key, press_time_ns] presses which may be from
           a light touch to a resistive screen where many presses are generated
           and filter them to reach a verdict on the most likely key."""
        key_verdict = None

        clean_list = []
        last_idx = len(press_list) - 1
        for p_idx, (key, press_time_ns) in enumerate(press_list):
            duration_s = ((lift_time_ns if p_idx == last_idx
                           else press_list[p_idx + 1][1]) - press_time_ns) / 1e9
            if not (key == self.OFF_KEYBOARD and duration_s < self._off_time):
                if len(clean_list) == 0 or clean_list[-1][0] != key:
                    clean_list.append([key, duration_s])
                else:
                    clean_list[-1][1] += duration_s

        for key, press_time_ns in clean_list:
            if press_time_ns > self._min_press_time:
                key_verdict = key

        return key_verdict if key_verdict != self.OFF_KEYBOARD else None


    def _getCharTouchScreen(self):
        key = None

        point = None
        last_button = None
        presses = []
        while key is None:
            while True:
                point = self._touch_screen.touch_point
                if point is not None:
                    break

            while True:
                ### Scan each key
                key_pressed = False
                for row_idx, row in enumerate(self._dio_keyboard):
                    for col_idx, butt in enumerate(row):
                        point_keyb = (point[0] - self._dio_keyboard.x,
                                      point[1] - self._dio_keyboard.y)
                        if butt.contains(point_keyb):
                            key_pressed = True
                            if last_button != butt:
                                key = self._keys[row_idx][col_idx]
                                presses.append([key, time.monotonic_ns()])
                                if last_button is not None:
                                    last_button.selected = False
                                butt.selected = True
                                last_button = butt
                            break
                    if key_pressed:
                        break

                ### Ignore press if touch has slid off the keyboard
                if not key_pressed and key != self.OFF_KEYBOARD:
                    key = self.OFF_KEYBOARD
                    presses.append([key, time.monotonic_ns()])
                    if last_button is not None:
                        last_button.selected = False
                        last_button = None

                point = self._touch_screen.touch_point
                if point is None:
                    break

            key = self._decodePresses(presses, time.monotonic_ns())
            if last_button:
                last_button.selected = False

        ### Clear the visible selection
        if last_button:
            last_button.selected = False

        return key


    def _getTiltAngles(self, axes_idxs):
        angles = self._accel.acceleration
        tilts = []
        for idx in axes_idxs:
            c1, c2 = self._accel_lr_ud[idx]
            tilt_r = math.atan2(math.copysign(1, c1) * angles[abs(c1)],
                                math.copysign(1, c2) * angles[abs(c2)])
            tilts.append(math.degrees(tilt_r))

        return tilts


    def _buttonSelect(self, select_rowcol=None, unselect_rowcol=None):
        if select_rowcol:
            self._dio_keyboard[select_rowcol[0]][select_rowcol[1]].selected = True

        if unselect_rowcol:
            self._dio_keyboard[unselect_rowcol[0]][unselect_rowcol[1]].selected = False


    def _getCharAccel(self):
        key = None

        ### select button under cursor
        self._buttonSelect(self._keycursor)
        button_down = 0
        time_period_ns = 10 * 1000 * 1000
        xy_dead_angle = 6.0
        ud_dead_angle = 10.0
        speed_conv = 1.0 / 4.0 / (1e9 / time_period_ns)
        xy_offset = 0.0
        ud_offset = 0.0
        press_steps = round(self._min_press_time * 1e9 / time_period_ns)

        while True:
            start_time_ns = time.monotonic_ns()
            target_end_time_ns = start_time_ns + time_period_ns

            if self._button():
                button_down += 1
            elif self._button() > 0:
                button_down -= 1

            angles = self._getTiltAngles((0, 1))
            ### measure left/right and up/down tilt
            if abs(angles[0]) > xy_dead_angle:
                xy_offset += angles[0] * speed_conv
            else:
                xy_offset = 0.0

            if abs(angles[1]) > ud_dead_angle:
                ud_offset += angles[1] * speed_conv
            else:
                ud_offset = 0.0

            ### Done if button has been pressed for long enough
            if button_down >= press_steps:
                key = self._keys[self._keycursor[0]][self._keycursor[1]]
                break

            ### Change button left/right if offset is great enough
            if xy_offset >= 1.0 and self._keycursor[1] < len(self._dio_keyboard[self._keycursor[0]]) - 1:
                self._buttonSelect(None, self._keycursor)
                self._keycursor[1] += 1
                self._buttonSelect(self._keycursor)
                xy_offset = 0.0

            elif xy_offset <= -1.0 and self._keycursor[1] > 0:
                self._buttonSelect(None, self._keycursor)
                self._keycursor[1] -= 1
                self._buttonSelect(self._keycursor)
                xy_offset = 0.0

            ### Change button up/down if offset is great enough and
            ### take care with shorter rows of keys
            if ud_offset >= 1.0 and self._keycursor[0] < len(self._dio_keyboard) - 1:
                self._buttonSelect(None, self._keycursor)
                self._keycursor[0] += 1
                self._keycursor[1] = min(self._keycursor[1],
                                         len(self._dio_keyboard[self._keycursor[0]]) - 1)
                self._buttonSelect(self._keycursor)
                ud_offset = 0.0

            elif ud_offset <= -1.0 and self._keycursor[0] > 0:
                self._buttonSelect(None, self._keycursor)
                self._keycursor[0] -= 1
                self._keycursor[1] = min(self._keycursor[1],
                                         len(self._dio_keyboard[self._keycursor[0]]) - 1)
                self._buttonSelect(self._keycursor)
                ud_offset = 0.0

            while time.monotonic_ns() < target_end_time_ns:
                pass

        ### Wait for the button up
        while self._button():
            pass

        self._buttonSelect(None, self._keycursor)
        return key


    def getChar(self, stay_shown=False, reset_cursor=True):
        key = None

        if (reset_cursor and self._keycursor is None
                and self._keycursor_home is not None):
            self._keycursor = list(self._keycursor_home)

        ### Wait for a tap
        self.showKeyboard()
        if self._touch_screen:
            key = self._getCharTouchScreen()
        elif self._accel:
            key = self._getCharAccel()

        if not stay_shown:
            self.hideKeyboard()

        if reset_cursor and self._keycursor_home is not None:
            self._keycursor = None

        return key


    def getLine(self,
                text="",
                min_len=None, max_len=None,
                return_at_max=False, cb_kwargs=None):
        chars = []
        text_idx = 0

        if self._keycursor is None and self._keycursor_home is not None:
            self._keycursor = list(self._keycursor_home)

        while True:
            if text_idx < len(text):
                char = text[text_idx]
                text_idx += 1
            else:
                char = self.getChar(stay_shown=True, reset_cursor=False)

            if char == self.BACKSPACE:
                if chars:
                    _ = chars.pop()
                    kwargs = self._cb_kwargs if cb_kwargs is None else cb_kwargs
                    self._cb(len(chars), self._blank_char, **kwargs)

            elif char == self.ENTER:
                if min_len is None or len(chars) >= min_len:
                    break
            else:
                if max_len is None or len(chars) < max_len:
                    chars.append(char)
                    if self._cb:
                        kwargs = self._cb_kwargs if cb_kwargs is None else cb_kwargs
                        self._cb(len(chars) - 1, char, **kwargs)

            if (return_at_max and max_len is not None
                    and len(chars) >= max_len):
                break

        self.hideKeyboard()
        if self._keycursor_home is not None:
            self._keycursor = None
        return "".join(str(c) for c in chars)


    @property
    def group(self):
        return self._dio_group


def grid_set_char(idx, char, row=None, wg=None):
    display_char = char.upper() if char is not None else WordGrid.BLANK
    wg.set(row, idx, display_char, None)


def popup_text(grp, text, show_time=2,
               *,
               font=default_font, font_scale=default_font_scale):
    grp.append(Label(font, scale=font_scale,
                     anchor_point=(0.5, 0.5),
                     anchored_position=(G_ORIGIN_X, G_ORIGIN_Y),
                     text=text,
                     color=WHITE, background_color=BLUE,
                     padding_left=6, padding_right=6
                     ))
    time.sleep(show_time)
    _ = grp.pop()


gc.collect()
main_group = displayio.Group()
display.show(main_group)

### Show empty word grid
##grid = WordGrid(font=default_font, font_scale=default_font_scale)
gc.collect()
grid = WordGrid()
gc.collect()
d_print(3, "GC after WordGrid", gc.mem_free())
main_group.append(grid.group)

### Create keyboard and add to displayio displayed group but the
### keyboard will not be visible at this stage
gc.collect()
keyboard = Keyboard(keyboard_device, cb=grid_set_char,
                    max_width=DISPLAY_WIDTH, max_height=DISPLAY_HEIGHT)
gc.collect()
d_print(3, "GC after Keyboard", gc.mem_free())
main_group.append(keyboard.group)

grid_start_y = 18
game_round = 1
while True:
    word = words.getNextWord()
    gc.collect()
    d_print(3, "GC main 1", gc.mem_free())

    grid.y = grid_start_y
    for line_idx in range(MAX_GUESSES):
        ### Get user's guess
        guess = ""
        while True:
            guess = keyboard.getLine(text=guess, min_len=5, max_len=5,
                                     cb_kwargs={"row": line_idx, "wg": grid})
            d_print(2, "line", line_idx, "is", guess)
            if words.isOkay(guess):
                break
            popup_text(main_group, "Not in word list")
            time.sleep(2.0)

        ### Score time
        correct = 0
        for char_idx in range(len(word)):
            if guess[char_idx] == word[char_idx]:
                grid.set(line_idx, char_idx, None, WordGrid.CORRECT_POSITION)
                correct += 1
            elif word.find(guess[char_idx]) >= 0:
                grid.set(line_idx, char_idx, None, WordGrid.PRESENT)
            time.sleep(0.5)

        if correct == len(word):
            ### Winner, winner, chicken dinner
            grid.y = grid_start_y
            msg = GRADE_TEXT[line_idx]
            popup_text(main_group, msg)
            d_print(1, "WIN on line", line_idx + 1, msg)
            break
        elif line_idx == MAX_GUESSES - 1:
            ### All guesses wrong
            grid.y = grid_start_y
            popup_text(main_group, word.upper())
            d_print(1, "LOSE")

        if line_idx >= 3 and line_idx != MAX_GUESSES - 1:
            for _ in range(0, 34, 2):
                grid.y -= 2
                time.sleep(0.025)

    game_round += 1
    if game_round > ROUNDS:
        break

d_print(1, "GAME OVER")
time.sleep(20)
