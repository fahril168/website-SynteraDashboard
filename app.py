"""
SYNTERA - Smart AI-IoT Dehumidification Dryer System
Flask Backend Server with Multi-Device Support, Authentication & AI Decision Engine

PKM-KI 2026 - Universitas Halu Oleo (UHO)
"""

from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
from functools import wraps
import time
import os

# =============================================================================
# APP & DATABASE CONFIGURATION
# =============================================================================

app = Flask(__name__, static_folder='.', template_folder='.')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'syntera-dev-secret-key-2026')

# Database: PostgreSQL untuk production, SQLite fallback untuk dev lokal tanpa PostgreSQL
database_url = os.environ.get('DATABASE_URL', '')
if not database_url:
    # Dev lokal: coba PostgreSQL, fallback ke SQLite jika tidak tersedia
    try:
        import psycopg2
        conn = psycopg2.connect('postgresql://postgres:postgres@localhost:5432/syntera_dev')
        conn.close()
        database_url = 'postgresql://postgres:postgres@localhost:5432/syntera_dev'
    except Exception:
        database_url = 'sqlite:///syntera_dev.db'
        print("[DEV] PostgreSQL tidak tersedia, menggunakan SQLite lokal (syntera_dev.db)")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
CORS(app, supports_credentials=True)

# =============================================================================
# DATABASE MODELS
# =============================================================================

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='petani')  # 'petani' or 'admin'
    full_name = db.Column(db.String(120), nullable=False, default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    devices = db.relationship('Device', backref='owner', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'full_name': self.full_name
        }


class Device(db.Model):
    __tablename__ = 'devices'
    device_id = db.Column(db.String(40), primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    label = db.Column(db.String(120), nullable=False, default='Mesin SYNTERA')
    location = db.Column(db.String(200), nullable=False, default='')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    state = db.relationship('DeviceState', backref='device', uselist=False, lazy=True,
                            cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'device_id': self.device_id,
            'owner_id': self.owner_id,
            'label': self.label,
            'location': self.location,
        }


class DeviceState(db.Model):
    __tablename__ = 'device_state'
    device_id = db.Column(db.String(40), db.ForeignKey('devices.device_id'), primary_key=True)

    # Sensor readings
    current_temp = db.Column(db.Float, nullable=True)
    current_humidity = db.Column(db.Float, nullable=True)
    current_weight = db.Column(db.Float, nullable=True)
    current_drying_rate = db.Column(db.Float, nullable=True)
    heater_temp = db.Column(db.Float, nullable=True)
    run_time = db.Column(db.String(20), default='00:00:00')
    est_time = db.Column(db.String(20), default='--:--')
    machine_status = db.Column(db.String(20), default='STANDBY') # STANDBY, PROSES, SELESAI, ERROR

    # Actuator states
    is_ai_mode = db.Column(db.Boolean, default=True)
    heater_state = db.Column(db.Boolean, default=False)
    fan_state = db.Column(db.Boolean, default=False)
    exhaust_state = db.Column(db.Boolean, default=False)

    # Connection
    connection_status = db.Column(db.String(20), default='OFFLINE')
    last_seen = db.Column(db.Float, nullable=True)

    # AI diagnosis (stored as individual fields)
    ai_status_class = db.Column(db.String(30), default='STANDBY')
    ai_status_title = db.Column(db.String(200), default='STATUS: STANDBY')
    ai_status_desc = db.Column(db.Text, default='Menunggu transmisi data telemetri pertama dari sensor ESP32...')
    ai_confidence = db.Column(db.Float, default=0.0)
    ai_action_summary = db.Column(db.String(200), default='Sistem siap menerima data telemetri')

    def to_state_dict(self):
        """Return state dict in the same format the old single-device system_state used."""
        # Auto-detect offline: no data for > 10 seconds
        if self.last_seen and (time.time() - self.last_seen > 10):
            self.connection_status = 'OFFLINE'

        return {
            'is_system_on': True,
            'connection': self.connection_status,
            'machine_status': self.machine_status if self.connection_status == 'ONLINE' else 'STANDBY',
            'is_ai_mode': self.is_ai_mode,
            'current_temp': self.current_temp,
            'current_humidity': self.current_humidity,
            'current_weight': self.current_weight,
            'current_drying_rate': self.current_drying_rate,
            'heater_temp': self.heater_temp,
            'heater_state': self.heater_state,
            'fan_state': self.fan_state,
            'exhaust_state': self.exhaust_state,
            'last_seen': self.last_seen,
            'run_time': self.run_time if self.connection_status == 'ONLINE' else '00:00:00',
            'est_time': self.est_time if self.connection_status == 'ONLINE' else '--:--',
            'ai_diagnosis': {
                'status_class': self.ai_status_class,
                'status_title': self.ai_status_title,
                'status_desc': self.ai_status_desc,
                'confidence': self.ai_confidence,
                'action_summary': self.ai_action_summary,
            }
        }


class TelemetryLog(db.Model):
    __tablename__ = 'telemetry_logs'
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(40), db.ForeignKey('devices.device_id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    timestamp_str = db.Column(db.String(20))
    temp = db.Column(db.Float)
    humidity = db.Column(db.Float)
    weight = db.Column(db.Float, nullable=True)
    heater_temp = db.Column(db.Float, nullable=True)
    drying_rate = db.Column(db.Float, nullable=True)
    status_class = db.Column(db.String(30))
    action_summary = db.Column(db.String(200))

    def to_dict(self):
        return {
            'timestamp': self.timestamp_str or self.timestamp.strftime('%H:%M:%S'),
            'source': 'ESP32_AI',
            'temp': self.temp,
            'humidity': self.humidity,
            'weight': self.weight,
            'status_class': self.status_class,
            'action': self.action_summary,
        }


# =============================================================================
# AI DECISION ENGINE (unchanged logic, extracted for per-device use)
# =============================================================================

def predict_ai_condition(temp, rh, heater_temp=None, drying_rate=None):
    """
    Logika Kendali Histeresis Adaptif & AI Sesuai Laporan PKM-KI:
    - Target Suhu: 30-45 C (Heater ON saat <30, OFF saat >45)
    - Target Kelembapan: 40-60% RH (Exhaust Fan ON saat >60% hingga <40%)
    - Proteksi Darurat: DS18B20 > 65 C memutus pemanas seketika
    - Titik Henti AI: drying rate <= 0.5 g/menit
    """
    if heater_temp is not None and heater_temp > 65.0:
        return {
            "status_class": "EMERGENCY",
            "status_title": "PROTEKSI TERMAL DARURAT (>65°C)",
            "status_desc": f"Suhu elemen pemanas mencapai {heater_temp:.1f}°C (>65°C). Pemanas diputus otomatis demi keamanan minyak nilam.",
            "confidence": 100.0,
            "recommended_heater": False,
            "recommended_fan": True,
            "recommended_exhaust": True,
            "action_summary": "PROTEKSI AKTIF: Heater OFF, Fan & Exhaust Maksimal"
        }

    if drying_rate is not None and 0 < drying_rate <= 0.5:
        return {
            "status_class": "OPTIMAL",
            "status_title": "PENGERINGAN SELESAI",
            "status_desc": "Daun nilam sudah kering optimal. Pemanas dimatikan, mesin mendinginkan daun.",
            "confidence": 99.4,
            "recommended_heater": False,
            "recommended_fan": True,
            "recommended_exhaust": False,
            "action_summary": "Selesai: Pemanas Mati, Pendinginan Aktif"
        }

    if rh > 60.0:
        return {
            "status_class": "DEHUMIDIFYING",
            "status_title": "MEMBUANG UAP LEMBAP",
            "status_desc": f"Udara cukup lembap ({rh:.1f}%). Kipas buang menyala otomatis mengeluarkan uap air.",
            "confidence": 98.5,
            "recommended_heater": temp < 35.0,
            "recommended_fan": True,
            "recommended_exhaust": True,
            "action_summary": "Kipas Buang Menyala"
        }

    elif temp < 30.0:
        return {
            "status_class": "HEATING",
            "status_title": "MENAIKKAN SUHU RUANG",
            "status_desc": f"Suhu masih agak dingin ({temp:.1f}°C). Pemanas menyala otomatis menghangatkan daun.",
            "confidence": 97.2,
            "recommended_heater": True,
            "recommended_fan": True,
            "recommended_exhaust": rh > 55.0,
            "action_summary": "Pemanas Menyala Menghangatkan Ruang"
        }

    elif temp > 45.0:
        return {
            "status_class": "HEATING",
            "status_title": "SUHU TERLALU TINGGI (> 45°C)",
            "status_desc": f"Suhu mencapai {temp:.1f}°C. Pemanas dimatikan sementara agar minyak nilam tidak rusak.",
            "confidence": 99.0,
            "recommended_heater": False,
            "recommended_fan": True,
            "recommended_exhaust": True,
            "action_summary": "Pemanas Dimatikan Demi Keamanan"
        }

    else:
        return {
            "status_class": "OPTIMAL",
            "status_title": "KONDISI SANGAT BAGUS (AMAN)",
            "status_desc": f"Suhu ({temp:.1f}°C) dan kelembapan ({rh:.1f}%) berada di batas aman pengeringan nilam.",
            "confidence": 98.8,
            "recommended_heater": temp < 38.0,
            "recommended_fan": True,
            "recommended_exhaust": rh > 50.0,
            "action_summary": "Suhu & udara stabil terjaga"
        }


# =============================================================================
# AUTH HELPERS
# =============================================================================

def login_required(f):
    """Decorator to protect routes that need authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login diperlukan'}), 401
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    """Get the currently logged-in user from session."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    return db.session.get(User, user_id)


def user_can_access_device(user, device_id):
    """Check if a user has permission to access a device."""
    if user.role == 'admin':
        return True
    device = db.session.get(Device, device_id)
    return device is not None and device.owner_id == user.id


# =============================================================================
# SEED DATA
# =============================================================================

def seed_initial_data():
    """Create default admin and demo device if database is empty."""
    if User.query.count() == 0:
        admin = User(
            username='admin',
            role='admin',
            full_name='Administrator SYNTERA'
        )
        admin.set_password('admin123')
        db.session.add(admin)

        petani = User(
            username='pak_ahmad',
            role='petani',
            full_name='Pak Ahmad'
        )
        petani.set_password('petani123')
        db.session.add(petani)
        db.session.flush()

        device = Device(
            device_id='SYNTERA-001',
            owner_id=petani.id,
            label='Mesin Kebun Nilam',
            location='Konawe Selatan'
        )
        db.session.add(device)

        device_state = DeviceState(device_id='SYNTERA-001')
        db.session.add(device_state)

        db.session.commit()
        print("[SEED] Data awal berhasil dibuat: admin, pak_ahmad, SYNTERA-001")


# =============================================================================
# STATIC FILE ROUTES (must be AFTER all /api/ routes to avoid catch-all conflict)
# These are registered at the bottom, see end of file.
# =============================================================================


# =============================================================================
# AUTH API
# =============================================================================

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Username dan password diperlukan'}), 400

    user = User.query.filter_by(username=data['username']).first()
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Username atau password salah'}), 401

    session['user_id'] = user.id
    return jsonify({'status': 'success', 'user': user.to_dict()}), 200


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.pop('user_id', None)
    return jsonify({'status': 'logged_out'}), 200


@app.route('/api/auth/me', methods=['GET'])
@login_required
def api_me():
    user = get_current_user()
    return jsonify({'user': user.to_dict()}), 200


# =============================================================================
# USER DEVICE LIST API
# =============================================================================

@app.route('/api/user/devices', methods=['GET'])
@login_required
def api_user_devices():
    user = get_current_user()
    if user.role == 'admin':
        devices = Device.query.all()
    else:
        devices = Device.query.filter_by(owner_id=user.id).all()

    result = []
    for d in devices:
        info = d.to_dict()
        if d.state:
            info['connection'] = d.state.connection_status
            if d.state.last_seen and (time.time() - d.state.last_seen > 10):
                info['connection'] = 'OFFLINE'
        else:
            info['connection'] = 'OFFLINE'
        info['owner_name'] = d.owner.full_name if d.owner else ''
        result.append(info)

    return jsonify({'devices': result}), 200


# =============================================================================
# ESP32 TELEMETRY API (no auth — ESP32 sends device_id in payload)
# =============================================================================

@app.route('/api/esp32/telemetry', methods=['POST'])
def handle_esp32_telemetry():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON payload received"}), 400

    device_id = data.get('device_id')
    if not device_id:
        return jsonify({"error": "device_id is required"}), 400

    try:
        # Lookup device
        device = db.session.get(Device, device_id)
        if not device:
            return jsonify({"error": f"Device '{device_id}' not registered"}), 404

        # Ensure DeviceState exists
        state = device.state
        if not state:
            state = DeviceState(device_id=device_id)
            db.session.add(state)

        # Parse sensor data
        temp = float(data.get('temp', 0))
        hum = float(data.get('humidity', 0))
        heater_t = float(data.get('heater_temp', 0)) if 'heater_temp' in data else None
        weight = float(data.get('weight', 0)) if 'weight' in data else None
        drying_rate = float(data.get('drying_rate', 0)) if 'drying_rate' in data else None

        # Update device state
        state.current_temp = temp
        state.current_humidity = hum
        if heater_t is not None:
            state.heater_temp = heater_t
        if weight is not None:
            state.current_weight = weight
        if drying_rate is not None:
            state.current_drying_rate = drying_rate

        # Baca status fisik aktuator asli dari ESP32
        if 'heater' in data:
            state.heater_state = bool(data['heater'])
        if 'fan' in data:
            state.fan_state = bool(data['fan'])
        if 'exhaust' in data:
            state.exhaust_state = bool(data['exhaust'])
        
        try:
            if 'run_time' in data:
                state.run_time = str(data['run_time'])
            if 'est_time' in data:
                state.est_time = str(data['est_time'])
            if 'status' in data:
                state.machine_status = str(data['status'])
        except Exception:
            pass

        state.connection_status = 'ONLINE'
        state.last_seen = time.time()

        # AI evaluation for this specific device
        ai_res = predict_ai_condition(temp, hum, heater_t, drying_rate)

        state.ai_status_class = ai_res['status_class']
        state.ai_status_title = ai_res['status_title']
        state.ai_status_desc = ai_res['status_desc']
        state.ai_confidence = ai_res['confidence']
        state.ai_action_summary = ai_res['action_summary']

        # Jika alat dalam posisi STANDBY (belum ditekan ON atau sudah ditekan OFF):
        # Paksa semua aktuator MATI di server agar dashboard tidak salah menampilkan ON
        if state.machine_status == 'STANDBY':
            state.heater_state = False
            state.fan_state = False
            state.exhaust_state = False
        elif state.is_ai_mode and 'heater' not in data:
            state.heater_state = ai_res['recommended_heater']
            state.fan_state = ai_res['recommended_fan']
            state.exhaust_state = ai_res['recommended_exhaust']

        # Log telemetry
        try:
            log = TelemetryLog(
                device_id=device_id,
                timestamp_str=time.strftime("%H:%M:%S"),
                temp=temp,
                humidity=hum,
                weight=weight,
                heater_temp=heater_t,
                drying_rate=drying_rate,
                status_class=ai_res['status_class'],
                action_summary=ai_res['action_summary']
            )
            db.session.add(log)

            # Trim old logs (keep last 100 per device)
            log_count = TelemetryLog.query.filter_by(device_id=device_id).count()
            if log_count > 100:
                oldest = TelemetryLog.query.filter_by(device_id=device_id)\
                    .order_by(TelemetryLog.id.asc()).limit(log_count - 100).all()
                for old in oldest:
                    db.session.delete(old)
        except Exception:
            pass

        db.session.commit()

        # Response back to ESP32
        return jsonify({
            "status": "success",
            "device_id": device_id,
            "is_ai_mode": state.is_ai_mode,
            "control": {
                "heater": state.heater_state,
                "fan": state.fan_state,
                "exhaust": state.exhaust_state
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        import traceback
        tb = traceback.format_exc()
        print("[CRITICAL TELEMETRY ERROR]", tb)
        return jsonify({"error": str(e), "traceback": tb}), 500


# =============================================================================
# DASHBOARD STATE API (per device)
# =============================================================================

@app.route('/api/dashboard/state/<device_id>', methods=['GET'])
@login_required
def get_dashboard_state(device_id):
    user = get_current_user()
    if not user_can_access_device(user, device_id):
        return jsonify({'error': 'Akses ditolak'}), 403

    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'error': 'Device tidak ditemukan'}), 404

    state = device.state
    if not state:
        state = DeviceState(device_id=device_id)
        db.session.add(state)
        db.session.commit()

    # Get recent logs
    logs = TelemetryLog.query.filter_by(device_id=device_id)\
        .order_by(TelemetryLog.id.desc()).limit(15).all()

    return jsonify({
        "device": device.to_dict(),
        "system_state": state.to_state_dict(),
        "logs": [l.to_dict() for l in logs]
    }), 200


# Legacy endpoint compatibility (redirects to first device or returns empty)
@app.route('/api/dashboard/state', methods=['GET'])
def get_dashboard_state_legacy():
    # For backward compatibility: if logged in, return first device
    user = get_current_user()
    if user:
        if user.role == 'admin':
            device = Device.query.first()
        else:
            device = Device.query.filter_by(owner_id=user.id).first()
        if device and device.state:
            logs = TelemetryLog.query.filter_by(device_id=device.device_id)\
                .order_by(TelemetryLog.id.desc()).limit(15).all()
            return jsonify({
                "device": device.to_dict(),
                "system_state": device.state.to_state_dict(),
                "logs": [l.to_dict() for l in logs]
            }), 200

    # Return empty standby state
    return jsonify({
        "system_state": {
            "is_system_on": True,
            "connection": "OFFLINE",
            "is_ai_mode": True,
            "current_temp": None,
            "current_humidity": None,
            "current_weight": None,
            "current_drying_rate": None,
            "heater_temp": None,
            "heater_state": False,
            "fan_state": False,
            "exhaust_state": False,
            "last_seen": None,
            "ai_diagnosis": {
                "status_class": "STANDBY",
                "status_title": "STATUS: STANDBY",
                "status_desc": "Menunggu transmisi data telemetri pertama dari sensor ESP32...",
                "confidence": 0.0,
                "action_summary": "Sistem siap menerima data telemetri"
            }
        },
        "logs": []
    }), 200


# =============================================================================
# DASHBOARD CONTROL API (per device)
# =============================================================================

@app.route('/api/dashboard/control/<device_id>', methods=['POST'])
@login_required
def update_dashboard_control(device_id):
    user = get_current_user()
    if not user_can_access_device(user, device_id):
        return jsonify({'error': 'Akses ditolak'}), 403

    device = db.session.get(Device, device_id)
    if not device:
        return jsonify({'error': 'Device tidak ditemukan'}), 404

    state = device.state
    if not state:
        return jsonify({'error': 'Device state tidak ditemukan'}), 404

    data = request.get_json()
    if 'is_ai_mode' in data:
        state.is_ai_mode = bool(data['is_ai_mode'])
    if 'heater' in data:
        state.heater_state = bool(data['heater'])
    if 'fan' in data:
        state.fan_state = bool(data['fan'])
    if 'exhaust' in data:
        state.exhaust_state = bool(data['exhaust'])
    if 'peltier' in data:
        state.exhaust_state = bool(data['peltier'])

    db.session.commit()

    return jsonify({
        "status": "updated",
        "system_state": state.to_state_dict()
    }), 200


# Legacy control endpoint
@app.route('/api/dashboard/control', methods=['POST'])
@login_required
def update_dashboard_control_legacy():
    user = get_current_user()
    if user.role == 'admin':
        device = Device.query.first()
    else:
        device = Device.query.filter_by(owner_id=user.id).first()

    if not device or not device.state:
        return jsonify({'error': 'Tidak ada device'}), 404

    return update_dashboard_control(device.device_id)


# =============================================================================
# STATIC FILE ROUTES
# Explicit routes for each static file to avoid catch-all conflicts with API
# =============================================================================

@app.route('/')
def serve_index():
    return send_from_directory('.', 'login.html')

@app.route('/login.html')
def serve_login():
    return send_from_directory('.', 'login.html')

@app.route('/devices.html')
def serve_devices():
    return send_from_directory('.', 'devices.html')

@app.route('/index.html')
def serve_dashboard():
    return send_from_directory('.', 'index.html')

@app.route('/captive_portal.html')
def serve_captive():
    return send_from_directory('.', 'captive_portal.html')

@app.route('/app.js')
def serve_appjs():
    return send_from_directory('.', 'app.js')

@app.route('/styles.css')
def serve_css():
    return send_from_directory('.', 'styles.css')


@app.route('/api/fix-db-schema-now', methods=['GET'])
def fix_db_schema_now():
    """Endpoint darurat untuk memastikan kolom ada tanpa perlu akses terminal sqlite."""
    msg = []
    with db.engine.connect() as conn:
        for col, col_type, default_val in [
            ('machine_status', 'VARCHAR(20)', "'STANDBY'"),
            ('run_time', 'VARCHAR(20)', "'00:00:00'"),
            ('est_time', 'VARCHAR(20)', "'--:--'")
        ]:
            try:
                conn.execute(db.text(f"ALTER TABLE device_state ADD COLUMN {col} {col_type} DEFAULT {default_val}"))
                conn.commit()
                msg.append(f"Added {col}")
            except Exception as e:
                msg.append(f"{col} error: {e}")
    return jsonify({"status": "done", "details": msg}), 200


# =============================================================================
# STARTUP
# =============================================================================

with app.app_context():
    db.create_all()
    # Migrasi otomatis jika kolom baru belum ada di tabel SQLite
    try:
        with db.engine.connect() as conn:
            conn.execute(db.text("ALTER TABLE device_state ADD COLUMN run_time VARCHAR(20) DEFAULT '00:00:00'"))
            conn.commit()
    except Exception:
        pass
    try:
        with db.engine.connect() as conn:
            conn.execute(db.text("ALTER TABLE device_state ADD COLUMN est_time VARCHAR(20) DEFAULT '--:--'"))
            conn.commit()
    except Exception:
        pass
    seed_initial_data()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"SYNTERA Flask IoT Server running on port {port}")
    print(f"Database: {database_url[:50]}...")
    print(f"Default login: admin/admin123 atau pak_ahmad/petani123")
    app.run(host='0.0.0.0', port=port, debug=False)
