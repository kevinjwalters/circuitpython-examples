### A compact DotStar class for PyRuler/Trinket

### SPDX-FileCopyrightText: 2016 Damien P. George (original Neopixel object)
### SPDX-FileCopyrightText: 2017 Ladyada
### SPDX-FileCopyrightText: 2017 Scott Shawcroft for Adafruit Industries
### SPDX-FileCopyrightText: 2025 Kevin J. Walters
###
### SPDX-License-Identifier: MIT

### adafruit_dotstar.DotStar which uses adafruit_pixelbuf.PixelBuf is memory heavy
### This is a very stripped-down, SPI only, pre-PixelBuf version


import busio


START_HEADER_SIZE = 4
LED_START = 0b11100000

class DotStar:
    def __init__(
        self,
        clock,
        data,
        n,
        *,
        auto_write = True,
        brightness = 1.0
    ):
        self._spi = busio.SPI(clock, MOSI=data)
        self._spi.try_lock()
        self._spi.configure(baudrate=4_000_000)
        self._spi.unlock()

        self._n = n
        self.end_header_size = n // 16
        if n % 16 != 0:
            self.end_header_size += 1
        self._buf = bytearray(n * 4 + START_HEADER_SIZE + self.end_header_size)
        self.end_header_index = len(self._buf) - self.end_header_size
        for i in range(START_HEADER_SIZE):
            self._buf[i] = 0x00
        for i in range(START_HEADER_SIZE, self.end_header_index, 4):
            self._buf[i] = 0xFF
        for i in range(self.end_header_index, len(self._buf)):
            self._buf[i] = 0xFF

        self._brightness_byte = round(brightness * 31.49)
        self.auto_write = auto_write

    def _set_item(self, index, value):
        offset = index * 4 + START_HEADER_SIZE
        rgb = value
        if isinstance(value, int):
            rgb = (value >> 16, (value >> 8) & 0xFF, value & 0xFF)

        self._buf[offset] = self._brightness_byte | LED_START
        self._buf[offset + 1] = rgb[2]
        self._buf[offset + 2] = rgb[1]
        self._buf[offset + 3] = rgb[0]

    def __setitem__(self, index, val):
        self._set_item(index, val)

        if self.auto_write:
            self.show()

    def __len__(self):
        return self._n

    def fill(self, color):
        auto_write = self.auto_write
        self.auto_write = False
        for i in range(self._n):
            self[i] = color
        if auto_write:
            self.show()
        self.auto_write = auto_write

    def show(self):
        buf = self._buf
        self._spi.try_lock()
        self._spi.write(buf)
        self._spi.unlock()
