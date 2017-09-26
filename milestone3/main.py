from flask import Flask, request, render_template, redirect
from uuid import getnode as get_mac
import math
import sys
import config
import requests
import hashlib
import time
import json
import threading
import Queue

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

    def __repr__(self):
        return "%s@%s:%s" % (self.node_id, self.ip_address, self.port)

    def __hash__(self):
        return hash(self.node_id)

    def to_triple(self):
        return self.ip_address, self.port, self.node_id


def is_alive(contact):
    try:
        send_ping(contact.ip_address, contact.port, 0)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        return False
    return True


def add_to_bucket(contact):
    print("Adding %s to a bucket." % contact)
    if (contact.node_id == my_id):
        return  # We may never, ever add ourselves to our own bucket!
    index = int(math.log(distance(my_id, contact.node_id), 2))
    buckets_lock.acquire()
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
    buckets_lock.release()


@app.route("/api/kademlia/id/", methods=["GET"])
def receive_ping():
    ip_address = request.remote_addr
    port = request.headers["port"]
    needs_ping_back = int(request.headers["needs_ping_back"])
    if needs_ping_back:
        send_delayed_ping(ip_address, port, 0)
    return str(my_id)


@app.route("/get_value")
def handle_get_value():
    key = request.args["key"]
    return "TODO"


@app.route("/store_value", methods=["POST"])
def handle_store_value():
    key = request.form["key"]
    value = request.form["value"]
    key_value_pairs[key] = value
    return redirect("/", code=302)


def get_top_k(node_id):
    buckets_lock.acquire()
    contacts = [contact for bucket in buckets for contact in bucket]
    contacts = sorted(contacts, key=lambda c: distance(c.node_id, node_id))
    print(contacts)
    top_k = contacts[:config.k]
    buckets_lock.release()
    return top_k


@app.route("/api/kademlia/closest_nodes/<int:node_id>/", methods=["GET"])
def get_closest_nodes_as_json(node_id):
    return json.dumps([contact.to_triple() for contact in get_top_k(node_id)])


@app.route("/closest_nodes/", methods=["GET"])
def get_closest_nodes_as_html():
    node_id = request.args.get('node_id')
    buckets_lock.acquire()
    result = render_template("template.html",
                             node_id=my_id,
                             buckets=enumerate(buckets),
                             search_result=iterative_find_node(int(node_id)),
                             kv_pairs=key_value_pairs.items()),
    buckets_lock.release()
    return result


def iterative_find_node(node_id):
    UNPROBED = 0
    LIVE = 1
    DEAD = 2

    def get_first_alpha_unprobed(L):
        L = sorted(L.items(), key=lambda c: distance(c[0].node_id, node_id))
        unprobed_contacts = [t for t in L if t[1] == UNPROBED]
        return unprobed_contacts[:config.alpha]

    buckets_lock.acquire()
    L = {contact: UNPROBED for bucket in buckets for contact in bucket}
    buckets_lock.release()
    while True:
        first_alpha_unprobed_contacts = get_first_alpha_unprobed(L)
        q = Queue.Queue()
        threads = []
        for contact, _ in first_alpha_unprobed_contacts:
            t = threading.Thread(target=probe, args=(q, contact, node_id))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
            contact, result = q.get()
            if result is None:
                L[contact] = DEAD
            else:
                L[contact] = LIVE
                for ip, port, node_id in result:
                    received_contact = Contact(node_id, ip, port, 0)
                    if received_contact not in L:
                        L[received_contact] = UNPROBED
        if (get_number_contacts_with_status(L, LIVE) >= config.k
            or get_number_contacts_with_status(L, UNPROBED) == 0):
            break
    return [contact for contact, status in L.items() if status == LIVE][:config.k]


def probe(q, contact, node_id):
    url = "http://%s:%s/api/kademlia/closest_nodes/%d/" % (contact.ip_address, contact.port, node_id)
    try:
        response = requests.get(url, timeout=config.timeout)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        q.put((contact, None))
        return
    q.put((contact, json.loads(response.text)))


def get_number_contacts_with_status(L, status):
    return len([t for t in L.items() if t[1] == status])


def send_ping(ip, other_port, needs_ping_back):
    headers = {"port": str(my_port), "needs_ping_back": str(needs_ping_back)}
    url = "http://%s:%s/api/kademlia/id/" % (ip, other_port)
    response = requests.get(url, headers=headers, timeout=config.timeout)
    contact = Contact(int(response.text), ip, other_port, time.time())
    add_to_bucket(contact)
    print(response.text)


def send_delayed_ping(ip, other_port, needs_ping_back):
    def do_send_delayed_ping():
        time.sleep(2)
        send_ping(ip, other_port, needs_ping_back)

    t = threading.Thread(target=do_send_delayed_ping)
    t.start()


@app.route("/api/kademlia/values/", methods=["POST"])
def receive_store():
    key = request.form["key"]
    value = request.form["value"]
    key_value_pairs[key] = value
    return "", 201


def store(ip, port, key, value):
    data = {"key": key, "value": value}
    url = "http://%s:%d/api/kademlia/values/" % (ip, port)
    response = requests.post(url, data=data)
    return response.status_code == 201


@app.route("/api/kademlia/values/", methods=["GET"])
def search_for_value():
    key = request.headers["key"]
    node_id = request.headers["node_id"]
    try:
        value = key_value_pairs[key]
    except KeyError:
        return get_closest_nodes_as_json(node_id)
    return value


def find_value(ip, port, key):
    headers = {"node_id": my_id, "key": key}
    url = "http://%s:%d/api/kademlia/values/" % (ip, port)
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        return json.loads(response.text)


def distance(x, y):
    return x ^ y


def init_id():
    global my_id
    value_to_be_hashed = str(get_mac()) + str(my_port)
    num_digits = config.B / 4
    hex_digest = hashlib.sha256(value_to_be_hashed).hexdigest()
    my_id = int(hex_digest[:num_digits], 16)
    print("My ID is: %d" % my_id)


def init_buckets():
    global buckets
    buckets = [[] for _ in range(config.B)]


def init_key_value_pairs():
    global key_value_pairs
    key_value_pairs = {}


@app.route("/")
def render_this_path():
    buckets_lock.acquire()
    result = render_template("template.html",
                             node_id=my_id,
                             buckets=enumerate(buckets),
                             search_result=None,
                             kv_pairs=key_value_pairs.items())
    buckets_lock.release()
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("No port given")
        exit(1)

    global my_port
    my_port = int(sys.argv[1])

    init_id()
    init_key_value_pairs()
    init_buckets()
    buckets_lock = threading.RLock()

    if len(sys.argv) > 3:
        initial_peer_ip = sys.argv[2]
        initial_peer_port = int(sys.argv[3])
        send_ping(initial_peer_ip, initial_peer_port, 1)

    app.run(host="0.0.0.0", port=my_port)
