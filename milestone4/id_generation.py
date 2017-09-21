import hashlib
import config

def generate_id(value_to_be_hashed):
	num_digits = config.B / 4
	hex_digest = hashlib.sha256(value_to_be_hashed).hexdigest()
	my_id = int(hex_digest[:num_digits], 16)
	return my_id
