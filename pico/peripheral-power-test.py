### peripheral-power-test v1.2

### Peripheral power test

### Copy this file to Pi Pico or Feather nRF52840 Express board as code.py

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

### Other "ports"
### https://github.com/kevinjwalters/arduino-examples/blob/master/uno/peripheral-power-test/peripheral-power-test.ino
### https://github.com/kevinjwalters/micropython-examples/blob/master/microbit/peripheral-power-test.py

import os
import time

import board
import digitalio
import pwmio

import neopixel
from adafruit_motor import servo


machine = os.uname().machine
if "Pico" in machine:
    BOARDLED_PIN = board.LED
    HIGH_PIN = board.GP18
    RGBPIXELS_PIN = board.GP19
    SERVO_PIN = board.GP20
elif "Feather" in machine:
    BOARDLED_PIN = board.LED
    HIGH_PIN = board.D6
    RGBPIXELS_PIN = board.D9
    SERVO_PIN = board.D10
elif "Cytron Maker Nano" in machine:
    ### board.LED is just GP2 - use GP16 instead
    BOARDLED_PIN = board.GP16
    HIGH_PIN = board.GP2
    RGBPIXELS_PIN = board.GP3
    SERVO_PIN = board.GP4
else:
    raise ValueError("Unsupported board")


high_out = digitalio.DigitalInOut(HIGH_PIN)
high_out.switch_to_output(True)  ### set high

board_led = digitalio.DigitalInOut(BOARDLED_PIN)
board_led.switch_to_output()

### If NUM_PIXELS is changed then review SERVO_SPEED_LOOPS
NUM_PIXELS = 12
SERVO_SPEED_LOOPS = 4  ### Double speed every N loops

SERVO_MIN = 0
SERVO_MAX = 180

pixels = neopixel.NeoPixel(RGBPIXELS_PIN, NUM_PIXELS, brightness=1, auto_write=False)

pixel_black = 0x000000
pixel_white = 0xffffff

ARDUINO_MIN_PULSE = 544
ARDUION_MAX_PULSE = 2400
servo_pwm = pwmio.PWMOut(SERVO_PIN, duty_cycle=0, frequency=50)
myservo = servo.Servo(servo_pwm,
                       min_pulse=ARDUINO_MIN_PULSE, max_pulse=ARDUION_MAX_PULSE)
myservo.angle = None  ### turn off servo

### Default servo range is 750 to 2250, lower than Arduino default
### https://docs.circuitpython.org/projects/motor/en/latest/api.html#adafruit_motor.servo.Servo


def pixels_off():
    for p_idx in range(NUM_PIXELS):
        pixels[p_idx] = pixel_black
    pixels.show()

pixels_off()


if False:
    ### This is to allow the current for a single pixel to be measured
    ### Unbranded ring of 12 50mm ones, 44mA at 5V, 36mA at 3.3V
    ### all twelve at 5V 403mA
    pixels[0] = pixel_white
    pixels.show()
    time.sleep(3)
    pixels[0] = pixel_black
    pixels.show()
    time.sleep(60)


while True:
    ### Flash onboard LED five times to signify start
    for _ in range(5):
        board_led.value = True
        time.sleep(1)
        board_led.value = False
        time.sleep(1)


    ### Now start the simultaneous pixel lighting and servo movement
    start_pos = SERVO_MIN
    end_pos = SERVO_MAX
    old_start_pos = end_pos
    degree_step = 3
    reps = 1
    duration_s = 2
    for idx in range(NUM_PIXELS):
        pixels[idx] = pixel_white
        pixels.show()

        step_pause_s = degree_step * duration_s / reps / 180
        for swing in range(reps):
            pos = start_pos
            while pos != end_pos:
                myservo.angle = pos
                time.sleep(step_pause_s)

                ### Move the servo position but keep within limits
                if end_pos > start_pos:
                    pos += degree_step
                    if pos > SERVO_MAX:
                        pos = SERVO_MAX
                else:
                    pos -= degree_step
                    if pos < SERVO_MIN:
                        pos = SERVO_MIN


            ### Swap start and end servo positions
            old_start_pos = start_pos
            start_pos = end_pos
            end_pos = old_start_pos

        ### For a ring of 12 every 4 pixels double the number of servo movements
        if idx % SERVO_SPEED_LOOPS == SERVO_SPEED_LOOPS - 1:
            reps *= 2
            degree_step *= 2

    ### Test complete
    pixels_off()
    myservo.angle = None
    time.sleep(10)
