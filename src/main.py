from flask import Flask
import sys

# needed for Flask to work
app = Flask(__name__)


@app.route("/api/kademlia/ping", methods=['POST'])
def receive_ping():
    return "Hello,World!"


@app.route("/api/kademlia/nodes", methods=['GET'])
def find_node():
    return "TODO:node_id"


if __name__ == "__main__":
    port = int(sys.argv[1])
    app.run(port=port)
