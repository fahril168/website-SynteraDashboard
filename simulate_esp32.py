"""
SYNTERA - ESP32 Telemetry Simulator
Script untuk menguji dashboard dan server tanpa ESP32 fisik.
Mengirim telemetri berkala (default setiap 5 detik) dengan data sensor yang bergerak dinamis.

Penggunaan:
    python simulate_esp32.py [SERVER_URL] [DEVICE_ID]

Contoh:
    python simulate_esp32.py http://localhost:5001 SYNTERA-001
    python simulate_esp32.py https://syntera.onrender.com SYNTERA-001
"""

import sys
import time
import json
import random
import urllib.request
import urllib.error

DEFAULT_SERVER = "http://localhost:5001"
DEFAULT_DEVICE = "SYNTERA-001"

server_base = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SERVER
device_id = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DEVICE

endpoint = f"{server_base.rstrip('/')}/api/esp32/telemetry"

print("=" * 60)
print(f"SYNTERA IoT - ESP32 Telemetry Simulator")
print(f"Target Server : {endpoint}")
print(f"Device ID     : {device_id}")
print("Interval      : 5 detik")
print("Tekan CTRL+C untuk berhenti")
print("=" * 60)

# Initial state variables
temp = 36.5
humidity = 58.0
weight = 4.85
drying_rate = 1.6
heater_temp = 45.0

step = 0

try:
    while True:
        step += 1

        # Simulate physics: temperature oscillates slightly, humidity drops, weight decreases
        temp += random.uniform(-0.4, 0.4)
        temp = max(30.0, min(44.0, temp))

        humidity += random.uniform(-0.6, 0.3)
        humidity = max(38.0, min(65.0, humidity))

        weight -= random.uniform(0.002, 0.008)
        weight = max(1.2, weight)

        drying_rate = max(0.2, drying_rate - random.uniform(0.01, 0.03))
        heater_temp = temp + random.uniform(5.0, 10.0)

        payload = {
            "device_id": device_id,
            "temp": round(temp, 1),
            "humidity": round(humidity, 1),
            "heater_temp": round(heater_temp, 1),
            "weight": round(weight, 2),
            "drying_rate": round(drying_rate, 2)
        }

        data_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            endpoint,
            data=data_bytes,
            headers={'Content-Type': 'application/json'}
        )

        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                resp_json = json.loads(response.read().decode('utf-8'))
                ctrl = resp_json.get('control', {})
                print(
                    f"[{time.strftime('%H:%M:%S')}] Step #{step:03d} | "
                    f"Suhu: {payload['temp']}°C | RH: {payload['humidity']}% | Bobot: {payload['weight']}kg | "
                    f"Heater: {'ON' if ctrl.get('heater') else 'OFF'} | "
                    f"Fan: {'ON' if ctrl.get('fan') else 'OFF'} | "
                    f"Exhaust: {'ON' if ctrl.get('exhaust') else 'OFF'}"
                )
        except urllib.error.URLError as e:
            print(f"[{time.strftime('%H:%M:%S')}] Gagal mengirim telemetri: {e}")

        time.sleep(5)

except KeyboardInterrupt:
    print("\nSimulator dihentikan.")
