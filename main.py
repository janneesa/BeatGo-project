import time
from machine import Pin, I2C, Timer, ADC
from ssd1306 import SSD1306_I2C
from fifo import Fifo

MENU_OPTIONS = ["HR MEASUREMENT",
                "HRV ANALYSIS",
                "KUBIOS",
                "HISTORY"]

# DISPLAY SETUP
i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
oled_width = 128
oled_height = 64
oled = SSD1306_I2C(oled_width, oled_height, i2c)

# ROTARY ENCODER SETUP
class Encoder:
    def __init__(self):
        self.a = Pin(10, Pin.IN, Pin.PULL_UP)
        self.b = Pin(11, Pin.IN, Pin.PULL_UP)
        self.c = Pin(12, Pin.IN, Pin.PULL_UP)
        self.fifo = Fifo(30, typecode = 'i')
        self.a.irq(handler = self.rot_handler, trigger = Pin.IRQ_RISING, hard=True)
        self.c.irq(handler = self.push_handler, trigger = Pin.IRQ_RISING, hard=True)

    def rot_handler(self, pin):
        if self.b():
            self.fifo.put(-1)
        else:
            self.fifo.put(1)

    def push_handler(self, pin):
        self.fifo.put(0)

# SETUP, DEFAULT
rot = Encoder()
selected = 0 
rot_val = 0

while True:
    oled.fill(0)
    for i, menu_item in enumerate(MENU_OPTIONS):
        if selected == i:
            menu_item = "> " + menu_item
        oled.text(menu_item, 0, i * 10, 1)
    oled.show()
    if rot.fifo.has_data():
        cur_rot_val = rot.fifo.get()
        if cur_rot_val == 0:
            if selected == 0:
                print("HR Measurement")
            elif selected == 1:
                print("HRV Analysis")
            elif selected == 2:
                print("Kubios")
            elif selected == 3:
                print("History")
        rot_val += cur_rot_val
        if abs(rot_val) > 5:
            selected += cur_rot_val
            rot_val = 0
            if selected >= len(MENU_OPTIONS):
                selected = 0
            elif selected < 0:
                selected = len(MENU_OPTIONS)-1



