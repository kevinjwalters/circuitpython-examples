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

import struct

from adafruit_ble.advertising import Advertisement, LazyObjectField
from adafruit_ble.advertising.standard import ManufacturerData, ManufacturerDataField

### TODO - this is flawed because of the absence of version numbers to identify the
###        protocol / message type / type of crypto used

### These are in adafruit_ble.advertising but are private :(
MANUFACTURING_DATA_ADT = const(0xFF)
ADAFRUIT_COMPANY_ID = const(0x0822)

### This is from https://github.com/adafruit/Adafruit_CircuitPython_BLE_BroadcastNet/blob/c6328d5c7edf8a99ff719c3b1798cb4111bab397/adafruit_ble_broadcastnet.py#L84-L85
ADAFRUIT_SEQ_ID = const(0x0003)

### According to https://github.com/adafruit/Adafruit_CircuitPython_BLE/blob/master/adafruit_ble/advertising/adafruit.py
### 0xf000 (to 0xffff) is for range for Adafruit customers
GM_JOIN_ID = const(0xfe30)

RPS_VERSION = const(0xff30)
### DIRTY HACK - cannot us 0xff31 for RPS_ROUND_ID
### DIRTY HACK - as number affects hash order and order affects prefix matching
### 0xff42 was moved by 0x0003
RPS_ROUND_ID = const(0xff74)

RPS_ENC_DATA_ID = const(0xff34)
### DIRTY HACK - cannot use 0xff33 for RPS_KEY_DATA_ID
### DIRTY HACK - as number affects hash order and order affects prefix matching
### Issue raised in https://github.com/adafruit/Adafruit_CircuitPython_BLE/issues/79
RPS_KEY_DATA_ID = const(0xff54)

### DIRTY HACK - cannot use 0xff35 for RPS_KEY_DATA_ID
### DIRTY HACK - as number affects hash order and order affects prefix matching
RPS_ACK_ID = const(0xff52)

### TODO prefix improvements mentioned in https://github.com/adafruit/Adafruit_CircuitPython_BLE/issues/82
### may not happen in time though

### Data formats for shared fields
### The ManufacturerDataField does not currently properly support data-less
### fields - _DATA_FMT_ACK only needs to be present / not present
_DATA_FMT_ROUND = "B"
_DATA_FMT_ACK = "B"

_SEQ_FMT = "B"


class RpsEncDataAdvertisement(Advertisement):
    """An RPS (broadcast) message.
       This sends the encrypted choice of the player. 
       This is not connectable and does not elicit a scan response
       based on defaults in Advertisement parent class. 
       """
    flags = None

    _PREFIX_FMT = "<B" "BHBH"
    _DATA_FMT_ENC_DATA = "8s"

    ### prefix appears to be used to determine whether an incoming
    ### packet matches this class
    ### The second struct.calcsize needs to include the _DATA_FMT(s) for some
    ### reason I either don't know or can't remember
    prefix = struct.pack(
        _PREFIX_FMT,
        struct.calcsize(_PREFIX_FMT) - 1,
        MANUFACTURING_DATA_ADT,
        ADAFRUIT_COMPANY_ID,
        ##struct.calcsize("<H" + _SEQ_FMT + _DATA_FMT),
        ##struct.calcsize("<H" + _DATA_FMT_ENC_DATA + _DATA_FMT_ROUND),  ### does not work
        struct.calcsize("<H" + _DATA_FMT_ENC_DATA),
        ##struct.calcsize("<H"),
        RPS_ENC_DATA_ID
    )
    manufacturer_data = LazyObjectField(
        ManufacturerData,
        "manufacturer_data",
        advertising_data_type=MANUFACTURING_DATA_ADT,
        company_id=ADAFRUIT_COMPANY_ID,
        key_encoding="<H"
    )

### https://github.com/adafruit/Adafruit_CircuitPython_BLE_BroadcastNet/blob/c6328d5c7edf8a99ff719c3b1798cb4111bab397/adafruit_ble_broadcastnet.py#L66-L67
### has a sequence_number - this will be use for for Complex Game
###    sequence_number = ManufacturerDataField(0x0003, "<B")
###    """Sequence number of the measurement. Used to detect missed packets."""

    sequence_number = ManufacturerDataField(ADAFRUIT_SEQ_ID, "<" + _SEQ_FMT)
    """Sequence number of the data. Used in acknowledgements."""

    enc_data = ManufacturerDataField(RPS_ENC_DATA_ID, "<" + _DATA_FMT_ENC_DATA)
    round_no = ManufacturerDataField(RPS_ROUND_ID, "<" + _DATA_FMT_ROUND)
    ack = ManufacturerDataField(RPS_ACK_ID, "<" + _DATA_FMT_ACK)
    """Round number starting at 1."""

    def __init__(self, *, enc_data=None, round_no=None, ack=None, sequence_number=None):
        """ack must be set to () to send this optional, data-less field."""
        super().__init__()
        if enc_data is not None:
            self.enc_data = enc_data
        if round_no is not None:
            self.round_no = round_no
        if ack is not None:
            self.ack = ack
        if sequence_number is not None:
            self.sequence_number = sequence_number


class RpsKeyDataAdvertisement(Advertisement):
    """An RPS (broadcast) message.
       This sends the key to decrypt the previous encrypted choice of the player.
       This is not connectable and does not elicit a scan response
       based on defaults in Advertisement parent class. 
       """
    flags = None

    _PREFIX_FMT = "<B" "BHBH"
    _DATA_FMT_KEY_DATA = "8s"

    ### prefix appears to be used to determine whether an incoming
    ### packet matches this class
    ### The second struct.calcsize needs to include the _DATA_FMT for some
    ### reason I either don't know or can't remember
    prefix = struct.pack(
        _PREFIX_FMT,
        struct.calcsize(_PREFIX_FMT) - 1,
        MANUFACTURING_DATA_ADT,
        ADAFRUIT_COMPANY_ID,
        struct.calcsize("<H" + _DATA_FMT_KEY_DATA),
        RPS_KEY_DATA_ID
    )
    manufacturer_data = LazyObjectField(
        ManufacturerData,
        "manufacturer_data",
        advertising_data_type=MANUFACTURING_DATA_ADT,
        company_id=ADAFRUIT_COMPANY_ID,
        key_encoding="<H"
    )

    sequence_number = ManufacturerDataField(ADAFRUIT_SEQ_ID, "<" + _SEQ_FMT)
    """Sequence number of the data. Used in acknowledgements."""

    key_data = ManufacturerDataField(RPS_KEY_DATA_ID, "<" + _DATA_FMT_KEY_DATA)
    round_no = ManufacturerDataField(RPS_ROUND_ID, "<" + _DATA_FMT_ROUND)
    ack = ManufacturerDataField(RPS_ACK_ID, "<" + _DATA_FMT_ACK)
    """Round number starting at 1."""

    def __init__(self, *, key_data=None, round_no=None, ack=None, sequence_number=None):
        """ack must be set to () to send this optional, data-less field."""
        super().__init__()
        if key_data is not None:
            self.key_data = key_data
        if round_no is not None:
            self.round_no = round_no
        if ack is not None:
            self.ack = ack
        if sequence_number is not None:
            self.sequence_number = sequence_number


class RpsRoundEndAdvertisement(Advertisement):
    """An RPS (broadcast) message.
       This informs other players the round_no is complete.
       This is not connectable and does not elicit a scan response
       based on defaults in Advertisement parent class. 
       """
    flags = None

    _PREFIX_FMT = "<B" "BHBH"

    ### prefix appears to be used to determine whether an incoming
    ### packet matches this class
    ### The second struct.calcsize needs to include the _DATA_FMT for some
    ### reason I either don't know or can't remember
    prefix = struct.pack(
        _PREFIX_FMT,
        struct.calcsize(_PREFIX_FMT) - 1,
        MANUFACTURING_DATA_ADT,
        ADAFRUIT_COMPANY_ID,
        struct.calcsize("<H" + _DATA_FMT_ROUND),
        RPS_ROUND_ID
    )
    manufacturer_data = LazyObjectField(
        ManufacturerData,
        "manufacturer_data",
        advertising_data_type=MANUFACTURING_DATA_ADT,
        company_id=ADAFRUIT_COMPANY_ID,
        key_encoding="<H"
    )

    sequence_number = ManufacturerDataField(ADAFRUIT_SEQ_ID, "<" + _SEQ_FMT)
    """Sequence number of the data. Used in acknowledgements."""

    round_no = ManufacturerDataField(RPS_ROUND_ID, "<" + _DATA_FMT_ROUND)
    ack = ManufacturerDataField(RPS_ACK_ID, "<" + _DATA_FMT_ACK)
    """Round number starting at 1."""

    def __init__(self, *, round_no=None, ack=None, sequence_number=None):
        """ack must be set to () to send this optional, data-less field."""
        super().__init__()
        if round_no is not None:
            self.round_no = round_no
        if ack is not None:
            self.ack = ack
        if sequence_number is not None:
            self.sequence_number = sequence_number


class JoinGameAdvertisement(Advertisement):
    """A join game (broadcast) message used as the first message to work out who is playing.
       This is not connectable and does not elicit a scan response
       based on defaults in Advertisement parent class. 
       """
    flags = None

    _PREFIX_FMT = "<B" "BHBH"
    _DATA_FMT = "8s"  ### this NUL pads for 8s if necessary

    ### prefix appears to be used to determine whether an incoming
    ### packet matches this class
    ### The second struct.calcsize needs to include the _DATA_FMT for some
    ### reason I either don't know or can't remember
    prefix = struct.pack(
        _PREFIX_FMT,
        struct.calcsize(_PREFIX_FMT) - 1,
        MANUFACTURING_DATA_ADT,
        ADAFRUIT_COMPANY_ID,
        ##struct.calcsize("<H" + _SEQ_FMT + _DATA_FMT),
        struct.calcsize("<H" + _DATA_FMT),
        ##struct.calcsize("<H"),
        GM_JOIN_ID
    )
    manufacturer_data = LazyObjectField(
        ManufacturerData,
        "manufacturer_data",
        advertising_data_type=MANUFACTURING_DATA_ADT,
        company_id=ADAFRUIT_COMPANY_ID,
        key_encoding="<H"
    )

    game = ManufacturerDataField(GM_JOIN_ID, "<" + _DATA_FMT)
    """RPS choice."""

    def __init__(self, *, game=None):
        super().__init__()
        if game is not None:
            self.game = game
