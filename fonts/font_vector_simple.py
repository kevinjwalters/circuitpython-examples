### font-vector-simple

### MIT License

### Copyright (c) 2019 Kevin J. Walters

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

### size is 50 high, 36 width, all characters same width (monospaced)
### starts at left if possibe and then bottom if possible
### top-left is (0, 0) bottom-right is (36, 50)
### avoid over drawing lines if easy to avoid - assume line thickness is 1

### For simple font keep lines to a minimum
### Can do a more detailed version once this is proven to work ok

### TODO - B-Z and 0-8
FONT_VECTOR_SIMPLE = {
    'A' : [[(0, 50), (0, 0), (36, 0), (36, 50)],
           [(1, 25), (35, 25)],  ### 1 to 35 to avoid overlap
          ],
    'B' : [[ ]], ### TODO
    'C' : [[(36, 0), (0, 0), (0, 50), (36, 50)]],
    'D' : [[(0, 50), (0, 0), (26, 0), (36, 10), (36, 40), (26, 50), (1, 50)]],
    'E' : [[(36, 0), (0, 0), (0, 50), (36, 50)],
           [(1, 25), (26, 25)]],
    
    'Z' : [[(0, 0), (36, 0), (0, 50), (36, 50)]],

    '0' : [[(0, 50), (0, 0), (36, 0), (36, 49)]],
    '1' : [[ ]], ### TODO
    '3' : [[(0, 0), (36, 0), (36, 50), (0, 50)],
           [(10, 25), (35, 25)]],
    '4' : [[(0, 0), (0, 40), (36, 40)],
           [(18, 30), (18, 50)]],  ### crosses other line
    '5' : [[(36, 0), (0, 0), (0, 25), (36, 25), (36, 50), (0, 50)]],
    
    '9' : [[(0, 50), (36, 50), (0, 36), (0, 0), (0, 25), (35, 25)]]
                      }
