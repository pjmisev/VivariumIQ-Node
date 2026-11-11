import time
import board
import digitalio

pir = digitalio.DigitalInOut(board.D22)
pir.direction = digitalio.Direction.INPUT

while True:
    print("Motion detected!" if pir.value else "No motion")
    time.sleep(0.5)
