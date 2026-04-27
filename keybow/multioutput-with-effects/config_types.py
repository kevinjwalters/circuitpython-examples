from adafruit_hid.consumer_control_code import ConsumerControlCode

class CCC(int):
    def __init__(self, arg):
        super().__init__(getattr(ConsumerControlCode, arg))

class MIDI(int):
    pass
