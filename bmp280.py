import time
import adafruit_bmp280
import board
import busio

i2c = busio.I2C(board.SCL, board.SDA)
sensor = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=0x76)

# Optional: Set sea level pressure in hPa for altitude calculation if you want it
sensor.sea_level_pressure = 1013.25

while True:
    temp = sensor.temperature
    pressure = sensor.pressure
    altitude = sensor.altitude

    print(
        f"Temp: {temp:.2f} °C | Pressure: {pressure:.2f} hPa | Altitude: {altitude:.2f} m"
    )
    time.sleep(3.0)
