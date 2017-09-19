from flask import Flask, render_template, request
import Adafruit_DHT
import RPi.GPIO as GPIO

# in Board mode
LED_PIN = 7
MOTION_PIN = 11

app = Flask(__name__)

@app.route("/")
def render_root():
    humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, 12)
    nearby = bool(GPIO.input(MOTION_PIN))
    return render_template("index.html", temperature=temperature,
                                         humidity=humidity,
                                         nearby=nearby) 

@app.route("/pi/sensors/temperature/0/")
def get_temperature():
    humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, 12)
    return "%f" % temperature

@app.route("/pi/sensors/humidity/0/")
def get_humidity():
    humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, 12)
    return "%f" % humidity

@app.route("/pi/sensors/motion/0/")
def get_motion():
    return "%d" % GPIO.input(MOTION_PIN)

@app.route("/pi/actuators/leds/0/", methods=["POST"])
def handle_led_set_value():
    value = GPIO.LOW if request.form["value"] == "0" else GPIO.HIGH
    GPIO.output(LED_PIN, value)
    return "OK"

def main():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(MOTION_PIN, GPIO.IN)
    GPIO.setup(LED_PIN, GPIO.OUT)
    app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    main()
