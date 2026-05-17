from flask import Flask, render_template_string, request, Response, jsonify
import cv2
import numpy as np
import socket
import time
import threading
import zenoh
import json 

# --- ESP32 UDP RELAY CONFIG ---
ESP32_IP = "192.168.137.137"
ESP32_PORT = 4210
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

app = Flask(__name__)

# Global variables for the 3 vision feeds
latest_frames = {
    "rgb": None,
    "opencv": None,
    "depth": None
}

telemetry_data = {
    "steering_cmd": 0.0, "throttle_cmd": 0.0, "goStop_cmd": 0,
    "fps": 0.0, "yolo_latency": 0, "depth_latency": 0,
    "phone_temp": 0.0, "ram_usage": 0
}

# Advanced F1-Style Dashboard
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Edge AI Telemetry | Pit Wall</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;700&display=swap" rel="stylesheet">
    <style>
        body { background-color: #0b0c10; color: #ffffff; font-family: 'Rajdhani', sans-serif; margin: 0; padding: 20px; overflow-x: hidden; }
        .header { text-align: center; text-transform: uppercase; letter-spacing: 4px; font-size: 24px; color: #4facfe; margin-bottom: 20px; text-shadow: 0px 0px 10px rgba(79, 172, 254, 0.5); }
        .dashboard-container { display: flex; flex-direction: column; gap: 20px; max-width: 1400px; margin: 0 auto; }
        .top-row { display: flex; justify-content: space-between; gap: 20px; height: 450px; }
        .panel { background: #14161a; border: 1px solid #2a2d34; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); display: flex; flex-direction: column; position: relative; }
        
        /* New Vision Cluster Grid */
        .vision-cluster { flex: 3; display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; background: transparent; border: none; box-shadow: none; }
        .video-panel { padding: 10px; border-top: 3px solid #4facfe; align-items: center; justify-content: center; background: #14161a; border-radius: 8px; position: relative; display: flex; flex-direction: column;}
        .video-panel img { width: 100%; height: 100%; object-fit: contain; border-radius: 4px; background: #000; }
        
        .steering-panel { flex: 1; border-top: 3px solid #ffcc00; align-items: center; justify-content: center; }
        .data-label { position: absolute; top: 15px; left: 20px; font-size: 14px; color: #8892b0; text-transform: uppercase; letter-spacing: 2px; z-index: 10; }
        .steering-graphic { width: 150px; height: 150px; border: 8px dashed #4facfe; border-radius: 50%; position: relative; transition: transform 0.1s ease-out; margin-top: 20px; box-shadow: 0px 0px 20px rgba(79, 172, 254, 0.2); }
        .steering-graphic::before { content: ''; position: absolute; top: 10px; left: 50%; transform: translateX(-50%); width: 6px; height: 25px; background: #ffcc00; border-radius: 3px; }
        .steering-value { font-size: 50px; font-weight: 700; margin-top: 15px; text-shadow: 0px 0px 10px rgba(255,255,255,0.3); }
        .graph-panel { height: 300px; padding: 20px; border-top: 3px solid #00ff66; }
        .diagnostics-panel { border-top: 3px solid #ffcc00; padding: 35px 20px 20px 20px; }
        
        /* Adjusted grid to perfectly fit 5 items instead of 7 */
        .diag-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 15px; width: 100%; }
        .diag-item { background: #1e2128; padding: 15px; border-radius: 6px; text-align: center; }
        .diag-title { font-size: 12px; color: #8892b0; text-transform: uppercase; margin-bottom: 5px; }
        .diag-val { font-size: 26px; font-weight: 700; color: #00ff66; }
        .diag-val.warn { color: #ffcc00; }
        .diag-val.danger { color: #ff0055; }
        .diag-val.info { color: #4facfe; }
    </style>
</head>
<body>
    <div class="header">PitWall Dash</div>
    <div class="dashboard-container">
        <div class="top-row">
            
            <div class="vision-cluster">
                <div class="video-panel">
                    <div class="data-label">Raw RGB</div>
                    <img id="stream_rgb" src="/video_feed/rgb" />
                </div>
                <div class="video-panel" style="border-top-color: #00ff66;">
                    <div class="data-label">OpenCV / YOLO</div>
                    <img id="stream_opencv" src="/video_feed/opencv" />
                </div>
                <div class="video-panel" style="border-top-color: #ff0055;">
                    <div class="data-label">MonoDepth</div>
                    <img id="stream_depth" src="/video_feed/depth" />
                </div>
            </div>

            <div class="panel steering-panel">
                <div class="data-label">Steering Angle</div>
                <div class="steering-graphic" id="steering_wheel"></div>
                <div class="steering-value" id="steering_val">0&deg;</div>
            </div>
        </div>
        <div class="panel graph-panel">
            <div class="data-label">Pedal Intensity (0 - 100%)</div>
            <canvas id="telemetryChart"></canvas>
        </div>
        <div class="panel diagnostics-panel">
            <div class="data-label">Edge Node Diagnostics</div>
            <div class="diag-grid">
                <div class="diag-item"><div class="diag-title">Vision FPS</div><div class="diag-val" id="val_fps">0.0</div></div>
                <div class="diag-item"><div class="diag-title">YOLO Latency</div><div class="diag-val" id="val_yolo">0 ms</div></div>
                <div class="diag-item"><div class="diag-title">Depth Latency</div><div class="diag-val" id="val_depthlat">0 ms</div></div>
                <div class="diag-item"><div class="diag-title">CPU Temp</div><div class="diag-val" id="val_temp">0 &deg;C</div></div>
                <div class="diag-item"><div class="diag-title">RAM Usage</div><div class="diag-val" id="val_ram">0 MB</div></div>
            </div>
        </div>
    </div>
    <script>
        const ctx = document.getElementById('telemetryChart').getContext('2d');
        const telemetryChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [], 
                datasets: [
                    { label: 'Throttle Intensity (%)', borderColor: '#00ff66', backgroundColor: 'rgba(0, 255, 102, 0.1)', borderWidth: 3, pointRadius: 0, data: [], fill: true, tension: 0.1 },
                    { label: 'Brake/Reverse Intensity (%)', borderColor: '#ff0055', backgroundColor: 'rgba(255, 0, 85, 0.1)', borderWidth: 3, pointRadius: 0, data: [], fill: true, tension: 0.1 }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false, animation: false,
                scales: { x: { display: false }, y: { min: 0, max: 100, grid: { color: '#2a2d34' }, ticks: { color: '#8892b0' } } },
                plugins: { legend: { position: 'top', align: 'end', labels: { color: '#fff' } } }
            }
        });
        const maxDataPoints = 25; 
        setInterval(() => {
            fetch('/telemetry')
            .then(response => response.json())
            .then(data => {
                const rawSteer = Number(data.steering_cmd ?? 0);
                const rawThrottle = Number(data.throttle_cmd ?? 0);
                const steerDeg = (rawSteer * 45).toFixed(0);
                let forwardPercent = 0; let reversePercent = 0;
                if (rawThrottle > 0) { forwardPercent = (rawThrottle / 127.0) * 100; } 
                else if (rawThrottle < 0) { reversePercent = (Math.abs(rawThrottle) / 127.0) * 100; }
                forwardPercent = Math.max(0, Math.min(100, forwardPercent));
                reversePercent = Math.max(0, Math.min(100, reversePercent));
                document.getElementById('steering_val').innerText = steerDeg + "°";
                document.getElementById('steering_wheel').style.transform = `rotate(${steerDeg}deg)`;
                document.getElementById('val_fps').innerText = parseFloat(data.fps || 0).toFixed(1);
                document.getElementById('val_yolo').innerText = (data.yolo_latency || 0) + " ms";
                document.getElementById('val_depthlat').innerText = (data.depth_latency || 0) + " ms";
                const tempEl = document.getElementById('val_temp');
                tempEl.innerText = parseFloat(data.phone_temp || 0).toFixed(1) + " °C";
                tempEl.className = "diag-val " + (data.phone_temp > 42 ? "danger" : (data.phone_temp > 38 ? "warn" : ""));
                document.getElementById('val_ram').innerText = (data.ram_usage || 0) + " MB";
                const now = new Date().toISOString();
                telemetryChart.data.labels.push(now);
                telemetryChart.data.datasets[0].data.push(forwardPercent.toFixed(1));
                telemetryChart.data.datasets[1].data.push(reversePercent.toFixed(1));
                if (telemetryChart.data.labels.length > maxDataPoints) {
                    telemetryChart.data.labels.shift();
                    telemetryChart.data.datasets[0].data.shift();
                    telemetryChart.data.datasets[1].data.shift();
                }
                telemetryChart.update();
            })
            .catch(err => console.error("Telemetry Error:", err));
        }, 200);
    </script>
</body>
</html>
"""

# --- ZENOH SUBSCRIBER LOGIC ---
def zenoh_listener():
    print("[Zenoh] Connecting to session...")
    config = zenoh.Config()
    config.insert_json5("mode", "'peer'")
    session = zenoh.open(config)
    print(f"[Zenoh] Connected. ZID: {session.zid()}")

    # A generic callback generator for the 3 different vision streams
    def make_cam_cb(feed_name):
        def cb(sample):
            global latest_frames
            try:
                nparr = np.frombuffer(sample.payload.to_bytes(), np.uint8)
                decoded = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if decoded is not None:
                    # Rotate the depth feed 90 degrees counter-clockwise (to the left)
                    if feed_name == "depth":
                        decoded = cv2.rotate(decoded, cv2.ROTATE_90_COUNTERCLOCKWISE)
                    latest_frames[feed_name] = decoded
            except Exception as e:
                print(f"Cam decode error on {feed_name}: {e}")
        return cb

    def telemetry_cb(sample):
        global telemetry_data
        try:
            data_str = sample.payload.to_string()
            data_json = json.loads(data_str)
            telemetry_data.update(data_json)
        except Exception as e:
            print(f"Telemetry decode error: {e}")

    def drive_cb(sample):
        global telemetry_data
        try:
            payload = sample.payload.to_bytes()
            if len(payload) >= 2:
                left = int.from_bytes(payload[0:1], byteorder='little', signed=True)
                right = int.from_bytes(payload[1:2], byteorder='little', signed=True)
                
                msg = f"{left},{right}".encode('utf-8')
                udp_sock.sendto(msg, (ESP32_IP, ESP32_PORT))

                telemetry_data["throttle_cmd"] = (left + right) / 2.0
                telemetry_data["steering_cmd"] = (right - left) / 255.0
                
        except Exception as e:
            print(f"Drive relay error: {e}")

    # Declare subscribers for the new topics
    sub_rgb = session.declare_subscriber("robot/camera/rgb", make_cam_cb("rgb"))
    sub_cv = session.declare_subscriber("robot/camera/opencv", make_cam_cb("opencv"))
    sub_depth = session.declare_subscriber("robot/camera/depth", make_cam_cb("depth"))
    
    sub_drive = session.declare_subscriber("robot/drive", drive_cb)
    sub_tele = session.declare_subscriber("robot/telemetry", telemetry_cb) 

    while True:
        time.sleep(1)

threading.Thread(target=zenoh_listener, daemon=True).start()

# --- FLASK WEB ROUTES ---
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/telemetry')
def telemetry():
    return jsonify(telemetry_data)

def generate_frames(feed_name):
    global latest_frames
    
    blank_image = np.zeros((240, 320, 3), np.uint8)
    cv2.putText(blank_image, "WAITING...", (80, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    ret, blank_buffer = cv2.imencode('.jpg', blank_image)
    blank_bytes = blank_buffer.tobytes()

    while True:
        frame_data = latest_frames.get(feed_name)
        if frame_data is not None:
            ret, buffer = cv2.imencode('.jpg', frame_data)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.05) 
        else:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + blank_bytes + b'\r\n')
            time.sleep(0.5)  

# Dynamic route to handle all 3 video feeds
@app.route('/video_feed/<feed_name>')
def video_feed(feed_name):
    if feed_name not in latest_frames:
        return "Invalid feed", 404
    return Response(generate_frames(feed_name), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
