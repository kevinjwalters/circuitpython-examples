# Circuit Playground Express D6 Dice - v2.0
# 
# Roll them bones.
# Tap the CPX twice or shake to roll the die.
# Left button emulates keyboard and types the otal of rolls.
# Right button adjusts brightness.
#
# Authors: Carter Nelson, Kevin Walters

# MIT License

# Copyright (c) 2018 Carter Nelson, Kevin J. Walters

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import time
import random
from adafruit_circuitplayground.express import cpx

from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
 
keyboard = Keyboard()
layout = KeyboardLayoutUS(keyboard)

ROLL_THRESHOLD  = 30        # Total acceleration 
DICE_COLOR      = (0xEA, 0x62, 0x92)  # Dice digits color
DICE_MAXBRIGHTNESS = 6

# dictionary storing the NeoPixels to set for each face
dice_pixels = {
 1 : (2,),
 2 : (4, 9),
 3 : (0, 4, 7),
 4 : (1, 3, 6, 8),
 5 : (0, 2, 4, 5, 9),
 6 : (0, 2, 4, 5, 7, 9)
}

# Configure double tap detection
cpx.detect_taps = 2

# Seed the random function with light sensor value
# (try commenting this out and see if it matters)
random.seed(cpx.light)

# Initialize the global states
new_roll = False
rolling = False
roll_total = 0
dice_color = DICE_COLOR
# Brightness representation is an integer between 0 and DICE_MAXBRIGHTNESS
dice_brightness = DICE_MAXBRIGHTNESS

# Show the die value on the NeoPixels
# Note: this could be more efficient with explicit use of show()
def show_die(pixels, roll, color):
    pixels.fill(0)
    for p in dice_pixels[roll]:
        cpx.pixels[p] = color

# cpx.pixels.brightness is the usual solution to change
# brightness across all NeoPixels - this solution demonstrates
# some programming techniques
##def adjust_color(color, brightness):
##    if brightness < 0.0 or brightness > 1.0:
##        raise ValueError("brightness must be between 0.0 and 1.0")
##  
##    if isinstance(color, tuple):
##        # python list comprehension syntax but for tuples
##        return tuple(int(elem * brightness + 0.5) for elem in color)
##    elif isinstance(color, list):
##        newcolor = []
##        for elem in color:
##            newcolor.append(int(elem * brightness + 0.5))
##        return newcolor
##    elif isinstance(color, int):
##        # pull apart rgb values in int, adjust, then re-assemble
##        r = (color >> 16) & 0xff
##        g = (color >> 8) & 0xFF
##        b = color & 0xfF
##        rgblist = adjust_color([r, g, b])
##        return (rgblist[0] << 16) + (rgblist[1] << 8) + rgblist[2]
##    else:
##        raise ValueError("Unexpected color type: " + type(color))

# Loop forever
while True:
    # If left button pressed and die has been rolled at least once
    # then type the total score and press enter and zero total
    if cpx.button_a and roll_total > 0:
        layout.write(str(roll_total) + '\n')
        roll_total = 0
    
    # If right button pressed the decrease brightness
    # wrap around at 0 to original maximum value
    if cpx.button_b:
        if dice_brightness == 0:
            dice_brightness = DICE_MAXBRIGHTNESS
        else:
            dice_brightness -= 1
        cpx.pixels.brightness = 1 / (2**(DICE_MAXBRIGHTNESS - dice_brightness))
        ##dice_color = adjust_color(dice_color,
        ##                          1 / (2**(DICE_MAXBRIGHTNESS - dice_brightness)))
        ##show_die(cpx.pixels, roll_number, dice_color)
        # wait for use to take finger off button
        while cpx.button_b:
            pass

    # Check for rolling
    if cpx.shake() or cpx.tapped:
        roll_start_time = time.monotonic()
        new_roll = True
        rolling = True
        
    # Rolling momentum
    # Keep rolling for a period of time even after shaking stops
    if new_roll:
        if time.monotonic() - roll_start_time > 1:
            rolling = False
        
    # Display status on NeoPixels
    if rolling:
        # Compute a random number from 1 to 6
        roll_number = random.randrange(1,7)
        # Make some noise and show the dice roll number
        cpx.start_tone(random.randrange(400,2000))
        show_die(cpx.pixels, roll_number, dice_color)
        time.sleep(0.02)
        cpx.stop_tone()
    elif new_roll:
        # Show the dice roll number
        new_roll = False
        show_die(cpx.pixels, roll_number, dice_color)
        roll_total += roll_number
