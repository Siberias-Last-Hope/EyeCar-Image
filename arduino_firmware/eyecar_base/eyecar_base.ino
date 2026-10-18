// Copyright (C) 2026 MaxX-Akela, MIT License
//
// EyeCar base controller: drive ESC and steering servo behind a serial link.
//
// Hardware: Arduino Mega 2560 + KvantoShield, signal row S2 = steering servo,
// S3 = drive ESC. Both take a servo pulse (microseconds).
//
// Serial, 115200 8N1, text lines terminated with '\n'.
//
//   host -> board   D,<motor>,<steer>,<arm>   motor, steer: -1000..1000; arm: 0 or 1
//   board -> host   R,EYECAR_BASE,1           once after boot
//                   S,<armed>,<motor_us>,<steer_us>,<flags>   every STATUS_PERIOD_MS
//                   E,BAD | E,LONG            rejected line
//
// The host repeats D every ~50 ms. Without a valid D for LINK_TIMEOUT_MS the motor is
// forced to neutral (flags bit 0) until the next frame. Steering holds its last value.
// Disarmed (arm = 0), the motor stays at neutral whatever <motor> says; steering still
// follows <steer>.

#include <Servo.h>

// ---- pins
const uint8_t PIN_STEERING = 2;
const uint8_t PIN_MOTOR = 3;

// ---- serial
const unsigned long SERIAL_BAUD = 115200;
const uint8_t LINE_MAX = 40;

// ---- timing, ms
const unsigned long ESC_ARM_MS = 1500;       // neutral after boot so the ESC can arm
const unsigned long LINK_TIMEOUT_MS = 300;
const unsigned long STATUS_PERIOD_MS = 100;
const unsigned long BRAKE_MS = 180;          // first step of entering reverse
const unsigned long COAST_MS = 180;          // second step: neutral before reverse

// ---- pulses, microseconds (calibrate on the real car)
const int NEUTRAL_US = 1500;
const int FORWARD_SPAN_US = 130;             // full forward  = NEUTRAL + span
const int REVERSE_SPAN_US = 150;             // full reverse  = NEUTRAL - span
const int BRAKE_US = 1350;
const int STEER_CENTER_US = 1500;
const int STEER_SPAN_US = 200;               // full lock = center +/- span
const int CMD_MAX = 1000;

// flags in the status line
const uint8_t FLAG_LINK_LOST = 1;

enum ReversePhase : uint8_t { REV_IDLE, REV_BRAKE, REV_COAST, REV_READY };

Servo motor;
Servo steering;

char line[LINE_MAX + 1];
uint8_t lineLen = 0;
bool lineOverflow = false;

int cmdMotor = 0;
int cmdSteer = 0;
bool cmdArm = false;
bool haveFrame = false;
unsigned long lastFrameMs = 0;
unsigned long lastStatusMs = 0;

ReversePhase phase = REV_IDLE;
unsigned long phaseSinceMs = 0;
int motorUs = NEUTRAL_US;
int steerUs = STEER_CENTER_US;

int clampCmd(long v) {
  if (v > CMD_MAX) return CMD_MAX;
  if (v < -CMD_MAX) return -CMD_MAX;
  return (int)v;
}

// Parse "D,<motor>,<steer>,<arm>". Returns false on anything else.
bool parseFrame(const char *s, int &m, int &st, bool &arm) {
  if (*s++ != 'D') return false;
  long v[3];
  for (uint8_t i = 0; i < 3; i++) {
    if (*s++ != ',') return false;
    char *end;
    v[i] = strtol(s, &end, 10);
    if (end == s) return false;
    s = end;
  }
  if (*s != '\0') return false;
  if (v[2] != 0 && v[2] != 1) return false;
  m = clampCmd(v[0]);
  st = clampCmd(v[1]);
  arm = (v[2] == 1);
  return true;
}

void handleLine(unsigned long now) {
  int m, st;
  bool arm;
  if (parseFrame(line, m, st, arm)) {
    cmdMotor = m;
    cmdSteer = st;
    cmdArm = arm;
    haveFrame = true;
    lastFrameMs = now;
  } else {
    Serial.println(F("E,BAD"));
  }
}

void readSerial(unsigned long now) {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (lineOverflow) {
        Serial.println(F("E,LONG"));
      } else if (lineLen > 0) {
        line[lineLen] = '\0';
        handleLine(now);
      }
      lineLen = 0;
      lineOverflow = false;
    } else if (lineLen < LINE_MAX) {
      line[lineLen++] = c;
    } else {
      lineOverflow = true;
    }
  }
}

// Pulse for the requested throttle. Entering reverse takes a brake and a neutral step
// first (what the ESC expects); it restarts whenever the throttle leaves reverse.
int motorPulse(int cmd, unsigned long now) {
  if (cmd >= 0) {
    phase = REV_IDLE;
    return NEUTRAL_US + (int)((long)cmd * FORWARD_SPAN_US / CMD_MAX);
  }
  if (phase == REV_IDLE) {
    phase = REV_BRAKE;
    phaseSinceMs = now;
  }
  if (phase == REV_BRAKE) {
    if (now - phaseSinceMs < BRAKE_MS) return BRAKE_US;
    phase = REV_COAST;
    phaseSinceMs = now;
  }
  if (phase == REV_COAST) {
    if (now - phaseSinceMs < COAST_MS) return NEUTRAL_US;
    phase = REV_READY;
  }
  return NEUTRAL_US + (int)((long)cmd * REVERSE_SPAN_US / CMD_MAX);
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  motor.attach(PIN_MOTOR);
  steering.attach(PIN_STEERING);
  motor.writeMicroseconds(NEUTRAL_US);
  steering.writeMicroseconds(STEER_CENTER_US);
  Serial.println(F("R,EYECAR_BASE,1"));
}

void loop() {
  unsigned long now = millis();
  readSerial(now);

  bool linkLost = haveFrame && (now - lastFrameMs > LINK_TIMEOUT_MS);
  bool armed = cmdArm && (now >= ESC_ARM_MS);

  int motorCmd = (armed && !linkLost) ? cmdMotor : 0;
  motorUs = motorPulse(motorCmd, now);
  motor.writeMicroseconds(motorUs);

  steerUs = STEER_CENTER_US + (int)((long)cmdSteer * STEER_SPAN_US / CMD_MAX);
  steering.writeMicroseconds(steerUs);

  if (now - lastStatusMs >= STATUS_PERIOD_MS) {
    lastStatusMs = now;
    Serial.print(F("S,"));
    Serial.print(armed ? 1 : 0);
    Serial.print(',');
    Serial.print(motorUs);
    Serial.print(',');
    Serial.print(steerUs);
    Serial.print(',');
    Serial.println(linkLost ? FLAG_LINK_LOST : 0);
  }
}
