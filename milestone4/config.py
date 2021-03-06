# The degree of parallelism, while searching
alpha = 1

# size of the ID-space (and thus number of buckets)
B = 8
assert (B % 4 == 0)

# number of items in each bucket
k = 2

# timeout for pings
timeout = 10

# how long to wait between each fetch of WoT data
fetch_timeout = 10

# How many fetches to be missed before we suspect that a node is dead
max_missed_fetches = 3
