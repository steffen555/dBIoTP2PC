from flask import Flask, request, render_template, redirect
from uuid import getnode as get_mac
from gevent.wsgi import WSGIServer
import id_generation
import math
import sys
import config
import requests
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
		return	# We may never, ever add ourselves to our own bucket!
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


class WOTNode:
	def __init__(self, node_id, url, description, responsible):
		self.node_id = node_id
		self.url = url
		self.description = description
		self.we_are_responsible = responsible
		self.last_seen = time.time()

	def __str__(self):
		return "Node %d (url: '%s', description: '%s')" % (
			self.node_id, self.url, self.description)

	def __cmp__(self, other):
		return self.node_id == other.node_id

	def __hash__(self):
		return hash(self.node_id)


@app.route("/api/wotds/responsibility/", methods=["GET"])
def receive_kademlia_wot_registration():
	node_id = int(request.headers["node_id"])
	url = request.headers["url"]
	description = request.headers["description"]
	node = WOTNode(node_id, url, description, True)
	known_wot_nodes[node.node_id] = node
	return "OK"


def register_wot_node(wot_node):
	closest_other_nodes = iterative_find_node(wot_node.node_id)
	if (len(closest_other_nodes) == 0 or
				distance(my_id,
						 wot_node.node_id) < distance(closest_other_nodes[0].node_id,
													  wot_node.node_id)):
		# we are closest
		print "I AM CLOSEST; I AM THE CHOSEN ONE"
		wot_node.we_are_responsible = True
		known_wot_nodes[wot_node.node_id] = wot_node
	else:
		# send it on to the closest one
		node = closest_other_nodes[0]
		print "someone else is the hero :( it is", node
		headers = {"node_id": str(wot_node.node_id),
				   "url": wot_node.url,
				   "description": wot_node.description}
		url = "http://%s:%s/api/wotds/responsibility/" % (node.ip_address, node.port)
		requests.get(url, headers=headers)


@app.route("/api/wotds/registration/", methods=["GET"])
def receive_wot_registration():
	node_id = int(request.headers["node_id"])
	url = request.headers["url"]
	description = request.headers["description"]
	node = WOTNode(node_id, url, description, True)
	register_wot_node(node)
	return "OK"


@app.route("/api/wotds/datapoints/", methods=["POST"])
def receive_data_point():
	timestamp = float(request.form["timestamp"])
	raw_data = request.form["data"]
	originator_nodeid = int(request.form["originator_nodeid"])
	originator_url = request.form["originator_url"]
	description = request.form["description"]
	node = WOTNode(originator_nodeid, originator_url, description, False)
	known_wot_nodes[node.node_id] = node
	add_data_point(node, timestamp, raw_data)
	return "OK"


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


def iterative_find_node(key):
	return node_lookup(LookupType.NODE, key).k_closest_nodes


class LookupType:
	NODE = 0
	VALUE = 1


class NodeStatus:
	UNPROBED = 0
	LIVE = 1
	DEAD = 2
	HAS_VALUE = 3


class NodeLookupResult:
	def __init__(self):
		self.value = None
		self.k_closest_nodes = None


def node_lookup(lookup_type, key):
	result = NodeLookupResult()

	def get_first_alpha_unprobed(L):
		L = sorted(L.items(), key=lambda c: distance(c[0].node_id, key))
		unprobed_contacts = [t for t in L if t[1] == NodeStatus.UNPROBED]
		return unprobed_contacts[:config.alpha]

	def probe(q, contact):
		try:
			if lookup_type == LookupType.NODE:
				url = "http://%s:%s/api/kademlia/closest_nodes/%d/" % (contact.ip_address, contact.port, key)
				response = requests.get(url, timeout=config.timeout)
			elif lookup_type == LookupType.VALUE:
				headers = {"key": str(key)}
				url = "http://%s:%s/api/kademlia/values/" % (contact.ip_address, contact.port)
				response = requests.get(url, headers=headers, timeout=config.timeout)
			else:
				assert False
		except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
			q.put((contact, None))
			return
		q.put((contact, response))

	buckets_lock.acquire()
	L = {contact: NodeStatus.UNPROBED for bucket in buckets for contact in bucket}
	buckets_lock.release()
	while True:
		first_alpha_unprobed_contacts = get_first_alpha_unprobed(L)
		q = Queue.Queue()
		threads = []
		for contact, _ in first_alpha_unprobed_contacts:
			t = threading.Thread(target=probe, args=(q, contact))
			threads.append(t)
			t.start()
		for t in threads:
			t.join()
			contact, response = q.get()
			if response is None:
				L[contact] = NodeStatus.DEAD
			else:
				if lookup_type == LookupType.VALUE and response.status_code == 200:
					L[contact] = NodeStatus.HAS_VALUE
					result.value = response.text
				else:
					L[contact] = NodeStatus.LIVE
					for ip, port, node_id in json.loads(response.text):
						received_contact = Contact(node_id, ip, port, 0)
						if received_contact not in L and received_contact.node_id != my_id:
							L[received_contact] = NodeStatus.UNPROBED
		if ((lookup_type == LookupType.NODE and get_number_contacts_with_status(L, NodeStatus.LIVE) >= config.k)
			or get_number_contacts_with_status(L, NodeStatus.UNPROBED) == 0
			or result.value is not None):
			break
	result.k_closest_nodes = sorted(
		[contact for contact, status in L.items()
		 if status == NodeStatus.LIVE][:config.k],
		key=lambda c: distance(c.node_id, key))
	return result


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
	key = int(request.form["key"])
	value = request.form["value"]
	key_value_pairs[key] = value
	return "", 201


def store(ip, port, key, value):
	data = {"key": str(key), "value": value}
	url = "http://%s:%s/api/kademlia/values/" % (ip, port)
	response = requests.post(url, data=data)
	return response.status_code == 201


@app.route("/store_value/", methods=["POST"])
def iterative_store():
	key = int(request.form["key"])
	value = request.form["value"]
	closest_nodes = iterative_find_node(key)
	for contact in closest_nodes:
		store(contact.ip_address, contact.port, key, value)
	return redirect("/", code=302)


@app.route("/api/kademlia/values/", methods=["GET"])
def search_for_value():
	key = int(request.headers["key"])
	try:
		value = key_value_pairs[key]
	except KeyError:
		return get_closest_nodes_as_json(key), 303
	return value


@app.route("/get_value/")
def iterative_find_value():
	key = int(request.args.get("key"))
	try:
		return key_value_pairs[key]
	except KeyError:
		result = node_lookup(LookupType.VALUE, key)
		if result.value is None:
			return json.dumps([c.to_triple() for c in result.k_closest_nodes]), 404
		if len(result.k_closest_nodes) != 0:
			contact = result.k_closest_nodes[0]
			store(contact.ip_address, contact.port, key, result.value)
		return result.value


def distance(x, y):
	return x ^ y


def init_id():
	global my_id
	my_id = id_generation.generate_id(str(get_mac()) + str(my_port))
	print("My ID is: %d" % my_id)


def init_buckets():
	global buckets
	buckets = [[] for _ in range(config.B)]


def init_key_value_pairs():
	global key_value_pairs
	key_value_pairs = {}


@app.route("/")
def render_root():
	return render_template("root.html")


@app.route("/wotds/")
def render_wotds():
	return render_template("wotds.html",
						   nodes=known_wot_nodes.values(),
						   sensordata_collections=collected_data.values())


@app.route("/kademlia/")
def render_kademlia():
	buckets_lock.acquire()
	result = render_template("template.html",
							 node_id=my_id,
							 buckets=enumerate(buckets),
							 search_result=None,
							 kv_pairs=key_value_pairs.items())
	buckets_lock.release()
	return result


class DataPoint:
	def __init__(self, timestamp, raw_data):
		self.raw_data = raw_data
		self.timestamp = timestamp

	def __eq__(self, other):
		return self.raw_data == other.raw_data and self.timestamp == other.raw_data

	def __hash__(self):
		return hash(self.raw_data)


def add_data_point(node, timestamp, raw_data):
	if node.node_id not in collected_data:
		collected_data[node.node_id] = SensorDataCollection(node.description)
	collected_data[node.node_id].add_data_point(DataPoint(timestamp, raw_data))


def fetch_wot_data_from(node):
	timestamp, raw_data = json.loads(requests.get(node.url).text)
	add_data_point(node, timestamp, raw_data)

	# TODO handle if node dies

	# find k-1 closest nodes
	closest_contacts = iterative_find_node(node.node_id)[:config.k - 1]

	# push the data_point to them
	for contact in closest_contacts:
		data = {"timestamp": str(timestamp), "data": raw_data,
				"originator_nodeid": str(node.node_id),
				"originator_url": node.url,
				"description": node.description}
		url = "http://%s:%s/api/wotds/datapoints/" % (contact.ip_address, contact.port)
		requests.post(url, data=data)


# TODO: refactor this file to move out the Kademlia layer.

class SensorDataCollection:
	def __init__(self, description):
		self.data_points = set()
		self.description = description

	def add_data_point(self, data_point):
		self.data_points.add(data_point)


known_wot_nodes = {}
collected_data = {}


def check_liveness_of_responsible_node(wot_node):
	time_since_last = time.time() - wot_node.last_seen
	if (time_since_last > config.fetch_timeout * config.max_missed_fetches):
		print "I am the node", my_id
		print "I know of this node:", wot_node
		print "and I suspect that it is dead."
		# We suspect that the thing or the responsible node is dead
		# We check if the thing is alive
		try:
			requests.get(wot_node.url, timeout=config.timeout)
			print "The thing is alive!!!!!!"
		except (requests.exceptions.Timeout, requests.exceptions.ConnectionError), e:
			# The thing did not respond, so we assume it's dead
			print "The thing is dead!"
			print "the exception was:", e
			del known_wot_nodes[wot_node.node_id]
			return
		# The thing is alive, so we (re)assign the responsibility
		register_wot_node(wot_node)


def wot_fetcher():
	while True:
		for wot_node in known_wot_nodes.values():
			if (wot_node.we_are_responsible):
				# TODO add try/catch to this in case thing or replicant dies.
				fetch_wot_data_from(wot_node)
			else:
				check_liveness_of_responsible_node(wot_node)

		time.sleep(config.fetch_timeout)


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

	t = threading.Thread(target=wot_fetcher)
	t.start()

	if len(sys.argv) > 3:
		initial_peer_ip = sys.argv[2]
		initial_peer_port = int(sys.argv[3])
		send_ping(initial_peer_ip, initial_peer_port, 1)

	#http_server = WSGIServer(('', my_port), app)
	#http_server.serve_forever()
	app.run(host="0.0.0.0", port=my_port, threaded=True)
