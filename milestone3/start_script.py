import subprocess
import random
import time
import os

number_of_peers = 100

peers_list = []
p = subprocess.Popen(["python2", "main.py", "5000"])
for i in range(0, number_of_peers - 1):
    time.sleep(0.3)
    p = subprocess.Popen(["python2", "main.py", "%d" % (5001 + i), "127.0.0.1", "%d" % (5000 + random.randint(0, i/5))])
    peers_list.append(p)
raw_input("Type anything to close all peers\n")
p.kill()
os.system("killall python2")
print("Done!")
