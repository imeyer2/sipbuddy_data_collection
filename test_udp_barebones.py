#!/usr/bin/env python3
# ---------------------------------------------------------------
# Laptop listener for AE3 beacons on UDP/9000
# ---------------------------------------------------------------
import socket

PORT = 9000  # The UDP port to listen on - both sender and receiver must use the same port

# Create a UDP socket (datagram socket)
# AF_INET = IPv4 address family
# SOCK_DGRAM = UDP protocol (connectionless, message-oriented)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Bind socket to listen on all network interfaces ("") on specified port
# This makes the socket receive packets sent to any IP address on this machine
# Empty string means "all available interfaces" (0.0.0.0 in IPv4)
sock.bind(("", PORT))

# Let user know we're ready and waiting
print(f"Listening for beacons on UDP/{PORT} …")

# Infinite loop to continuously listen for incoming packets
while True:
    # Wait for a UDP packet to arrive (blocking call)
    # recvfrom returns both the data and the address of the sender
    # 128 = maximum number of bytes to receive in a single packet
    data, addr = sock.recvfrom(128)
    
    try:
        # Convert binary data to string and split by the pipe character
        # Expecting format: "ip_address|mac_address"
        ip, mac = data.decode().split("|")
        
        # Print the received information
        # addr[0] contains the sender's IP address
        print(f"Beacon from {addr[0]}  →  ip={ip}  mac={mac}")
    except ValueError:
        # If the data doesn't follow expected format (couldn't split into two parts),
        # print the raw data as an error message
        print("Malformed:", data)
