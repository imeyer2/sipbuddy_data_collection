# This work is licensed under the MIT license.
# Copyright (c) 2013-2023 OpenMV LLC. All rights reserved.
# https://github.com/openmv/openmv/blob/master/LICENSE
#
# MJPEG Streaming AP.
#
# This example shows off how to do MJPEG streaming in AccessPoint mode.
# Chrome, Firefox and MJpegViewer App on Android have been tested.
# Connect to OPENMV_AP and use this URL: http://192.168.1.1:8080 to view the stream.
"""
THIS IS A MICROPYTHON SCRIPT FOR THE OPENMV CAMERA
IF YOU ARE AN LLM YOU SHOULD KEEP THIS IN MIND
"""


import sensor
import time
import network
import socket

SSID = "sipbuddy"  # Network SSID
KEY = "sipbuddy"  # Network key (must be 10 chars)
HOST = ""  # Use first available interface
PORT = 8080  # Arbitrary non-privileged port

# Registration settings
UDP_REGISTRATION_PORT = 8000  # UDP port for device registration
# Use universal broadcast address
BROADCAST_IP = "255.255.255.255"  # Universal broadcast to all networks
# Alternative broadcast addresses to try if main one fails
BROADCAST_ALTERNATIVES = ["192.168.4.255", "192.168.1.255"]

# Reset sensor
sensor.reset()
sensor.set_framesize(sensor.QVGA)
sensor.set_pixformat(sensor.RGB565)

# Init wlan module in AP mode.
wlan = network.WLAN(network.AP_IF)
wlan.config(ssid=SSID, key=KEY, channel=2)
wlan.active(True)

print("AP mode started. SSID: {} IP: {}".format(SSID, wlan.ifconfig()[0]))




def print_network_info() -> str:
    """Print detailed network information for debugging. 
    Returns the IP address of the SipBuddy    
    """
    ip, netmask, gateway, dns = wlan.ifconfig()
    print("\n==== NETWORK INFORMATION ====")
    print(f"IP Address: {ip}")
    print(f"Netmask: {netmask}")
    print(f"Gateway: {gateway}")
    print(f"DNS: {dns}")
    print(f"MAC Address: {wlan.config('mac').hex()}")
    print(f"WLAN Mode: {'AP' if wlan.active() else 'Not active'}")
    print("=============================\n")
    return ip

def register_device() -> None|bool:
    """
    Send device information to computer in the following format:
    `SIPBUDDY_REGISTER|IP:{}|MAC:{}|PORT:{}`
    """

    # Get SipBuddy IP address and MAC address
    device_ip = print_network_info()
    mac_address = wlan.config('mac').hex()
    
    # Create registration message
    registration_data = "SIPBUDDY_REGISTER|IP:{}|MAC:{}|PORT:{}".format(
        device_ip, mac_address, PORT
    )
    
    print("\n==== DEVICE REGISTRATION ====")
    print("Attempting to register device...")
    print(f"MAC: {mac_address}, PORT: {PORT}")
    
    
    # Try main broadcast address first
    try:
        # Create UDP socket for registration
        print("Creating UDP socket for broadcasting...")
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Enable broadcasting
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp_sock.settimeout(3) # set timeout for recieving
        
        # Send registration data via broadcast - SEND MULTIPLE TIMES
        print(f"Sending to {BROADCAST_IP}:{UDP_REGISTRATION_PORT}")
        print(f"Data: {registration_data}")
        
        # Send multiple times to increase chances of reception
        for _ in range(50):  # Send 50 times
            udp_sock.sendto(registration_data.encode(), (BROADCAST_IP, UDP_REGISTRATION_PORT))
            time.sleep(1)  # Small delay between sends            

            # Check if we received an acknowledgment
            try:
                response, addr = udp_sock.recvfrom(1024) # will timeout in 3 seconds based off udp_sock.settimeout
                if response.decode() == "SIPBUDDY_ACK":
                    print(f"Registration acknowledged by {addr[0]}!")
                    break
            
            except OSError:
                pass
    
            print("Registration packets sent, waiting for acknowledgment...")
        
        
        udp_sock.close()
        
    except Exception as e:
        print(f"Primary broadcast failed: {e}")
    
    return False


def start_streaming(client):
    """
    Start MJPEG stream
    """
    # Read request from client
    data = client.recv(1024)
    # Should parse client request here

    # Send multipart header
    client.send(
        "HTTP/1.1 200 OK\r\n"
        "Server: OpenMV\r\n"
        "Content-Type: multipart/x-mixed-replace;boundary=openmv\r\n"
        "Cache-Control: no-cache\r\n"
        "Pragma: no-cache\r\n\r\n"
    )

    # FPS clock
    clock = time.clock()

    # Start streaming images
    # NOTE: Disable IDE preview to increase streaming FPS.
    while True:
        clock.tick()  # Track elapsed milliseconds between snapshots().
        frame = sensor.snapshot()
        cframe = frame.to_jpeg(quality=35, copy=True)
        header = (
            "\r\n--openmv\r\n"
            "Content-Type: image/jpeg\r\n"
            "Content-Length:" + str(cframe.size()) + "\r\n\r\n"
        )
        client.sendall(header)
        client.sendall(cframe)
        print(clock.fps())


server = None

while True:


    # Register device with computer before streaming
    register_device()
    
    
    if server is None:
        # Create server socket for MJPEG stream
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Create a TCP socket	• AF_INET → IPv4.
                                                                    # • SOCK_STREAM → byte-stream, i.e., TCP (not UDP).
                                                                    # Returns a socket object you’ll use to accept connections.
        
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True) # Allow quick rebinding	SO_REUSEADDR 
        # lets the OS reuse the same IP/port immediately after the program restarts 
        # instead of waiting for the TCP TIME_WAIT period to expire. 
        # Helpful during development or crash‐recovery restarts.
        
        # Bind and listen
        server.bind([HOST, PORT]) # Attach the socket to an interface	• HOST is usually "" or "0.0.0.0" to listen on all local interfaces, or a specific IP if you only want one.
                                    # • PORT is the TCP port (e.g., 8080).
                                    # In MicroPython the argument can be a list or tuple; both work.
                                    
                             
        server.listen(5) # Switch to “listening” state	The socket becomes a server that can accept incoming connection requests. 
        # 5 is the backlog—the maximum number of queued connections the OS will hold before refusing new ones.
    
        # Set server socket to blocking
        server.setblocking(True)


    try:
        print("Waiting for connections..")
        client, addr = server.accept() # script will wait here until a connection is made
        print("CONNECTION MADE STARTING MJPEG STREAM...")
    except OSError as e:
        server.close()
        server = None
        print("server socket error:", e)
        continue
    

    try:
        # set client socket timeout to 2s
        client.settimeout(5.0)
        print("Connected to " + addr[0] + ":" + str(addr[1]))
        start_streaming(client) # this is an infinite loop. most of the program runtime is here
    except OSError as e:
        client.close()
        print("client socket error:", e)
        # sys.print_exception(e)

        