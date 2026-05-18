# Zenoh Robot Protocol v1.0

## Overview

This document defines the data contract between the Android phone (publisher), ESP32 (subscriber), and laptop (subscriber/viewer) in the Zenoh Robot Bridge system.

## Topics

### `robot/drive`

**Direction:** Phone → ESP32  
**Frequency:** 10–30 Hz (model-dependent)  
**Payload:** 2 bytes

| Byte | Field | Type | Range | Description |
|------|-------|------|-------|-------------|
| 0 | left | int8 | -127 to +127 | Left motor speed. Negative = reverse. |
| 1 | right | int8 | -127 to +127 | Right motor speed. Negative = reverse. |

**ESP32 Scaling:**
```c
left_pwm = (left * 255) / 127;   // Maps to 0-255 for LEDC
right_pwm = (right * 255) / 127;
```

**Examples:**
```kotlin
// Forward full
byteArrayOf(127, 127)

// Spin left (left back, right forward)
byteArrayOf(-127, 127)

// Gentle right turn while moving
byteArrayOf(80, 100)

// Stop
byteArrayOf(0, 0)
```

### `robot/camera`

**Direction:** Phone → Laptop  
**Frequency:** 5 FPS (throttled to avoid WiFi saturation)  
**Payload:** JPEG-encoded ByteArray  
**Format:** Standard JPEG, any resolution  

**Android (Kotlin):**
```kotlin
val jpegBytes = imageProxy.toJpeg()  // CameraX → JPEG
rgbCamPub.put(ZBytes.from(jpegBytes))
```

**Python Viewer:**
```python
import cv2, numpy as np, zenoh

def on_frame(sample):
    nparr = np.frombuffer(bytes(sample.payload), np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    cv2.imshow("Camera", frame)
```

### Dependencies & Build Configurations
 1. Android Dependency Configuration (build.gradle.kts)
To incorporate the native Zenoh client bindings into the Android pipeline, ensure your repositories query Maven Central. The library wraps the underlying performance architecture using the native Android NDK ecosystem layer.

```Kotlin
repositories {
    mavenCentral()
}

dependencies {
    // Core Eclipse Zenoh Android Binding Library
    implementation("org.eclipse.zenoh:zenoh-kotlin-android:1.1.1")
}
```

 2. Android Platform Permissions (AndroidManifest.xml)
Zenoh utilizes socket interfaces for mesh routing. The following application hardware configurations are required:
```XML
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
<uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
<uses-permission android:name="android.permission.CHANGE_WIFI_MULTICAST_STATE" />
```

### `robot/depth` (Optional)

**Direction:** Phone → Laptop  
**Frequency:** 1–2 FPS  
**Payload:** JPEG-encoded depth visualization  

Same format as `robot/camera`, but carries a depth map rendered as grayscale or color-mapped JPEG.

## Discovery

### Multicast Scouting (Preferred)

All clients use UDP multicast to `224.0.0.224:7446` to discover the router.

**Android:**
```kotlin
val config = Config.default()  // Peer mode, auto-scout
session = Zenoh.open(config)
```

**ESP32:**
```c
zp_config_insert(config, Z_CONFIG_MODE_KEY, "client");
// No Z_CONFIG_CONNECT_KEY = multicast scouting
```

### Fallback: Direct Connect

If multicast is blocked (common on mobile hotspots), use the gateway IP:

| Hotspot Type | Gateway IP |
|-------------|-----------|
| Windows Mobile Hotspot | `192.168.137.1` |
| Android Hotspot | `192.168.43.1` or `192.168.12.1` |
| Linux (NetworkManager) | `10.42.0.1` |

**ESP32 Fallback:**
```c
zp_config_insert(config, Z_CONFIG_CONNECT_KEY, "tcp/192.168.12.1:7447");
```

## Zenoh Configuration

### Router (Laptop)
```bash
zenohd --listen tcp/0.0.0.0:7447
```

### Android (Peer)
```kotlin
val config = Config.default()
val session = Zenoh.open(config)
```

### ESP32 (Client)
```c
z_config_default(&config);
zp_config_insert(z_loan_mut(config), Z_CONFIG_MODE_KEY, "client");
```

## Version Compatibility

| Component | Version |
|-----------|---------|
| Zenoh Rust (router) | 1.9.0 |
| Zenoh Python | 1.1.1 |
| Zenoh Kotlin (Android) | 1.1.1 |
| Zenoh-Pico (ESP32) | 1.9.0 |
| ESP-IDF | v5.2.6 |

## Third-Party Integration

Any device that speaks Zenoh can join the mesh:

```python
import zenoh

s = zenoh.open(zenoh.Config())

# Publish drive commands
s.put("robot/drive", bytes([100, 100]))

# Subscribe to camera
s.declare_subscriber("robot/camera", lambda sample: print(len(sample.payload)))
```

No IP addresses. No pairing. Just Zenoh.
"""

# --- .gitignore ---
gitignore = """# ESP-IDF
build/
sdkconfig
sdkconfig.old
managed_components/

# Android
*.iml
.gradle/
local.properties
.idea/
build/
captures/
.externalNativeBuild/
.cxx/

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.env
venv/

# OS
.DS_Store
Thumbs.db
