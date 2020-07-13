### clue-label-test v1.0
### Test labels with a background with various libraries

### Tested with CLUE and Circuit Playground Bluefruit Alpha with TFT Gizmo
### using CircuitPython and 5.3.0

### copy this file to CLUE as code.py

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
import gc

import board
import displayio
from displayio import Group
import terminalio

### These are libraries renamed based on
### prefix of their git commit
from adafruit_display_text.label_b506a0a import Label as LabelFeb
from adafruit_display_text.label_f5288fc import Label as LabelJun
from adafruit_display_text.label_bbc0ea9 import Label as LabelJul


display = board.DISPLAY
font = terminalio.FONT
scale = 2

mem_free1 = 0
mem_free_feb = 0
mem_free_jun = 0
mem_free_jul = 0

mem_free1 = gc.mem_free()
label_feb = LabelFeb(font,
                     text="This is\na Label\nFEB",
                     scale=scale,
                     color=0xffff00,
                     background_color=0x0000ff)
mem_free_feb = gc.mem_free()

label_jun = LabelJun(font,
                     text="This is\na Label\nJUN",
                     scale=scale,
                     color=0xffff00,
                     background_color=0x0000ff)               
mem_free_jun = gc.mem_free()
            
label_jul = LabelJul(font,
                     text="This is\na Label\nJUL",
                     scale=scale,
                     color=0xffff00,
                     background_color=0x0000ff)                   
mem_free_jul = gc.mem_free()

mem_free_jul = mem_free_jun - mem_free_jul
mem_free_jun = mem_free_feb - mem_free_jun
mem_free_feb = mem_free1 - mem_free_feb

print("MF (NO GC)",
      "Feb", mem_free_feb, 
      "Jun", mem_free_jun, 
      "Jul", mem_free_jul) 

time.sleep(4)

font_width, font_height = font.get_bounding_box()

steps = 36
### Large enough radius to test out clipping too
radius = display.width // 2 - 40
### label width is 15
x_off = round((display.width - 7 * scale * font_width) / 2)
y_off = display.height // 2
pos = []


### Make an array of positions around a circle
for step in range(steps):
    rad_angle = step * 2 * math.pi / steps
    x_pos = round(x_off + math.sin(rad_angle) * radius)
    y_pos = round(y_off - math.cos(rad_angle) * radius)
    pos.append((x_pos, y_pos))


### Move each label around the circle in approximately
### 2 seconds then pause for 1 seconds
while True:
    for label in (label_feb, label_jun, label_jul):
        display.show(label)
        for px, py in pos:
            label.x = px
            label.y = py
            time.sleep(1.0 / steps - 0.003)
        
        time.sleep(2.0)
