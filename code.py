import sys
import digitalio
import analogio
import busio
import time
import board
import gc
import os

voltage_pin = analogio.AnalogIn(board.D9)

from config import CONFIG
print("imported config: %s" % CONFIG)

try:
    os.stat("/lora_frame_count.txt")
except OSError:
    print("/lora_frame_count.txt not found, creating new file...")
    with open("/lora_frame_count.txt", "w") as f:
        f.write("0")

def read_lora_frame_count():
    with open("/lora_frame_count.txt", "r") as f:
        try:
            lora_frame_counter = int(f.read().strip())
        except:
            print("There was an error reading the lora_frame_counter file, setting lora_frame_count to 0")
            lora_frame_counter = 0
        print("read /lora_frame_count.txt count is %s" % lora_frame_counter)
    return lora_frame_counter

def write_lora_frame_count(count):
    with open("/lora_frame_count.txt", "w") as f:
        f.write(str(count))
        print("wrote /lora_frame_count.txt count %s to /lora_frame_count.txt" % count)

def send_lora_message(data):
    from adafruit_tinylora.adafruit_tinylora import TTN, TinyLoRa
    lora_frame_counter = read_lora_frame_count()
    ttn_config = TTN(CONFIG["LORA"]["device_address"], CONFIG["LORA"]["network_key"], CONFIG["LORA"]["application_key"], country=CONFIG["LORA"]["country"])
    spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
    cs = digitalio.DigitalInOut(board.RFM9X_CS)
    irq = digitalio.DigitalInOut(board.RFM9X_D0)
    rst = digitalio.DigitalInOut(board.RFM9X_RST)
    lora = TinyLoRa(spi, cs, irq, rst, ttn_config)
    lora.frame_counter = lora_frame_counter
    lora.send_data(data, len(data), lora.frame_counter)
    print("LoRa frame %s sent!" % lora.frame_counter)
    lora.frame_counter += 1
    write_lora_frame_count(lora.frame_counter)

def get_gps_position():
    import adafruit_gps
    uart = busio.UART(board.TX, board.RX, baudrate=9600, timeout=10)
    gps = adafruit_gps.GPS(uart, debug=True)
    gps.send_command(b"PMTK314,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
    gps.send_command(b"PMTK220,1000")
    while True:
        gps.update()
        if gps.has_fix:
            print("We have fix!")
            del(adafruit_gps)
            del(sys.modules["adafruit_gps"])
            gc.collect()
            return gps.longitude, gps.latitude
        else:
            print("waiting for fix...")
            time.sleep(0.1)

def get_battery_voltage():
    return ((voltage_pin.value * 3.3) / 65536) * 2

while True:
    try:
        lon, lat = get_gps_position()
        v = get_battery_voltage()
        msg = bytes('{"location":{"latitude":%.6f,"longitude":%.6f}, "battery_voltage": %s}' % (lat, lon, v), "ASCII")
        print("sending message %s" % msg)
        send_lora_message(msg)
    except Exception as E:
        print("exception %s" % E)
    print("sleeping %s seconds before reset..." % CONFIG["SLEEP_SECONDS"])
    time.sleep(CONFIG["SLEEP_SECONDS"])
    print("Done sleeping - resetting feather to reclaim lost RAM...")
    import supervisor
    supervisor.reload()
