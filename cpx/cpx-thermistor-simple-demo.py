### cpx-thermistor-simple-demo v1.0
### Circuit Playground Express (CPX) thermistor demo
### prints temperature every half second and displays as binary on neopixels

### copy this file to CPX as main.py

### MIT License

### Copyright (c) 2018 Kevin J. Walters

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


import board
import digitalio
import time

import neopixel
import adafruit_thermistor

### Inspire by https://learn.adafruit.com/adafruit-circuit-playground-express/playground-temperature
### Some values specific to CPX
series_resistor     = 10000
nominal_resistance  = 10000
nominal_temperature = 25
b_coefficient       = 3950
thermistor = adafruit_thermistor.Thermistor(board.TEMPERATURE,
                                            series_resistor,
                                            nominal_resistance,
                                            nominal_temperature,
                                            b_coefficient)

redled = digitalio.DigitalInOut(board.D13)
redled.direction = digitalio.Direction.OUTPUT

black = (0, 0, 0)
red   = (0x20, 0, 0)
green = (0, 0x20, 0)
blue  = (0, 0, 0x20)

### CPX has 10 leds
leds = neopixel.NeoPixel(board.NEOPIXEL, 10, auto_write=False)

tempbits = 8
tempbitsfmt = '{0:0' + str(tempbits) + 'b}'

redled.value = False
colours = [red, green, blue]
colouridx=0
while True:
    temp_c = thermistor.temperature
    print("Temperature is: {:.2f}C".format(temp_c))
    temp_c_binarystr = tempbitsfmt.format(int(temp_c + 0.5))
    for idx in range(len(temp_c_binarystr)):
        if temp_c_binarystr[idx] == '0':
            leds[idx] = black
        elif temp_c_binarystr[idx] == '1':
            leds[idx] = red
            
    ### lightshow on the remaining two leds
    leds[tempbits:] = [colours[colouridx]] * (len(leds) - tempbits)
    colouridx += 1
    if colouridx >= len(colours):
        colouridx = 0
    
    leds.show()
    redled.value = not redled.value
    time.sleep(0.5)
