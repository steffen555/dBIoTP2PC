from flask import Flask
import sys
import config
import requests

# needed for Flask to work
app = Flask(__name__)


@app.route("/api/kademlia/nodes/<node_id>/", methods=["PUT"])
def receive_ping(node_id):
	return "Hello, %s" % node_id

@app.route("/api/kademlia/nodes/", methods=["GET"])
def find_node():
	return "TODO:node_id"


def send_ping(port):
	my_id = "TODO_node_id"
	data = {"port": port}
	url = "http://%s:%d/api/kademlia/nodes/%s/" % (config.initial_ip,
		config.initial_port, my_id)
	req = requests.put(url, data=data)

if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("No port given")
		exit(1)

	port = int(sys.argv[1])

	if port != config.initial_port:
		send_ping(port)

	app.run(port=port)


