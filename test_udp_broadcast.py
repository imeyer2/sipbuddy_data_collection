#!/usr/bin/env python3
"""
Test UDP broadcasting and receiving for SipBuddy system.
Run this on your computer to verify that broadcasts can be sent and received.
"""

import socket
import time
import threading
import argparse
import sys

# Default ports and broadcast address
REGISTRATION_PORT = 8000
BROADCAST_ADDR = "255.255.255.255"  # Universal broadcast

def setup_receiver():
    """Setup a UDP receiver that listens for messages"""
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Allow broadcast packets
    try:
        receiver.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except:
        print("Warning: Could not set SO_BROADCAST on receiver")
    
    try:
        receiver.bind(('', REGISTRATION_PORT))
        print(f"Receiver listening on *:{REGISTRATION_PORT}")
        # Print all local IP addresses to help debugging
        try:
            # import socket
            hostname = socket.gethostname()
            print(f"Computer hostname: {hostname}")
            print("Local IP addresses:")
            addrs = socket.getaddrinfo(hostname, None)
            for addr in addrs:
                if addr[0] == socket.AF_INET:  # Only IPv4
                    print(f"  - {addr[4][0]}")
        except:
            print("Could not determine local IP addresses")
            
        return receiver
    except Exception as e:
        print(f"ERROR: Could not bind to port {REGISTRATION_PORT}: {e}")
        
        # Try to check if the port is in use
        try:
            import subprocess
            if sys.platform == 'win32':
                output = subprocess.check_output(f"netstat -ano | findstr :{REGISTRATION_PORT}", shell=True).decode()
                print(f"Port usage information:\n{output}")
            elif sys.platform == 'darwin':  # macOS
                output = subprocess.check_output(f"lsof -i :{REGISTRATION_PORT}", shell=True).decode()
                print(f"Port usage information:\n{output}")
            else:  # Linux
                output = subprocess.check_output(f"netstat -tuln | grep :{REGISTRATION_PORT}", shell=True).decode()
                print(f"Port usage information:\n{output}")
        except:
            print("Could not check port usage")
            
        sys.exit(1)

def setup_sender():
    """Setup a UDP sender that can broadcast messages"""
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    return sender

def receive_thread(receiver):
    """Thread to receive and display incoming UDP messages"""
    print("Waiting for UDP messages... Press Ctrl+C to exit")
    while True:
        try:
            data, addr = receiver.recvfrom(1024)
            data_str = data.decode('utf-8', errors='replace')  # Handle any encoding issues
            print(f"\n[RECEIVED] From {addr[0]}:{addr[1]}: {data_str}")
            
            # Check if this looks like a SipBuddy registration
            if "SIPBUDDY_REGISTER" in data_str:
                print(f"Detected SipBuddy registration! Sending acknowledgment")
                # Send acknowledgment
                print(f"[SENDING] Acknowledgment to {addr[0]}:{addr[1]}")
                receiver.sendto("SIPBUDDY_ACK".encode(), addr)
            else:
                # Still acknowledge other messages for testing
                print(f"[SENDING] Test acknowledgment to {addr[0]}:{addr[1]}")
                receiver.sendto("TEST_ACK".encode(), addr)
                
        except Exception as e:
            print(f"Error receiving: {e}")
            time.sleep(1)  # Add delay to avoid tight loops on errors

def broadcast_test_message(sender, message="TEST_BROADCAST", broadcast_addr=BROADCAST_ADDR):
    """Send a test broadcast message"""
    try:
        print(f"[SENDING] Broadcast to {broadcast_addr}:{REGISTRATION_PORT}: {message}")
        sender.sendto(message.encode(), (broadcast_addr, REGISTRATION_PORT))
        return True
    except Exception as e:
        print(f"Error sending: {e}")
        return False

def main():
    global REGISTRATION_PORT
    parser = argparse.ArgumentParser(description="Test UDP broadcasting for SipBuddy")
    parser.add_argument("--send-only", action="store_true", help="Only send test broadcasts")
    parser.add_argument("--receive-only", action="store_true", help="Only listen for broadcasts")
    parser.add_argument("--broadcast-ip", default=BROADCAST_ADDR, help="Broadcast IP address")
    parser.add_argument("--message", default="SIPBUDDY_REGISTER|IP:127.0.0.1|MAC:112233445566", 
                        help="Message to broadcast")
    parser.add_argument("--port", type=int, default=REGISTRATION_PORT, 
                        help="UDP port for communication")
    parser.add_argument("--verbose", action="store_true", help="Show detailed debug information")
    
    args = parser.parse_args()
    
    # Update port if specified
    # global REGISTRATION_PORT
    REGISTRATION_PORT = args.port
    
    if args.verbose:
        print("\n==== NETWORK INFORMATION ====")
        # Print all network interfaces
        try:
            import netifaces
            print("Available network interfaces:")
            for interface in netifaces.interfaces():
                try:
                    addresses = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET in addresses:
                        for addr_info in addresses[netifaces.AF_INET]:
                            print(f"  - {interface}: {addr_info['addr']}")
                except:
                    pass
        except ImportError:
            print("Install netifaces package for more network info: pip install netifaces")
            
            # Basic fallback method
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                print(f"Primary local IP: {local_ip}")
            except:
                print("Could not determine local IP")
        print("=============================\n")
    
    # By default, both send and receive
    do_send = not args.receive_only
    do_receive = not args.send_only
    
    # Setup receiver if needed
    if do_receive:
        receiver = setup_receiver()
        thread = threading.Thread(target=receive_thread, args=(receiver,), daemon=True)
        thread.start()
    
    # Setup sender if needed
    if do_send:
        sender = setup_sender()
        
        try:
            while True:
                broadcast_test_message(sender, args.message, args.broadcast_ip)
                time.sleep(5)  # Send every 5 seconds
        except KeyboardInterrupt:
            print("\nSender terminated by user")
    else:
        # Just keep the receiver running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nReceiver terminated by user")

if __name__ == "__main__":
    main()
