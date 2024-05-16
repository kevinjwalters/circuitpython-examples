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


import array
import math

import bitmaptools


### This is some basic arc drawing code for single pixel width curves
### drawn with some straight line segments
### There are going to be more efficient ways to draw arcs ...

### Yet More Graphics Primitives
class YMGP:

    ###
    ### Angle is from anti-clockwise from east, For angles 0 is right, pi/2 is up

    @classmethod
    def draw_arc_cr_rad(cls,
                        bitmap,
                        cx,
                        cy,
                        radius,
                        start_angle,
                        angle,
                        pal_idx,
                        *,
                        segments=None):
        """ ."""
        ### pylint: disable=too-many-locals

        l_segments = 2 + round(angle * radius / 10.0) if segments is None else segments

        num_points = l_segments + 1
        x_points = array.array("h", [0] * num_points)
        y_points = array.array("h", [0] * num_points)
        p_idx = 0
        for i in range(num_points):
            alpha = i * angle / l_segments + start_angle
            x0 = radius * math.cos(alpha)
            y0 = radius * math.sin(alpha)
            x_points[p_idx] = round(cx + x0)
            y_points[p_idx] = round(cy - y0)  ### TODO does this need to be negative
            p_idx = p_idx + 1

        bitmaptools.draw_polygon(bitmap,
                                 x_points,
                                 y_points,
                                 pal_idx,
                                 close=False)


    @classmethod
    def draw_arc_points(cls,
                        bitmap,
                        x1,
                        y1,
                        x2,
                        y2,
                        radius,
                        pal_idx,
                        *,
                        segments=None):
        """Draw an arc from x1,y1 to x2,y2 with radius using segments number of lines."""
        ### pylint: disable=too-many-locals

        ### Calculate vector components for the line
        ldx = x2 - x1
        ldy = y2 - y1
        line_len = math.sqrt(ldx * ldx + ldy * ldy)
        ### Angle is from anti-clockwise from east
        line_angle = 0.0 - math.atan2(ldy, ldx)

        line_over_diameter = line_len / (2 * radius)
        if line_over_diameter > 1.0:
            line_over_diameter = 1.0
            ##raise ValueError("Radius is not large enough")

        half_angle = math.asin(line_over_diameter)
        height = radius * math.cos(half_angle)

        cx = x1 + ldx / 2 + height * (ldy / line_len)
        cy = y1 + ldy / 2 - height * (ldx / line_len)

        cls.draw_arc_cr_rad(bitmap,
                            cx,
                            cy,
                            radius,
                            line_angle - half_angle - math.pi / 2,
                            2 * half_angle,
                            pal_idx,
                            segments=segments)
