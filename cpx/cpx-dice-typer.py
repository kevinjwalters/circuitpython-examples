# Circuit Playground Express D6 Dice
# 
# Roll them bones.
#
# Author: Carter Nelson
# MIT License (https://opensource.org/licenses/MIT)
import time
import random
from adafruit_circuitplayground.express import cpx

ROLL_THRESHOLD  = 30        # Total acceleration 
DICE_COLOR      = 0xEA6292  # Dice digits color

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

# Loop forever
while True:
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
    
    # Compute a random number from 1 to 6
    roll_number = random.randrange(1,7)
    
    # Display status on NeoPixels
    if rolling:
        # Make some noise and show the dice roll number
        cpx.start_tone(random.randrange(400,2000))
        cpx.pixels.fill(0)
        for p in dice_pixels[roll_number]:
            cpx.pixels[p] = DICE_COLOR
        time.sleep(0.02)
        cpx.stop_tone()
    elif new_roll:
        # Show the dice roll number
        new_roll = False
        cpx.pixels.fill(0)
        for p in dice_pixels[roll_number]:
            cpx.pixels[p] = DICE_COLOR