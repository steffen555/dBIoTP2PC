from flask import Flask, request, render_template
from uuid import getnode as get_mac
import math
import sys
import config
import requests
import hashlib
import time

# needed for Flask to work
app = Flask(__name__)


class Contact:
    def __init__(self, node_id, ip_address, port, most_recent_comm):
        self.node_id = node_id
        self.ip_address = ip_address
        self.port = port
        self.most_recent_comm = most_recent_comm

    def __eq__(self, other):
        return self.node_id == other.node_id

    def __str__(self):
        return "%s:%s" % (self.ip_address, self.port)


def is_alive(contact):
    # TODO do this better
    return False


def add_to_bucket(contact):
    print("Adding %s to a bucket." % contact)
    index = int(math.log(distance(my_id, contact.node_id), 2))
    bucket = buckets[index]
    assert len(bucket) <= config.k

    if contact in bucket:
        # it's already there, so put it at the end
        bucket.remove(contact)
        bucket.append(contact)
    elif len(bucket) < config.k:
        # there's space, so just put it at the end
        bucket.append(contact)
    else:
        # there's no space, so see if the oldest is alive
        oldest_contact = bucket[0]
        if not is_alive(oldest_contact):
            bucket.remove(oldest_contact)
            bucket.append(contact)

    print("Bucket %d is now %s" % (index, bucket))

    buckets[index] = bucket


@app.route("/api/kademlia/nodes/<int:node_id>/", methods=["PUT"])
def receive_ping(node_id):
    ip_address = request.remote_addr
    port = request.form["port"]
    contact = Contact(node_id, ip_address, port, time.time())
    add_to_bucket(contact)

    # TODO: we should send back data so the client can also add us to its
    # bucket.
    return "PONG!"


@app.route("/api/kademlia/nodes/", methods=["GET"])
def view_nodes():
    return "TODO:node_id"


def send_ping(ip, other_port, my_port):
    data = {"port": my_port}
    url = "http://%s:%d/api/kademlia/nodes/%d/" % (ip, other_port, my_id)
    req = requests.put(url, data=data)
    print(req.text)


def distance(x, y):
    return x ^ y


def init_id(my_port):
    global my_id
    value_to_be_hashed = str(get_mac()) + str(my_port)
    num_digits = config.B / 4
    hex_digest = hashlib.sha256(value_to_be_hashed).hexdigest()
    my_id = int(hex_digest[:num_digits], 16)
    print("My ID is: %d" % my_id)


def init_buckets():
    global buckets
    buckets = [[] for _ in range(config.B)]


@app.route("/")
def render_this_path():
    result = render_template("template.html",
                             node_id=my_id,
                             buckets=buckets)
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("No port given")
        exit(1)

    my_port = int(sys.argv[1])

    init_id(my_port)
    init_buckets()

    if len(sys.argv) > 3:
        initial_peer_ip = sys.argv[2]
        initial_peer_port = int(sys.argv[3])
        send_ping(initial_peer_ip, initial_peer_port, my_port)

    app.run(host="0.0.0.0", port=my_port)
