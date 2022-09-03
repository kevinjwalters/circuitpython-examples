### cloud-status.py v1.0
### Show the status of popular rent-a-computer services

### Tested with Adafruit MagTag and CircuitPython 7.3.3

### copy this file to Adafruit MagTag as code.py

### MIT License

### Copyright (c) 2022 Kevin J. Walters

### Permission is hereby granted, free of charge, to any person obtaining a copy
### of this software and associated documentation files (the "Software"), to deal
### in the Software without restriction, including without limitation the rights
### to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
### copies of the Software, and to permit persons to whom the Software is
### furnished to do so, subject to the following conditions:

### The above copyright notice and this permission notice shall be included in all
### copies or substantial portions of the Software.

### THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
### IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANholdTIES OF MERCHANTABILITY,
### FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
### AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
### LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
### OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
### SOFTWARE.

### GCP implementation is fragile as it's an html scraper with iffy parsing

### TODO AWS, IBM and the other lot
### TODO low power for battery
###      remember light sleep is no use on CircuitPython ESP32-S2
### TODO use NeoPixels dimly, briefly for battery
###      and bright, perm on for usb power
###      indicate fetching, indicate
### TODO odd/even table bg


import time
import re
import ssl

import board
import displayio
import terminalio
import supervisor

from adafruit_bitmap_font import bitmap_font
from adafruit_display_text.bitmap_label import Label
import wifi
import socketpool
import alarm
import adafruit_requests as requests


try:
    from secrets import secrets
except ImportError:
    print("Wi-Fi SSID and password go in secrets.py file")
    raise

SPARTAN_FONT_FILE = "fonts/LeagueSpartan-Light.bdf"
GCP_LOGO_BMP_FILE = "gcp-logo-on-black-100x80.bmp"

debug = 1

def d_print(level, *args, **kwargs):
    """A simple conditional print for debugging based on global debug level."""
    if not isinstance(level, int):
        print(level, *args, **kwargs)
    elif debug >= level:
        print(*args, **kwargs)


### Update every one or five minutes
TOTAL_UPDATE_TIME_S = 20
FREQUENT_SLEEP_TIME_S = 1 * 60 - TOTAL_UPDATE_TIME_S
NORMAL_SLEEP_TIME_S = 5 * 60 - TOTAL_UPDATE_TIME_S
EINK_REFRESH_PAUSE_S = 10
WIFI_RECONNECT_PAUSE_S = 8
FETCH_RETRY_PAUSE_S = 4
GET_TIMEOUT_S = 22


### The four MagTag brightness levels
BLACK = 0x000000
DARKGREY = 0x404040   ### MagTag's eink is very dark for this one
LIGHTGREY = 0x909090
WHITE = 0xffffff


class CloudStatus():
    def __init__(self, provider, display_,
                 *,
                 products=None,
                 table_font=terminalio.FONT,
                 x=0, y=0,
                 width=None, height=None,
                 refresh=True):
        ### MagTag is 296x128
        ### For 6x14 table will be 30 chars wide and 1 header plus 8 data rows
        ### 123456789012345678901234567890
        ### GCE   Amer EMEA APAC M-R. Glob
        ### Game
        cs_width = display_.width if width is None else width
        cs_height = display_.height if width is None else height

        self._cs_width = cs_width
        self._cs_height = cs_height
        self._provide = provider
        self._display = display_
        self._products = products
        self._group = displayio.Group()
        self._group.x = x
        self._group.y = y
        self._name_logo = displayio.Group()
        self._name_logo_width = 25 * cs_width // 74

        self._table_font = table_font
        self._table_font_width, self._table_font_height = table_font.get_bounding_box()[:2]
        self._status_table = displayio.Group()
        ### x offset will be 100 + 16 for MagTag leaving 180 table width
        ### y offset deals with Label's quirky mid height positioning
        self._status_table.x = (25 + 4) * cs_width // 74
        ### self._status_table.y = self._table_font_height // 2
        self._status_table_top_header = displayio.Group()
        self._status_table_side_header = displayio.Group()
        self._col2x = (5 + 1) * self._table_font_width
        self._row2y = self._table_font_height
        self._status_table_values = displayio.Group()
        self._status_table_values.x = self._col2x
        self._status_table_values.y = self._row2y
        self._status_table.append(self._status_table_top_header)
        self._status_table.append(self._status_table_side_header)
        self._status_table.append(self._status_table_values)

        self._status_timestamp = Label(text="",
                                       font=self._table_font,
                                       color=WHITE,
                                       line_spacing=12/14,
                                       anchor_point=(0.5, 0.5),
                                       anchored_position=(self._name_logo_width//2,
                                                          self._cs_height - self._table_font_height))

        self._group.append(self._name_logo)
        self._group.append(self._status_timestamp)
        self._group.append(self._status_table)


        self._refresh = refresh
        if self._display:
            self._display.show(self._group)

        ### Make a tick in a Bitmap
        self._tick_bmp = displayio.Bitmap(8, 8, 2)
        b_y = 5
        y_add = 1
        for b_x in range(8):
            self._tick_bmp[b_x, b_y - 1] = 1
            self._tick_bmp[b_x, b_y] = 1
            b_y += y_add
            if b_y == 8:
                b_y = 6
                y_add = -1

        self._tick_palette = displayio.Palette(2)
        self._tick_palette[0] = BLACK
        self._tick_palette[1] = WHITE


    def fetch(self):
        raise NotImplementedError()


    def _make_tick(self, x=0, y=0):
        t_g = displayio.TileGrid(self._tick_bmp, pixel_shader=self._tick_palette)
        t_g.x = x
        t_g.y = y
        return t_g


    def _init_table(self, locations, products):
        if locations:
            x = self._col2x
            y = self._table_font_height // 2
            header_chars = 4
            for value in locations:
                header = Label(text=value[:header_chars], font=self._table_font, color=WHITE)
                header.x = x
                header.y = y
                self._status_table_top_header.append(header)
                x += (header_chars + 1) * self._table_font_width

        if products:
            x = 0
            y = self._row2y + self._table_font_height // 2
            header_chars = 5
            for value in products:
                header = Label(text=value[:header_chars], font=self._table_font, color=WHITE)
                header.x = x
                header.y = y
                self._status_table_side_header.append(header)
                y += self._table_font_height


    def _update_table(self, table, timestamp):
        ### Remove old values
        for _ in range(len(self._status_table_values)):
            _ = self._status_table_values.pop()

        s_y = 0
        ###table[0] = ["a", "c", "d", None, "o"]
        for row in table:
            s_x = self._table_font_width * 3 // 2
            for col in row:

                if col is not None:
                    if col == "a":
                        status = self._make_tick(x=s_x, y=s_y+4)
                    else:
                        char = "X" if col=="o" else ("D" if col=="d" else col)
                        status = Label(text=char,
                                       font=self._table_font,
                                       color=WHITE,
                                       x=s_x, y=s_y+self._table_font_height//2)
                    self._status_table_values.append(status)
                s_x += self._table_font_width * 5
            s_y += self._table_font_height
        ### TODO timestamp
        if len(timestamp) * self._table_font_width > self._name_logo_width:
            self._status_timestamp.text = re.sub("(2[01]\\d\\d)\s*", "\\1\n", timestamp)
        else:
            self._status_timestamp.text = timestamp


    def update_display(self):
        if self._display and self._refresh:
            try:
                self._display.refresh()
            except RuntimeError:
                time.sleep(EINK_REFRESH_PAUSE_S)
                self._display.refresh()


class CloudStatusGCP(CloudStatus):
    _DEFAULT_PRODUCTS = ["Google Compute Engine",
                         "Persistent Disk",
                         "Google Kubernetes Engine",
                         "Google Cloud Networking",
                         "Virtual Private Cloud (VPC)",
                         "Cloud Load Balancing",
                         "Identity and Access Management",
                         "Game Servers",
                         ##"Orkut II"
                         ]

    ### 5 chars
    _TABLE_PNAMES = {"Google Compute Engine": "GCE",
                     "Persistent Disk": "PD",
                     "Google Kubernetes Engine": "GKE",
                     "Google Cloud Networking": "Net",
                     "Virtual Private Cloud (VPC)": "VPC",
                     "Cloud Load Balancing": "LB",
                     "Identity and Access Management": "IAM",
                     "Game Servers": "Game",
                   }

    ### 4 chars
    _TABLE_LNAMES = {"Americas (regions)": "Amer",
                     "Europe (regions)": "EMEA",
                     "Asia Pacific (regions)": "APAC",
                     "Multi-regions": "M*R",
                     "Global": "Glob",
                     }

    _STATES = {"available": "a",
               "information": "i",
               "disruption": "d",
               "outage": "o",
               "warning": "w",
               }

    def __init__(self, display_, *, products=None):
        gcp_products = self._DEFAULT_PRODUCTS if products is None else products
        super().__init__("GCP", display_, products=gcp_products)
        self._url = "https://status.cloud.google.com/index.html"
        self._data_locations = None
        self._data_product_status = None
        self._data_product_status_ts = None
        self._data_locations_init = False
        self._data_products_init = False

        logo_text = Label(text="Google Cloud",
                          font=bitmap_font.load_font(SPARTAN_FONT_FILE),
                          color=WHITE,
                          x=0, y=10)
        self._name_logo.append(logo_text)
        logo_bmp = displayio.OnDiskBitmap(GCP_LOGO_BMP_FILE)
        logo_tg = displayio.TileGrid(logo_bmp, pixel_shader=logo_bmp.pixel_shader)
        logo_tg.y = 24
        self._name_logo.append(logo_tg)


    def fetch(self):
        ok = True
        response=None
        for _ in range(3):
            try:
                d_print(2, "Fetching", self._url)
                response = requests.get(self._url, timeout=GET_TIMEOUT_S)
                break
            except (RuntimeError, OSError) as ex:
                print("Failed GET request", repr(ex))
                time.sleep(FETCH_RETRY_PAUSE_S)

        if response is None:
            raise ex

        d_print(4, "Response headers", response.headers)
        lump_count = 0
        ### lump_size must be big enough to hold the opening tag
        lump_size = 512
        text_buffer = ""
        trim_tb_size = 4096
        node_count = 0
        found_header = False
        header_row = False
        ### This is slow
        tdth_s = re.compile(r"<(t[dh])(>|\s+[^>]*)>")
        tdth_e = re.compile(r"</(t[dh])>")
        locations = []
        product_status = []
        current_product = None
        for lump in response.iter_content(lump_size):
            ### CircuitPython supportsutf-8 decode() only, no latin_1
            ### re library has some bugs with unicode and regular expression matching
            ### https://github.com/adafruit/circuitpython/issues/6860
            ### Stripping high bit chars for now
            ##text_buffer += lump.decode()
            text_buffer += "".join([chr(b) for b in lump if b <= 127])
            lump_count += 1
            while True:
                m_s = tdth_s.search(text_buffer)
                m_e = tdth_e.search(text_buffer)
                if m_s and m_e:
                    if m_s.start() < m_e.start():
                        ### TODO - check tags match
                        tag = m_s.groups()[0]
                        attr = m_s.groups()[1]
                        node = text_buffer[m_s.end():m_e.start()]
                        if not found_header:
                            if tag == "th" and attr.find("__product") >= 0:
                                found_header = True
                                header_row = True

                        elif header_row:
                            ## TODO d_print(2, "HR TAG", tag, "ATTR", attr, "NODE", node)
                            if tag == "th" and attr.find("__location") >= 0:
                                locations.append(node)
                            else:
                                header_row = False

                        if found_header and not header_row:
                            if tag == "th" and attr.find("__product") >= 0:
                                current_product = node
                                if current_product in self._products:
                                    product_status.append([current_product])
                            elif current_product in self._products and tag == "td" and attr.find("__cell") >= 0:
                                status = None
                                for state in self._STATES:
                                    if node.find("__" + state) >= 0:
                                        status = self._STATES[state]
                                product_status[-1].append(status)

                        d_print(5, "TAG", tag, "ATTR", attr, "NODE", node)
                        node_count += 1
                    else:
                        d_print(2, "Found end tag first")
                    text_buffer = text_buffer[m_e.end():]
                    continue


                ### If there was just a start tag then trim to that
                ### and carry on reading more lumps
                if m_s:
                    if m_s.start() > 0:
                        text_buffer = text_buffer[m_s.start():]
                    if len(text_buffer) > trim_tb_size:
                        text_buffer = text_buffer[lump_size:]
                    break

                ### No start or end tags so discard and read more lumps
                ##text_buffer = ""  ### THIS IS WRONG AS IT CAN KILL HALF A TAG
                break

        d_print(3, "lumps", lump_count, "of size", lump_size, "T?", node_count)
        d_print(3, "locations", locations)
        d_print(3, "product_status", product_status)

        response.close()
        self._data_locations = locations

        ### product_status is in the retrieval order not display order
        products_r_order = [row[0] for row in product_status]
        status_values = []
        for product in self._products:
            try:
                idx = products_r_order.index(product)
                status_values.append(product_status[idx][1:])
                if len(status_values[-1]) != len(locations):
                    d_print(2, "Mismatch between row and header", product)
                    ok = False
            except ValueError:
                status_values.append([None] * len(locations))

        self._data_product_status = status_values
        self._data_product_status_ts = re.sub("^\w+,\s*", "", response.headers["date"])
        return ok


    def update_display(self):
        if not self._data_locations_init or not self._data_products_init:
            locations = products = None
            if not self._data_locations_init:
                locations = [self._TABLE_LNAMES.get(l) if self._TABLE_LNAMES.get(l) else l
                             for l in self._data_locations]

            if not self._data_products_init:
                products = [self._TABLE_PNAMES.get(p) if self._TABLE_PNAMES.get(p) else p
                            for p in self._products]
            super()._init_table(locations, products)
            self._data_locations_init = bool(locations)
            self._data_products_init = bool(products)

        super()._update_table(self._data_product_status, self._data_product_status_ts)
        super().update_display()


display = board.DISPLAY

d_print(1, "Connecting to Wi-Fi")
try:
    wifi.radio.connect(secrets["ssid"],
                       secrets["password"])

    socket = socketpool.SocketPool(wifi.radio)
    requests = requests.Session(socket, ssl.create_default_context())
except OSError:
    print("Failed to connect to Wi-Fi")
    time.sleep(WIFI_RECONNECT_PAUSE_S)
    supervisor.reload()


status_page = CloudStatusGCP(board.DISPLAY)

while True:
    ### TODO - rework exception/retry strategy
    try:
        d_print(1, "Fetching")
        fetch_ok = status_page.fetch()
    except (RuntimeError, OSError) as ex:
        print("Failed GET request:", repr(ex))
        time.sleep(WIFI_RECONNECT_PAUSE_S)
        supervisor.reload()

    if fetch_ok:
        status_page.update_display()
    else:
        print("Failed to parse GET request")

    ### Deep sleep wake-up alarm
    sleep_time = NORMAL_SLEEP_TIME_S
    time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + sleep_time)
    alarm.exit_and_deep_sleep_until_alarms(time_alarm)
    ### Even on USB power this is never reached
