from flask import Flask, render_template, request
import Adafruit_DHT
import RPi.GPIO as GPIO
import id_generation
import requests
import json
import time

WEB_SERVER_IP = "127.0.0.1"
WEB_SERVER_PORT = 8080
INITIAL_PEER_IP = "127.0.0.1"
INITIAL_PEER_PORT = 5000

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
	return json.dumps([time.time(), temperature])

@app.route("/pi/sensors/humidity/0/")
def get_humidity():
	humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, 12)
	return json.dumps([time.time(), humidity])

@app.route("/pi/sensors/motion/0/")
def get_motion():
	return json.dumps([time.time(), GPIO.input(MOTION_PIN)])

@app.route("/pi/actuators/leds/0/", methods=["POST"])
def handle_led_set_value():
	value = GPIO.LOW if request.form["value"] == "0" else GPIO.HIGH
	GPIO.output(LED_PIN, value)
	return "OK"

def connect_sensor_to_kademlia(sensor_url, description):
	sensor_id = id_generation.generate_id(sensor_url)
	headers = {"node_id": str(sensor_id), "url": sensor_url, "description": description}
	url = "http://%s:%d/api/wotds/registration/" % (INITIAL_PEER_IP, INITIAL_PEER_PORT)
	requests.get(url, headers=headers)

def connect_sensors_to_kademlia():
	my_url = "http://%s:%d" % (WEB_SERVER_IP, WEB_SERVER_PORT)
	connect_sensor_to_kademlia(my_url + "/pi/sensors/humidity/0/", "Humidity Sensor")
	connect_sensor_to_kademlia(my_url + "/pi/sensors/temperature/0/", "Temperature Sensor")
	connect_sensor_to_kademlia(my_url + "/pi/sensors/motion/0/", "Motion Sensor")

def main():
	GPIO.setwarnings(False)
	GPIO.setmode(GPIO.BOARD)
	GPIO.setup(MOTION_PIN, GPIO.IN)
	GPIO.setup(LED_PIN, GPIO.OUT)

	connect_sensors_to_kademlia()

	app.run(host="0.0.0.0", port=WEB_SERVER_PORT)

if __name__ == "__main__":
	main()
