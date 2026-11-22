// ---------------------------------------------------------------------------------------------
// Dock controller configuration: pins, mechanics, limits. Change these to match your wiring.
// Only boot-safe ESP32 pins are used for outputs; all 8 limit switches sit on an MCP23017.
// ---------------------------------------------------------------------------------------------
#pragma once

// ---- Wi-Fi + API ----------------------------------------------------------------------------
#define WIFI_SSID        "your-wifi"
#define WIFI_PASSWORD    "your-password"
#define API_TOKEN        "change-me"          // every request needs the header  X-Token: change-me
#define HOSTNAME         "drone-dock"         // http://drone-dock.local

// ---- centering pushers: 4x NEMA17 on TMC2209 ----------------------------------------------------
// Each pair (X, Y) has two motors on the two belts of that axis. They get their own STEP pin so each side
// can be homed (squared) on its own endstop; direction is shared and the TMC2209 'shaft' bit flips the
// motor that sits at the opposite corner.
#define PIN_X1_STEP      25
#define PIN_X2_STEP      26
#define PIN_X_DIR        27
#define PIN_Y1_STEP      14
#define PIN_Y2_STEP      13
#define PIN_Y_DIR        33
#define PIN_STEPPER_EN   32                   // LOW = drivers on. Fit a 10k pull-UP so they stay off at boot.
#define PIN_TMC_TX       17                   // UART2 -> all 4 TMC2209 PDN_UART (1k on TX), addresses 0..3
#define PIN_TMC_RX       16                   //          via MS1/MS2: X1=0, X2=1, Y1=2, Y2=3
const bool TMC_SHAFT_INVERT[4] = {false, true, false, true};

#define STEPS_PER_MM     80.0f                // GT2 20T pulley (40 mm/rev), 200 step motor, 16 microsteps
#define PUSHER_PARK_MM   260.0f               // pusher centre line from the dock centre when parked (CAD)
#define PUSHER_X_CENTRED 105.43f              // X pusher touching the legs (CAD BAR_X_CENTRED)
#define PUSHER_Y_CENTRED 106.28f              // Y pusher touching the legs (CAD BAR_Y_CENTRED)
#define PUSHER_SQUEEZE   1.0f                 // mm past touching, so the drone is held firmly
#define PUSHER_SPEED     60.0f                // mm/s
#define PUSHER_ACCEL     150.0f               // mm/s^2
#define HOMING_SPEED     15.0f                // mm/s
#define PUSH_CURRENT_MA  450                  // low current while pushing the drone: a jam only stalls the motor
#define MOVE_CURRENT_MA  700
#define RSENSE           0.11f                // TMC2209 module sense resistor

// ---- covers: 2x 12 V worm-gear motor (>= 7 N*m) on DRV8871 -------------------------------------
#define PIN_COVER_R_IN1  18
#define PIN_COVER_R_IN2  19
#define PIN_COVER_L_IN1  23
#define PIN_COVER_L_IN2  4
#define COVER_TIMEOUT_MS 30000                // a full 180 deg move takes ~12 s; anything longer is a fault

// ---- MCP23017 (I2C 0x20): limit switches, closed = LOW, internal pull-ups ------------------------
#define MCP_ADDR         0x20
enum McpPin { HOME_X1 = 0, HOME_X2, HOME_Y1, HOME_Y2, COVER_R_OPEN, COVER_R_CLOSED, COVER_L_OPEN, COVER_L_CLOSED };

// ---- charging -------------------------------------------------------------------------------
#define PIN_CHARGE_EN    2                    // HIGH = relay connects the 25.2 V CC/CV charger to the pads
#define PIN_ONEWIRE      15                   // DS18B20s: one under the deck pads, one in the electronics bay
#define I2C_SDA          21                   // shared by the MCP23017 and the INA226
#define I2C_SCL          22
#define INA226_ADDR      0x40                 // current/voltage on the charge line
#define SHUNT_OHMS       0.010f
#define CHARGE_DONE_A    0.30f                // CV phase finished when the current falls below ~C/10
#define CHARGE_NO_CONTACT_A 0.05f             // less than this for 15 s after start = feet not on the pads
#define CHARGE_MAX_V     25.4f                // 6S full is 25.2 V; anything above is a charger fault
#define CHARGE_MAX_C     45.0f                // stop charging above this temperature
#define CHARGE_MAX_MS    (2UL * 3600UL * 1000UL)

// ---- spare inputs -----------------------------------------------------------------------------
#define PIN_ESTOP        34                   // emergency-stop button to GND (external 10k pull-up), LOW = stop
