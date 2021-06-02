import sys
import digitalio
import analogio
import busio
import time
import board
import gc
import os

voltage_pin = analogio.AnalogIn(board.D9)

from config import LORA_CONFIG, GPS_CONFIG

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
    write_lora_frame_count(lora.frame_counter)

def read_gps_location_from_disk():
    try:
        with open("/last_gps_location.txt", "r") as f:
            lon, lat = [float(x) for x in f.read().strip().split(",")]
            print("Read GPS coordinates lon %s lat %s from /last_gps_location.txt" % (lon, lat))
        return lon, lat
    except OSError:
        return None, None

def write_gps_location_to_disk(lon, lat):
    with open("/last_gps_location.txt", "w") as f:
        f.write("%s,%s" % (lon, lat))
        print("wrote GPS coordinates lon %s lat %s to /last_gps_location.txt" % (lon, lat))

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
            if not fix_time:
                fix_time = time.monotonic()
            else:
                current = time.monotonic()
                if current - fix_time >= GPS_CONFIG["fix_time_seconds"]:
                    # we've had fix long enough, unload gps module and GC.collect so we can fit lora modules
                    del(adafruit_gps)
                    del(sys.modules["adafruit_gps"])
                    gc.collect()
                    return gps.longitude, gps.latitude
                else:
                    print("We have GPS fix! - Waiting to send until we had fix for %s seconds" % GPS_CONFIG["fix_time_seconds"])
                    time.sleep(1)
        else:
            print("waiting for fix...")
            time.sleep(0.1)

def get_radians(coordinate):
    return math.radians(coordinate)

def get_distance(oldlon, oldlat, newlon, newlat):
    if not all([oldlon, oldlat, newlon, newlat]):
        return 0

    # do the math
    import math
    R = 6373.0

    oldlon = get_radians(oldlon)
    newlon = get_radians(newlon)
    dlon = newlon - oldlon

    oldlat = get_radians(oldlat)
    newlat = get_radians(newlon)
    dlat = newlat - oldlat

    a = math.sin(dlat / 2)**2 + math.cos(oldlat) * math.cos(newlat) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_battery_voltage():
    return ((voltage_pin.value * 3.3) / 65536) * 2

while True:
    lon, lat = get_gps_position()
    oldlon, oldlat = read_gps_location_from_disk()
    distance_moved = get_distance(oldlon, oldlat, lon, lat)
    v = get_battery_voltage()
    msg = bytes("%s|%s|%s|%s" % (lon, lat, distance_moved, v), "ASCII")
    print("sending message %s" % msg)
    send_lora_message(msg)
    print("resetting feather to reclaim lost RAM...")
    import supervisor
    supervisor.reload()
