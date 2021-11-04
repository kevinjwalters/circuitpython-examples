### pmsensors-adafruitio v1.0
### Send values from Plantower PMS5003, Sensirion SPS-30 and Omron B5W LD0101 to Adafruit IO

### Tested with Maker Pi PICO using CircuitPython 7.0.0
### and ESP-01S using Cytron's firmware 2.2.0.0

### copy this file to Maker Pi Pico as code.py

### MIT License

### Copyright (c) 2021 Kevin J. Walters

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


import random
import time
from collections import OrderedDict

from secrets import secrets

import board
import busio
import analogio
import digitalio
import pwmio
##import ulab
from neopixel import NeoPixel


### ESP-01S
##import adafruit_requests as requests
import adafruit_espatcontrol.adafruit_espatcontrol_socket as socket
from adafruit_espatcontrol import adafruit_espatcontrol
from adafruit_espatcontrol import adafruit_espatcontrol_wifimanager
import adafruit_minimqtt.adafruit_minimqtt as MQTT
from adafruit_io.adafruit_io import IO_MQTT
from microcontroller import cpu

### Particulate Matter sensors
from adafruit_pm25.uart import PM25_UART
from adafruit_b5wld0101 import B5WLD0101
from adafruit_sps30.i2c import SPS30_I2C



debug = 5
mu_output = 2

### Instructables video was shot with this set to 25 seconds
UPLOAD_PERIOD = 25   ### TODO - DEFAULT VALUE??? 60?   NOTE
ADAFRUIT_IO_GROUP_NAME = "mpp-pm"
VCC_DIVIDER = 2.0
SENSORS = ("pms5003", "sps30", "b5wld0101")

### Pins
SPS30_SDA = board.GP0
SPS30_SCL = board.GP1

PMS5003_EN = board.GP2
PMS5003_RST = board.GP3
PMS5003_TX = board.GP4
PMS5003_RX = board.GP5

B5WLD0101_OUT1 = board.GP10
B5WLD0101_OUT2 = board.GP11
B5WLD0101_VTH = board.GP12

ESP01_TX = board.GP16
ESP01_RX = board.GP17

### Pi Pico only has three analogue capable inputs GP26 - GP28
B5WLD0101_VTH_MON = board.GP26
B5WLD0101_VCC_DIV2 = board.GP27

### Maker Pi Pico has a WS2812 RGB pixel on GP28
### In general, GP28 can be used for analogue input but
### should be last choice given its dual role on this board)
MPP_NEOPIXEL = board.GP28

### RGB pixel indications
GOOD = (0, 8, 0)
UPLOADING = (0, 0, 12)
ERROR = (12, 0, 0)
BLACK = (0, 0, 0)

### Voltage of GPIO PWM
PWM_V = 3.3
MS_TO_NS = 1000 * 1000 * 1000
PMS5003_READ_ATTEMPTS = 10
ADC_SAMPLES = 100

### Data fields to publish to Adafruit IO
UPLOAD_PMS5003 = ("pm10 standard", "pm25 standard")
UPLOAD_SPS30 = ("pm10 standard", "pm25 standard")
UPLOAD_B5WLD0101 = ("raw out1", "raw out2")

UPLOAD_PM_FIELDS = ("pms5003-pm10-standard", "pms5003-pm25-standard",
                    "sps30-pm10-standard",   "sps30-pm25-standard",
                    "b5wld0101-raw-out1",    "b5wld0101-raw-out2")
UPLOAD_V_FIELDS = ("b5wld0101-vth", "b5wld0101-vcc")
UPLOAD_CPU_FIELDS = ("cpu-temperature",)
UPLOAD_FIELDS = UPLOAD_PM_FIELDS + UPLOAD_V_FIELDS + UPLOAD_CPU_FIELDS


def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


pixel = NeoPixel(MPP_NEOPIXEL, 1)
pixel.fill(BLACK)

### Initialise the trio of sensors
### Plantower PMS5003 - serial connected
pms5003_en = digitalio.DigitalInOut(PMS5003_EN)
pms5003_en.direction = digitalio.Direction.OUTPUT
pms5003_en.value = True
pms5003_rst = digitalio.DigitalInOut(PMS5003_RST)
pms5003_rst.direction = digitalio.Direction.OUTPUT
pms5003_rst.value = True
serial = busio.UART(PMS5003_TX,
                    PMS5003_RX,
                    baudrate=9600,
                    timeout=15.0)

### Sensirion SPS30 - i2c connected
i2c = busio.I2C(SPS30_SCL, SPS30_SDA)
pms5003 = PM25_UART(serial)
sps30 = SPS30_I2C(i2c, fp_mode=True)
b5wld0101 = B5WLD0101(B5WLD0101_OUT1, B5WLD0101_OUT2)

### Omron B5W LD0101 - pulsed outputs
### create Vth with smoothed PWM
b5wld0101_vth_pwm = pwmio.PWMOut(B5WLD0101_VTH, frequency=125 * 1000)
### R=10k (to pin) C=0.1uF - looks flat on 0.1 AC on scope
### 0.5 shows as 515mV (496mV on Astro AI at pin GP26, 491mV on resistor on breadboard)
b5wld0101_vth_pwm.duty_cycle = round(0.5 / PWM_V * 65535)
b5wld0101_vth_mon = analogio.AnalogIn(B5WLD0101_VTH_MON)
b5wld0101_vcc_div2 = analogio.AnalogIn(B5WLD0101_VCC_DIV2)


def read_voltages(samples=ADC_SAMPLES):
    v_data = OrderedDict()
    conv = b5wld0101_vth_mon.reference_voltage / (samples * 65535)
    v_data["b5wld0101-vcc"] = (sum([b5wld0101_vcc_div2.value
                                    for _ in range(samples)]) * conv * VCC_DIVIDER)
    v_data["b5wld0101-vth"] = (sum([b5wld0101_vth_mon.value
                                    for _ in range(samples)]) * conv)
    return v_data


def get_pm(sensors):
    all_data = OrderedDict()

    for sensor in sensors:
        s_data = {}
        if sensor == "pms5003":
            for _ in range(PMS5003_READ_ATTEMPTS):
                try:
                    s_data = pms5003.read()
                except RuntimeError:
                    pass
                if s_data:
                    break
        elif sensor == "sps30":
            s_data = sps30.read()
        elif sensor == "b5wld0101":
            s_data = b5wld0101.read()
        else:
            print("Whatcha talkin' bout Willis?")

        for key in s_data.keys():
            new_key = sensor + "-" + key.replace(" ","-")
            all_data[new_key] = s_data[key]

    return all_data


class DataWarehouse():
    SECRETS_REQUIRED = ("ssid", "password", "aio_username", "aio_key")

    def __init__(self, secrets_, *,
                 esp01_pins=[],
                 esp01_uart=None,
                 esp01_baud=115200,
                 pub_prefix="",
                 debug=False ### pylint: disable=redefined-outer-name
                 ):

        if esp01_uart:
            self.esp01_uart = esp01_uart
        else:
            self.esp01_uart = busio.UART(*esp01_pins, receiver_buffer_size=2048)

        self.debug = debug
        self.esp = adafruit_espatcontrol.ESP_ATcontrol(self.esp01_uart,
                                                       esp01_baud,
                                                       debug=debug)
        self.esp_version = self.esp.get_version()
        self.wifi = None
        try:
            _ = [secrets_[key] for key in self.SECRETS_REQUIRED]
        except KeyError:
            raise RuntimeError("secrets.py must contain: "
                               + " ".join(self.SECRETS_REQUIRED))
        self.secrets = secrets_
        self.io = None
        self.pub_prefix = pub_prefix
        self.pub_name = {}
        self.init_connect()


    def init_connect(self):
        self.esp.soft_reset()

        self.wifi = adafruit_espatcontrol_wifimanager.ESPAT_WiFiManager(self.esp,
                                                                        self.secrets)
        ### A few retries here seems to greatly improve reliability
        for _ in range(4):
            print("Connecting to WiFi...")
            try:
                self.wifi.connect()
                print("Connected!")
                break
            except (RuntimeError, TypeError) as ex:
                print("wifi.connect exception", repr(ex))

        ### This uses global variables
        socket.set_interface(self.esp)

        ### MQTT Client
        ### pylint: disable=protected-access
        self.mqtt_client = MQTT.MQTT(
            broker="io.adafruit.com",
            username=self.secrets["aio_username"],
            password=self.secrets["aio_key"],
            socket_pool=socket,
            ssl_context=MQTT._FakeSSLContext(self.esp)
            )
        self.io = IO_MQTT(self.mqtt_client)
        ### Callbacks of interest on io are
        ### on_connect on_disconnect on_subscribe
        self.io.connect()


    def reset_and_reconnect(self):
        self.wifi.reset()
        self.io.reconnect()


    def update_pub_name(self, field_name):
        pub_name = self.pub_prefix + field_name
        return pub_name


    def poll(self):
        poll_ok = True
        try:
            ### Process any incoming messages
            self.io.loop()
        except (ValueError, RuntimeError, MQTT.MMQTTException) as ex:
            print("Failed to get data", repr(ex))

            poll_ok = False

        return poll_ok


    def publish(self, p_data, p_fields):
        all_ok = True
        print("UPLOAD")  ### TODO

        for field_name in p_fields:
            try:
                pub_name = self.pub_name[field_name]
            except KeyError:
                pub_name = self.update_pub_name(field_name)
            try:
                self.io.publish(pub_name, p_data[field_name])
            except (ValueError, RuntimeError, MQTT.MMQTTException):
                all_ok = False
                self.reset_and_reconnect()

        return all_ok


dw = DataWarehouse(secrets,
                   esp01_pins=(ESP01_TX, ESP01_RX),
                   pub_prefix=ADAFRUIT_IO_GROUP_NAME + ".",
                   debug=(debug >= 5))

last_upload_ns = 0

while True:
    pixel.fill(GOOD)
    if not dw.poll():
        pixel.fill(ERROR)
        print("ESP_ATcontrol OKError exception")
        for _ in range(20):
            print("EXCEPTION")

    cpu_temp = cpu.temperature
    voltages = read_voltages()
    time_ns = time.monotonic_ns()

    data = get_pm(SENSORS)
    data.update(voltages)
    data.update({"cpu-temperature": cpu_temp})

    if debug >= 2:
        print(data)
    elif mu_output:
        output = ("("
                  + ",".join(str(item)
                             for item in [data[key] for key in UPLOAD_PM_FIELDS])
                  + ")")
        print(output)

    if time_ns - last_upload_ns >= UPLOAD_PERIOD * MS_TO_NS:
        pixel.fill(UPLOADING)
        pub_ok = dw.publish(data, UPLOAD_FIELDS)
        pixel.fill(GOOD if pub_ok else ERROR)
        if pub_ok:
            last_upload_ns = time_ns
        else:
            for _ in range(20):
                print("UPLOAD ERROR")

    time.sleep(1.5 + random.random())
