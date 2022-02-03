### cordlepy 1.3
### A port of Wordle word game

### Tested with an Adafruit PyPortal and CircuitPython and 7.1.1

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

### TODO - top left / bottom right press for calibration at start
###        or auto calibration based on keypresses if keen
### TODO - improve keyboard for light touches
### TODO - statistics at end of round
### TODO - Adafruit IO integration of some sort? A misused heatmap?
### TODO - a few sound effects?

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
    import digitalio
    pin_a = board.BUTTON_A
    pin_b = board.BUTTON_B
    pin_but_a = digitalio.DigitalInOut(pin_a)
    pin_but_a.switch_to_input(pull=digitalio.Pull.UP)
    pin_but_b = digitalio.DigitalInOut(pin_b)
    pin_but_b.switch_to_input(pull=digitalio.Pull.UP)
    left_button = lambda: not pin_but_a.value
    right_button = lambda: not pin_but_b.value
    ts = None
    default_font = terminalio.FONT
    default_font_scale = 2
else:
    left_button = right_button = None  ### Assume PyPortal
    import adafruit_touchscreen
    ### These numbers borrowed from
    ### https://learn.adafruit.com/pyportal-calculator-using-the-displayio-ui-elements
    PYPORTAL_TSCAL_X = (5800, 59000)
    PYPORTAL_TSCAL_Y = (5800, 57000)
    ts = adafruit_touchscreen.Touchscreen(board.TOUCH_XL, board.TOUCH_XR,
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
            print("INIT PALETTE") ### TODO REMOVE
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
                 cb=None,
                 cb_kwargs={},
                 blank_char=" "
                 ):
        self._keys = []
        self._dio_keyboard = displayio.Group()
        ### TODO - tidy up all the positioning code
        self._dio_keyboard.x = 8
        self._dio_keyboard.y = 132
        self._key_width = 26
        self._key_height = 26
        self._keycap_fg = keycap_fg
        self._keycap_bg = keycap_bg
        self._keycap_font = keycap_font
        self._initKeys(layout,
                       enter=enter, backspace=backspace, space=space,
                       numbers=numbers, keycaps_upper=keycaps_upper,
                       shift=shift, control=control, symbols=False)
        self._dio_group = displayio.Group()
        self._touch_screen = None
        self._min_press_time = min_press_time
        self._off_time = 0.05
        self._cb = cb
        self._cb_kwargs = cb_kwargs
        self._blank_char = blank_char
        try:
            _ = input_device.touch_point
            self._touch_screen = input_device
        except AttributeError:
            raise ValueError("Need an input_device which supports touch_point")

    def _addButton(self, x, y, key, text, width=None, height=None):
        button = Button(x=x,
                        y=y,
                        width=self._key_width if width is None else width,
                        height=self._key_width if height is None else height,
                        label=text,
                        label_font=self._keycap_font,
                        label_color=self._keycap_fg,
                        fill_color=self._keycap_bg,
                        style=Button.ROUNDRECT)
        self._keys.append(key)
        self._dio_keyboard.append(button)

    def _initKeys(self, layout,
                  enter=True, backspace=True, space=False,
                  numbers=False, keycaps_upper=True,
                  shift=False, control=False, symbols=False):
        try:
            layout = self._ALPHA_LAYOUT[layout]
        except KeyError:
            raise ValueError("Unknown layout " + layout)
        for row_idx, (line, offset) in enumerate(layout):
            x_pos = int(offset * (self._key_width + 5))
            on_last_row = row_idx == len(layout) - 1
            y_pos = row_idx * (self._key_height + 7)
            if enter and on_last_row:
                x_pos = 0  ### remove offset
                wide_width = int(1.333 * self._key_width)
                self._addButton(x_pos, y_pos,
                                self.ENTER, "EN",
                                width=wide_width)
                x_pos += wide_width + 5

            for char in line:
                self._addButton(x_pos, y_pos,
                                char,
                                char.upper() if keycaps_upper else char)
                x_pos += self._key_width + 5

            if backspace and on_last_row:
                wide_width = int(1.333 * self._key_width)
                self._addButton(x_pos, y_pos,
                                self.BACKSPACE, "BS",
                                width=wide_width)
                x_pos += wide_width + 4


    def showKeyboard(self):
        if len(self._dio_group) == 0:
            self._dio_group.append(self._dio_keyboard)


    def hideKeyboard(self):
        if len(self._dio_group) > 0:
            _ = self._dio_group.pop()


    def getChar(self, stay_shown=False):
        key = None
        point = None

        ### Wait for a tap
        self.showKeyboard()
        last_button = None
        while key is None:
            while True:
                point = self._touch_screen.touch_point
                if point is not None:
                    break

            last_keydown_ns = time.monotonic_ns()
            off_keyboard_ns = 0
            while True:
                key_pressed = False
                for b_idx, butt in enumerate(self._dio_keyboard):
                    point_keyb = (point[0] - self._dio_keyboard.x,
                                  point[1] - self._dio_keyboard.y)
                    if butt.contains(point_keyb):
                        key_pressed = True
                        if last_button != butt:
                            last_keydown_ns = time.monotonic_ns()
                            if last_button is not None:
                                last_button.selected = False
                            butt.selected = True
                            key = self._keys[b_idx]
                            last_button = butt
                        break

                ### Ignore press if touch has slid off the keyboard
                if not key_pressed:
                    off_keyboard_ns = time.monotonic_ns()

                if (last_button
                        and (off_keyboard_ns - last_keydown_ns) / 1e9 > self._off_time):
                    last_button.selected = False
                    last_button = None
                    key = None
                    key_pressed = False

                point = self._touch_screen.touch_point
                if point is None:
                    break

            ### Optionally ignore brief key presses
            if last_button and self._min_press_time is not None:
                keyup_ns = time.monotonic_ns()
                press_time = (keyup_ns - last_keydown_ns) / 1e9
                if press_time < self._min_press_time:
                    last_button.selected = False
                    key = None

        ### Clear the visible selection
        if last_button:
            last_button.selected = False

        if not stay_shown:
            self.hideKeyboard()
        print("---")
        return key


    def getLine(self,
                text="",
                min_len=None, max_len=None,
                return_at_max=False, cb_kwargs=None):
        chars = []
        text_idx = 0

        while True:
            if text_idx < len(text):
                char = text[text_idx]
                text_idx += 1
            else:
                char = self.getChar(stay_shown=True)

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
keyboard = Keyboard(ts, cb=grid_set_char)
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
        ### TODO - game requires this to be in word list
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
