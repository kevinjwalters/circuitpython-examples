### gemma-m0-tinylidar-simple v1.0
### Gemma M0 simple distance reading example from a MicroElectronicDesign tinyLiDAR
### tested with CircuitPython 2.2.0 and tinyLiDAR with firmware 1.3.7

### copy this file to Gemma M0 as main.py 
### needs lib/adafruit_dotstar.mpy and lib/adafruit_bus_device/i2c_device.mpy

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
import busio
import time
import digitalio
import adafruit_dotstar
from adafruit_bus_device.i2c_device import I2CDevice

### For Trinket M0, Gemma M0, and ItsyBitsy M0 Express
### For other boards see
### https://learn.adafruit.com/circuitpython-essentials/circuitpython-internal-rgb-led
board_pixel = adafruit_dotstar.DotStar(board.APA102_SCK, board.APA102_MOSI, 1)
brightred = (255, 0, 0);

board_led = digitalio.DigitalInOut(board.D13)
board_led.direction = digitalio.Direction.OUTPUT

print("creating I2C and I2CDevice object")
### 0x10 is default address of the tinyLiDAR and selecting 100kHz
i2c_addr = 0x10
sclpin = board.D2
sdapin = board.D0
i2c = busio.I2C(sclpin, sdapin, frequency = 100*1000)
device = I2CDevice(i2c, i2c_addr)

getdistancecmd = b'D';
getdistanceresplen = 2

time.sleep(1)

while True:
    distance=-1
    getdistancebuf = bytearray([255] * getdistanceresplen)
    try:
        with device:
            device.write(getdistancecmd)
        with device:
            device.readinto(getdistancebuf)
        distance = (getdistancebuf[0] << 8) + getdistancebuf[1]
        ### distance should be 0 to about 2254, scaling to 8 bit brightness
        pixval = min(int(distance / 10), 255)
        board_pixel[0] = (pixval, pixval, pixval)
        print('distance={:d}mm'.format(distance))
    except Exception as e:
        board_pixel[0] = brightred
        print('exception from write() or readinto(): ' + repr(e))

    ### required pause - comment is based on Arduino minimal example code 
    ### https://microedco.s3.amazonaws.com/tinyLiDAR/Arduino/minimalRead.ino
    time.sleep(0.1)  ### delay as required (13ms or higher in default single step mode)
    board_led.value = not board_led.value

