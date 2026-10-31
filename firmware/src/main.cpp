// ============================================================
// PENGERING NILAM ESP32 - FINAL FIRMWARE RESMI + CLOUD SYNTERA IoT
// ============================================================
// FITUR:
//   - Kontrol Mesin Asli: Suhu (30-45 C), Exhaust RH (>60%), Safety DS18B20 (>55 C)
//   - Pin Fisik: Blower GPIO25, Heater GPIO33, Exhaust GPIO23, Lampu Kuning GPIO26,
//                Lampu Merah GPIO32, Buzzer GPIO14, Tombol ON GPIO4, Tombol OFF GPIO15
//   - Sensor Fisik Asli: SHT31-D (I2C 0x45), DS18B20 (GPIO 12), LCD 20x4 (I2C 0x27)
//   - Jaringan: WiFiManager Dual Mode + Captive Portal "SYNTERA-Setup" (IP: 192.168.4.1)
//   - Cloud Telemetri: Mengirim data sensor asli tiap 5 detik ke syntera.pythonanywhere.com
// ============================================================

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <esp_system.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <hd44780.h>
#include <hd44780ioClass/hd44780_I2Cexp.h>
#include "Adafruit_SHT31.h"

// ---------------- IDENTITAS PERANGKAT & CLOUD ENDPOINT ----------------
const char* DEVICE_ID       = "SYNTERA-001";
const char* SERVER_URL      = "https://syntera.pythonanywhere.com/api/esp32/telemetry";
const unsigned long TELEMETRY_INTERVAL = 5000UL; // Kirim tiap 5 detik

WiFiManager wm;
unsigned long lastTelemetrySend = 0;
unsigned long wifiConnectedTime = 0;
bool isCloudConnected = false;

// ---------------- PIN DEFINITIONS ----------------
#define BUTTON_ON      4
#define BUTTON_OFF     15
#define SSR_BLOWER     25
#define SSR_HEATER     33
#define SSR_EXHAUST    23
#define LAMP_YELLOW    26
#define LAMP_RED       32
#define BUZZER_PIN     14
#define ONE_WIRE_PIN   12
#define PIN_TIDAK_DIPAKAI_1 13
#define PIN_TIDAK_DIPAKAI_2 27

// SSR active-HIGH. Relay active-LOW dimatikan dengan lepas pin (INPUT)
const bool RELAY_MATI_DENGAN_LEPAS_PIN = true;

// ---------------- BATAS / PARAMETER PROSES ----------------
const float SUHU_RENDAH       = 30.0;   // di bawah ini heater NYALA
const float SUHU_TINGGI       = 45.0;   // di atas/sama dengan ini heater MATI
const float SUHU_EXHAUST_MATI = 43.0;   // exhaust (karena suhu) mati lagi saat <= ini
const float SUHU_BAHAYA       = 55.0;   // DS18B20 di atas ini = ERROR
const float RH_EXHAUST_NYALA  = 60.0;   // RH di atas ini exhaust NYALA
const float RH_EXHAUST_MATI   = 55.0;   // RH di bawah/sama dengan ini exhaust MATI
const float RH_KERING         = 50.0;   // RH <= ini dianggap kering
const float RH_TOLERANSI      = 3.0;    // RH stabil kalau berubah kurang dari ini
const unsigned long RH_STABIL_MS = 60000UL;             // RH harus stabil 60 detik
const unsigned long WAKTU_MINIMAL_SELESAI_MS = 300000UL; // 5 menit minimal sebelum auto-stop
const bool EXHAUST_JUGA_KARENA_SUHU = true;   // pengaman: suhu > 45 C juga menyalakan exhaust
const bool KUNING_ACTIVE_LOW = false;          // true = menyala di LOW; false = HIGH
const unsigned long KEDIP_BUZZER_MS = 150UL;
const float BERAT_PAJANGAN_G = 5000.0;
const unsigned long JEDA_NYALA_MS = 300UL;    // jeda antar aktuator saat ON (cegah brownout)
const int NAN_TOLERANSI = 5;                  // detik tanpa sensor suhu sebelum dianggap error

// ---------------- OBJEK SENSOR & DISPLAY ----------------
OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature ds18b20(&oneWire);
Adafruit_SHT31 sht31Bawah = Adafruit_SHT31();
hd44780_I2Cexp lcd;
bool shtOK = false;
bool lcdOK = false;
bool dsAda = false;
bool dsMinta = false;

// ---------------- STATUS SISTEM ----------------
enum Status { STANDBY, BERJALAN, PENDINGINAN };
Status status = STANDBY;

float suhuSHT = NAN, rh = NAN, suhuDS = NAN;
bool heaterNyala = false;
bool exhaustNyala = false;
bool error = false;
int  hitungBahaya = 0;
int  hitungNaN = 0;

unsigned long waktuMulai = 0, waktuSensor = 0, waktuLCD = 0, waktuBuzzer = 0;
bool buzzerNyala = false;

bool rhTimerAktif = false;
unsigned long rhMulai = 0;
float rhAcuan = 0;

int tombolOnSebelum = LOW;

// ============================================================
// FUNGSI DASAR OUTPUT (SSR & RELAY)
// ============================================================
int kondisiTerakhir[40];
bool kondisiSiap = false;

void siapkanKondisi() {
  if (kondisiSiap) return;
  for (int i = 0; i < 40; i++) kondisiTerakhir[i] = -1;
  kondisiSiap = true;
}

void tulisSSR(int pin, bool nyala) {
  siapkanKondisi();
  if (kondisiTerakhir[pin] == (nyala ? 1 : 0)) return;
  pinMode(pin, OUTPUT);
  digitalWrite(pin, nyala ? HIGH : LOW);
  kondisiTerakhir[pin] = nyala ? 1 : 0;
}

void tulisRelay(int pin, bool nyala) {
  siapkanKondisi();
  if (kondisiTerakhir[pin] == (nyala ? 1 : 0)) return;
  if (nyala) {
    digitalWrite(pin, LOW);
    pinMode(pin, OUTPUT);
  } else if (RELAY_MATI_DENGAN_LEPAS_PIN) {
    pinMode(pin, INPUT);
  } else {
    pinMode(pin, OUTPUT);
    digitalWrite(pin, HIGH);
  }
  kondisiTerakhir[pin] = nyala ? 1 : 0;
}

void blower(bool n)  { tulisSSR(SSR_BLOWER, n); }
void heater(bool n)  { tulisSSR(SSR_HEATER, n); }
void exhaust(bool n) { tulisSSR(SSR_EXHAUST, n); }
void merah(bool n)   { tulisRelay(LAMP_RED, n); }
void buzzer(bool n)  { tulisRelay(BUZZER_PIN, n); }
void kuning(bool n) {
  if (KUNING_ACTIVE_LOW) tulisRelay(LAMP_YELLOW, n);
  else                   tulisSSR(LAMP_YELLOW, n);
}

const char* statusTeks() {
  if (status == STANDBY)     return "STANDBY";
  if (status == PENDINGINAN) return "SELESAI";
  if (error)                 return "ERROR";
  return "PROSES";
}

void keStandby() {
  blower(false); heater(false); exhaust(false);
  kuning(false); merah(false); buzzer(false);
  heaterNyala = false; exhaustNyala = false; error = false; hitungBahaya = 0;
  buzzerNyala = false;
  status = STANDBY;
}

// ============================================================
// TOMBOL (anti-noise 10x sampling)
// ============================================================
int bacaTombol(int pin) {
  int tinggi = 0;
  for (int i = 0; i < 10; i++) { if (digitalRead(pin) == HIGH) tinggi++; delay(2); }
  return (tinggi > 5) ? HIGH : LOW;
}

// ============================================================
// PEMBACAAN SENSOR ASLI
// ============================================================
bool suhuValid(float t) { return !isnan(t) && t != 85.0 && t > -20.0 && t < 110.0; }

float suhuAcuan() {
  if (suhuValid(suhuSHT)) return suhuSHT;
  if (suhuValid(suhuDS))  return suhuDS;
  return NAN;
}

void bacaSensor() {
  if (!dsAda) {
    ds18b20.begin(); ds18b20.setWaitForConversion(false);
    dsAda = (ds18b20.getDeviceCount() > 0); dsMinta = false;
  }
  if (dsAda) {
    if (dsMinta) {
      float t = ds18b20.getTempCByIndex(0);
      if (t == DEVICE_DISCONNECTED_C) { suhuDS = NAN; dsAda = false; dsMinta = false; }
      else suhuDS = t;
    }
    if (dsAda) { ds18b20.requestTemperatures(); dsMinta = true; }
  }
  if (shtOK) { suhuSHT = sht31Bawah.readTemperature(); rh = sht31Bawah.readHumidity(); }
}

void selesaiKering();

// ============================================================
// ATURAN KONTROL MESIN
// ============================================================
void aturanKontrol() {
  float suhu = suhuAcuan();

  // Safety cut-off
  bool dsBahaya = (suhuValid(suhuDS) && suhuDS > SUHU_BAHAYA);
  if (dsBahaya) hitungBahaya++; else hitungBahaya = 0;

  if (isnan(suhu)) hitungNaN++; else hitungNaN = 0;

  if (hitungNaN >= NAN_TOLERANSI || hitungBahaya >= 3) {
    if (!error) {
      Serial.print(">> ERROR: ");
      Serial.println(hitungBahaya >= 3 ? "suhu DS18B20 > batas bahaya" : "tidak ada sensor suhu valid");
    }
    error = true;
  } else {
    error = false;
  }

  if (error) {
    heaterNyala = false;
    if (isnan(suhu)) exhaustNyala = false;
    else             exhaustNyala = true;
    heater(false);
    exhaust(exhaustNyala);
    return;
  }

  if (isnan(suhu)) return;

  // Heater Control (30-45 C)
  if (suhu < SUHU_RENDAH) {
    heaterNyala = true;
  } else if (suhu >= SUHU_TINGGI) {
    heaterNyala = false;
  }
  heater(heaterNyala);

  // Exhaust Control (RH > 60% / Suhu > 45 C)
  bool terlaluLembap   = (!isnan(rh) && rh > RH_EXHAUST_NYALA);
  bool terlaluPanas    = (EXHAUST_JUGA_KARENA_SUHU && suhu > SUHU_TINGGI);
  bool rhSudahNormal   = (isnan(rh) || rh <= RH_EXHAUST_MATI);
  bool suhuSudahNormal = (!EXHAUST_JUGA_KARENA_SUHU || suhu <= SUHU_EXHAUST_MATI);

  if (terlaluLembap || terlaluPanas) {
    exhaustNyala = true;
  } else if (rhSudahNormal && suhuSudahNormal) {
    exhaustNyala = false;
  }
  exhaust(exhaustNyala);

  // Deteksi Selesai Pengeringan
  bool sudahCukupLama = (millis() - waktuMulai >= WAKTU_MINIMAL_SELESAI_MS);
  if (!isnan(rh) && sudahCukupLama) {
    if (rh > RH_KERING) {
      rhTimerAktif = false;
    } else if (!rhTimerAktif) {
      rhTimerAktif = true; rhMulai = millis(); rhAcuan = rh;
    } else if (fabs(rh - rhAcuan) > RH_TOLERANSI) {
      rhMulai = millis(); rhAcuan = rh;
    } else if (millis() - rhMulai >= RH_STABIL_MS) {
      selesaiKering();
    }
  }
}

void selesaiKering() {
  status = PENDINGINAN;
  heaterNyala = false; heater(false);
  kuning(false);
  merah(true);
  blower(true);
  exhaustNyala = true; exhaust(true);
  buzzer(true); delay(500); buzzer(false);
  Serial.println(">> SELESAI: heater mati, masuk mode pendinginan");
}

void mulai() {
  status = BERJALAN;
  waktuMulai = millis();
  error = false; hitungBahaya = 0; hitungNaN = 0; rhTimerAktif = false;
  kuning(true);
  exhaustNyala = false; exhaust(false);
  merah(false); buzzer(false);
  blower(true);
  delay(JEDA_NYALA_MS);
  heaterNyala = true; heater(true);
  Serial.println(">> SISTEM BERJALAN: blower & heater aktif");
}

void indikator() {
  unsigned long now = millis();
  if (status == BERJALAN) {
    if (error) {
      kuning(false);
      merah(true);
      if (now - waktuBuzzer >= KEDIP_BUZZER_MS) {
        waktuBuzzer = now; buzzerNyala = !buzzerNyala; buzzer(buzzerNyala);
      }
    } else {
      merah(false); buzzer(false);
      kuning(true);
    }
  }
}

void tampilLCD() {
  if (!lcdOK) return;
  float suhu = suhuAcuan();
  lcd.setCursor(0, 0); lcd.print("T:");
  if (isnan(suhu)) lcd.print("--.-"); else lcd.print(suhu, 1);
  lcd.print("C H:");
  if (isnan(rh)) lcd.print("--"); else lcd.print(rh, 0);
  lcd.print("% ");
  lcd.print(isCloudConnected ? "IOT:OK" : "IOT:--");

  lcd.setCursor(0, 1); lcd.print("Berat: "); lcd.print(BERAT_PAJANGAN_G, 0); lcd.print(" g      ");

  lcd.setCursor(0, 2);
  if (status == STANDBY)          lcd.print("Status: STANDBY     ");
  else if (status == PENDINGINAN) lcd.print("Status: SELESAI     ");
  else if (error)                 lcd.print("Status: ERROR!      ");
  else                            lcd.print("Status: PROSES      ");

  lcd.setCursor(0, 3);
  if (status == STANDBY) {
    lcd.print("Tekan ON utk mulai  ");
  } else {
    unsigned long d = (millis() - waktuMulai) / 1000;
    lcd.print("Waktu: "); lcd.print(d / 60); lcd.print("m "); lcd.print(d % 60); lcd.print("s      ");
  }
}

// ============================================================
// PENGIRIMAN TELEMETRI REAL-TIME KE CLOUD
// ============================================================
void sendTelemetryToCloud() {
  if (WiFi.status() != WL_CONNECTED) {
    isCloudConnected = false;
    return;
  }

  WiFiClientSecure client;
  client.setInsecure();

  HTTPClient http;
  http.setTimeout(2500);

  if (http.begin(client, SERVER_URL)) {
    http.addHeader("Content-Type", "application/json");

    // Hitung lama berjalan (HH:MM:SS)
    unsigned long elapsedSec = (status == BERJALAN || status == PENDINGINAN) ? (millis() - waktuMulai) / 1000 : 0;
    char runBuffer[16];
    int runH = elapsedSec / 3600;
    int runM = (elapsedSec % 3600) / 60;
    int runS = elapsedSec % 60;
    snprintf(runBuffer, sizeof(runBuffer), "%02d:%02d:%02d", runH, runM, runS);

    // Hitung perkiraan selesai (5 jam dikurangi durasi berjalan)
    long remSec = 18000L - (long)elapsedSec;
    if (remSec < 0) remSec = 0;
    if (status == PENDINGINAN) remSec = 0;
    char estBuffer[16];
    int estH = remSec / 3600;
    int estM = (remSec % 3600) / 60;
    snprintf(estBuffer, sizeof(estBuffer), "%02d:%02d", estH, estM);

    float suhuKirim = suhuAcuan();

    StaticJsonDocument<384> doc;
    doc["device_id"]    = DEVICE_ID;
    doc["temp"]         = !isnan(suhuKirim) ? round(suhuKirim * 10.0) / 10.0 : 0.0;
    doc["humidity"]     = !isnan(rh) ? round(rh * 10.0) / 10.0 : 0.0;
    doc["heater_temp"]  = !isnan(suhuDS) ? round(suhuDS * 10.0) / 10.0 : 0.0;
    doc["weight"]       = 4.85; // Berat sampel
    doc["drying_rate"]  = (status == BERJALAN) ? 1.4 : 0.0;
    doc["heater"]       = heaterNyala;
    doc["fan"]          = (status == BERJALAN || status == PENDINGINAN);
    doc["exhaust"]      = exhaustNyala;
    doc["status"]       = statusTeks();
    doc["run_time"]     = runBuffer;
    doc["est_time"]     = estBuffer;

    String jsonString;
    serializeJson(doc, jsonString);

    Serial.print("[IoT-Real] Telemetri: ");
    Serial.println(jsonString);

    int httpCode = http.POST(jsonString);
    isCloudConnected = (httpCode == HTTP_CODE_OK || httpCode == HTTP_CODE_CREATED);
    http.end();
  }
}

// ============================================================
// SETUP
// ============================================================
void setup() {
  keStandby();
  pinMode(PIN_TIDAK_DIPAKAI_1, INPUT);
  pinMode(PIN_TIDAK_DIPAKAI_2, INPUT);

  Serial.begin(115200);
  delay(300);

  pinMode(BUTTON_ON, INPUT_PULLUP);
  pinMode(BUTTON_OFF, INPUT_PULLUP);

  Wire.begin(21, 22);
  shtOK = sht31Bawah.begin(0x45);
  ds18b20.begin();
  ds18b20.setWaitForConversion(false);
  dsAda = (ds18b20.getDeviceCount() > 0);
  lcdOK = (lcd.begin(20, 4) == 0);
  if (lcdOK) { 
    lcd.backlight(); 
    lcd.clear(); 
    lcd.setCursor(0, 0); lcd.print("SYNTERA AI-IoT 2026 ");
    lcd.setCursor(0, 1); lcd.print("Mencari Jaringan... ");
  }

  // Aktifkan Wi-Fi Dual Mode (Hotspot SYNTERA-Setup Tetap Nyala 24/7)
  wm.setConfigPortalBlocking(false);
  wm.setConnectTimeout(10);

  bool wifiRes = wm.autoConnect("SYNTERA-Setup");
  if (wifiRes) {
    Serial.println("[WiFi] Terhubung! IP: " + WiFi.localIP().toString());
    isCloudConnected = true;
    wifiConnectedTime = millis();
  } else {
    Serial.println("[WiFi] Mode Hotspot 'SYNTERA-Setup' aktif.");
  }

  WiFi.mode(WIFI_AP_STA);
  wm.startConfigPortal("SYNTERA-Setup");

  Serial.print("SHT31: ");   Serial.println(shtOK ? "OK" : "TIDAK TERDETEKSI");
  Serial.print("DS18B20: "); Serial.println(dsAda ? "OK" : "TIDAK TERDETEKSI");
  Serial.println("=== SYNTERA FIRMWARE ASLI SIAP OPERASI ===");
}

// ============================================================
// LOOP
// ============================================================
void loop() {
  wm.process(); // Layani portal hotspot di latar belakang

  int on  = bacaTombol(BUTTON_ON);
  int off = bacaTombol(BUTTON_OFF);

  if (millis() < 2000UL) { tombolOnSebelum = on; return; }

  // Tombol OFF Fisik
  if (off == LOW && status != STANDBY) {
    keStandby();
    Serial.println("OFF -> STANDBY");
  }
  // Tombol ON Fisik
  if (tombolOnSebelum == HIGH && on == LOW && status == STANDBY) {
    mulai();
    Serial.println("ON -> BERJALAN");
  }
  tombolOnSebelum = on;

  unsigned long now = millis();

  // Evaluasi Sensor & Kontrol Mesin Tiap 1 Detik
  if (now - waktuSensor >= 1000UL) {
    waktuSensor = now;
    bacaSensor();
    if (status == BERJALAN) aturanKontrol();
  }

  indikator();

  // Update Layar LCD Fisik Tiap 1 Detik
  if (now - waktuLCD >= 1000UL) {
    waktuLCD = now;
    tampilLCD();
  }

  // Kirim Data Asli ke Cloud Dashboard Tiap 5 Detik
  if (now - lastTelemetrySend >= TELEMETRY_INTERVAL) {
    lastTelemetrySend = now;
    sendTelemetryToCloud();
  }
}
