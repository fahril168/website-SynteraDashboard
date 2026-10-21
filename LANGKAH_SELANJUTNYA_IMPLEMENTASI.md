# RENCANA AKSI & PANDUAN IMPLEMENTASI SISTEM MULTI-DEVICE
## SYNTERA (Smart AI-IoT Dehumidification Dryer)
**Program Kreativitas Mahasiswa - Karya Inovatif (PKM-KI) 2026**
**Universitas Halu Oleo (UHO)**

---

## 1. Pendahuluan

Dokumen ini merinci langkah konkret teknis (action plan & implementation roadmap) untuk merealisasikan arsitektur cloud multi-alat (*multi-device*) dan autentikasi terpusat sesuai dengan spesifikasi di `KONSEPSI_KONEKSI_JARAK_JAUH.md`. 

Sistem bertransisi dari penanganan *single-device in-memory* menjadi sistem *production-ready* terhubung ke database **PostgreSQL** — baik di lingkungan pengembangan lokal maupun di cloud Render.com. Database yang sama digunakan di semua tahap agar tidak ada perbedaan perilaku antara dev dan production.

---

## 2. Roadmap Implementasi Bertahap

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TAHAPAN EKSEKUSI UTAMA                          │
├────────────────────────────────────────────────────────────────────────┤
│ 1. PONDASI DATABASE & MODEL DATA                                       │
│    └── Integrasi SQLAlchemy & skema Users, Devices, Logs, DeviceState │
│ 2. REFAKTORISASI BACKEND FLASK (app.py)                                │
│    └── Endpoint Auth, API Device Registry, Telemetri Multi-Device      │
│ 3. PENGEMBANGAN ANTARMUKA PENGGUNA (FRONTEND)                          │
│    └── login.html, devices.html, integrasi dashboard (device-aware)    │
│ 4. PEMBARUAN FIRMWARE ESP32                                            │
│    └── Payload JSON beridentitas device_id & WiFiManager setup         │
│ 5. PENGUJIAN LOKAL & DEPLOYMENT CLOUD (Render.com)                     │
│    └── Persiapan requirements.txt, environment variables, live deploy  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Rincian Teknis Langkah Demi Langkah

### TAHAP 1: Dependensi & Model Database (SQLAlchemy)

#### 1.1 Penambahan Pustaka (`requirements.txt`)
Pustaka berikut ditambahkan untuk mendukung konektivitas database dan keamanan:
```txt
flask>=3.0.0
flask-cors>=4.0.0
gunicorn>=21.2.0
flask-sqlalchemy>=3.1.0
psycopg2-binary>=2.9.9
werkzeug>=3.0.0
```

#### 1.2 Skema Tabel & Relasi
* **User**: `id`, `username`, `password_hash`, `role` (`petani` / `admin`), `full_name`, `created_at`.
* **Device**: `device_id` (PK, string), `owner_id` (FK ke `User.id`), `label`, `location`, `created_at`.
* **DeviceState**: `device_id` (PK/FK), `is_ai_mode`, `heater_state`, `fan_state`, `exhaust_state`, `current_temp`, `current_humidity`, `current_weight`, `current_drying_rate`, `heater_temp`, `last_seen`, `connection_status`.
* **TelemetryLog**: `id` (PK), `device_id` (FK), `timestamp`, `temp`, `humidity`, `weight`, `heater_temp`, `drying_rate`, `status_class`, `action_summary`.

---

### TAHAP 2: Refaktorisasi Backend (`app.py`)

#### 2.1 Konfigurasi Database PostgreSQL (Dev & Production Seragam)
Baik di lokal maupun di cloud, sistem menggunakan **PostgreSQL** sebagai satu-satunya database. Ini menghilangkan risiko perbedaan perilaku antara environment:

```python
import os
database_url = os.environ.get('DATABASE_URL', 'postgresql://localhost:5432/syntera_dev')
if database_url.startswith("postgres://"):
    # Penyesuaian skema URI untuk SQLAlchemy modern
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
```

**Setup PostgreSQL lokal (sekali saja):**
1. Install PostgreSQL di laptop.
2. Buat database dev:
   ```bash
   psql -U postgres -c "CREATE DATABASE syntera_dev;"
   ```
3. Set environment variable (opsional, jika tidak di-set maka Flask otomatis pakai `postgresql://localhost:5432/syntera_dev`):
   ```bash
   export DATABASE_URL=postgresql://postgres:password@localhost:5432/syntera_dev
   ```

#### 2.2 Endpoint REST API yang Diimplementasikan
1. **Autentikasi & Pengguna**:
   * `POST /api/auth/login`: Menerima username & password, mengembalikan session/cookie status & user role.
   * `POST /api/auth/logout`: Membersihkan session pengguna.
   * `GET  /api/auth/me`: Mengembalikan data profil user yang sedang aktif.
   * `GET  /api/user/devices`: Mengembalikan daftar mesin yang dimiliki (atau seluruh mesin jika admin).
2. **Telemetri Perangkat Keras (ESP32 Uplink/Downlink)**:
   * `POST /api/esp32/telemetry`:
     * Menerima payload: `{ "device_id": "SYNTERA-001", "temp": ..., "humidity": ..., ... }`.
     * Menjalankan evaluasi AI histeresis terisolasi khusus mesin tersebut.
     * Mengupdate record `DeviceState` terkait dan mencatat ke `TelemetryLog`.
     * Mengembalikan status kendali aktuator spesifik untuk mesin tersebut.
3. **Dashboard Monitoring & Kendali Jarak Jauh**:
   * `GET  /api/dashboard/state/<device_id>`: Mengambil snapshot telemetri dan log terbaru alat tertentu (dengan verifikasi hak akses user).
   * `POST /api/dashboard/control/<device_id>`: Mengubah toggle aktuator manual atau beralih moda AI khusus untuk alat yang dipilih.

#### 2.3 Auto-Seeding Data Awal
Saat pertama kali dijalankan, server membuat tabel secara otomatis (`db.create_all()`) dan membuat akun admin serta unit mesin contoh (`SYNTERA-001`) jika database masih kosong.

---

### TAHAP 3: Pengembangan Frontend

#### 3.1 Halaman Baru yang Dibuat
1. **`login.html`**: Form masuk bersih, responsif, dan aman dengan brand SYNTERA.
2. **`devices.html`**: Halaman portal daftar perangkat (Device Selector).
   * Menampilkan kartu untuk tiap unit mesin (`SYNTERA-001`, dsb).
   * Menampilkan badge indikator *ONLINE / OFFLINE* per mesin berdasarkan `last_seen`.
   * Tombol "Masuk Dashboard" yang mengarahkan ke `index.html?device=SYNTERA-001`.

#### 3.2 Modifikasi `index.html` & `app.js`
* Dashboard membaca parameter query string URL (`?device=SYNTERA-001`).
* Menampilkan informasi unit aktif di header (misal: "Unit: SYNTERA-001 - Konawe Selatan").
* Tombol "Ganti Alat" untuk kembali ke `devices.html`.
* Polling data diarahkan ke `/api/dashboard/state/<device_id>`.
* Pengiriman kontrol diarahkan ke `/api/dashboard/control/<device_id>`.

---

### TAHAP 4: Standarisasi Firmware ESP32

Setiap unit ESP32 ditanamkan kode identitas yang seragam:
```cpp
// Konfigurasi Unik Mesin
const char* DEVICE_ID = "SYNTERA-001";
const char* SERVER_URL = "https://syntera.onrender.com/api/esp32/telemetry";

// Pembentukan Payload
String jsonPayload = "{";
jsonPayload += "\"device_id\":\"" + String(DEVICE_ID) + "\",";
jsonPayload += "\"temp\":" + String(t) + ",";
jsonPayload += "\"humidity\":" + String(h) + ",";
jsonPayload += "\"heater_temp\":" + String(ht) + ",";
jsonPayload += "\"weight\":" + String(w) + ",";
jsonPayload += "\"drying_rate\":" + String(dr);
jsonPayload += "}";
```

---

### TAHAP 5: Checklist Pengujian & Deployment

- [ ] **Uji Lokal (Dev Mode — PostgreSQL Lokal)**:
  - Pastikan PostgreSQL berjalan di laptop dan database `syntera_dev` sudah dibuat.
  - Jalankan `python app.py` (otomatis inisialisasi tabel dan seed data awal).
  - Coba login menggunakan akun admin default.
  - Simulasi POST telemetri dari curl/Postman dengan payload `device_id: SYNTERA-001`.
  - Pastikan dashboard merefleksikan perubahan suhu, kelembapan, dan relay.
- [ ] **Deploy Cloud (Render.com — PostgreSQL Cloud)**:
  - Buat database PostgreSQL di Render (lihat `KONSEPSI_KONEKSI_JARAK_JAUH.md` Langkah 1a).
  - Tambahkan service Web `syntera` dan pasang environment variable `DATABASE_URL` (Internal Database URL dari Render PostgreSQL).
  - Trigger deployment via Git push.
  - Verifikasi akses live di `https://syntera.onrender.com`.
  - Konfirmasi bahwa data tetap aman setelah redeploy.

---
*Dokumen ini merupakan panduan kerja teknis pelengkap dokumen arsitektur utama SYNTERA.*
