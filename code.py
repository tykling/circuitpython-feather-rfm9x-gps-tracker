import sys
import digitalio
import analogio
import busio
import time
import board
import gc
import os

voltage_pin = analogio.AnalogIn(board.D9)

# load config file
from config import LORA_CONFIG, GPS_CONFIG

try:
    os.stat("/lora_frame_count.txt")
except OSError:
    print("/lora_frame_count.txt not found, creating new file...")
    with open("/lora_frame_count.txt", "w") as f:
        f.write("0")

def send_lora_message(data):
    with open("/lora_frame_count.txt", "r") as f:
        lora_frame_counter = int(f.read().strip())
        print("read /lora_frame_count.txt count is %s" % lora_frame_counter)

    from adafruit_tinylora.adafruit_tinylora import TTN, TinyLoRa
    ttn_config = TTN(LORA_CONFIG["device_address"], LORA_CONFIG["network_key"], LORA_CONFIG["application_key"], country=LORA_CONFIG["country"])
    spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
    cs = digitalio.DigitalInOut(board.RFM9X_CS)
    irq = digitalio.DigitalInOut(board.RFM9X_D0)
    rst = digitalio.DigitalInOut(board.RFM9X_RST)
    lora = TinyLoRa(spi, cs, irq, rst, ttn_config)
    lora.frame_counter = lora_frame_counter
    lora.send_data(data, len(data), lora.frame_counter)
    print("LoRa frame %s sent!" % lora.frame_counter)
    lora.frame_counter += 1
    with open("/lora_frame_count.txt", "w") as f:
        f.write(str(lora.frame_counter))
        print("wrote /lora_frame_count.txt count is %s" % lora.frame_counter)
    del(TinyLoRa)
    del(sys.modules["adafruit_tinylora"])
    del(sys.modules["adafruit_tinylora.adafruit_tinylora"])
    del(sys.modules["adafruit_tinylora.adafruit_tinylora_encryption"])
    gc.collect()

def get_gps_position():
    import adafruit_gps
    uart = busio.UART(board.TX, board.RX, baudrate=9600, timeout=10)
    gps = adafruit_gps.GPS(uart, debug=True)
    gps.send_command(b"PMTK314,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
    gps.send_command(b"PMTK220,1000")

    fix_time = None
    while True:
        gps.update()
        if gps.has_fix:
            print("have fix - quality %s" % gps.fix_quality)
            if not fix_time:
                fix_time = time.monotonic()
            else:
                current = time.monotonic()
                if current - fix_time >= GPS_CONFIG["fix_time_seconds"]:
                    # we've had fix long enough, unload gps modules so we can fit lora modules
                    del(adafruit_gps)
                    del(sys.modules["adafruit_gps"])
                    gc.collect()
                    # and return location + quality
                    return gps.longitude, gps.latitude, gps.fix_quality
                else:
                    print("waiting to send until we had fix for %s seconds" % GPS_CONFIG["fix_time_seconds"])
                    time.sleep(1)
        else:
            print("waiting for fix...")
            time.sleep(0.1)

def get_battery_voltage():
    return ((voltage_pin.value * 3.3) / 65536) * 2

while True:
    lon, lat, qual = get_gps_position()
    print("got gps %s" % gc.mem_free())
    v = get_battery_voltage()
    print("got voltage %s" % v)
    msg = bytes("%s|%s|%s|%s" % (lon, lat, qual, v), "ASCII")
    print("sending message %s" % msg)
    send_lora_message(msg)
    print("resetting feather to reclaim lost RAM...")
    import supervisor
    supervisor.reload()
