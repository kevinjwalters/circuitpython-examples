### servo-current-mcp3208 v1.4

### Measuring servo current using MCP3208 and optional external LM385 vref

### Copy this file to EDU PICO board as code.py
### Potentiometer should be turned towards 0 to avoid exceeding
### ADC vref if lowered below 3.3V

### MIT License

### Copyright (c) 2024 Kevin J. Walters

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

import array
import gc
import math
import os
import struct
import time

import analogio
import board
import busio
import digitalio
import displayio
import pwmio
import terminalio
from ulab import numpy as np

import adafruit_displayio_ssd1306   ### Not adafruit_ssd1306

##import neopixel
import adafruit_mcp3xxx.mcp3208 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn as MCPAnalogIn
from adafruit_motor import servo
from adafruit_display_text.bitmap_label import Label
##from adafruit_display_text.outlined_label import OutlinedLabel

### EDU PICO has switch on GP15, top position "Enable" is low,
### bottom position "Disable" is high - intended to be used to write enable CIRCUITPY

### EDU PICO's i2c for display
I2C_SDA = board.GP4
I2C_SCL = board.GP5

SERVO_PIN = board.GP6

### EDU PICO's pins for sdcard reader - reused here for MCP3208
SPI_RX  = board.GP16
SPI_CS  = board.GP17
SPI_SCK  = board.GP18
SPI_TX  = board.GP19

### This is GP23 on Pi Pico and WL_GPIO1 on Pi Pico W
PICO_PS_PIN = board.SMPS_MODE

EDU_PICO_POT_PIN = board.GP28
### Avoid GP26 as it's connected to the EDU PICO potentiometer module
ADC_PIN  = board.GP27

SERVO_MIN = 0
SERVO_MAX = 180

##pixels = neopixel.NeoPixel(RGBPIXELS_PIN, NUM_PIXELS, brightness=1, auto_write=False)

pixel_black = 0x000000
pixel_white = 0xffffff

ARDUINO_MIN_PULSE = 544
ARDUION_MAX_PULSE = 2400

SSD1306_WIDTH = 128
SSD1306_HEIGHT = 64
SSD1306_ADDR = 0x3c

LM385_REFV = 1.24

console = False
stats = True
output_type = "bin"

### CIRCUITPY will only be writeable if boot.py has made it so
try:
    file_number = 1
    ### This is fragile if any other similar sounding files appear in the list
    filenames = [x for x in os.listdir("")
                 if x.endswith("." + output_type) and x.startswith("adc-")]
    if filenames:
        file_number = max([int(s.strip("adc-").rstrip("." + output_type)) for s in filenames])
        file_number += 1

    data_file = open("/adc-{:d}.{:s}".format(file_number, output_type), "ab")
except OSError as ose:
    data_file = None


displayio.release_displays()
i2c = busio.I2C(I2C_SCL, I2C_SDA, frequency=400 * 1000)

display_bus = displayio.I2CDisplay(i2c, device_address=SSD1306_ADDR)
display = adafruit_displayio_ssd1306.SSD1306(display_bus,
                                             width=SSD1306_WIDTH,
                                             height=SSD1306_HEIGHT)

### EDU PICO has buttons A yellow (top) on GPO and B cyan (bottom) on GP1
pin_a = board.GP0
pin_b = board.GP1
pin_but_a = digitalio.DigitalInOut(pin_a)
pin_but_a.switch_to_input(pull=digitalio.Pull.UP)
pin_but_b = digitalio.DigitalInOut(pin_b)
pin_but_b.switch_to_input(pull=digitalio.Pull.UP)
yellow_button_a = lambda: not pin_but_a.value
cyan_button_b = lambda: not pin_but_b.value

### RT6154 PS mode - default is low due to hardware pull down
### Low is pulse frequency modulation (PFM)
### High is pulse-width modulation (PWM)
pico_ps_pwm_enable = digitalio.DigitalInOut(PICO_PS_PIN)
pico_ps_pwm_enable.switch_to_output(False)

servo_pwm = pwmio.PWMOut(SERVO_PIN, duty_cycle=0, frequency=50)
myservo = servo.Servo(servo_pwm,
                      min_pulse=ARDUINO_MIN_PULSE, max_pulse=ARDUION_MAX_PULSE)
myservo.angle = None  ### turn off servo

### Default servo range is 750 to 2250, lower than Arduino default
### https://docs.circuitpython.org/projects/motor/en/latest/api.html#adafruit_motor.servo.Servo



spi = busio.SPI(clock=SPI_SCK, MISO=SPI_RX, MOSI=SPI_TX)
cs = digitalio.DigitalInOut(SPI_CS)
mcp = MCP.MCP3208(spi, cs, ref_voltage=LM385_REFV)
ch0_adc = MCPAnalogIn(mcp, MCP.P0)
edu_pico_pot = analogio.AnalogIn(EDU_PICO_POT_PIN)
int_adc = analogio.AnalogIn(ADC_PIN)

font_width, font_height = terminalio.FONT.get_bounding_box()[:2]
left_num = Label(font=terminalio.FONT,
                 text="----",
                 color=pixel_white,
                 background_color=pixel_black,
                 save_text=False)
left_num.y = font_height // 3
right_num = Label(font=terminalio.FONT,
                  text="---- -----",
                  color=pixel_white,
                  background_color=pixel_black,
                  save_text=False)
right_num.x = display.width - 9 * font_width
right_num.y = font_height // 3

### Scale of 2 is viable but it hides most of the display
### for two line messages
message = Label(font=terminalio.FONT,
                        text="",
                        color=pixel_black,
                        background_color=pixel_white,
                        save_text=False,
                        scale=1,
                        line_spacing=0.85,
                        anchor_point=(0.5, 0.5),
                        anchored_position=(display.width // 2, display.height // 2))

num_height = (font_height + 4) // 2
simple_plot_bmp = displayio.Bitmap(display.width, display.height - num_height, 2)
palette = displayio.Palette(2)
palette[1] = 0xffffff

tg = displayio.TileGrid(bitmap=simple_plot_bmp,
                        pixel_shader=palette)
tg.y = num_height
main_group = displayio.Group()
main_group.append(left_num)
main_group.append(right_num)
main_group.append(tg)

display.auto_refresh = False
display.root_group = main_group
display.refresh()

DEF_SAMPLE_COUNT = 200

### 'Q' is 8 bytes in size, 'L' is only 4 on CircuitPython with RP2040
int_values_std = np.zeros(DEF_SAMPLE_COUNT, dtype=np.uint16)
int_values_std_ts = array.array('Q', int_values_std)
mcp_values = np.zeros(DEF_SAMPLE_COUNT, dtype=np.uint16)
mcp_values_ts = array.array('Q', mcp_values)
int_values_lown = np.zeros(DEF_SAMPLE_COUNT, dtype=np.uint16)
int_values_lown_ts = array.array('Q', int_values_lown)


def read_samples(cnt, dly):
    for idx in range(cnt):
        t_int_value_std = time.monotonic_ns()
        int_value_std = int_adc.value

        t_mcp_value = time.monotonic_ns()
        mcp_value = ch0_adc.value

        pico_ps_pwm_enable.value = True
        t_int_value_lown = time.monotonic_ns()
        int_value_lown = int_adc.value
        pico_ps_pwm_enable.value = False

        ### Store values in arrays
        int_values_std[idx] = int_value_std
        int_values_std_ts[idx] = t_int_value_std - start_ns
        mcp_values[idx] = mcp_value
        mcp_values_ts[idx] = t_mcp_value - start_ns
        int_values_lown[idx] = int_value_lown
        int_values_lown_ts[idx] = t_int_value_lown - start_ns

        time.sleep(dly)


def output_samples(cnt, *, pad=" ", pad_len=0, end=b"\x0d\x0a", encoding="ascii"):

    for idx in range(cnt):
        out_bytes = bytearray()
        for name, timestamps, values in (("RP2040 GP27", int_values_std_ts, int_values_std),
                                         ("MCP3208 CH0", mcp_values_ts, mcp_values),
                                         ("RP2040 GP27 PFM", int_values_lown_ts, int_values_lown)
                                        ):
            text = '{:d},{:d},"{:s}",{:d}'.format(timestamps[idx], idx, name, values[idx])

            if pad and pad_len:
                line_text = text + " " * (pad_len - len(text) - len(end))
            else:
                line_text = text

            if console:
                print(line_text)
            if data_file:
                if output_type == "csv":
                    out_bytes += line_text.encode(encoding) + end
                elif output_type == "bin":
                    ### TODO - implement padding
                    out_bytes += struct.pack("!fH", timestamps[idx] * 1e-9, values[idx])

        if data_file:
            data_file.write(out_bytes)

    if data_file:
        data_file.flush()

    if stats:
        npfuncs = (np.min, np.mean, np.median, np.max, np.std)
        print("INT STD", [fn(int_values_std[:cnt]) for fn in npfuncs])
        print("MCP3208", [fn(mcp_values[:cnt]) for fn in npfuncs])
        print("INT LWN", [fn(int_values_lown[:cnt]) for fn in npfuncs])


def display_message(new_text):
    """Show a short message in the middle of the display."""
    changed = True

    if new_text is None:
        if main_group[-1] == message:
            main_group.pop()
        else:
            changed = False
    else:
        message.text = new_text
        if main_group[-1] != message:
            main_group.append(message)

    if changed:
        display.refresh()


def adc_plot_value(value_16b):
    """Map a 12 bit ADC value to 0-63 output."""
    value = value_16b >> 4
    if value < 16:
        return value  ### 0-15
    if value < 48:
        return 16 + ((value - 16) >> 1)  ### 16-31
    elif value < 176:
        return 32 + ((value - 48) >> 3)  ### 32-47
    else:
        return round(math.log(value) * 4.6 + 24.7)  ### 48 to 63


def multiple_samples(count=DEF_SAMPLE_COUNT, delay=0.045):
    gc.collect()
    display_message("Sampling\nfor 10s")
    time.sleep(1)
    read_samples(count, delay)
    display_message("Writing")
    output_samples(count, pad_len=64)
    display_message("Complete")
    time.sleep(1)
    display_message(None)


loop_idx = 0

### Move to middle
myservo.angle = 90
time.sleep(1.0)

max_val = SSD1306_WIDTH // 2 - 1
plot_rows = simple_plot_bmp.height
mcp_history = [max_val] * plot_rows
int_history = [max_val] * plot_rows

last_loop_ns = 0
min_loop_ns = 20_000_000   ### 20ms
number_update_rate = 25
start_ns = time.monotonic_ns()

offset = 0  ### 16bit scaled value

while True:
    if yellow_button_a():
        multiple_samples()

    new_offset = max((edu_pico_pot.value - 1800) // 40, 0)
    offset  = (offset >> 1) + (new_offset >> 1) + 1
    mcp_val = ch0_adc.value
    int_val = int_adc.value

    row_idx = loop_idx % plot_rows
    mcp_val_x = adc_plot_value(mcp_val)
    int_val_x = SSD1306_WIDTH - 1 - adc_plot_value(max((int_val - (offset & 0xfff0)), 0))
    if mcp_val_x != mcp_history [row_idx]:
        simple_plot_bmp[mcp_history[row_idx], row_idx] = 0
        simple_plot_bmp[mcp_val_x, row_idx] = 1
        mcp_history[row_idx] = mcp_val_x

    if int_val_x != mcp_history [row_idx]:
        simple_plot_bmp[int_history[row_idx], row_idx] = 0
        simple_plot_bmp[int_val_x, row_idx] = 1
        int_history[row_idx] = int_val_x

    ### Update numbers less frequently to make them more readable
    if loop_idx % number_update_rate == 0:
        left_num.text = str(mcp_val >> 4)
        right_num.text = "{:4d}-{:<4d}".format(int_val >> 4, offset >> 4)

    display.refresh()
    loop_idx +=1
    while time.monotonic_ns() < last_loop_ns + min_loop_ns:
        if yellow_button_a():
            multiple_samples()

    last_loop_ns = time.monotonic_ns()
