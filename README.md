# 🤖 Zenoh Robot Bridge

A location-transparent robotics control system using [Zenoh](https://zenoh.io) — zero IP hardcoding, zero mDNS, pure peer-to-peer discovery over WiFi.

Built for ESP32 motor control, Android AI vision, and laptop telemetry — no IP addresses, no configuration files, just power on and go.

---

## 🎬 What This Does

| Component | Role | Zenoh Mode |
|-----------|------|------------|
| **Laptop** | Zenoh Router + Web Dashboard | `router` |
| **Android Phone** | AI Lane Detection + Camera Stream | `peer` |
| **ESP32** | Motor Driver (TB6612FNG) | `client` |

The phone runs a lane-following model, publishes steering commands to `robot/drive`, and streams camera frames to `robot/camera`. The ESP32 receives drive commands and controls the motors. The laptop hosts the Zenoh router and a web joystick for manual override.

**No hardcoded IPs. No mDNS. No pairing. Power on → auto-discover → drive.**

---

## 🏗️ Architecture

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│  Android Phone  │         │     Laptop      │         │     ESP32       │
│  (Zenoh Peer)   │◄───────►│  Zenoh Router   │◄───────►│  (Zenoh Client) │
│                 │   WiFi  │  Port 7447      │   WiFi  │                 │
│ • Lane Model    │         │                 │         │ • TB6612FNG     │
│ • Camera Stream │         │ • Web Joystick  │         │ • Auto-scout    │
│ • Drive Pub     │         │ • Viewer        │         │ • Motor Control │
└─────────────────┘         └─────────────────┘         └─────────────────┘
        ▲                          ▲
        │                          │
        └────── Web Browser ───────┘
              http://laptop:8080
              Virtual joystick
```

**Discovery:** All devices find the router via UDP multicast scouting on `224.0.0.224:7446`. If multicast is blocked (common on phone hotspots), the ESP32 falls back to direct connect using the predictable gateway IP.

---

## 📡 Data Protocol

| Topic | Direction | Payload | Format |
|-------|-----------|---------|--------|
| `robot/drive` | Phone → ESP32 | 2 bytes | `byteArrayOf(left, right)` signed 8-bit |
| `robot/camera` | Phone → Laptop | JPEG bytes | CameraX frame, throttled to 5 FPS |
| `robot/depth` | Phone → Laptop | JPEG bytes | Depth map visualization |

**Drive command detail:**
- Byte 0: Left motor, `-127` (full reverse) to `+127` (full forward)
- Byte 1: Right motor, same range
- ESP32 scales `127 → 255` for 8-bit PWM internally

---

## 🚀 Quick Start

### 1. Laptop — Start the Router

```bash
pip install eclipse-zenoh
zenohd --listen tcp/0.0.0.0:7447
```

### 2. ESP32 — Flash the Firmware

```bash
cd esp32/
# Set your WiFi credentials via menuconfig
idf.py menuconfig
idf.py build flash monitor
```

The ESP32 will auto-discover the router via multicast scouting. No IP configuration needed.

### 3. Android — Build & Run

Open `android/` in Android Studio. The app uses CameraX for frame capture and publishes to Zenoh.

### 4. Web Joystick (Optional Manual Control)

```bash
cd laptop/
pip install aiohttp
python3 web_joystick.py
# Open http://laptop-ip:8080 on any browser
```

---

## 📁 Repository Structure

```
zenoh-robot-bridge/
├── esp32/                    # ESP-IDF firmware
│   ├── main/
│   │   └── main.c           # WiFi + Zenoh + Motor control
│   ├── components/
│   │   └── zenoh_wrapper/   # ESP-IDF v5.x compatible wrapper
│   ├── CMakeLists.txt
│   └── sdkconfig.defaults
├── android/                  # Android Studio project
│   └── app/src/main/java/...
│       └── ZenohNode.kt     # Kotlin Zenoh publisher
├── laptop/                   # Python tools
│   ├── router.py            # Zenohd launcher wrapper
│   ├── teleop.py            # Keyboard teleoperation
│   ├── web_joystick.py      # Browser-based joystick
│   ├── viewer.py            # Camera frame viewer (OpenCV)
│   ├── doctor.py            # Live network diagnostic
│   └── camera_checker.py    # Simple camera data verification
├── PROTOCOL.md              # Full protocol specification
└── README.md                # This file
```

---

## 🛠️ Hardware

| Component | Spec |
|-----------|------|
| MCU | ESP32 (Xtensa LX6) |
| Motor Driver | TB6612FNG |
| Motors | 6V DC with encoders |
| Power | 2S LiPo (7.4V) |
| Phone | Any Android with CameraX support |

**Pinout (ESP32):**
```
AIN1 = GPIO 4      BIN1 = GPIO 25
AIN2 = GPIO 18     BIN2 = GPIO 26
PWMA = GPIO 19     PWMB = GPIO 27
STBY = GPIO 5
```

---

## 🔧 Why Zenoh?

| Feature | Why It Matters |
|---------|---------------|
| **Location Transparency** | No IP addresses in application code |
| **Multicast Scouting** | Auto-discovery on any LAN |
| **Compact Binary** | ~5 byte header vs HTTP/MQTT overhead |
| **One-to-Many** | Phone publishes once, ESP32 + Laptop receive simultaneously |
| **Resilience** | Auto-reconnects after WiFi blips |
| **No Broker** | Direct peer-to-peer, no single point of failure |

---

## 📜 Protocol Specification

See [PROTOCOL.md](PROTOCOL.md) for the full data contract, byte layouts, and integration guide for third-party clients.

---

## 🤝 Contributing

This is a reference implementation for the robotics community. PRs welcome for:
- ROS 2 bridge nodes
- WebRTC camera streaming overlay
- SLAM integration
- Additional motor driver support (L298N, DRV8833)

---

## 📄 License

MIT License — use it, fork it, build something cool.

---

Built with ☕, 🔧, and zero hardcoded IPs.
