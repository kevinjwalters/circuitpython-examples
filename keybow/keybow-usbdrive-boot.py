### Disable CIRCUITPY drive over USB
### unless bottom left button is held down at power-up

import board
import digitalio
import storage


bottom_left_switch = digitalio.DigitalInOut(board.SW0)
bottom_left_switch.pull = digitalio.Pull.UP

if bottom_left_switch.value:
    storage.disable_usb_drive()

bottom_left_switch.deinit()
