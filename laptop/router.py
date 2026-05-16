#!/usr/bin/env python3
"""
Zenoh Router — DEBUG VERSION
"""
import subprocess
import sys
import os

def main():
    print("Starting Zenoh Router (DEBUG LOGS)...")
    print("Listening on all interfaces, port 7447")
    print("Multicast scouting on 224.0.0.224:7446")
    print("Press Ctrl+C to stop\n")
    
    env = os.environ.copy()
    env["RUST_LOG"] = "debug"  # Rust/Zenoh uses RUST_LOG, not --log-level
    
    try:
        subprocess.run([
            "zenohd",
            "--listen", "tcp/0.0.0.0:7447"
        ], env=env, check=True)
    except FileNotFoundError:
        print("ERROR: 'zenohd' not found. Install with: pip install eclipse-zenoh")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nRouter stopped.")

if __name__ == "__main__":
    main()
