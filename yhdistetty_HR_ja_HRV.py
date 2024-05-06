import micropython
import ssd1306
import fifo
from fifo import Fifo
import time
import utime
import machine
from machine import Pin, UART, I2C, Timer, ADC
from ssd1306 import SSD1306_I2C
from filefifo import Filefifo
import urequests as requests
import ujson
import network
from time import sleep
from umqtt.simple import MQTTClient

##################
# ADC, OLED, LED #
##################
adc = ADC(26)

display_WIDTH = 128
display_HEIGHT = 64
i2c = I2C(1, scl=Pin(15), sda=Pin(14), freq=400000)
display = SSD1306_I2C(display_WIDTH, display_HEIGHT, i2c)

micropython.alloc_emergency_exception_buf(200)

led = Pin("LED", Pin.OUT)

#################
# STATIC VALUES #
#################
MAX_CURRENT_250_SAMPLES = 250
MOVING_PPI_MAX = 10
MAX_BPM = 200
MIN_BPM = 30
SAMPLE_MAX_READING = 50000
SAMPLE_MIN_READING = 20000

# Network credentials
SSID = "KME759_Group_2"
PASSWORD = "group2budapest"
BROKER_IP = "192.168.2.253"

# Kubios credentials
APIKEY = "pbZRUi49X48I56oL1Lq8y8NDjq6rPfzX3AQeNo3a"
CLIENT_ID = "3pjgjdmamlj759te85icf0lucv"
CLIENT_SECRET = "111fqsli1eo7mejcrlffbklvftcnfl4keoadrdv1o45vt9pndlef"

LOGIN_URL = "https://kubioscloud.auth.eu-west-1.amazoncognito.com/login"
TOKEN_URL = "https://kubioscloud.auth.eu-west-1.amazoncognito.com/oauth2/token"
REDIRECT_URI = "https://analysis.kubioscloud.com/v1/portal/login"

#############
# Variables #
#############
menu_option = 1
last_time = 0
last_y = 0


######################
# Encoder and button #
######################
# Encoder
class Encoder:
    def __init__(self, rot_a, rot_b):
        self.a = Pin(rot_a, mode=Pin.IN, pull=Pin.PULL_UP)
        self.b = Pin(rot_b, mode=Pin.IN, pull=Pin.PULL_UP)
        self.fifo = Fifo(30, typecode='i')
        self.a.irq(handler=self.handler, trigger=Pin.IRQ_RISING, hard=True)

    def handler(self, pin):
        if self.b():
            self.fifo.put(-1)
        else:
            self.fifo.put(1)

# Create Rot
rot = Encoder(10, 11)


# Button
class Button:
    def __init__(self, pin):
        self.a = Pin(pin, mode=Pin.IN, pull=Pin.PULL_UP)
        self.fifo = Fifo(30, typecode='i')
        self.a.irq(handler=self.handler, trigger=Pin.IRQ_RISING, hard=True)

    def handler(self, pin):
        global last_time
        new_time = utime.ticks_ms()
        if (new_time - last_time) > 200:
            last_time = new_time
            self.fifo.put(1)

# Create button
button = Button(12)


#############
# FUNCTIONS #
#############
# Draw menu options
def draw_menu():
    if menu_option <= 5:
        display.fill(0)
        display.text("> HR", 0, 0)
        display.text("  HRV", 0, 10)
        display.text("  HISTORY", 0, 20)
        display.text("  KUBIOS", 0, 30)
        display.show()
    elif menu_option <= 10 and menu_option > 5:
        display.fill(0)
        display.text("  HR", 0, 0)
        display.text("> HRV", 0, 10)
        display.text("  HISTORY", 0, 20)
        display.text("  KUBIOS", 0, 30)
        display.show()
    elif menu_option <= 15 and menu_option > 10:
        display.fill(0)
        display.text("  HR", 0, 0)
        display.text("  HRV", 0, 10)
        display.text("> HISTORY", 0, 20)
        display.text("  KUBIOS", 0, 30)
        display.show()
    elif menu_option <= 20 and menu_option > 15:
        display.fill(0)
        display.text("  HR", 0, 0)
        display.text("  HRV", 0, 10)
        display.text("  HISTORY", 0, 20)
        display.text("> KUBIOS", 0, 30)
        display.show()


# Select Wanted program
def select_program():
    if menu_option <= 5:
        detect_hr()
    elif menu_option <= 10 and menu_option > 5:
        detect_hr()
    elif menu_option <= 15 and menu_option > 10:
        history_menu()
    elif menu_option <= 20 and menu_option > 15:
        detect_hr()


# Refresh OLED
def refresh_oled(bpm, beat, v, min_value, maxima, array):
    global last_y, menu_option, PPI

    if menu_option <= 5:
        display.vline(0, 0, 32, 0)
        display.scroll(-1, 0)  # Scroll left 1 pixel

        if maxima - min_value > 0:
            # Draw beat line.
            y = 32 - int(16 * (v - min_value) / (maxima - min_value))
            display.line(125, last_y, 126, y, 1)
            last_y = y

        display.fill_rect(0, 0, 128, 16, 0)

        if bpm:
            display.text("%d bpm" % bpm, 12, 0)

        display.show()

    elif menu_option <= 10 and menu_option > 5 or menu_option <= 20 and menu_option > 15:

        display.fill(0)
        display.text("Collecting data", 0, 0)
        display.text(str(len(array)) + "/60", 0, 10)

        display.show()


# Calculate average PPI
def calculate_average_ppi(array):
    if array:
        ppi_average = sum(array) / len(array)
        return int(ppi_average)


# Calculate average HR
def calculate_average_bpm(array):
    if array:
        average_hr = sum(array) / len(array)
        average_hr = 60000 / average_hr
        return int(average_hr)


# Calculate SDNN
def calculate_average_sdnn(data, PPI):
    total = 0
    for i in data:
        total += (i - PPI) ** 2
    SDNN = (total / (len(data) - 1)) ** (1 / 2)
    rounded_SDNN = round(SDNN, 0)
    return int(rounded_SDNN)


# Calculate RMSSD
def calculate_average_rmssd(data):
    i = 0
    total = 0
    while i < len(data) - 1:
        total += (data[i + 1] - data[i]) ** 2
        i += 1
    rounded_RMSSD = round((total / (len(data) - 1)) ** (1 / 2), 0)
    return int(rounded_RMSSD)


# Show if no finger detect_hred
def no_finger_detected():
    display.fill(0)
    display.text("place finger", 0, 0)
    display.text("on the sensor", 0, 12)
    display.show()
    time.sleep(3)
    display.fill(0)
    display.show()


# Main function to detect_hr HR
def detect_hr():
    # create and zero all variables
    CURRENT_250_SAMPLES = [700]
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

        # Tresholds
        MAX_TRESHOLD = (min_value + max_value * 3) // 4  # 3/4
        MIN_TRESHOLD = (min_value + max_value) // 2  # 1/2

        #######################
        # MAIN PEAK DETECTION #
        #######################
        if v > MAX_TRESHOLD and beat == False:
            SAMPLE_TIME = new_time
            INTERVAL_MS = SAMPLE_TIME - LAST_SAMPLE_TIME
            # Check if time between samples is more than 200ms
            if INTERVAL_MS > 200:
                # If 5 beats have been detected we can calculate accurate bpm
                if PPI_AVERAGE_CALCULATED:
                    # Get latest PPI average
                    average = calculate_average_ppi(PPI_AVERAGE_ARRAY)
                    # Check if interval change is within range 70%-130% of the average PPI
                    if INTERVAL_MS > (average * 0.70) and INTERVAL_MS < (average * 1.30):
                        # If doing HRV or KUBIOS, append PPI to a list
                        if menu_option <= 10 and menu_option > 5 or menu_option <= 20 and menu_option > 15:
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

                # If less than 5 beats have been detected. Add possible peak to peak intervals to array so average can be determined
                else:
                    BEATS_DETECTED += 1
                    beat = True
                    if BEATS_DETECTED > 5:
                        PPI_AVERAGE_CALCULATED = True
                        PPI_AVERAGE_ARRAY.append(INTERVAL_MS)
                        PPI_AVERAGE_ARRAY = PPI_AVERAGE_ARRAY[-MOVING_PPI_MAX:]
                    LAST_SAMPLE_TIME = SAMPLE_TIME

        if v < MIN_TRESHOLD and beat == True:
            led.off()
            beat = False

        if DISPLAY_COUNT > 10:
            refresh_oled(bpm, beat, v, min_value, max_value, PPI_ALL_ARRAY)
            DISPLAY_COUNT = 0

        # Check if enaugh data has been collected for HRV or KUBIOS
        if len(PPI_ALL_ARRAY) > 59:
            if menu_option <= 10 and menu_option > 5:

                average_ppi = calculate_average_ppi(PPI_ALL_ARRAY)
                average_hr = calculate_average_bpm(PPI_ALL_ARRAY)
                average_sdnn = calculate_average_sdnn(PPI_ALL_ARRAY, average_ppi)
                average_rmssd = calculate_average_rmssd(PPI_ALL_ARRAY)
                
                # There was a separate display here to inform the user that data is been sent through MQTT
                # Removed, as the process mostly only takes a second or less, so it would only flash on the screen
                current_time = utime.localtime()
                
                save_measurement(
                    str(current_time[2]) + "." + str(current_time[1]) + "." + str(current_time[0]) + "," + str(current_time[3]) + ":" +
                    str(current_time[4]) + "," +str(average_ppi) + "," + str(average_hr) + "," + str(average_sdnn) + "," + str(average_rmssd)
                )
                connect_wlan()
                send_mqtt(str(current_time[2]) + "." + str(current_time[1]) + "." + str(current_time[0]) + ", " + str(current_time[3]) + ":" +
                    str(current_time[4]) + "\nPPI: " + str(average_ppi) + "\nHR: " + str(average_hr) + "\nSDNN: " + str(average_sdnn) + "\nRMSSD: " +
                    str(average_rmssd) + "\n")
                
                display.fill(0)
                display.text("Results:", 0, 0)
                display.text("PPI   " + str(average_ppi), 0, 10)
                display.text("HR    " + str(average_hr), 0, 20)
                display.text("SDNN  " + str(average_sdnn) + "ms", 0, 30)
                display.text("RMSSD " + str(average_rmssd) + "ms", 0, 40)
                display.show()
                while not button.fifo.has_data():
                    time.sleep(0.004)

                if button.fifo.has_data():
                    data = button.fifo.get()
                led.off()
                break

            elif menu_option <= 20 and menu_option > 15:
                led.off()
                display.fill(0)
                display.text("Sending data...", 0, 0)
                display.show()
                kubios(PPI_ALL_ARRAY)

                while not button.fifo.has_data():
                    time.sleep(0.004)

                if button.fifo.has_data():
                    data = button.fifo.get()
                break

        # Stop action if button is pressed
        if button.fifo.has_data():
            data = button.fifo.get()
            led.off()
            break


def history_menu():
    data_history = []
    selected = 0
    rot_val = 0
    try:
        file = open("history.csv", "r")
    except OSError:
        file = open("history.csv", "w+")

    for line in file:
        line = line.strip()
        line = line.split(",")
        data_history.append([f"{line[0]}", f"{line[1]}", f"PPI: {line[2]}", f"HR: {line[3]}", f"SDNN: {line[4]}", f"RMSSD: {line[5]}"])

    data_history.reverse()

    while True:
        display.fill(0)

        for i in range(len(data_history)):
            menu_text = f"{line[0]}"
            if selected == i:
                menu_text = "> " + menu_text
            display.text(menu_text, 0, i * 10, 1)

        back_text = "BACK"

        if selected == len(data_history):
            back_text = "> " + back_text
        display.text(back_text, 0, 10 * len(data_history), 1)
        display.show()

        if button.fifo.has_data():
            button.fifo.get()
            if 0 <= selected < len(data_history):
                show_measurement(data_history[selected])
                continue
            elif selected == len(data_history):
                break

        if rot.fifo.has_data():
            rot_data = rot.fifo.get()
            rot_val += rot_data
            if abs(rot_val) > 5:
                selected += rot_data
                rot_val = 0
                if selected > len(data_history):
                    selected = 0
                elif selected < 0:
                    selected = len(data_history)

    file.close()


def show_measurement(data):
    print(data)
    display.fill(0)
    for i, line in enumerate(data):
        display.text(line, 0, i * 10)
    display.show()
    while not button.fifo.has_data():
        pass
    button.fifo.get()


def save_measurement(data):
    try:
        with open("history.csv", "r") as file:
            lines = file.readlines()
        print(lines)
        lines.append(data + "\n")
    except OSError:
        with open("history.csv", "w+") as file:
            lines = [data + "\n"]

    with open("history.csv", "w") as file:
        for line in lines[-5:]:
            file.write(line)


def connect_wlan():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    ip = wlan.ifconfig()[0]
    return ip

def send_mqtt(data):
    topic = "hrv"
    mqtt_client = MQTTClient("", BROKER_IP)
    
    try:
        mqtt_client.connect(clean_session=True)
    except Exception:
        print("Failed to connect to MQTT...")
        
    try:
        mqtt_client.publish(topic, data)
    except Exception:
        print("Failed to send to MQTT...")

def kubios(array):
    try:
        connect_wlan()
    except Exception as e:
        print("Error while connecting:", str(e))
        machine.reset()

    try:
        response = requests.post(
            url=TOKEN_URL,
            data='grant_type=client_credentials&client_id={}'.format(CLIENT_ID),
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            auth=(CLIENT_ID, CLIENT_SECRET))

        response = response.json()
        access_token = response["access_token"]

        data_set = {
            "type": "RRI",
            "data": array,
            "analysis": {"type": "readiness"}
        }

        response = requests.post(
            url="https://analysis.kubioscloud.com/v2/analytics/analyze",
            headers={"Authorization": "Bearer {}".format(access_token),
                     "X-Api-Key": APIKEY},
            json=data_set)

        response = response.json()

        SNS = round(response['analysis']['sns_index'], 2)
        PNS = round(response['analysis']['pns_index'], 2)
        display.fill(0)
        display.text('Kubios results:', 0, 0)
        display.text('PNS:' + str(PNS), 0, 10)
        display.text('SNS:' + str(SNS), 0, 20)
        display.text('Press to go back', 0, 50)
        display.show()

        while not button.fifo.has_data():
            time.sleep(0.004)

        if button.fifo.has_data():
            data = button.fifo.get()


    except requests.exceptions.Timeout:
        print("Request timed out")
    except requests.exceptions.HTTPError as err:
        print("HTTP error occurred:", err)
    except requests.exceptions.RequestException as err:
        print("Error during requests to external API:", err)
    except KeyboardInterrupt:
        print("Operation cancelled by user")
        machine.reset()
    except Exception as e:
        print("Unexpected error:", str(e))
        machine.reset()

led.off()

while True:
    draw_menu()

    if button.fifo.has_data():
        data = button.fifo.get()
        select_program()

    if rot.fifo.has_data():
        rot_data = rot.fifo.get()
        menu_option += rot_data
        if menu_option > 20:
            menu_option = 1
        if menu_option < 0:
            menu_option = 20
