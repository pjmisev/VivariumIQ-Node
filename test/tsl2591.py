import time
import adafruit_tsl2591
import board
import busio

i2c = busio.I2C(board.SCL, board.SDA)
sensor = adafruit_tsl2591.TSL2591(i2c)

while True:
    broadband = sensor.infrared + sensor.visible
    lux = sensor.lux

    print(f"Lux: {lux:.2f} | Broadband: {broadband} | IR: {sensor.infrared}")
    time.sleep(3.0)
