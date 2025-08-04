#!/usr/bin/env python3
"""
Very-simple SipBuddy recorder (pull model)

 • Each camera stays an HTTP MJPEG server on port 8080.
 • Laptop pulls the stream and FFmpeg cuts 30-second MP4 files.

Requirements:
    - FFmpeg in PATH   (sudo apt install ffmpeg | brew install ffmpeg)
    - Python 3.8+

Edit the CAMERAS list to match your IPs (or .local hostnames).
"""

import subprocess, pathlib, datetime, time, threading

# ───── CONFIGURE YOUR CAMERAS HERE ─────────────────────────────────────────
CAMERAS = [
    {"ip": "192.168.4.1", "id": "ian_sipbuddy"},
    # {"ip": "192.168.4.102", "id": "bar_center"},
    # {"ip": "192.168.4.103", "id": "bar_right"},
    # Or use mDNS hostnames like "sipbuddy-001.local"
]
SEGMENT_SECONDS = 30                       # length of each .mp4 chunk
OUT_ROOT        = pathlib.Path("recordings")
# ───────────────────────────────────────────────────────────────────────────

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
    OUT_ROOT.mkdir(exist_ok=True)
    threads = []
    for cam in CAMERAS:
        t = threading.Thread(target=run_ffmpeg, args=(cam,), daemon=True)
        t.start()
        threads.append(t)
    # Keep main thread alive
    for t in threads: t.join()

if __name__ == "__main__":
    main()
