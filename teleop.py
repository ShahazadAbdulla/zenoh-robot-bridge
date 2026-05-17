#!/usr/bin/env python3
"""
Zenoh Robot Teleop — FINAL VERSION
Sends per-wheel speeds: bytes([left, right]) where -127..127
"""
import zenoh
import sys
import termios
import tty
import select

# If your robot spins left when you press D, set this to True
SWAP_MOTORS = True

def get_key():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        if select.select([sys.stdin], [], [], 0.1)[0]:
            return sys.stdin.read(1)
        return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def main():
    print("Zenoh Robot Teleop")
    print("------------------")
    print("W: Forward   S: Backward")
    print("A: Spin Left D: Spin Right")
    print("Space: Stop  Q: Quit")
    print("------------------")

    config = zenoh.Config()
    config.insert_json5("mode", "'peer'")
    session = zenoh.open(config)
    pub = session.declare_publisher("robot/drive")

    print(f"[INFO] Connected. ZID: {session.zid()}\n")
    
    speed = 127  # Max 127. This is your "speed limit" in Python.

    def send(left, right):
        left = max(-127, min(127, left))
        right = max(-127, min(127, right))
        
        if SWAP_MOTORS:
            left, right = right, left
            
        payload = bytes([left & 0xFF, right & 0xFF])
        pub.put(payload)
        
        l_disp = int.from_bytes(payload[0:1], byteorder='little', signed=True)
        r_disp = int.from_bytes(payload[1:2], byteorder='little', signed=True)
        print(f"\r[TX] L={l_disp:4d} R={r_disp:4d} | hex: {payload.hex()}  ", end="", flush=True)

    try:
        while True:
            key = get_key()
            if key is None:
                continue

            if key in ('w', 'W'):
                send(speed, speed)
            elif key in ('s', 'S'):
                send(-speed, -speed)
            elif key in ('a', 'A'):
                send(-speed, speed)      # Left back, Right forward = spin left
            elif key in ('d', 'D'):
                send(speed, -speed)      # Left forward, Right back = spin right
            elif key == ' ':
                send(0, 0)
            elif key in ('q', 'Q'):
                print("\n[INFO] Quitting...")
                break

    finally:
        send(0, 0)
        pub.undeclare()
        session.close()

if __name__ == "__main__":
    main()
