import subprocess
import random
import time

number_of_peers = 50

peers_list = []
p = subprocess.Popen(["python", "main.py", "5000"])
for i in range(0, number_of_peers - 1):
    time.sleep(0.3)
    p = subprocess.Popen(["python", "main.py", "%d" % (5001 + i), "127.0.0.1", "%d" % (5000 + random.randint(0, i/5))])
    peers_list.append(p)
raw_input("Type anything to close all peers\n")
p.kill()
for peer in peers_list:
    peer.kill()
print("Done!")
