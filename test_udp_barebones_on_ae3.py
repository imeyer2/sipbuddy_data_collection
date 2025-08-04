# SPDX-License-Identifier: MIT
# ---------------------------------------------------------------
# AE3  •  Soft-AP + one-line UDP beacon
# ---------------------------------------------------------------
import network, socket, time, ubinascii as ub

# ----- Wi-Fi AP credentials ------------------------------------
SSID = "sipbuddy"            # change if you like
KEY  = "sipbuddy"            # 10-char WEP key (lab/demo use)

# ----- Bring up Soft-AP ----------------------------------------
ap = network.WLAN(network.AP_IF)
ap.active(True)                               # interface ON
ap.config(ssid=SSID, key=KEY, channel=2)      # set SSID/PW

print("AP up → SSID:", SSID, "IP:", ap.ifconfig()[0])

# ----- Prepare beacon socket -----------------------------------
BCAST_IP = "255.255.255.255"   # send to everyone
PORT     = 9000                # fixed listener port

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

# ----- Build static payload once --------------------------------
device_ip  = ap.ifconfig()[0]
device_mac = ub.hexlify(ap.config('mac')).decode()  # e.g. aabbccddeeff
payload    = f"{device_ip}|{device_mac}".encode()   # "ip|mac"

# ----- Beacon forever -------------------------------------------
while True:
    sock.sendto(payload, (BCAST_IP, PORT))
    print('sent')
    time.sleep(1)            # 1 Hz beacon
