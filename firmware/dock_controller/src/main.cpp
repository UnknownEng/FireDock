// =============================================================================================
// Drone dock controller (ESP32)
//   covers  : 2x worm-gear motor, open/closed limit switches, timeout
//   pushers : 4x NEMA17 / TMC2209 (X pair + Y pair), homed to PARK on endstops, centre the drone
//   charge  : relay -> 25.2 V CC/CV charger -> deck contact pads; INA226 + DS18B20 supervision
//   API     : HTTP on Wi-Fi, every request needs header  X-Token: <API_TOKEN>
//       GET  /status                      JSON state
//       POST /launch                      stop charging, open covers, park pushers -> ready for take-off
//       POST /dock                        centre the drone, close covers, start charging (after landing)
//       POST /open  /close                covers only
//       POST /center  /release            pushers to the drone / back to park
//       POST /charge/start  /charge/stop
//       POST /home                        re-home the pushers
//       POST /stop                        emergency stop (motors + charging off) -> ERROR until /reset
//       POST /reset
// Safety interlocks: covers never move while the pushers move and vice versa; charging only with the
// pushers centred; any fault (timeout, over-temperature, over-voltage, e-stop) switches everything off.
// =============================================================================================
#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <Wire.h>
#include <AccelStepper.h>
#include <TMCStepper.h>
#include <ArduinoJson.h>
#include <INA226.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Adafruit_MCP23X17.h>
#include "config.h"

// ------------------------------------------------------------------ hardware objects
Adafruit_MCP23X17 mcp;
INA226 ina(INA226_ADDR);
OneWire oneWire(PIN_ONEWIRE);
DallasTemperature temps(&oneWire);
WebServer http(80);

TMC2209Stepper drv[4] = {TMC2209Stepper(&Serial2, RSENSE, 0), TMC2209Stepper(&Serial2, RSENSE, 1),
                         TMC2209Stepper(&Serial2, RSENSE, 2), TMC2209Stepper(&Serial2, RSENSE, 3)};
AccelStepper mot[4] = {AccelStepper(AccelStepper::DRIVER, PIN_X1_STEP, PIN_X_DIR),
                       AccelStepper(AccelStepper::DRIVER, PIN_X2_STEP, PIN_X_DIR),
                       AccelStepper(AccelStepper::DRIVER, PIN_Y1_STEP, PIN_Y_DIR),
                       AccelStepper(AccelStepper::DRIVER, PIN_Y2_STEP, PIN_Y_DIR)};
const uint8_t HOME_PIN[4] = {HOME_X1, HOME_X2, HOME_Y1, HOME_Y2};

// ------------------------------------------------------------------ state
enum class Cover { UNKNOWN, OPEN, CLOSED, OPENING, CLOSING };
enum class Pusher { UNKNOWN, HOMING, PARKED, CENTRED, MOVING_IN, MOVING_OUT };
enum class Charge { OFF, ON, DONE };
enum class Step { NONE, STOP_CHARGE, OPEN, CLOSE, PARK, CENTRE, CHARGE };

struct {
  Cover cover = Cover::UNKNOWN;
  Pusher pusher = Pusher::UNKNOWN;
  Charge charge = Charge::OFF;
  bool error = false;
  String errorText;
  uint32_t coverStart = 0, chargeStart = 0, lowCurrentSince = 0;
  bool coverRDone = false, coverLDone = false;
  float volts = 0, amps = 0, tempPad = NAN, tempBay = NAN;
  Step queue[6];
  uint8_t qHead = 0, qLen = 0;
} S;

const char* coverName(Cover c) {
  switch (c) { case Cover::OPEN: return "open"; case Cover::CLOSED: return "closed"; case Cover::OPENING: return "opening";
               case Cover::CLOSING: return "closing"; default: return "unknown"; }
}
const char* pusherName(Pusher p) {
  switch (p) { case Pusher::HOMING: return "homing"; case Pusher::PARKED: return "parked"; case Pusher::CENTRED: return "centred";
               case Pusher::MOVING_IN: return "moving_in"; case Pusher::MOVING_OUT: return "moving_out"; default: return "unknown"; }
}
const char* chargeName(Charge c) { return c == Charge::ON ? "charging" : c == Charge::DONE ? "full" : "off"; }

bool coverBusy() { return S.cover == Cover::OPENING || S.cover == Cover::CLOSING; }
bool pusherBusy() { return S.pusher == Pusher::HOMING || S.pusher == Pusher::MOVING_IN || S.pusher == Pusher::MOVING_OUT; }
bool busy() { return coverBusy() || pusherBusy() || S.qLen > 0; }
bool sw(uint8_t pin) { return mcp.digitalRead(pin) == LOW; }     // switch pressed

// ------------------------------------------------------------------ outputs off / faults
void coverMotor(int r, int l) {           // -1 close, 0 stop, +1 open
  digitalWrite(PIN_COVER_R_IN1, r > 0); digitalWrite(PIN_COVER_R_IN2, r < 0);
  digitalWrite(PIN_COVER_L_IN1, l > 0); digitalWrite(PIN_COVER_L_IN2, l < 0);
}
void chargeOff() { digitalWrite(PIN_CHARGE_EN, LOW); if (S.charge == Charge::ON) S.charge = Charge::OFF; }
void allStop() {
  coverMotor(0, 0);
  for (auto& m : mot) { m.setSpeed(0); m.moveTo(m.currentPosition()); }
  digitalWrite(PIN_STEPPER_EN, HIGH);
  chargeOff();
  S.qLen = 0;
}
void fault(const String& why) {
  allStop();
  S.error = true; S.errorText = why;
  if (coverBusy()) S.cover = Cover::UNKNOWN;
  if (pusherBusy()) S.pusher = Pusher::UNKNOWN;
  Serial.println("FAULT: " + why);
}

// ------------------------------------------------------------------ covers
void coversStart(bool open) {
  if (open && sw(COVER_R_OPEN) && sw(COVER_L_OPEN)) { S.cover = Cover::OPEN; return; }
  if (!open && sw(COVER_R_CLOSED) && sw(COVER_L_CLOSED)) { S.cover = Cover::CLOSED; return; }
  S.cover = open ? Cover::OPENING : Cover::CLOSING;
  S.coverRDone = S.coverLDone = false;
  S.coverStart = millis();
  coverMotor(open ? 1 : -1, open ? 1 : -1);
}
void coversUpdate() {
  if (!coverBusy()) return;
  bool open = S.cover == Cover::OPENING;
  if (!S.coverRDone && sw(open ? COVER_R_OPEN : COVER_R_CLOSED)) S.coverRDone = true;
  if (!S.coverLDone && sw(open ? COVER_L_OPEN : COVER_L_CLOSED)) S.coverLDone = true;
  int d = open ? 1 : -1;
  coverMotor(S.coverRDone ? 0 : d, S.coverLDone ? 0 : d);
  if (S.coverRDone && S.coverLDone) S.cover = open ? Cover::OPEN : Cover::CLOSED;
  else if (millis() - S.coverStart > COVER_TIMEOUT_MS) fault(open ? "cover open timeout" : "cover close timeout");
}

// ------------------------------------------------------------------ pushers
long mmFromPark(float centreLine) { return lroundf((PUSHER_PARK_MM - centreLine) * STEPS_PER_MM); }

void pusherCurrent(uint16_t mA) { for (auto& d : drv) d.rms_current(mA); }

void pushersHome() {
  digitalWrite(PIN_STEPPER_EN, LOW);
  pusherCurrent(MOVE_CURRENT_MA);
  for (auto& m : mot) m.setSpeed(-HOMING_SPEED * STEPS_PER_MM);       // toward park
  S.pusher = Pusher::HOMING;
  S.coverStart = millis();
}
void pushersMove(bool in) {
  digitalWrite(PIN_STEPPER_EN, LOW);
  pusherCurrent(in ? PUSH_CURRENT_MA : MOVE_CURRENT_MA);
  long x = in ? mmFromPark(PUSHER_X_CENTRED - PUSHER_SQUEEZE) : 0;
  long y = in ? mmFromPark(PUSHER_Y_CENTRED - PUSHER_SQUEEZE) : 0;
  mot[0].moveTo(x); mot[1].moveTo(x); mot[2].moveTo(y); mot[3].moveTo(y);
  S.pusher = in ? Pusher::MOVING_IN : Pusher::MOVING_OUT;
}
void pushersUpdate() {
  if (S.pusher == Pusher::HOMING) {
    bool all = true;
    for (int i = 0; i < 4; i++) {
      if (sw(HOME_PIN[i])) { mot[i].setSpeed(0); mot[i].setCurrentPosition(0); }
      else { mot[i].runSpeed(); all = false; }
    }
    if (all) { S.pusher = Pusher::PARKED; }
    else if (millis() - S.coverStart > 20000) fault("pusher homing timeout (endstop?)");
    return;
  }
  if (S.pusher == Pusher::MOVING_IN || S.pusher == Pusher::MOVING_OUT) {
    bool running = false;
    for (auto& m : mot) running |= m.run();
    if (!running) {
      S.pusher = (S.pusher == Pusher::MOVING_IN) ? Pusher::CENTRED : Pusher::PARKED;
      if (S.pusher == Pusher::PARKED) digitalWrite(PIN_STEPPER_EN, HIGH);   // parked: drivers off (held by belts)
      // centred: drivers stay on at low current so the drone is held while the covers move
    }
  }
}

// ------------------------------------------------------------------ charging
void readSensors() {
  static uint32_t last = 0;
  if (millis() - last < 1000) return;
  last = millis();
  S.volts = ina.getBusVoltage();
  S.amps = ina.getCurrent();
  temps.requestTemperatures();
  S.tempPad = temps.getTempCByIndex(0);
  S.tempBay = temps.getTempCByIndex(1);
}
bool chargeStart() {
  if (S.pusher != Pusher::CENTRED) return false;
  digitalWrite(PIN_CHARGE_EN, HIGH);
  S.charge = Charge::ON;
  S.chargeStart = millis();
  S.lowCurrentSince = 0;
  return true;
}
void chargeUpdate() {
  if (S.charge != Charge::ON) return;
  uint32_t t = millis() - S.chargeStart;
  float hot = max(isnan(S.tempPad) ? 0.0f : S.tempPad, isnan(S.tempBay) ? 0.0f : S.tempBay);
  if (hot > CHARGE_MAX_C) { fault("over-temperature while charging"); return; }
  if (S.volts > CHARGE_MAX_V) { fault("charge voltage too high"); return; }
  if (t > CHARGE_MAX_MS) { fault("charge timeout"); return; }
  if (t > 15000 && t < 20000 && S.amps < CHARGE_NO_CONTACT_A) { chargeOff(); S.errorText = "no charge current: feet not on the pads?"; return; }
  if (t > 60000 && S.amps < CHARGE_DONE_A) {
    if (!S.lowCurrentSince) S.lowCurrentSince = millis();
    if (millis() - S.lowCurrentSince > 30000) { digitalWrite(PIN_CHARGE_EN, LOW); S.charge = Charge::DONE; }
  } else S.lowCurrentSince = 0;
}

// ------------------------------------------------------------------ command queue (macros)
void enqueue(std::initializer_list<Step> steps) {
  S.qHead = 0; S.qLen = 0;
  for (Step s : steps) S.queue[S.qLen++] = s;
}
void queueUpdate() {
  if (S.qLen == 0 || S.error || coverBusy() || pusherBusy()) return;
  if (S.qHead >= S.qLen) { S.qLen = 0; return; }
  Step s = S.queue[S.qHead++];
  switch (s) {
    case Step::STOP_CHARGE: chargeOff(); break;
    case Step::OPEN: coversStart(true); break;
    case Step::CLOSE: coversStart(false); break;
    case Step::PARK: chargeOff(); pushersMove(false); break;
    case Step::CENTRE: pushersMove(true); break;
    case Step::CHARGE: if (!chargeStart()) S.errorText = "charge refused: pushers not centred"; break;
    default: break;
  }
}

// ------------------------------------------------------------------ HTTP API
bool authorised() {
  if (http.header("X-Token") == API_TOKEN) return true;
  http.send(401, "application/json", "{\"error\":\"bad token\"}");
  return false;
}
void sendStatus(int code = 200) {
  JsonDocument j;
  j["cover"] = coverName(S.cover);
  j["pusher"] = pusherName(S.pusher);
  j["charge"] = chargeName(S.charge);
  j["busy"] = busy();
  j["error"] = S.error;
  j["message"] = S.errorText;
  j["charge_v"] = S.volts;
  j["charge_a"] = S.amps;
  j["temp_pad_c"] = S.tempPad;
  j["temp_bay_c"] = S.tempBay;
  j["ready_for_takeoff"] = S.cover == Cover::OPEN && S.pusher == Pusher::PARKED && !busy() && !S.error;
  j["uptime_s"] = millis() / 1000;
  String out;
  serializeJson(j, out);
  http.send(code, "application/json", out);
}
void command(const char* path, std::function<bool()> fn) {
  http.on(path, HTTP_POST, [fn]() {
    if (!authorised()) return;
    if (S.error) { http.send(409, "application/json", "{\"error\":\"in ERROR state, POST /reset first\"}"); return; }
    if (busy()) { http.send(409, "application/json", "{\"error\":\"busy\"}"); return; }
    if (!fn()) { http.send(409, "application/json", "{\"error\":\"not allowed in this state\"}"); return; }
    sendStatus(202);
  });
}
void setupHttp() {
  const char* hdrs[] = {"X-Token"};
  http.collectHeaders(hdrs, 1);
  http.on("/status", HTTP_GET, []() { if (authorised()) sendStatus(); });
  command("/launch", []() { enqueue({Step::STOP_CHARGE, Step::OPEN, Step::PARK}); return true; });
  command("/dock", []() { enqueue({Step::CENTRE, Step::CLOSE, Step::CHARGE}); return S.cover == Cover::OPEN; });
  command("/open", []() { enqueue({Step::STOP_CHARGE, Step::OPEN}); return true; });
  command("/close", []() { enqueue({Step::CLOSE}); return true; });
  command("/center", []() { enqueue({Step::CENTRE}); return true; });
  command("/release", []() { enqueue({Step::PARK}); return true; });
  command("/charge/start", []() { return chargeStart(); });
  command("/charge/stop", []() { chargeOff(); return true; });
  command("/home", []() { pushersHome(); return true; });
  http.on("/stop", HTTP_POST, []() { if (!authorised()) return; fault("emergency stop (API)"); sendStatus(); });
  http.on("/reset", HTTP_POST, []() {
    if (!authorised()) return;
    S.error = false; S.errorText = "";
    pushersHome();                          // positions are unknown after a fault: re-home first
    sendStatus(202);
  });
  http.onNotFound([]() { http.send(404, "application/json", "{\"error\":\"unknown endpoint\"}"); });
  http.begin();
}

// ------------------------------------------------------------------ setup / loop
void setup() {
  Serial.begin(115200);
  pinMode(PIN_STEPPER_EN, OUTPUT); digitalWrite(PIN_STEPPER_EN, HIGH);
  pinMode(PIN_CHARGE_EN, OUTPUT); digitalWrite(PIN_CHARGE_EN, LOW);
  for (int p : {PIN_COVER_R_IN1, PIN_COVER_R_IN2, PIN_COVER_L_IN1, PIN_COVER_L_IN2}) { pinMode(p, OUTPUT); digitalWrite(p, LOW); }
  pinMode(PIN_ESTOP, INPUT);

  Wire.begin(I2C_SDA, I2C_SCL);
  if (!mcp.begin_I2C(MCP_ADDR)) Serial.println("MCP23017 not found");
  for (int i = 0; i < 8; i++) mcp.pinMode(i, INPUT_PULLUP);
  if (!ina.begin()) Serial.println("INA226 not found");
  ina.setMaxCurrentShunt(6.0, SHUNT_OHMS);
  temps.begin();

  Serial2.begin(115200, SERIAL_8N1, PIN_TMC_RX, PIN_TMC_TX);
  for (int i = 0; i < 4; i++) {
    drv[i].begin();
    drv[i].toff(4);
    drv[i].microsteps(16);
    drv[i].rms_current(MOVE_CURRENT_MA);
    drv[i].pwm_autoscale(true);
    drv[i].en_spreadCycle(false);           // StealthChop: quiet
    drv[i].shaft(TMC_SHAFT_INVERT[i]);
    mot[i].setMaxSpeed(PUSHER_SPEED * STEPS_PER_MM);
    mot[i].setAcceleration(PUSHER_ACCEL * STEPS_PER_MM);
  }

  WiFi.mode(WIFI_STA);
  WiFi.setHostname(HOSTNAME);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(250);
  Serial.printf("Wi-Fi %s, IP %s\n", WiFi.status() == WL_CONNECTED ? "connected" : "NOT connected",
                WiFi.localIP().toString().c_str());
  MDNS.begin(HOSTNAME);
  setupHttp();

  // where are the covers? then home the pushers
  if (sw(COVER_R_CLOSED) && sw(COVER_L_CLOSED)) S.cover = Cover::CLOSED;
  else if (sw(COVER_R_OPEN) && sw(COVER_L_OPEN)) S.cover = Cover::OPEN;
  pushersHome();
}

void loop() {
  static uint32_t lastHttp = 0;
  if (digitalRead(PIN_ESTOP) == LOW && !S.error) fault("emergency stop (button)");
  pushersUpdate();                          // called every pass: steppers need frequent run() calls
  coversUpdate();
  if (millis() - lastHttp > 5) {
    lastHttp = millis();
    http.handleClient();
    readSensors();
    chargeUpdate();
    queueUpdate();
    if (WiFi.status() != WL_CONNECTED && millis() % 10000 < 6) WiFi.reconnect();
  }
}
