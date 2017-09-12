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

def send_ping(ip, port):
	my_id = "TODO_node_id"
	data = {"port": port}
	url = "http://%s:%d/api/kademlia/nodes/%s/" % (ip, port, my_id)
	req = requests.put(url, data=data)
	print(req.text)

if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("No port given")
		exit(1)

	my_port = int(sys.argv[1])

	if len(sys.argv) > 3:
		initial_peer_ip = sys.argv[2]
		initial_peer_port = int(sys.argv[3])
		send_ping(initial_peer_ip, initial_peer_port)

	app.run(port=my_port)

