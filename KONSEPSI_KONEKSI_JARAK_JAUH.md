# DOKUMEN TEKNIS ARSITEKTUR KOMUNIKASI & AKSES JARAK JAUH
## SYNTERA (Smart AI-IoT Dehumidification Dryer)
**Program Kreativitas Mahasiswa - Karya Inovatif (PKM-KI) 2026**  
**Universitas Halu Oleo (UHO)**

---

## 1. Ringkasan Eksekutif & Konsep Dasar

Sebagai produk inovatif skala penuh (1:1), mesin pengering daun nilam **SYNTERA** mengintegrasikan sistem fisik kabinet pengering dengan komputasi cerdas berbasis *Internet of Things* (IoT). 

Untuk mewujudkan pemantauan dan kendali **jarak jauh (Remote Access)** tanpa batas geografis (misalnya alat beroperasi di sentra nilam Kabupaten Konawe Selatan dan dipantau dari Kota Kendari / kampus), sistem menerapkan arsitektur **Cloud Deployment**. Server backend Flask di-deploy ke platform cloud **Render.com** sehingga berjalan **24/7** dengan URL publik permanen, tanpa memerlukan laptop yang selalu menyala, IP publik statis, ataupun konfigurasi router yang rumit.

### Model Koneksi: Multi-Alat dengan Identitas Unik

Sistem dirancang untuk mendukung **banyak unit mesin** secara simultan dalam satu platform. Setiap unit mesin pengering memiliki **Device ID** unik (misalnya `SYNTERA-001`, `SYNTERA-002`) yang tertanam di firmware ESP32. Pengguna (petani/operator) mengakses dashboard melalui satu URL yang sama, lalu melakukan **login** dan memilih alat yang ingin dipantau.

Arsitektur multi-alat ini memungkinkan:

* **Skalabilitas** — satu server cloud melayani banyak unit mesin yang tersebar di berbagai lokasi (Konawe Selatan, Kolaka, Kendari, dll.) tanpa perlu deploy server terpisah per alat.
* **Kepemilikan** — setiap petani hanya melihat dan mengontrol alat miliknya sendiri setelah login.
* **Pemantauan terpusat** — admin atau tim SYNTERA dapat melihat status seluruh alat sekaligus dari satu panel.

---

## 2. Diagram Alur Koneksi (Topologi Sistem)

```
                     FASE 1: PROVISIONING JARINGAN
                     ─────────────────────────────
  ┌──────────────────────────────────────────────────────────────┐
  │  KABINET SYNTERA (Fisik 1:1)                                 │
  │                                                              │
  │  ESP32 DOIT DevKit V1  ── Device ID: SYNTERA-001             │
  │  ┌────────────────────────────────────┐                      │
  │  │  WiFiManager Library               │                      │
  │  │  ┌──────────────────────────────┐  │                      │
  │  │  │ 1. Power ON                  │  │                      │
  │  │  │ 2. Cek WiFi tersimpan        │──│── Ada? ──► Langsung  │
  │  │  │ 3. Tidak ada / gagal?        │  │           ke FASE 2  │
  │  │  │    ► Buka Hotspot AP:        │  │                      │
  │  │  │      "SYNTERA-Setup"         │  │                      │
  │  │  └──────────────────────────────┘  │                      │
  │  └────────────────────────────────────┘                      │
  └──────────────────────────────────────────────────────────────┘
                          │
            ┌─────────────┘ (Hotspot Sementara)
            ▼
  ┌──────────────────────────┐
  │  📱 HP Petani / Operator │
  │  Sambung ke SYNTERA-Setup│
  │                          │
  │  ► Captive Portal muncul │     ┌──────────────────────────┐
  │  ► Pilih WiFi sekitar:   │────►│  WiFi Tersedia:          │
  │    - IndiHome_Pak_Ahmad   │     │  ☑ IndiHome_Pak_Ahmad    │
  │    - Hotspot HP Telkomsel │     │  ○ Hotspot_Telkomsel     │
  │  ► Masukkan password      │     │  ○ WiFi_Kantor_Desa      │
  │  ► Tekan "Simpan"        │     └──────────────────────────┘
  └──────────────────────────┘
            │
            ▼
  ESP32 menyimpan kredensial ► Restart ► Terkoneksi WiFi ► Hotspot mati


                     FASE 2: OPERASIONAL REAL-TIME (MULTI-ALAT)
                     ──────────────────────────────────────────

  [ LOKASI A: KONAWE SELATAN ]        [ LOKASI B: KOLAKA ]
  ┌───────────────────────┐            ┌───────────────────────┐
  │  SYNTERA-001          │            │  SYNTERA-002          │
  │  Milik: Pak Ahmad     │            │  Milik: Bu Siti       │
  │  WiFi: IndiHome       │            │  WiFi: Hotspot HP     │
  │  POST /5 detik ───────│────┐  ┌────│─── POST /5 detik     │
  └───────────────────────┘    │  │    └───────────────────────┘
                               │  │
                               ▼  ▼
                      (( INTERNET PUBLIK ))
                               │
                               ▼
  ┌──────────────────────────────────────────────────────────────┐
  │  ☁️  CLOUD SERVER (Render.com - Always On 24/7)              │
  │                                                              │
  │  URL Permanen: https://syntera.onrender.com                  │
  │                                                              │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │  BACKEND SERVER (Flask + Gunicorn)                     │  │
  │  │                                                        │  │
  │  │  ┌──────────────────────────────────────────────────┐  │  │
  │  │  │  DEVICE REGISTRY (Multi-Alat)                    │  │  │
  │  │  │                                                  │  │  │
  │  │  │  SYNTERA-001 ──► { state, logs, owner }          │  │  │
  │  │  │  SYNTERA-002 ──► { state, logs, owner }          │  │  │
  │  │  │  SYNTERA-003 ──► { state, logs, owner }          │  │  │
  │  │  │  ...                                             │  │  │
  │  │  └──────────────────────────────────────────────────┘  │  │
  │  │                                                        │  │
  │  │  POST /api/esp32/telemetry     ◄── + device_id         │  │
  │  │  GET  /api/dashboard/state/<id> ◄── Data per alat      │  │
  │  │  POST /api/dashboard/control/<id> ◄── Kontrol per alat │  │
  │  │  POST /api/auth/login           ◄── Autentikasi user   │  │
  │  │  GET  /api/user/devices         ◄── Daftar alat user   │  │
  │  │                                                        │  │
  │  │  + Logika Histeresis & AI Decision Engine (per alat)   │  │
  │  │  + Proteksi Termal Darurat (DS18B20 > 65°C)           │  │
  │  │  + Deteksi Titik Akhir (Drying Rate ≤ 0.5 g/menit)    │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                                                              │
  │  + Web Dashboard (index.html, app.js, styles.css)            │
  │  + Halaman Login & Pemilihan Alat                            │
  │  + Captive Portal UI (captive_portal.html)                   │
  └──────────────────────────────────────────────────────────────┘
                               ▲
                               │
         ┌─────────────────────┴─────────────────────┐
         │                                           │
         ▼                                           ▼
  ┌────────────────────────┐            ┌────────────────────────┐
  │  📱 HP PAK AHMAD       │            │  💻 LAPTOP JURI PKM    │
  │  (4G Telkomsel)         │            │  (WiFi Kampus UHO)     │
  │                          │            │                        │
  │  Login ► Pilih alat:     │            │  Login (admin) ►       │
  │  ☑ SYNTERA-001 ● Online │            │  Lihat semua alat:     │
  │                          │            │  ☑ SYNTERA-001 ● Online│
  │  ► Dashboard real-time   │            │  ○ SYNTERA-002 ○ Offline│
  │  ► Kontrol alatnya saja  │            │  ○ SYNTERA-003 ● Online│
  └────────────────────────┘            └────────────────────────┘
```

---

## 3. Komponen & Alur Komunikasi

### A. Sisi Perangkat Keras (ESP32) — Provisioning & Telemetri

#### A1. Identitas Perangkat (Device ID)

Setiap unit mesin SYNTERA memiliki **Device ID** unik yang di-hardcode pada firmware ESP32 saat proses produksi:

```cpp
// Identitas unik unit mesin ini (tidak pernah berubah)
const char* deviceId = "SYNTERA-001";
```

Konvensi penamaan:

| Device ID       | Pemilik / Lokasi                    |
|-----------------|-------------------------------------|
| `SYNTERA-001`   | Pak Ahmad — Konawe Selatan          |
| `SYNTERA-002`   | Bu Siti — Kolaka                    |
| `SYNTERA-003`   | Koperasi Nilam — Kendari            |
| `SYNTERA-...`   | *(unit selanjutnya)*                |

Device ID ini menjadi kunci untuk memisahkan data telemetri, log, dan kendali antar unit di server.

#### A2. Penyambungan Jaringan Dinamis (WiFiManager)

Menggunakan pustaka `WiFiManager` (tzapu/WiFiManager) pada firmware ESP32. Mekanisme kerja:

1. **Power ON** — ESP32 menyala dan mencoba menyambung ke WiFi yang tersimpan di memori flash (NVS/EEPROM).
2. **WiFi ditemukan** — Langsung terkoneksi, lanjut ke pengiriman telemetri.
3. **WiFi tidak ditemukan / gagal** — ESP32 otomatis beralih ke **mode Access Point (AP)** dan memancarkan hotspot sementara bernama `SYNTERA-Setup`.
4. **Captive Portal** — Operator menyambungkan HP ke hotspot tersebut. Halaman konfigurasi (`captive_portal.html`) muncul otomatis, menampilkan daftar jaringan WiFi yang terdeteksi di sekitar lokasi.
5. **Pemilihan & Penyimpanan** — Operator memilih WiFi (misalnya IndiHome, hotspot HP, WiFi kantor desa), memasukkan password, lalu menekan "Simpan & Hubungkan".
6. **Koneksi** — ESP32 menyimpan kredensial ke memori flash, melakukan restart, dan terhubung ke WiFi yang dipilih. Hotspot `SYNTERA-Setup` otomatis mati.
7. **Failover Otomatis** — Jika sewaktu-waktu WiFi terputus atau berpindah lokasi, ESP32 otomatis kembali ke mode hotspot `SYNTERA-Setup` agar dapat dikonfigurasi ulang tanpa perlu memprogram ulang firmware.

#### A3. Pengiriman Telemetri (Uplink ke Cloud)

Setiap **5 detik**, ESP32 membaca seluruh sensor dan mengirim data beserta **Device ID** via **HTTP POST** dalam format JSON ke server cloud:

```
POST https://syntera.onrender.com/api/esp32/telemetry
Content-Type: application/json

{
  "device_id": "SYNTERA-001",
  "temp": 37.2,
  "humidity": 52.8,
  "heater_temp": 48.5,
  "weight": 3.42,
  "drying_rate": 1.85
}
```

| Field          | Sumber       | Satuan   | Keterangan                         |
|----------------|--------------|----------|------------------------------------|
| `device_id`    | Firmware     | string   | Identitas unik unit mesin          |
| `temp`         | SHT31-D      | °C       | Suhu ruang kabinet pengering       |
| `humidity`     | SHT31-D      | %RH      | Kelembapan relatif ruang           |
| `heater_temp`  | DS18B20      | °C       | Suhu elemen pemanas (cut-off 65°C) |
| `weight`       | HX711        | kg       | Bobot sampel daun nilam            |
| `drying_rate`  | Kalkulasi    | g/menit  | Laju susut bobot                   |

Server menerima `device_id` dan menyimpan data ke slot state yang sesuai, terpisah dari unit lain.

#### A4. Penerimaan Instruksi Aktuator (Downlink dari Cloud)

Respons dari HTTP POST langsung membawa status kendali relay dari mesin keputusan AI di server, spesifik untuk unit tersebut:

```json
{
  "status": "success",
  "device_id": "SYNTERA-001",
  "is_ai_mode": true,
  "control": {
    "heater": true,
    "fan": true,
    "exhaust": false
  }
}
```

ESP32 segera mengeksekusi logika pin relay fisik sesuai respons tersebut. Setiap unit menerima instruksi yang independen — keputusan AI untuk `SYNTERA-001` tidak mempengaruhi `SYNTERA-002`.

---

### B. Sisi Server Cloud & Mesin Keputusan AI (`app.py`)

#### B1. Platform & Deployment

| Parameter           | Spesifikasi                                    |
|---------------------|------------------------------------------------|
| Platform Hosting    | **Render.com** (Free Tier)                     |
| Runtime             | Python 3.11+ dengan **Gunicorn** WSGI server   |
| URL Permanen        | `https://syntera.onrender.com`                 |
| Auto-Deploy         | Terhubung ke repositori GitHub (auto-deploy saat push) |
| Always Active       | Selama ada ESP32 yang mengirim data, server tidak pernah sleep |

#### B2. Arsitektur Data Multi-Alat (Device Registry)

Server menyimpan state setiap unit mesin secara terpisah menggunakan **Device Registry**:

```
Struktur Data (Konseptual):

devices = {
    "SYNTERA-001": {
        "state": {
            "connection": "ONLINE",
            "current_temp": 37.2,
            "current_humidity": 52.8,
            "heater_state": true,
            "fan_state": true,
            "exhaust_state": false,
            "is_ai_mode": true,
            "last_seen": 1729432800,
            ...
        },
        "logs": [ ... ],
        "owner": "pak_ahmad"
    },
    "SYNTERA-002": {
        "state": { ... },
        "logs": [ ... ],
        "owner": "bu_siti"
    }
}
```

Setiap panggilan API menyertakan atau merujuk pada `device_id` spesifik:

| Endpoint                              | Metode | Fungsi                                         |
|---------------------------------------|--------|-------------------------------------------------|
| `/api/esp32/telemetry`                | POST   | ESP32 kirim data sensor + `device_id`           |
| `/api/dashboard/state/<device_id>`    | GET    | Dashboard ambil data alat tertentu              |
| `/api/dashboard/control/<device_id>`  | POST   | Kontrol manual/mode AI untuk alat tertentu      |
| `/api/auth/login`                     | POST   | Login pengguna (username + password)            |
| `/api/auth/register`                  | POST   | Registrasi pengguna baru                        |
| `/api/user/devices`                   | GET    | Daftar alat milik pengguna yang sedang login    |

#### B3. Sistem Autentikasi & Kepemilikan Alat

Terdapat dua peran pengguna:

| Peran        | Akses                                                       |
|--------------|--------------------------------------------------------------|
| **Petani**   | Login, melihat dan mengontrol alat miliknya saja             |
| **Admin**    | Login, melihat dan mengontrol seluruh alat di semua lokasi   |

Alur autentikasi:

```
1. Buka https://syntera.onrender.com
2. Halaman LOGIN muncul (username + password)
3. Server memvalidasi kredensial
4. Jika berhasil, server mengembalikan token sesi (session/JWT)
5. Dashboard menampilkan daftar alat milik pengguna tersebut
6. Pengguna memilih alat ► masuk ke dashboard real-time alat tersebut
```

#### B4. Logika Histeresis & Proteksi Termal (Per Alat)

Setiap unit mesin menjalankan evaluasi AI secara independen berdasarkan data telemetri masing-masing:

* **Proteksi Darurat:** Jika suhu pemanas DS18B20 $> 65^\circ\text{C}$, pemanas diputus seketika.
* **Titik Akhir Otomatis:** Jika *drying rate* $\le 0.5\text{ g/menit}$ stabil, siklus pengeringan dihentikan otomatis.
* **Target Suhu Presisi:** Menjaga suhu antara $30^\circ\text{C} - 45^\circ\text{C}$ agar senyawa *Patchouli Alcohol* (PA) tidak rusak.
* **Evakuasi Uap Air:** Jika RH $> 60\%$, Exhaust Fan aktif hingga kelembapan turun di bawah $40\%$.

Keputusan AI untuk `SYNTERA-001` (misalnya: heater ON karena suhu < 30°C) tidak mempengaruhi state `SYNTERA-002` (yang mungkin sedang optimal di 38°C).

#### B5. Keunggulan Cloud Deployment vs Tunneling (ngrok/Cloudflare)

| Aspek                    | Tunneling (ngrok)                        | Cloud Deployment (Render.com)             |
|--------------------------|------------------------------------------|-------------------------------------------|
| **Laptop harus menyala?**| ✗ Ya, wajib 24/7                         | ✓ Tidak, server di cloud                  |
| **URL tetap?**           | ✗ Berubah setiap restart (tier gratis)   | ✓ Permanen (`syntera.onrender.com`)       |
| **Banner/halaman blokir**| ✗ Ada (ngrok interstitial page)          | ✓ Tidak ada, langsung tampil dashboard    |
| **Multi-alat?**          | ✗ Sulit, perlu 1 tunnel per alat         | ✓ Satu server melayani semua alat         |
| **Biaya**                | Gratis (terbatas)                        | Gratis (Free Tier Render.com)             |
| **Keandalan**            | Bergantung koneksi laptop                | ✓ Uptime cloud ~99.9%                     |
| **Setup tambahan**       | Install ngrok + jalankan manual          | ✓ Sekali deploy, berjalan otomatis        |

---

### C. Sisi Pengguna (Web Dashboard) — Login, Pilih Alat, Pantau

Alur penggunaan dashboard untuk pengguna akhir:

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  1. HALAMAN LOGIN                                           │
│  ┌───────────────────────────────────┐                      │
│  │  SYNTERA IoT                      │                      │
│  │                                   │                      │
│  │  Username: [pak_ahmad          ]  │                      │
│  │  Password: [••••••••           ]  │                      │
│  │                                   │                      │
│  │  [ MASUK ]                        │                      │
│  └───────────────────────────────────┘                      │
│                     │                                       │
│                     ▼                                       │
│  2. HALAMAN DAFTAR ALAT SAYA                                │
│  ┌───────────────────────────────────┐                      │
│  │  Selamat datang, Pak Ahmad        │                      │
│  │                                   │                      │
│  │  Alat Saya:                       │                      │
│  │  ┌─────────────────────────────┐  │                      │
│  │  │ ● SYNTERA-001    ONLINE     │  │  ◄── Klik untuk      │
│  │  │   Konawe Selatan            │  │      masuk dashboard  │
│  │  └─────────────────────────────┘  │                      │
│  │  ┌─────────────────────────────┐  │                      │
│  │  │ ○ SYNTERA-004    OFFLINE    │  │                      │
│  │  │   Gudang Kendari            │  │                      │
│  │  └─────────────────────────────┘  │                      │
│  └───────────────────────────────────┘                      │
│                     │                                       │
│                     ▼                                       │
│  3. DASHBOARD REAL-TIME (per alat)                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  SYNTERA IoT ─ SYNTERA-001 (Konawe Selatan) ● Online │  │
│  │                                                       │  │
│  │  [Speedometer Suhu] [RH] [Bobot HX711] [Estimasi AI] │  │
│  │  [Grafik Telemetri Real-Time]                         │  │
│  │  [Status & Kendali Aktuator]                          │  │
│  │  [Log Aktivitas & AI Decision Feed]                   │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Detail fungsionalitas:

1. **Login** — Pengguna memasukkan username dan password di `https://syntera.onrender.com`.
2. **Daftar Alat** — Setelah login, sistem menampilkan daftar unit mesin milik pengguna beserta status online/offline masing-masing.
3. **Dashboard Per Alat** — Pengguna memilih satu alat, lalu masuk ke dashboard real-time yang menampilkan data khusus alat tersebut:
   * Speedometer suhu SHT31-D
   * Grafik tren telemetri
   * Timbangan bobot HX711 & laju susut
   * Status 3 aktuator (Heater, Duct Fan, Exhaust Fan)
   * Log keputusan AI
4. **Kontrol Jarak Jauh** — Operator dapat melakukan *override* kendali manual khusus untuk alat yang sedang dilihat.
5. **Polling** — Dashboard melakukan polling otomatis setiap **5 detik** ke `/api/dashboard/state/<device_id>`.

---

### D. Penyimpanan Data (Database PostgreSQL di Render.com)

Untuk mendukung multi-alat dan autentikasi pengguna, sistem memerlukan penyimpanan data **persisten** — bukan in-memory dictionary Python yang hilang setiap kali server restart. Database disimpan di **PostgreSQL** yang disediakan oleh **Render.com** sebagai service terpisah dalam satu platform yang sama.

#### Mengapa PostgreSQL, Bukan SQLite?

| Aspek                    | SQLite                                    | PostgreSQL (Render.com)                  |
|--------------------------|-------------------------------------------|------------------------------------------|
| **Penyimpanan**          | File `.db` di filesystem server           | Service database terpisah                |
| **Data setelah redeploy**| ✗ **Hilang** (Render free = ephemeral FS) | ✓ **Tetap aman**, data persisten         |
| **Cocok untuk cloud**    | ✗ Tidak (data hilang saat restart)        | ✓ Ya, dirancang untuk cloud              |
| **Biaya di Render**      | -                                         | Gratis (Free Tier, 1 GB storage)         |
| **Koneksi dari Flask**   | `sqlite:///local.db`                      | `DATABASE_URL` (otomatis dari Render)    |

#### Arsitektur Database di Render.com

```
Render.com Platform
│
├── 🌐 Web Service: syntera
│   └── Flask + Gunicorn (app.py)
│       └── connect via DATABASE_URL ──────────┐
│                                               │
└── 🗄️ PostgreSQL Database: syntera-db          │
    │                                    ◄──────┘
    ├── tabel: users           (autentikasi & peran pengguna)
    ├── tabel: devices         (registrasi unit mesin & kepemilikan)
    ├── tabel: telemetry_logs  (riwayat data sensor per alat)
    └── tabel: device_state    (state real-time aktuator per alat)
```

Render.com secara otomatis menyediakan environment variable `DATABASE_URL` yang berisi connection string lengkap ke database PostgreSQL. Flask membaca variabel ini untuk terhubung ke database tanpa perlu konfigurasi manual:

```python
import os
DATABASE_URL = os.environ.get('DATABASE_URL')
# Contoh nilai: postgresql://user:pass@host:5432/syntera_db
```

#### Skema Tabel Database

```
┌──────────────────────────────────────────────────────────────────┐
│  TABEL: users                                                    │
│  ──────────────────────────────────────────────────────────────  │
│  id  │ username    │ password_hash │ role    │ name     │ created│
│  1   │ pak_ahmad   │ $2b$12$...    │ petani  │ Ahmad    │ 2026.. │
│  2   │ bu_siti     │ $2b$12$...    │ petani  │ Siti     │ 2026.. │
│  3   │ admin       │ $2b$12$...    │ admin   │ Admin    │ 2026.. │
│                                                                  │
│  * password_hash: bcrypt hash (password tidak pernah disimpan    │
│    dalam bentuk teks biasa)                                      │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  TABEL: devices                                                  │
│  ──────────────────────────────────────────────────────────────  │
│  device_id     │ owner_id │ label            │ location          │
│  SYNTERA-001   │ 1        │ Mesin Kebun      │ Konawe Selatan    │
│  SYNTERA-002   │ 2        │ Mesin Gudang     │ Kolaka            │
│  SYNTERA-003   │ 3        │ Mesin Demo PKM   │ Kendari           │
│                                                                  │
│  * owner_id: foreign key ke tabel users (kepemilikan alat)       │
│  * admin (role=admin) dapat mengakses semua device_id            │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  TABEL: telemetry_logs                                           │
│  ──────────────────────────────────────────────────────────────  │
│  id │ device_id   │ timestamp           │ temp │ rh   │ weight  │
│     │             │                     │      │      │         │
│  1  │ SYNTERA-001 │ 2026-10-20 14:30:05 │ 37.2 │ 52.8 │ 3.42   │
│  2  │ SYNTERA-001 │ 2026-10-20 14:30:10 │ 37.4 │ 52.5 │ 3.41   │
│  3  │ SYNTERA-002 │ 2026-10-20 14:30:07 │ 41.0 │ 44.1 │ 4.10   │
│  ...                                                             │
│                                                                  │
│  * Data masuk setiap 5 detik per alat                            │
│  * Digunakan untuk grafik tren, export CSV, dan analisis AI      │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  TABEL: device_state                                             │
│  ──────────────────────────────────────────────────────────────  │
│  device_id   │ is_ai_mode │ heater │ fan  │ exhaust │ last_seen │
│  SYNTERA-001 │ true       │ true   │ true │ false   │ 2026-10.. │
│  SYNTERA-002 │ true       │ false  │ true │ true    │ 2026-10.. │
│                                                                  │
│  * State real-time aktuator, diperbarui setiap kali ESP32        │
│    mengirim telemetri atau operator mengubah kontrol manual       │
│  * Baris ini yang dibaca oleh dashboard saat polling              │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Panduan Operasional Menjalankan Sistem

### Langkah 1: Deploy Backend ke Render.com (Sekali Saja)

#### 1a. Buat Database PostgreSQL

1. Buka [https://render.com](https://render.com), buat akun gratis.
2. Klik **"New" → "PostgreSQL"**.
3. Konfigurasi:

   | Parameter         | Nilai                |
   |-------------------|----------------------|
   | **Name**          | `syntera-db`         |
   | **Database**      | `syntera_db`         |
   | **Region**        | Singapore (terdekat) |
   | **Instance Type** | Free                 |

4. Klik **"Create Database"**. Setelah aktif, salin nilai **Internal Database URL** (digunakan di langkah berikutnya).

#### 1b. Buat Web Service (Flask)

1. Push seluruh kode proyek ke repositori **GitHub** (berisi `app.py`, `index.html`, `app.js`, `styles.css`, `captive_portal.html`, `requirements.txt`).

2. Di Render, klik **"New" → "Web Service"**.

3. Hubungkan repositori GitHub proyek SYNTERA.

4. Konfigurasi service:

   | Parameter         | Nilai                              |
   |-------------------|------------------------------------|
   | **Name**          | `syntera`                          |
   | **Runtime**       | Python 3                           |
   | **Build Command** | `pip install -r requirements.txt`  |
   | **Start Command** | `gunicorn app:app`                 |
   | **Instance Type** | Free                               |

5. Tambahkan **Environment Variable**:

   | Key              | Value                                                    |
   |------------------|----------------------------------------------------------|
   | `DATABASE_URL`   | *(paste Internal Database URL dari langkah 1a)*          |

6. Klik **"Create Web Service"**. Render akan membangun dan menjalankan server secara otomatis.

7. Setelah deploy selesai, catat URL yang diberikan:
   ```
   https://syntera.onrender.com
   ```

8. Setiap kali melakukan `git push` ke GitHub, Render akan **auto-deploy** versi terbaru. Database PostgreSQL tetap aman dan tidak terpengaruh oleh redeploy.

### Langkah 2: Konfigurasi Firmware ESP32 (Per Unit Mesin)

Pada kode firmware ESP32 (Arduino IDE), setiap unit mesin dikonfigurasi dengan Device ID unik dan URL cloud:

```cpp
// ===== KONFIGURASI PER UNIT MESIN =====
const char* deviceId  = "SYNTERA-001";  // Ubah untuk setiap unit
const char* serverUrl = "https://syntera.onrender.com/api/esp32/telemetry";
```

### Langkah 3: Provisioning WiFi di Lapangan (Setiap Lokasi Baru)

1. **Nyalakan alat** — ESP32 menyala, jika belum pernah tersambung WiFi di lokasi ini, otomatis memancarkan hotspot `SYNTERA-Setup`.
2. **Sambungkan HP** ke WiFi `SYNTERA-Setup`.
3. **Captive Portal muncul** — Pilih jaringan WiFi sekitar (IndiHome, hotspot HP, dll), masukkan password.
4. **Tekan "Simpan & Hubungkan"** — ESP32 restart dan terhubung ke WiFi yang dipilih.
5. **Selesai** — Alat langsung online dan mengirim data ke cloud. Proses ini hanya dilakukan sekali per lokasi; jika alat dimatikan dan dinyalakan kembali di lokasi yang sama, ESP32 langsung tersambung otomatis tanpa perlu konfigurasi ulang.

### Langkah 4: Akses Dashboard dari Mana Saja

1. Buka browser di HP/Laptop, ketik: `https://syntera.onrender.com`
2. **Login** dengan username dan password yang telah didaftarkan.
3. **Pilih alat** dari daftar unit mesin milik pengguna.
4. **Dashboard real-time** tampil — monitoring dan kontrol fungsional skala penuh untuk alat yang dipilih.

---

## 5. Ringkasan Alur Lengkap (End-to-End)

```
┌─────────┐  Hotspot   ┌──────────┐  WiFi     ┌──────────┐  HTTPS     ┌───────────┐
│  ALAT   │────────────►│  HP      │──────────►│  ESP32   │──────────►│  CLOUD    │
│  ON     │ SYNTERA-    │  PETANI  │ IndiHome/ │  Online  │ POST +    │  Render   │
│         │ Setup       │  Config  │ Hotspot   │  Kirim   │ device_id │  .com     │
└─────────┘             └──────────┘           └──────────┘ /5 detik  └─────┬─────┘
                                                                            │
     (sama untuk SYNTERA-002, 003, ...)                                     │
                                                                            │
                                                      ┌────────────────────┘
                                                      │
                                                      ▼
                                            ┌───────────────────┐
                                            │  📱💻 PENGGUNA     │
                                            │                   │
                                            │  1. Login         │
                                            │  2. Pilih alat    │
                                            │  3. Dashboard:    │
                                            │     ► Real-time   │
                                            │     ► Kontrol     │
                                            │     ► Log AI      │
                                            └───────────────────┘
```

---

## 6. Pengembangan Lokal & Testing (Opsional)

Untuk pengembangan dan debugging di jaringan lokal **tanpa cloud**, backend dapat dijalankan langsung di laptop:

```bash
python app.py
```

Server aktif pada `http://127.0.0.1:5000`. ESP32 diarahkan ke IP lokal laptop (misalnya `http://192.168.1.10:5000/api/esp32/telemetry`). Dashboard diakses dari perangkat di jaringan WiFi yang sama.

Untuk testing akses jarak jauh tanpa deploy ke cloud, tunneling tetap bisa digunakan sebagai alternatif sementara:

```bash
ngrok http 5000
# atau
cloudflared tunnel --url http://localhost:5000
```

---
*Dokumen ini disusun untuk melengkapi berkas teknis dan spesifikasi sistem karya inovatif SYNTERA.*
