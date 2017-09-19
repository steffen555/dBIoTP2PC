import RPi.GPIO as GPIO
import time

"""
Connect negative (short part of LED) to pin 6 via a 330 ohm resistor,
and connect positive (long part of LED) to pin 12 directly.
"""

GPIO.setmode(GPIO.BCM)

GPIO.setwarnings(False)
GPIO.setup(4, GPIO.OUT)

SLEEP_TIME = 0.1

while True:

    print("ON")
    GPIO.output(4, GPIO.HIGH)

    time.sleep(SLEEP_TIME)

    print("OFF")
    GPIO.output(4, GPIO.LOW)
    time.sleep(SLEEP_TIME)

