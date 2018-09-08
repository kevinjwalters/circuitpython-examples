### For https://github.com/adafruit/Adafruit_CircuitPython_LIS3DH/issues/46
### bugs noted in:
### https://github.com/adafruit/Adafruit_CircuitPython_LIS3DH/blob/3.0.0/examples/spinner.py
### https://github.com/adafruit/Adafruit_CircuitPython_LIS3DH/blob/3.0.0/examples/spinner_advanced.py

import unittest
from unittest.mock import Mock

### A section of spinner example code
def maxmagniffy(lis3dh):
    maxval = lis3dh.acceleration[0]
    for i in range(31):
        x = abs(lis3dh.acceleration[0])
        if x > maxval:
            maxval = x
    return maxval

### Note extra abs()
def maxmagnfixed(lis3dh):
    maxval = abs(lis3dh.acceleration[0])
    for i in range(31):
        x = abs(lis3dh.acceleration[0])
        if x > maxval:
            maxval = x
    return maxval

### negative to positive values
refxnumbers1 = [(x-16)/16 for x in range(16)]+[x/16 for x in range(1,17)]
### negative only values
refxnumbers2 = [(x-32)/32 for x in range(32)]
#refaccels = [(x,0.0,0.0) for x in refxnumbers]

class TestMaxMagn(unittest.TestCase):

    ### lis3dh.acceleration returns a tuple of three
    ### a crude emulation is used here
    def checkMaxMagn(self, thefn, numbers):
        lis3dh = Mock()
        realxmax = max([abs(x) for x in numbers])
        ### iterate over the numbers in different orders
        for i in range(len(numbers)):
            ### create a rotated version of list
            testdata = numbers[i:] + numbers[:i]
            lis3dh.acceleration.__getitem__ = Mock(side_effect = testdata)
            maxval = thefn(lis3dh)
            self.assertEqual(maxval, realxmax)

    def testIffy(self):
        """
        """
        print("checking", refxnumbers1)
        self.checkMaxMagn(maxmagniffy, refxnumbers1) 
        print("checking", refxnumbers2)
        self.checkMaxMagn(maxmagniffy, refxnumbers2) 

    def testFixed(self):
        """
        """
        print("checking", refxnumbers1)
        self.checkMaxMagn(maxmagnfixed, refxnumbers1) 
        print("checking", refxnumbers2)
        self.checkMaxMagn(maxmagnfixed, refxnumbers2) 

verbose=2

if __name__ == '__main__':
    unittest.main(verbosity=verbose)
