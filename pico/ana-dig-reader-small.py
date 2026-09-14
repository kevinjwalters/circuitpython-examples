
import os
import time
import analogio
import board
import busio
import digitalio
SOFTWARE_NAME = "ana-dig-reader"
SOFTWARE_VERSION = "1.4"
LED_ON = True
LED_OFF = False
sysname = os.uname().sysname
machine = os.uname().machine
if (machine.find("Adafruit Feather M4 Express") >= 0 or
      machine.find("CircuitPlayground Express") >= 0 or
      machine.find("FeatherS2 with ESP32S2") >= 0 or
      machine.find("Adafruit Feather nRF52840 Express") >= 0):
    SERIAL_TX_PIN = board.TX   
    SERIAL_RX_PIN = board.RX   
    GPIO_PIN = board.A5
    LED_BUILTIN_PIN = board.LED
else:
    raise ValueError("Unsupported board...")
if machine.find("FeatherS2 with ESP32S2") >= 0:
    BOARD_MANU = "UM"
    BOARD_NAME = machine
elif machine.find("micro:bit") >= 0:
    BOARD_MANU = "BBC"
    BOARD_NAME = "micro:bit v2"
else:
    BOARD_MANU, BOARD_NAME = machine.split(" ", 2 - 1)
with_pos = BOARD_NAME.find(" with ")
if with_pos >= 0:
    BOARD_NAME = BOARD_NAME[:with_pos]
BOARD_MCU = sysname.upper()
elems = BOARD_MCU.split("ESP32")
if len(elems) == 2 and len(elems[1]) > 0:
    
    BOARD_MCU = "ESP32-" + elems[1]
pixels = None
if machine.find("CircuitPlayground Express") >= 0:
    import neopixel
    pixels = neopixel.NeoPixel(board.NEOPIXEL, 10)
if pixels:
    pixels.fill(0)  
ANALOGUE_PIN = str(GPIO_PIN).replace("board.", "")
ADC_VREF = 3.3
ADC_RESOLUTION = 12
SHIFT_BITS = 16 - ADC_RESOLUTION
if LED_BUILTIN_PIN is not None:
    led_builtin = digitalio.DigitalInOut(LED_BUILTIN_PIN)
    led_builtin.direction = digitalio.Direction.OUTPUT
    led_builtin.value = LED_OFF
else:
    led_builtin = None
SERIAL_BAUDRATE = 38400
CMD_READ_TIMEOUT_S = 1.0
serial = busio.UART(tx=SERIAL_TX_PIN, rx=SERIAL_RX_PIN,
                    baudrate=SERIAL_BAUDRATE,
                    timeout=CMD_READ_TIMEOUT_S)
READ_ANA_CMD = "A"
READM_ANA_CMD = "B"
READV_ANA_CMD = "C"
INFO_CMD = "I"
COUNT_OFFSET = ord(" ")
ENCODING = "utf-8"
gpio = None
def get_sample_analogue(ana, *,
                        samples=None,
                        iqrmean=True):
    if not iqrmean:
        return ana.value
def str_to_bytes(text):
    try:
        text_as_bytes = text.encode(ENCODING)
    except AttributeError:
        text_as_bytes = bytes(ord(c) for c in text)
    return text_as_bytes
def flash(f_count):
    if led_builtin is not None:
        for _ in range(f_count):
            led_builtin.value = LED_ON
            time.sleep(0.3)
            led_builtin.value = LED_OFF
            time.sleep(0.3)
flash(2)
one_byte_buf = bytearray(1)
while True:
    if serial.in_waiting:
        serial.readinto(one_byte_buf)
        cmd = chr(one_byte_buf[0])
        value = None
        if cmd in (READ_ANA_CMD, READM_ANA_CMD, READV_ANA_CMD):
            
            if not isinstance(gpio, analogio.AnalogIn):
                if gpio is not None:
                    gpio.deinit()
                gpio = analogio.AnalogIn(GPIO_PIN)
            if cmd == READ_ANA_CMD:
                value = get_sample_analogue(gpio)
            elif cmd == READM_ANA_CMD:
                pass   
            else:
                one_byte_buf[0] = COUNT_OFFSET
                serial.readinto(one_byte_buf)  
                count = one_byte_buf[0] - COUNT_OFFSET
                
                
                if count > 0:
                    for _ in range(count - 1):
                        serial.write(str_to_bytes(f"{get_sample_analogue(gpio, iqrmean=False) >> SHIFT_BITS} "))
                    serial.write(str_to_bytes(f"{get_sample_analogue(gpio, iqrmean=False) >> SHIFT_BITS}\n"))
                else:
                    value = ""
        elif cmd == INFO_CMD:
            flash(3)
            value = (f'"INFO","{SOFTWARE_NAME:s}","{SOFTWARE_VERSION:s}",' +
                     f'"{BOARD_MANU:s}","{BOARD_NAME:s}","{BOARD_MCU:s}",' +
                     '"CircuitPython",' +
                     f'"adc_bits={ADC_RESOLUTION:d};aref={ADC_VREF:.1f};' +
                     f'input_pin={ANALOGUE_PIN:s};read=raw"')
        elif cmd in ("\r", "\n", "\0"):
            pass   
        elif len(cmd) > 0:
            value = ""
        if value is not None:
            serial.write(str_to_bytes(f"{value}\n"))
