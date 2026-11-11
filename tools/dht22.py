import time
import adafruit_dht
import board

dht_device = adafruit_dht.DHT22(board.D4)

while True:
  try:
    temp = dht_device.temperature
    hum = dht_device.humidity
    print(f"Temp: {temp}C | Humidity: {hum}%")
  except RuntimeError as error:
    print(f"Read error: {error.args[0]}")
  time.sleep(3.0)
