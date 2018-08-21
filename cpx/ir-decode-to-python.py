### ir-decode-to-python v1.0
### Circuit Playground Express (CPX) IR code generator
### Read infrared codes as a user presses each one and names them to 
### generate array and dict data for python code to use

### copy this file to CPX as main.py

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

import time

import micropython

import pulseio
import board
import adafruit_irremote

### Based on the code from
### https://learn.adafruit.com/infrared-ir-receive-transmit-circuit-playground-express-circuit-python/ir-test-with-remote

### See also LIRC database http://lirc.org/ - probably a better source for this data!
### and http://rcoid.de/remotefiles.html looks interesting

### TODO would be useful to understand why max_pulse is set to 5000 in
### https://learn.adafruit.com/hacking-ikea-lamps-with-circuit-playground-express/circuitpython-remote-lamp

memdebug = 0

# Create a 'pulseio' input, to listen to infrared signals on the IR receiver
pulsein = pulseio.PulseIn(board.IR_RX, maxlen=200, idle_state=True)
# Create a decoder that will take pulses and turn them into numbers
decoder = adafruit_irremote.GenericDecode()

### names might be more naturally represented as a dictionary but
### collections.OrderedDict is not available so list works well instead
codes = []
names = []

### Dervived from https://github.com/adafruit/Adafruit_CircuitPython_IRRemote/blob/master/adafruit_irremote.py
### to investigate improving timeout behaviour
### https://github.com/adafruit/Adafruit_CircuitPython_IRRemote/issues/16
def my_read_pulses(input_pulses, max_pulse=10000, blocking=True, timeout=None):
    """Read out a burst of pulses until a pulse is longer than ``max_pulse`` microseconds.
       :param ~pulseio.PulseIn input_pulses: Object to read pulses from
       :param int max_pulse: Pulse duration to end a burst
       :param bool blocking: If True, will block until pulses found.
           If False, will return None if no pulses.
           Defaults to True for backwards compatibility
       :param timeout: set to number of microseconds to wait after a pulse
           or "max_pulse" to set to max_pulse value, default is no timeout.
       """
    if not input_pulses and not blocking:
        return None
    received = []
    if isinstance(timeout,str):
        if timeout == "max_pulse":
            timeout = max_pulse
        else:
            raise ValueError("bogus max_pulse")
    while True:
        t1 = time.monotonic()
        ### Wait for some IR pulses to be received
        while not input_pulses:
            if timeout is not None and received:
                durationus = (time.monotonic() - t1) * 1e6
                if (durationus > timeout):
                    ## print("TIMEOUT ({:f}",durationus)
                    return received ### timeout
            else:
                pass  ### nothing received yet
        while input_pulses:
            pulse = input_pulses.popleft()
            ### This print() completely changes timing - may cause or mask bugs
            ## print('input_pulses={:d} received={:d} latest={:d}'.format(len(input_pulses), len(received), pulse))
            if pulse > max_pulse:
                if not received:
                    continue
                else:
                    return received
            received.append(pulse)
    return received

print("Press button on the remote, then type name of button")
print("Press any button and enter an empty name to finish")
print("Enter IGNORE to not record a bogus value")

pulses = None
while True:
    ### Relocated - see further down
    ##pulsein.clear()
    ### 
    pulses = my_read_pulses(pulsein, timeout="max_pulse")
    print("Decoding {:d} pulses".format(len(pulses)))
    try:
        # Attempt to convert received pulses into numbers
        received_code = decoder.decode_bits(pulses, debug=False)
    except adafruit_irremote.IRNECRepeatException:
        # We got an unusual short code, probably a 'repeat' signal
        print("Try again: " + "NEC repeat!")
        continue
    except adafruit_irremote.IRDecodeException as e:
        # Something got distorted or maybe its not an NEC-type remote?
        print("Try again: " + "Failed to decode: ", e.args)
        continue

    print("NEC Infrared code received: ", received_code)
    codename = input("Enter a unique name for button: ")
    if codename == "":
        break
    ### An attempt to reduce memory fragmentation but pulsein implementation
    ### may use a preallocated buffer and python/micropython memory management
    ### may not do as we wish here
    pulsein.clear()  ### also needed to throw away any extra repeat codes
    del pulses
    if codename != "IGNORE":        
        names.append(codename)
        codes.append(received_code)


#if memdebug: micropython.mem_info(1)

### free up some memory
### previous string concatentation version would blow up with
### MemoryError: memory allocation failed, allocating 767 bytes
### with just 18 IR codes
del pulses
del pulsein

if memdebug: micropython.mem_info(1)

### Generate python code to represent data (pprint not available)
print("### Python code")
print("ircodes = [")
for c in codes:
    print("           " + str(c) + ",")
print("          ]")

print("irnames = {")
for idx in range(len(names)):
    print('           "{:s}": {:d},'.format(names[idx], idx))
print("          }")
