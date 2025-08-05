#!/usr/bin/env python3
"""
Very-simple SipBuddy recorder (pull model)

 • Each camera stays an HTTP MJPEG server on port 8080.
 • Laptop pulls the stream and FFmpeg cuts 30-second MP4 files.
 • Auto-discovers SipBuddy devices via UDP broadcasts.

Requirements:
    - FFmpeg in PATH   (sudo apt install ffmpeg | brew install ffmpeg)
    - Python 3.8+
"""

import subprocess, pathlib, datetime, time, threading
import socket
import logging
import queue
import re
import sys
import argparse

# ───── CONFIGURE YOUR CAMERAS HERE ─────────────────────────────────────────
# Default cameras (will be supplemented by auto-discovery)
CAMERAS = [
    # {"ip": "192.168.4.1", "id": "ian_sipbuddy"},
    # {"ip": "192.168.4.102", "id": "bar_center"},
    # {"ip": "192.168.4.103", "id": "bar_right"},
    # Or use mDNS hostnames like "sipbuddy-001.local"
]
SEGMENT_SECONDS = 30                       # length of each .mp4 chunk
OUT_ROOT        = pathlib.Path("recordings")
UDP_REGISTRATION_PORT = 8000                   # UDP port for device registration
# ───────────────────────────────────────────────────────────────────────────

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('sipbuddy')

# Queue for newly discovered cameras
discovered_cameras = queue.Queue()
# Dict to track known cameras by MAC
known_cameras = {}

def parse_registration(data):
    """Parse registration message from SipBuddy device."""
    try:
        # Expected format: "SIPBUDDY_REGISTER|IP:xxx.xxx.xxx.xxx|MAC:xxxxxxxxxxxx|PORT:xxxx"
        if not data.startswith("SIPBUDDY_REGISTER"):
            return None
        
        ip_match = re.search(r'IP:([^|]+)', data)
        mac_match = re.search(r'MAC:([^|]+)', data)
        port_match = re.search(r'PORT:(\d+)', data)
        
        if not (ip_match and mac_match):
            return None
            
        ip = ip_match.group(1)
        mac = mac_match.group(1)
        port = port_match.group(1) if port_match else "8080"
        
        return {
            "ip": ip,
            "mac": mac,
            "id": f"sipbuddy_{mac[-6:]}", # Use last 6 chars of MAC as ID
            "port": port
        }
    except Exception as e:
        logger.error(f"Failed to parse registration data: {e}")
        return None

def run_udp_listener():
    """Listen for SipBuddy device registrations via UDP."""
    logger.info(f"Starting UDP listener on port {UDP_REGISTRATION_PORT}")
    
    # Create UDP socket
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Try to bind to port
    try:
        udp_sock.bind(('', UDP_REGISTRATION_PORT))
        logger.info(f"Successfully bound to *:{UDP_REGISTRATION_PORT}")
    except Exception as e:
        logger.error(f"Failed to bind to port {UDP_REGISTRATION_PORT}: {e}")
        logger.info("Trying to detect if port is already in use...")
        
    while True:
        print("Searching for devices over UDP...")
        try:
            data, addr = udp_sock.recvfrom(512)  # Receive up to 512 bytes
            data_str = data.decode('utf-8')
            print(data_str)
            logger.info(f"Received registration from {addr[0]}:{addr[1]}: {data_str}")
            
            device_info = parse_registration(data_str)
            if device_info:
                mac = device_info["mac"]
                
                # Send acknowledgment
                udp_sock.sendto("SIPBUDDY_ACK".encode(), addr)
                logger.info(f"Sent acknowledgment to {addr[0]}")
                
                # Only add new cameras or update existing ones
                if mac not in known_cameras:
                    logger.info(f"New SipBuddy discovered: {device_info}")
                    known_cameras[mac] = device_info
                    discovered_cameras.put(device_info)
                elif known_cameras[mac]["ip"] != device_info["ip"]:
                    # IP has changed, update and re-add
                    logger.info(f"SipBuddy IP updated: {device_info}")
                    known_cameras[mac] = device_info
                    discovered_cameras.put(device_info)
        except Exception as e:
            logger.error(f"Error in UDP listener: {e}")
            time.sleep(1)

def run_ffmpeg(cam: dict) -> None:
    """Spawn (and respawn) one FFmpeg process for the given camera."""
    ip, cam_id = cam["ip"], cam["id"]
    while True:
        ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        out_dir = OUT_ROOT / cam_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_tpl = str(out_dir / f"{ts}_%03d.mp4")

        cmd = [
            "ffmpeg",
            "-hide_banner", "-loglevel", "error",
            "-i", f"http://{ip}:8080",     # pull MJPEG directly
            "-c", "copy",                  # no re-encode → tiny CPU load
            "-f", "segment",
            "-segment_time", str(SEGMENT_SECONDS),
            "-reset_timestamps", "1",
            out_tpl,
        ]

        print(f"[{cam_id}] ▶️  starting   → {out_tpl}")
        proc = subprocess.Popen(cmd)

        ret = proc.wait()
        print(f"[{cam_id}] ⚠️  ffmpeg exited with {ret}; retrying in 2 s")
        time.sleep(2)                      # simple back-off before restart

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="SipBuddy Recorder")
    parser.add_argument("--discovery-only", action="store_true", 
                      help="Run only in discovery mode without starting FFmpeg")
    args = parser.parse_args()

    OUT_ROOT.mkdir(exist_ok=True)
    threads = []
    
    # Start UDP listener for device discovery
    discovery_thread = threading.Thread(target=run_udp_listener, daemon=True)
    discovery_thread.start()
    threads.append(discovery_thread)
    
    if args.discovery_only:
        logger.info("Running in discovery-only mode. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Discovery mode terminated by user")
            return
    
    # Start threads for known cameras
    for cam in CAMERAS:
        t = threading.Thread(target=run_ffmpeg, args=(cam,), daemon=True)
        t.start()
        threads.append(t)
    
    # Process for handling newly discovered cameras
    def handle_discoveries():
        while True:
            try:
                new_cam = discovered_cameras.get(timeout=1.0)
                logger.info(f"Starting recording for newly discovered camera: {new_cam['id']} ({new_cam['ip']})")
                t = threading.Thread(target=run_ffmpeg, args=(new_cam,), daemon=True)
                t.start()
                threads.append(t)
            except queue.Empty:
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error handling discovered camera: {e}")
                time.sleep(1)
    
    discovery_handler = threading.Thread(target=handle_discoveries, daemon=True)
    discovery_handler.start()
    threads.append(discovery_handler)
    
    # Keep main thread alive
    for t in threads: t.join()

if __name__ == "__main__":
    main()
