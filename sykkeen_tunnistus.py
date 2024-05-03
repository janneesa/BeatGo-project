from machine import Pin, Signal, I2C, ADC, Timer
from ssd1306 import SSD1306_I2C
import ssd1306
import time
import utime

# ADC and OLED
adc = ADC(26)

i2c = I2C(1, scl=Pin(15), sda=Pin(14))
display = SSD1306_I2C(128, 64, i2c)
last_y = 0

led = Pin("LED", Pin.OUT)

# STATIC VALUES
MAX_CURRENT_250_SAMPLES = 250
MOVING_PPI_MAX = 10
MAX_BPM = 200
MIN_BPM = 30
SAMPLE_MAX_READING = 50000
SAMPLE_MIN_READING = 20000


#####################
# FUNCTIONS
#####################

# REFRESH OLED
def refresh(bpm, beat, v, min_value, maxima):
    global last_y

    display.vline(0, 0, 32, 0)
    display.scroll(-1, 0)  # Scroll left 1 pixel

    if maxima - min_value > 0:
        # Draw beat line.
        y = 32 - int(16 * (v - min_value) / (maxima - min_value))
        display.line(125, last_y, 126, y, 1)
        last_y = y

    # Clear top text area.
    display.fill_rect(0, 0, 128, 16, 0)

    # Show bpm on screen
    if bpm:
        display.text("%d bpm" % bpm, 12, 0)

    display.show()


def calculate_average_ppi(array):
    if array:
        ppi_average = sum(array) / len(array)
        return ppi_average


def calculate_average_bpm(array):
    if array:
        average_hr = sum(array) / len(array)
        average_hr = 60000 / average_hr
        return average_hr


def no_finger_detected():
    display.fill(0)
    display.text("place finger on the sensor", 0, 0)
    display.text("on the sensor", 0, 12)
    display.show()
    time.sleep(3)
    display.fill(0)
    display.show()


def detect():
    # create and zero all variables
    CURRENT_250_SAMPLES = []
    PPI_AVERAGE_ARRAY = []
    PPI_ALL_ARRAY = []
    beat = False
    bpm = None
    INTERVAL_MS = 0
    BEATS_DETECTED = 0
    PPI_AVERAGE_CALCULATED = False
    LAST_TIME = 0
    SAMPLE_TIME = 0
    LAST_SAMPLE_TIME = 0
    DISPLAY_COUNT = 0
    LAST_BPM = 0

    # Clear screen to start.
    display.fill(0)
    no_finger_detected()

    while True:

        new_time = utime.ticks_ms()
        if (new_time - LAST_TIME) > 4:
            LAST_TIME = new_time
            v = adc.read_u16()
            # If gotten sample is out of range ask user to adjust finger.
            if v > SAMPLE_MAX_READING or v < SAMPLE_MIN_READING:
                no_finger_detected()
            else:
                CURRENT_250_SAMPLES.append(v)
                DISPLAY_COUNT += 1

        # Keep list at 250 samples
        CURRENT_250_SAMPLES = CURRENT_250_SAMPLES[-MAX_CURRENT_250_SAMPLES:]

        # Get min and max values to help determine tresholds
        min_value, max_value = min(CURRENT_250_SAMPLES), max(CURRENT_250_SAMPLES)
        # Get average of 250 samples to help determine tresholds
        average_sample = sum(CURRENT_250_SAMPLES) / len(CURRENT_250_SAMPLES)

        # Tresholds
        MAX_TRESHOLD = (min_value + max_value * 3) // 4  # 3/4
        MIN_TRESHOLD = (min_value + max_value) // 2  # 1/2

        # Check if sample is more than 105% of current sample average and check that no beat is currently detected
        if v > MAX_TRESHOLD and beat == False:
            SAMPLE_TIME = new_time
            INTERVAL_MS = SAMPLE_TIME - LAST_SAMPLE_TIME
            # Check if time between samples is more than 200
            if INTERVAL_MS > 200:
                # If 10 beats have been detected we can calculate accurate bpm
                if PPI_AVERAGE_CALCULATED:
                    # Get latest PPI average
                    average = calculate_average_ppi(PPI_AVERAGE_ARRAY)
                    # Check if interval change is within range 70%-130% of the average PPI
                    if INTERVAL_MS > (average * 0.70) and INTERVAL_MS < (average * 1.30):
                        PPI_ALL_ARRAY.append(INTERVAL_MS)
                        # Change beat detected
                        beat = True
                        # Calculate bpm from 10 latest average ppi
                        bpm = calculate_average_bpm(PPI_AVERAGE_ARRAY)
                        if bpm > MAX_BPM or bpm < MIN_BPM:
                            bpm = LAST_BPM
                        else:
                            LAST_BPM = bpm
                        led.on()
                    # Add peak to peak interval to ppi_average_array
                    PPI_AVERAGE_ARRAY.append(INTERVAL_MS)
                    PPI_AVERAGE_ARRAY = PPI_AVERAGE_ARRAY[-MOVING_PPI_MAX:]
                    LAST_SAMPLE_TIME = SAMPLE_TIME

                # If less than 10 beats have been detected. Add possible peak to peak intervals to array so average can be determined
                else:
                    BEATS_DETECTED += 1
                    beat = True
                    if BEATS_DETECTED > 2:
                        PPI_AVERAGE_CALCULATED = True
                        PPI_AVERAGE_ARRAY.append(INTERVAL_MS)
                        PPI_AVERAGE_ARRAY = PPI_AVERAGE_ARRAY[-MOVING_PPI_MAX:]
                    LAST_SAMPLE_TIME = SAMPLE_TIME

        if v < MIN_TRESHOLD and beat == True:
            led.off()
            beat = False

        if DISPLAY_COUNT > 10:
            refresh(bpm, beat, v, min_value, max_value)
            DISPLAY_COUNT = 0


while True:
    detect()

