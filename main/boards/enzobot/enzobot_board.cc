/**
 * enzobot_board.cc — EnzoBot ZOD — Robot Cameriere AI con Visione
 *
 * Core 0: Xiaozhi (audio, WiFi, LLM, wake word, OLED)
 * Core 1: Task motori (L298N, sensori, K230 vision nav, MPU6050)
 *
 * Architettura ZOD (3 agenti):
 *   Server VPS (Claude LLM) → ESP32 (interazione + sicurezza) → K230 (navigazione YOLO)
 *
 * K230 Yahboom: navigazione via computer vision (YOLO), NO ArUco/line follow
 * Protocollo: JSON bidirezionale su UART1 @ 115200 baud
 */

#include "wifi_board.h"
#include "codecs/no_audio_codec.h"
#include "display/oled_display.h"
#include "application.h"
#include "button.h"
#include "config.h"
#include "mcp_server.h"
#include "led/single_led.h"
#include "assets/lang_config.h"

#include <esp_log.h>
#include <driver/i2c_master.h>
#include <driver/ledc.h>
#include <driver/uart.h>
#include <esp_lcd_panel_ops.h>
#include <esp_lcd_panel_vendor.h>
#include <esp_timer.h>
#include <esp_http_server.h>
#include <esp_wifi.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

#include <cstring>
#include <cmath>
#include <string>
#include "cJSON.h"
#include "k230_protocol.h"

#define TAG "EnzoBot"

// ============================================================
//  Comandi robot (coda thread-safe Core0 -> Core1)
// ============================================================

enum RobotCmdType {
    CMD_STOP = 0, CMD_FORWARD, CMD_BACKWARD,
    CMD_LEFT, CMD_RIGHT, CMD_ROTATE_L, CMD_ROTATE_R,
    CMD_SET_SPEED, CMD_GOTO_TABLE, CMD_GOTO_KITCHEN,
    CMD_ENABLE, CMD_DISABLE, CMD_BUZZER,
    CMD_DANCE, CMD_BOW,
    // ZOD — K230 Vision Navigation
    CMD_NAV_START,   // value = table number (0 = kitchen)
    CMD_NAV_ABORT,
    CMD_SCAN,
};

struct RobotCmd {
    RobotCmdType type;
    int value;
};

struct RobotState {
    int dist_rear = 999, dist_left = 999, dist_right = 999, dist_front = 999;
    int speed_left = 0, speed_right = 0;
    int speed_setting = CRUISE_SPEED;
    float weight_grams = 0;
    bool motors_enabled = true;
    char delivery_state[16] = "idle";
    int current_table = 0;
    int deliveries = 0;
    float heading = 0, pitch = 0, roll = 0;
    bool tilted = false, mpu_present = false;
    // ZOD — K230 navigation
    NavState nav_state = NAV_IDLE;
    bool k230_connected = false;
    int nav_progress = 0;
    int vision_objects = 0;
};

static QueueHandle_t cmd_queue = nullptr;
static RobotState robot_state = {};
static portMUX_TYPE robot_state_mux = portMUX_INITIALIZER_UNLOCKED;

// ZOD — K230 Vision
static K230Uart k230;
static K230State k230_state = {};
static portMUX_TYPE k230_state_mux = portMUX_INITIALIZER_UNLOCKED;

// ============================================================
//  MOTORI DC via L298N singolo (canale A = SX, canale B = DX)
// ============================================================

static void init_motors() {
    gpio_set_direction(MOT_L_IN1, GPIO_MODE_OUTPUT);
    gpio_set_direction(MOT_L_IN2, GPIO_MODE_OUTPUT);
    gpio_set_direction(MOT_R_IN1, GPIO_MODE_OUTPUT);
    gpio_set_direction(MOT_R_IN2, GPIO_MODE_OUTPUT);

    ledc_timer_config_t timer_conf = {};
    timer_conf.speed_mode = LEDC_LOW_SPEED_MODE;
    timer_conf.duty_resolution = (ledc_timer_bit_t)PWM_RESOLUTION_BITS;
    timer_conf.timer_num = LEDC_TIMER_0;
    timer_conf.freq_hz = PWM_FREQ_HZ;
    timer_conf.clk_cfg = LEDC_AUTO_CLK;
    ledc_timer_config(&timer_conf);

    ledc_channel_config_t ch = {};
    ch.speed_mode = LEDC_LOW_SPEED_MODE;
    ch.timer_sel = LEDC_TIMER_0;
    ch.duty = 0;
    ch.hpoint = 0;

    ch.gpio_num = (int)MOT_L_ENA;
    ch.channel = LEDC_CHANNEL_0;
    ledc_channel_config(&ch);

    ch.gpio_num = (int)MOT_R_ENA;
    ch.channel = LEDC_CHANNEL_1;
    ledc_channel_config(&ch);
}

// Target and current speeds for smooth ramping
static int target_left = 0, target_right = 0;
static int current_left = 0, current_right = 0;
static const int RAMP_STEP = 8;  // PWM units per 50ms tick — smooth ramp ~0.6s to full speed

static void apply_motors(int left, int right) {
    gpio_set_level(MOT_L_IN1, left > 0 ? 1 : 0);
    gpio_set_level(MOT_L_IN2, left < 0 ? 1 : 0);
    ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, abs(left));
    ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);

    gpio_set_level(MOT_R_IN1, right > 0 ? 1 : 0);
    gpio_set_level(MOT_R_IN2, right < 0 ? 1 : 0);
    ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_1, abs(right));
    ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_1);

    portENTER_CRITICAL(&robot_state_mux);
    robot_state.speed_left = left;
    robot_state.speed_right = right;
    portEXIT_CRITICAL(&robot_state_mux);
}

static void set_motors(int left, int right) {
    target_left = left;
    target_right = right;
}

// Ramp current toward target by RAMP_STEP per tick
static void ramp_motors() {
    bool changed = false;
    if (current_left < target_left) { current_left = std::min(current_left + RAMP_STEP, target_left); changed = true; }
    else if (current_left > target_left) { current_left = std::max(current_left - RAMP_STEP, target_left); changed = true; }
    if (current_right < target_right) { current_right = std::min(current_right + RAMP_STEP, target_right); changed = true; }
    else if (current_right > target_right) { current_right = std::max(current_right - RAMP_STEP, target_right); changed = true; }
    if (changed) apply_motors(current_left, current_right);
}

// Immediate stop (bypass ramp for emergency)
static void hard_stop() {
    target_left = target_right = current_left = current_right = 0;
    apply_motors(0, 0);
}

// ============================================================
//  ULTRASUONI (4x HC-SR04, auto-detect)
// ============================================================

struct USSensor { gpio_num_t trig, echo; bool present; int dist; };
static USSensor us[4] = {
    {US_REAR_TRIG, US_REAR_ECHO, false, 999},
    {US_LEFT_TRIG, US_LEFT_ECHO, false, 999},
    {US_RIGHT_TRIG, US_RIGHT_ECHO, false, 999},
    {US_FRONT_TRIG, US_FRONT_ECHO, false, 999},
};

static int read_us_one(gpio_num_t trig, gpio_num_t echo) {
    gpio_set_level(trig, 0); esp_rom_delay_us(2);
    gpio_set_level(trig, 1); esp_rom_delay_us(10);
    gpio_set_level(trig, 0);
    int64_t t0 = esp_timer_get_time(), timeout = t0 + 30000;
    while (!gpio_get_level(echo) && esp_timer_get_time() < timeout) {}
    int64_t start = esp_timer_get_time();
    if (start >= timeout) return 999;
    while (gpio_get_level(echo) && esp_timer_get_time() < timeout) {}
    return (int)((esp_timer_get_time() - start) / 58);
}

static void init_us() __attribute__((unused));
static void init_us() {
    const char* names[] = {"REAR", "LEFT", "RIGHT", "FRONT"};
    for (int i = 0; i < 4; i++) {
        gpio_set_direction(us[i].trig, GPIO_MODE_OUTPUT);
        gpio_set_direction(us[i].echo, GPIO_MODE_INPUT);
        for (int t = 0; t < 3 && !us[i].present; t++) {
            if (read_us_one(us[i].trig, us[i].echo) < 999) us[i].present = true;
            vTaskDelay(pdMS_TO_TICKS(30));
        }
        ESP_LOGI(TAG, "US %s: %s", names[i], us[i].present ? "OK" : "---");
    }
}

static void read_us_round() __attribute__((unused));
static void read_us_round() {
    static int cur = 0;
    for (int a = 0; a < 4; a++) {
        if (us[cur].present) {
            us[cur].dist = read_us_one(us[cur].trig, us[cur].echo);
            break;
        }
        cur = (cur + 1) % 4;
    }
    cur = (cur + 1) % 4;
    portENTER_CRITICAL(&robot_state_mux);
    robot_state.dist_rear  = us[0].present ? us[0].dist : 999;
    robot_state.dist_left  = us[1].present ? us[1].dist : 999;
    robot_state.dist_right = us[2].present ? us[2].dist : 999;
    robot_state.dist_front = us[3].present ? us[3].dist : 999;
    portEXIT_CRITICAL(&robot_state_mux);
}

// ============================================================
//  MPU6050 — TODO fase 2 (richiede i2c_master nuovo driver)
// ============================================================

// MPU6050 sara' aggiunto quando il sensore sara' disponibile.
// Usera' il bus I2C condiviso con OLED (GPIO 8/9, addr 0x68).

// ============================================================
//  K230 Yahboom — Inizializzazione (via k230_protocol.h)
// ============================================================

static void init_k230_vision() {
    k230.Init(K230_TX_PIN, K230_RX_PIN, K230_BAUD);
    if (k230.ok) {
        portENTER_CRITICAL(&k230_state_mux);
        k230_state.connected = true;
        portEXIT_CRITICAL(&k230_state_mux);
    }
}

// ============================================================
//  MOTOR TASK — Core 1
// ============================================================

static void motor_task(void* arg) {
    ESP_LOGI(TAG, "Motor task su Core %d", xPortGetCoreID());

    // Init motori
    init_motors();
    ESP_LOGI(TAG, "Motori OK");

    // Buzzer e LED
    if (BUZZER_PIN != GPIO_NUM_NC) gpio_set_direction(BUZZER_PIN, GPIO_MODE_OUTPUT);
    if (LED_STATUS_PIN != GPIO_NUM_NC) gpio_set_direction(LED_STATUS_PIN, GPIO_MODE_OUTPUT);
    if (LED_STATUS_PIN != GPIO_NUM_NC) gpio_set_level(LED_STATUS_PIN, 1);
    ESP_LOGI(TAG, "GPIO OK");

    // K230 Vision — init UART bidirezionale
    init_k230_vision();
    ESP_LOGI(TAG, "K230: %s", k230.ok ? "ONLINE (ZOD mode)" : "offline (manual mode)");

    ESP_LOGI(TAG, "Motor task pronto! [ZOD]");

    int spd = CRUISE_SPEED;
    RobotCmd cmd;
    uint32_t last_motor_cmd_ms = 0;
    static const uint32_t MOTOR_TIMEOUT_MS = 5000;  // Auto-stop dopo 5s senza comandi

    while (true) {
        uint32_t now_ms = xTaskGetTickCount() * portTICK_PERIOD_MS;

        // Comandi dalla coda
        while (xQueueReceive(cmd_queue, &cmd, 0) == pdTRUE) {
            last_motor_cmd_ms = now_ms;
            // Check motors_enabled per comandi movimento
            bool enabled = true;
            portENTER_CRITICAL(&robot_state_mux);
            enabled = robot_state.motors_enabled;
            portEXIT_CRITICAL(&robot_state_mux);

            switch (cmd.type) {
                case CMD_STOP:      hard_stop(); break;
                case CMD_FORWARD:   if (enabled) set_motors(spd, spd); break;
                case CMD_BACKWARD:  if (enabled) set_motors(-spd, -spd); break;
                case CMD_LEFT:      if (enabled) set_motors(spd/3, spd); break;
                case CMD_RIGHT:     if (enabled) set_motors(spd, spd/3); break;
                case CMD_ROTATE_L:  if (enabled) set_motors(-spd, spd); break;
                case CMD_ROTATE_R:  if (enabled) set_motors(spd, -spd); break;
                case CMD_SET_SPEED: {
                    spd = cmd.value < MIN_SPEED ? MIN_SPEED : (cmd.value > MAX_SPEED ? MAX_SPEED : cmd.value);
                    portENTER_CRITICAL(&robot_state_mux);
                    robot_state.speed_setting = spd;
                    portEXIT_CRITICAL(&robot_state_mux);
                    ESP_LOGI(TAG, "Speed: %d", spd);
                    break;
                }
                case CMD_GOTO_TABLE: {
                    // Legacy: direct command (works without K230)
                    char b[64]; snprintf(b, 64, "table_%d", cmd.value);
                    k230.SendNavigate(b);
                    portENTER_CRITICAL(&robot_state_mux);
                    robot_state.current_table = cmd.value;
                    strncpy(robot_state.delivery_state, "delivering", 15);
                    portEXIT_CRITICAL(&robot_state_mux);
                    break;
                }
                case CMD_GOTO_KITCHEN: k230.SendNavigate("kitchen"); break;
                case CMD_NAV_START: {
                    // ZOD: smart navigation via K230 vision
                    char dest[32];
                    if (cmd.value == 0) snprintf(dest, sizeof(dest), "kitchen");
                    else snprintf(dest, sizeof(dest), "table_%d", cmd.value);
                    k230.SendNavigate(dest);
                    portENTER_CRITICAL(&robot_state_mux);
                    robot_state.nav_state = NAV_NAVIGATING;
                    robot_state.current_table = cmd.value;
                    strncpy(robot_state.delivery_state, "navigating", 15);
                    portEXIT_CRITICAL(&robot_state_mux);
                    ESP_LOGI(TAG, "NAV START → %s", dest);
                    break;
                }
                case CMD_NAV_ABORT: {
                    k230.Send("{\"cmd\":\"abort\"}");
                    hard_stop();
                    portENTER_CRITICAL(&robot_state_mux);
                    robot_state.nav_state = NAV_IDLE;
                    strncpy(robot_state.delivery_state, "idle", 15);
                    portEXIT_CRITICAL(&robot_state_mux);
                    ESP_LOGW(TAG, "NAV ABORT");
                    break;
                }
                case CMD_SCAN: {
                    k230.Send("{\"cmd\":\"scan\"}");
                    portENTER_CRITICAL(&k230_state_mux);
                    k230_state.scan_ready = false;
                    portEXIT_CRITICAL(&k230_state_mux);
                    ESP_LOGI(TAG, "SCAN requested");
                    break;
                }
                case CMD_ENABLE:
                    portENTER_CRITICAL(&robot_state_mux);
                    robot_state.motors_enabled = true;
                    portEXIT_CRITICAL(&robot_state_mux);
                    break;
                case CMD_DISABLE:
                    hard_stop();
                    portENTER_CRITICAL(&robot_state_mux);
                    robot_state.motors_enabled = false;
                    portEXIT_CRITICAL(&robot_state_mux);
                    break;
                case CMD_BUZZER:
                    if (BUZZER_PIN != GPIO_NUM_NC) {
                        int beeps = cmd.value > 20 ? 20 : cmd.value;
                        for (int i = 0; i < beeps; i++) {
                            gpio_set_level(BUZZER_PIN, 1); esp_rom_delay_us(500);
                            gpio_set_level(BUZZER_PIN, 0); esp_rom_delay_us(500);
                        }
                    }
                    break;
                case CMD_DANCE:
                    if (enabled) {
                        int dance_spd = spd * 2 / 3;
                        for (int i = 0; i < 3; i++) {
                            apply_motors(-dance_spd, dance_spd); vTaskDelay(pdMS_TO_TICKS(400));
                            apply_motors(dance_spd, -dance_spd); vTaskDelay(pdMS_TO_TICKS(400));
                        }
                        apply_motors(dance_spd, dance_spd); vTaskDelay(pdMS_TO_TICKS(300));
                        apply_motors(-dance_spd, -dance_spd); vTaskDelay(pdMS_TO_TICKS(300));
                        hard_stop();
                        ESP_LOGI(TAG, "Danza completata!");
                    }
                    break;
                case CMD_BOW:
                    if (enabled) {
                        int bow_spd = SLOW_SPEED;
                        apply_motors(bow_spd, bow_spd); vTaskDelay(pdMS_TO_TICKS(300));
                        hard_stop(); vTaskDelay(pdMS_TO_TICKS(800));
                        apply_motors(-bow_spd, -bow_spd); vTaskDelay(pdMS_TO_TICKS(300));
                        hard_stop();
                        ESP_LOGI(TAG, "Inchino completato!");
                    }
                    break;
                default: break;
            }
        }

        // Smooth acceleration ramp (every 50ms tick)
        ramp_motors();

        // === K230 UART bidirezionale (ZOD) ===
        if (k230.ok) {
            k230.Receive(k230_state, k230_state_mux);

            // Process motor commands from K230 (visual navigation)
            portENTER_CRITICAL(&k230_state_mux);
            bool has_motor_cmd = k230_state.motor_cmd_pending;
            int ml = k230_state.motor_left, mr = k230_state.motor_right;
            int mdur = k230_state.motor_dur_ms;
            NavState k_nav = k230_state.nav_state;
            k230_state.motor_cmd_pending = false;
            portEXIT_CRITICAL(&k230_state_mux);

            // Execute K230 motor commands (only during navigation, with safety check)
            bool is_navigating = false;
            portENTER_CRITICAL(&robot_state_mux);
            is_navigating = (robot_state.nav_state == NAV_NAVIGATING || robot_state.nav_state == NAV_RETURNING);
            bool enabled = robot_state.motors_enabled;
            portEXIT_CRITICAL(&robot_state_mux);

            // Motor stop timer (non-blocking replacement for vTaskDelay)
            static uint32_t motor_stop_at_ms = 0;
            if (motor_stop_at_ms > 0 && now_ms >= motor_stop_at_ms) {
                apply_motors(0, 0);
                motor_stop_at_ms = 0;
            }

            if (has_motor_cmd && is_navigating && enabled) {
                // Safety: check ultrasonics before executing K230 motor command
                bool us_clear = (robot_state.dist_front > US_EMERGENCY_DIST || ml <= 0);
                if (us_clear) {
                    apply_motors(ml, mr);
                    last_motor_cmd_ms = now_ms;
                    // Non-blocking duration: schedule stop instead of vTaskDelay
                    if (mdur > 0) {
                        motor_stop_at_ms = now_ms + mdur;
                    }
                } else {
                    hard_stop();
                    motor_stop_at_ms = 0;
                    k230.Send("{\"cmd\":\"obstacle_detected\"}");
                    ESP_LOGW(TAG, "US safety override — K230 motor cmd blocked");
                }
            }

            // Navigation state sync from K230 (one-shot transition detection)
            NavState prev_nav;
            portENTER_CRITICAL(&robot_state_mux);
            prev_nav = robot_state.nav_state;
            portEXIT_CRITICAL(&robot_state_mux);

            if (k_nav == NAV_ARRIVED && prev_nav != NAV_ARRIVED) {
                hard_stop();
                motor_stop_at_ms = 0;
                portENTER_CRITICAL(&robot_state_mux);
                robot_state.nav_state = NAV_ARRIVED;
                strncpy(robot_state.delivery_state, "arrived", 15);
                robot_state.deliveries++;
                portEXIT_CRITICAL(&robot_state_mux);
                ESP_LOGI(TAG, "NAV: ARRIVED!");
            } else if (k_nav == NAV_ERROR && prev_nav != NAV_ERROR) {
                hard_stop();
                motor_stop_at_ms = 0;
                portENTER_CRITICAL(&robot_state_mux);
                robot_state.nav_state = NAV_ERROR;
                strncpy(robot_state.delivery_state, "error", 15);
                portEXIT_CRITICAL(&robot_state_mux);
                ESP_LOGE(TAG, "NAV: ERROR from K230");
            } else if (k_nav == NAV_NAVIGATING && prev_nav != NAV_NAVIGATING) {
                portENTER_CRITICAL(&robot_state_mux);
                robot_state.nav_state = NAV_NAVIGATING;
                strncpy(robot_state.delivery_state, "navigating", 15);
                portEXIT_CRITICAL(&robot_state_mux);
            }

            // K230 connection health check
            portENTER_CRITICAL(&k230_state_mux);
            uint32_t last_hb = k230_state.last_msg_ms;
            portEXIT_CRITICAL(&k230_state_mux);
            if (last_hb > 0 && (now_ms - last_hb > 5000)) {
                portENTER_CRITICAL(&k230_state_mux);
                k230_state.connected = false;
                portEXIT_CRITICAL(&k230_state_mux);
                if (is_navigating) {
                    hard_stop();
                    portENTER_CRITICAL(&robot_state_mux);
                    robot_state.nav_state = NAV_ERROR;
                    strncpy(robot_state.delivery_state, "k230_lost", 15);
                    portEXIT_CRITICAL(&robot_state_mux);
                    ESP_LOGE(TAG, "K230 timeout! Emergency stop");
                }
            }

            // Send sensor data to K230 every 200ms
            static uint32_t last_sensor_send = 0;
            if (now_ms - last_sensor_send > 200) {
                RobotState snap;
                portENTER_CRITICAL(&robot_state_mux);
                snap = robot_state;
                portEXIT_CRITICAL(&robot_state_mux);
                k230.SendSensors(snap.dist_front, snap.dist_rear, snap.dist_left, snap.dist_right);
                last_sensor_send = now_ms;
            }

            // Sync K230 state to robot_state for WebUI/MCP
            bool kc; int kp, ko;
            portENTER_CRITICAL(&k230_state_mux);
            kc = k230_state.connected;
            kp = k230_state.nav_progress;
            ko = k230_state.num_objects;
            portEXIT_CRITICAL(&k230_state_mux);
            portENTER_CRITICAL(&robot_state_mux);
            robot_state.k230_connected = kc;
            robot_state.nav_progress = kp;
            robot_state.vision_objects = ko;
            portEXIT_CRITICAL(&robot_state_mux);
        }

        // Auto-stop sicurezza: ferma motori se nessun comando per 5 secondi
        // (disabilitato durante navigazione K230 attiva)
        NavState cur_nav;
        portENTER_CRITICAL(&robot_state_mux);
        cur_nav = robot_state.nav_state;
        portEXIT_CRITICAL(&robot_state_mux);

        if (cur_nav == NAV_IDLE || cur_nav == NAV_ARRIVED || cur_nav == NAV_ERROR) {
            if (last_motor_cmd_ms > 0 && (now_ms - last_motor_cmd_ms > MOTOR_TIMEOUT_MS)) {
                if (target_left != 0 || target_right != 0) {
                    set_motors(0, 0);
                    ESP_LOGW(TAG, "Auto-stop: nessun comando per %lums", (unsigned long)MOTOR_TIMEOUT_MS);
                }
                last_motor_cmd_ms = 0;
            }
        }

        vTaskDelay(pdMS_TO_TICKS(50));  // yield per watchdog
    }
}

// Motor task con delay iniziale: aspetta che I2S sia configurato
static void motor_task_delayed(void* arg) {
    // Aspetta 5 secondi per permettere a Xiaozhi di completare
    // l'init audio (I2S) prima di configurare LEDC
    ESP_LOGI(TAG, "Motor task: attendo init audio...");
    vTaskDelay(pdMS_TO_TICKS(5000));
    motor_task(arg);
}

static void send_cmd(RobotCmdType type, int val = 0) {
    RobotCmd c = {type, val};
    xQueueSend(cmd_queue, &c, pdMS_TO_TICKS(10));
}

// ============================================================
//  WEB SERVER — Stato robot + comandi
// ============================================================

static httpd_handle_t webserver = nullptr;

static int current_volume = 100;  // Sync with AudioCodec default
static int us_threshold = US_WARNING_DIST;

static const char* WEBUI_HTML = R"rawhtml(
<!DOCTYPE html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>EnzoBot</title>
<style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{font-family:system-ui;background:#1a1a2e;color:#e0e0e0;margin:0;padding:10px;max-width:480px;margin:0 auto}
h1{color:#55aaff;margin:0 0 6px;font-size:20px}
h2{color:#88aacc;margin:10px 0 4px;font-size:14px;display:flex;align-items:center;gap:6px}
.card{background:#111122;border:1px solid #2a2a44;border-radius:10px;padding:8px;margin:4px 0}
.row{display:flex;justify-content:space-between;padding:2px 0;font-size:12px}
.lbl{color:#667}.val{color:#fff;font-weight:bold}
.ok{color:#0d6}.warn{color:#fb0}.err{color:#f33}.blue{color:#55aaff}
button{background:#1a3366;color:#fff;border:none;border-radius:8px;padding:12px 14px;margin:2px;font-size:15px;cursor:pointer;min-width:70px;touch-action:manipulation}
button:active{background:#2255aa;transform:scale(0.95)}
button.active{background:#225588;box-shadow:0 0 8px #55aaff}
.estop{background:#cc0000;font-size:18px;font-weight:bold;padding:14px;width:100%;border-radius:12px;margin:6px 0;letter-spacing:2px}
.estop:active{background:#ff0000}
.toggle{display:inline-flex;align-items:center;gap:8px;cursor:pointer;font-size:13px}
.toggle input{display:none}
.toggle .sw{width:40px;height:22px;background:#333;border-radius:11px;position:relative;transition:0.2s}
.toggle .sw::after{content:'';width:18px;height:18px;background:#888;border-radius:50%;position:absolute;top:2px;left:2px;transition:0.2s}
.toggle input:checked+.sw{background:#0a5}
.toggle input:checked+.sw::after{left:20px;background:#fff}
.grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:3px;max-width:280px;margin:4px auto}
input[type=range]{width:100%;accent-color:#55aaff;height:24px}
.sensors{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.sensor{text-align:center;padding:8px;border-radius:8px;background:#0a0a1a;border:2px solid #222}
.sensor.alert{border-color:#f33;background:#1a0505;animation:pulse 1s infinite}
@keyframes pulse{50%{border-color:#ff6666}}
.sensor .dist{font-size:22px;font-weight:bold}
.sensor .name{font-size:10px;color:#667}
.compass{width:70px;height:70px;margin:0 auto;position:relative}
.compass .arrow{position:absolute;left:50%;top:50%;width:3px;height:30px;background:#55aaff;transform-origin:bottom center;border-radius:2px;margin-left:-1.5px;margin-top:-30px;transition:transform 0.3s}
.compass .ring{width:70px;height:70px;border:2px solid #334;border-radius:50%;position:relative}
.compass .n{position:absolute;top:-2px;left:50%;transform:translateX(-50%);font-size:9px;color:#88a}
.delivery{display:flex;gap:10px;align-items:center}
.delivery .table{font-size:28px;font-weight:bold;color:#55aaff}
.info{font-size:11px;color:#556;text-align:center;margin-top:8px}
</style></head><body>
<h1>&#129302; EnzoBot <span style="font-size:11px;color:#556" id="ver">v2.1</span></h1>

<button class="estop" onclick="cmd('stop')">&#9632; STOP EMERGENZA</button>

<div class="card">
<div class="row"><span class="lbl">Chatbot</span><span class="val" id="chat">--</span></div>
<div class="row"><span class="lbl">IP</span><span class="val blue" id="ip">--</span></div>
<div class="row"><span class="lbl">WiFi</span><span class="val" id="rssi">--</span></div>
<div class="row"><span class="lbl">Heap</span><span class="val" id="heap">--</span></div>
<div class="row"><span class="lbl">Uptime</span><span class="val" id="up">--</span></div>
</div>

<div class="card">
<div class="delivery">
<div><div class="table" id="tbl">-</div><div style="font-size:10px;color:#667">Tavolo</div></div>
<div style="flex:1">
<div class="row"><span class="lbl">Stato</span><span class="val" id="del">idle</span></div>
<div class="row"><span class="lbl">Consegne</span><span class="val" id="cnt">0</span></div>
</div>
</div>
</div>

<h2>&#127925; Volume: <span id="vv">100</span>%</h2>
<input type="range" min="0" max="100" value="100" id="vol" oninput="document.getElementById('vv').textContent=this.value" onchange="fetch('/cmd?a=volume&v='+this.value)">

<h2>&#128663; Controllo
<label class="toggle"><input type="checkbox" id="men" checked onchange="fetch('/cmd?a='+(this.checked?'enable':'disable'))"><span class="sw"></span>Motori</label>
</h2>
<div style="text-align:center;margin:2px 0">
<span class="lbl">Velocita: <span id="sv">200</span></span>
<input type="range" min="80" max="255" value="200" id="spd" oninput="document.getElementById('sv').textContent=this.value" onchange="fetch('/cmd?a=speed&v='+this.value)">
</div>
<div class="grid">
<div></div><button id="bf" onclick="cmd('forward')">&#8593; Avanti</button><div></div>
<button id="bl" onclick="cmd('left')">&#8592; SX</button>
<button class="estop" style="font-size:14px;padding:10px;min-width:0" onclick="cmd('stop')">&#9632;</button>
<button id="br" onclick="cmd('right')">DX &#8594;</button>
<button id="brl" onclick="cmd('rotate_left')">&#8634;</button>
<button id="bb" onclick="cmd('backward')">&#8595; Dietro</button>
<button id="brr" onclick="cmd('rotate_right')">&#8635;</button>
</div>

<h2>&#128225; Sensori Ultrasuoni</h2>
<div class="card">
<div class="sensors">
<div class="sensor" id="us_f"><div class="dist" id="df">--</div><div class="name">&#9650; Davanti</div></div>
<div class="sensor" id="us_r"><div class="dist" id="dr">--</div><div class="name">&#9660; Dietro</div></div>
<div class="sensor" id="us_l"><div class="dist" id="dl">--</div><div class="name">&#9664; Sinistra</div></div>
<div class="sensor" id="us_rt"><div class="dist" id="drt">--</div><div class="name">&#9654; Destra</div></div>
</div>
<div style="margin-top:6px">
<span class="lbl">Soglia: <span id="tv">30</span>cm</span>
<input type="range" min="5" max="100" value="30" id="thr" oninput="document.getElementById('tv').textContent=this.value" onchange="fetch('/cmd?a=threshold&v='+this.value)">
</div>
</div>

<h2>&#129517; Bussola</h2>
<div class="card" style="text-align:center">
<div class="compass"><div class="ring"><div class="n">N</div><div class="arrow" id="arrow"></div></div></div>
<div class="row"><span class="lbl">Heading</span><span class="val" id="hdg">--</span></div>
<div class="row"><span class="lbl">Pitch/Roll</span><span class="val"><span id="pit">--</span> / <span id="rol">--</span></span></div>
<div class="row"><span class="lbl">Inclinato</span><span class="val" id="tlt">--</span></div>
</div>

<div class="info">EnzoBot &#8212; Robot Cameriere AI &#8212; enzobot.xamad.net</div>

<script>
var lastDir='';
function cmd(c){
fetch('/cmd?a='+c).then(r=>r.text()).then(t=>{
lastDir=c;hlDir(c);
document.getElementById('chat').textContent=t;
})}
function hlDir(d){
['bf','bb','bl','br','brl','brr'].forEach(id=>document.getElementById(id).classList.remove('active'));
var map={forward:'bf',backward:'bb',left:'bl',right:'br',rotate_left:'brl',rotate_right:'brr'};
if(map[d])document.getElementById(map[d]).classList.add('active');
if(d==='stop'){lastDir='';['bf','bb','bl','br','brl','brr'].forEach(id=>document.getElementById(id).classList.remove('active'));}
}
function poll(){fetch('/status').then(r=>r.json()).then(d=>{
document.getElementById('chat').textContent=d.chat||'idle';
document.getElementById('chat').className='val '+(d.chat==='listening'?'ok':d.chat==='speaking'?'warn':'');
document.getElementById('ip').textContent=d.ip;
document.getElementById('rssi').textContent=d.rssi+'dBm';
document.getElementById('rssi').className='val '+(d.rssi>-50?'ok':d.rssi>-70?'warn':'err');
document.getElementById('heap').textContent=(d.heap/1024|0)+'KB';
document.getElementById('up').textContent=(d.uptime/60|0)+'m '+(d.uptime%60)+'s';
document.getElementById('men').checked=d.motors_en;
document.getElementById('tbl').textContent=d.table||'-';
document.getElementById('del').textContent=d.delivery||'idle';
document.getElementById('cnt').textContent=d.deliveries||0;
document.getElementById('df').textContent=d.dist_f<999?d.dist_f+'cm':'--';
document.getElementById('dl').textContent=d.dist_l<999?d.dist_l+'cm':'--';
document.getElementById('drt').textContent=d.dist_rt<999?d.dist_rt+'cm':'--';
document.getElementById('dr').textContent=d.dist_r<999?d.dist_r+'cm':'--';
var t=d.threshold||30;
['us_f','us_l','us_rt','us_r'].forEach(function(id,i){
var v=[d.dist_f,d.dist_l,d.dist_rt,d.dist_r][i];
document.getElementById(id).className=v<t&&v<999?'sensor alert':'sensor';
});
document.getElementById('hdg').textContent=d.heading.toFixed(1)+'\u00B0';
document.getElementById('pit').textContent=d.pitch.toFixed(1)+'\u00B0';
document.getElementById('rol').textContent=d.roll.toFixed(1)+'\u00B0';
document.getElementById('tlt').textContent=d.tilted?'SI':'No';
document.getElementById('arrow').style.transform='rotate('+d.heading+'deg)';
if(d.volume!==undefined){document.getElementById('vol').value=d.volume;document.getElementById('vv').textContent=d.volume;}
if(d.speed){document.getElementById('spd').value=d.speed;document.getElementById('sv').textContent=d.speed;}
}).catch(e=>{})}
setInterval(poll,2000);poll();
</script></body></html>
)rawhtml";

static void set_cors(httpd_req_t* req) {
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
}

static esp_err_t webui_handler(httpd_req_t* req) {
    set_cors(req);
    httpd_resp_set_type(req, "text/html");
    httpd_resp_send(req, WEBUI_HTML, strlen(WEBUI_HTML));
    return ESP_OK;
}

static esp_err_t status_handler(httpd_req_t* req) {
    set_cors(req);
    char buf[700];
    esp_netif_ip_info_t ip_info = {};
    esp_netif_t* netif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
    if (netif) esp_netif_get_ip_info(netif, &ip_info);

    // WiFi RSSI
    wifi_ap_record_t ap;
    int rssi = -99;
    if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) rssi = ap.rssi;

    // Chatbot state
    auto& app = Application::GetInstance();
    const char* chat_state = "idle";
    switch (app.GetDeviceState()) {
        case kDeviceStateListening: chat_state = "listening"; break;
        case kDeviceStateSpeaking:  chat_state = "speaking"; break;
        case kDeviceStateConnecting: chat_state = "connecting"; break;
        case kDeviceStateActivating: chat_state = "activating"; break;
        case kDeviceStateWifiConfiguring: chat_state = "wifi_config"; break;
        default: chat_state = "idle"; break;
    }

    // Snapshot robot state
    RobotState snap;
    portENTER_CRITICAL(&robot_state_mux);
    snap = robot_state;
    portEXIT_CRITICAL(&robot_state_mux);

    snprintf(buf, sizeof(buf),
        "{\"chat\":\"%s\",\"ip\":\"" IPSTR "\",\"rssi\":%d,"
        "\"motors_en\":%s,\"speed\":%d,\"heap\":%lu,\"uptime\":%lu,"
        "\"table\":%d,\"delivery\":\"%s\",\"deliveries\":%d,"
        "\"dist_r\":%d,\"dist_l\":%d,\"dist_rt\":%d,\"dist_f\":%d,\"threshold\":%d,"
        "\"heading\":%.1f,\"pitch\":%.1f,\"roll\":%.1f,\"tilted\":%s,"
        "\"volume\":%d}",
        chat_state, IP2STR(&ip_info.ip), rssi,
        snap.motors_enabled ? "true" : "false",
        CRUISE_SPEED,
        (unsigned long)esp_get_free_heap_size(),
        (unsigned long)(esp_timer_get_time() / 1000000),
        snap.current_table, snap.delivery_state, snap.deliveries,
        snap.dist_rear, snap.dist_left, snap.dist_right, snap.dist_front,
        us_threshold,
        snap.heading, snap.pitch, snap.roll,
        snap.tilted ? "true" : "false",
        current_volume);
    httpd_resp_set_type(req, "application/json");
    httpd_resp_send(req, buf, strlen(buf));
    return ESP_OK;
}

static esp_err_t cmd_handler(httpd_req_t* req) {
    set_cors(req);
    char param[64] = {};
    if (httpd_req_get_url_query_str(req, param, sizeof(param)) == ESP_OK) {
        char action[20] = {};
        char value[10] = {};
        httpd_query_key_value(param, "a", action, sizeof(action));
        httpd_query_key_value(param, "v", value, sizeof(value));
        if (strcmp(action, "forward") == 0) send_cmd(CMD_FORWARD);
        else if (strcmp(action, "backward") == 0) send_cmd(CMD_BACKWARD);
        else if (strcmp(action, "left") == 0) send_cmd(CMD_LEFT);
        else if (strcmp(action, "right") == 0) send_cmd(CMD_RIGHT);
        else if (strcmp(action, "rotate_left") == 0) send_cmd(CMD_ROTATE_L);
        else if (strcmp(action, "rotate_right") == 0) send_cmd(CMD_ROTATE_R);
        else if (strcmp(action, "stop") == 0) send_cmd(CMD_STOP);
        else if (strcmp(action, "volume") == 0) {
            int v = atoi(value);
            if (v >= 0 && v <= 100) {
                current_volume = v;
                auto* codec = Board::GetInstance().GetAudioCodec();
                if (codec) codec->SetOutputVolume(v);
                ESP_LOGI(TAG, "Volume: %d%%", v);
            }
        }
        else if (strcmp(action, "speed") == 0) {
            int s = atoi(value);
            if (s >= MIN_SPEED && s <= MAX_SPEED) send_cmd(CMD_SET_SPEED, s);
        }
        else if (strcmp(action, "enable") == 0) { send_cmd(CMD_ENABLE); }
        else if (strcmp(action, "disable") == 0) { send_cmd(CMD_DISABLE); }
        else if (strcmp(action, "threshold") == 0) {
            int t = atoi(value);
            if (t >= 5 && t <= 200) {
                us_threshold = t;
                ESP_LOGI(TAG, "US threshold: %dcm", t);
            }
        }
        httpd_resp_set_type(req, "text/plain");
        httpd_resp_sendstr(req, "ok");
        return ESP_OK;
    }
    httpd_resp_set_type(req, "text/plain");
    httpd_resp_sendstr(req, "no action");
    return ESP_OK;
}

static void start_webserver() {
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.stack_size = 8192;
    if (httpd_start(&webserver, &config) == ESP_OK) {
        httpd_uri_t root = {.uri = "/", .method = HTTP_GET, .handler = webui_handler};
        httpd_register_uri_handler(webserver, &root);
        httpd_uri_t status = {.uri = "/status", .method = HTTP_GET, .handler = status_handler};
        httpd_register_uri_handler(webserver, &status);
        httpd_uri_t cmd = {.uri = "/cmd", .method = HTTP_GET, .handler = cmd_handler};
        httpd_register_uri_handler(webserver, &cmd);
        ESP_LOGI(TAG, "WebUI attiva su porta 80");
    }
}

// ============================================================
//  ENZOBOT BOARD
// ============================================================

class EnzoBotBoard : public WifiBoard {
private:
    i2c_master_bus_handle_t i2c_bus_ = nullptr;
    esp_lcd_panel_io_handle_t panel_io_ = nullptr;
    esp_lcd_panel_handle_t panel_ = nullptr;
    Display* display_ = nullptr;
    Button boot_button_;

    void InitI2c() {
        i2c_master_bus_config_t bus_cfg = {};
        bus_cfg.i2c_port = (i2c_port_t)0;
        bus_cfg.sda_io_num = DISPLAY_SDA_PIN;
        bus_cfg.scl_io_num = DISPLAY_SCL_PIN;
        bus_cfg.clk_source = I2C_CLK_SRC_DEFAULT;
        bus_cfg.glitch_ignore_cnt = 7;
        bus_cfg.flags.enable_internal_pullup = 1;
        ESP_ERROR_CHECK(i2c_new_master_bus(&bus_cfg, &i2c_bus_));
    }

    void InitDisplay() {
        esp_lcd_panel_io_i2c_config_t io_cfg = {};
        io_cfg.dev_addr = 0x3C;
        io_cfg.control_phase_bytes = 1;
        io_cfg.dc_bit_offset = 6;
        io_cfg.lcd_cmd_bits = 8;
        io_cfg.lcd_param_bits = 8;
        io_cfg.scl_speed_hz = 400000;
        ESP_ERROR_CHECK(esp_lcd_new_panel_io_i2c_v2(i2c_bus_, &io_cfg, &panel_io_));

        esp_lcd_panel_dev_config_t panel_cfg = {};
        panel_cfg.reset_gpio_num = -1;
        panel_cfg.bits_per_pixel = 1;
        esp_lcd_panel_ssd1306_config_t ssd_cfg = { .height = DISPLAY_HEIGHT };
        panel_cfg.vendor_config = &ssd_cfg;

        esp_err_t ret = esp_lcd_new_panel_ssd1306(panel_io_, &panel_cfg, &panel_);
        if (ret != ESP_OK) { ESP_LOGE(TAG, "OLED SSD1306 non trovato — continuo senza display"); }
        else {
            ret = esp_lcd_panel_reset(panel_);
            if (ret == ESP_OK) ret = esp_lcd_panel_init(panel_);
            if (ret == ESP_OK) {
                esp_lcd_panel_invert_color(panel_, false);
                esp_lcd_panel_disp_on_off(panel_, true);
            } else {
                ESP_LOGE(TAG, "OLED init fallito — display scollegato?");
            }
        }
        // Crea display comunque (XiaoZhi richiede display non-null)
        display_ = new OledDisplay(panel_io_, panel_, DISPLAY_WIDTH, DISPLAY_HEIGHT,
                                    DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y);
    }

public:
    EnzoBotBoard() : boot_button_(BOOT_BUTTON_GPIO) {
        // I2C + OLED
        InitI2c();
        InitDisplay();

        // Motor task: avviato con delay per evitare conflitto LEDC/I2S durante boot
        cmd_queue = xQueueCreate(16, sizeof(RobotCmd));
        xTaskCreatePinnedToCore(motor_task_delayed, "motor", 8192, this, 5, nullptr, 1);

        // Boot button = toggle mute
        boot_button_.OnClick([this]() {
            auto& app = Application::GetInstance();
            app.ToggleChatState();
        });

        // Registra comandi vocali robot
        InitializeTools();

        // Boot sound — aspetta che il device sia in stato idle (server connesso)
        xTaskCreate([](void* p) {
            for (int i = 0; i < 30; i++) {
                vTaskDelay(pdMS_TO_TICKS(1000));
                if (Application::GetInstance().GetDeviceState() == kDeviceStateIdle) break;
            }
            vTaskDelay(pdMS_TO_TICKS(500));  // Breve pausa dopo idle
            extern const char enzobot_opus_start[] asm("_binary_enzobot_opus_start");
            extern const char enzobot_opus_end[] asm("_binary_enzobot_opus_end");
            std::string_view sound(enzobot_opus_start, enzobot_opus_end - enzobot_opus_start);
            Application::GetInstance().PlaySound(sound);
            ESP_LOGI("EnzoBot", "Boot sound played (%d bytes)", (int)(enzobot_opus_end - enzobot_opus_start));
            vTaskDelete(nullptr);
        }, "boot_snd", 6144, nullptr, 2, nullptr);
        ESP_LOGI(TAG, "EnzoBot ready");

        // WebUI + OLED IP — avvia dopo connessione WiFi
        xTaskCreate([](void* p) {
            // Aspetta che l'IP sia assegnato
            esp_netif_ip_info_t ip = {};
            for (int i = 0; i < 30; i++) {
                vTaskDelay(pdMS_TO_TICKS(1000));
                esp_netif_t* netif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
                if (netif && esp_netif_get_ip_info(netif, &ip) == ESP_OK && ip.ip.addr != 0) break;
            }
            start_webserver();

            // Mostra IP sull'OLED dopo attivazione
            if (ip.ip.addr != 0) {
                vTaskDelay(pdMS_TO_TICKS(3000));  // Aspetta che l'attivazione finisca
                char ip_str[40];
                snprintf(ip_str, sizeof(ip_str), "IP: " IPSTR, IP2STR(&ip.ip));
                auto* display = Board::GetInstance().GetDisplay();
                if (display) display->SetStatus(ip_str);
                ESP_LOGI("EnzoBot", "OLED: %s", ip_str);
            }
            vTaskDelete(nullptr);
        }, "webui", 4096, nullptr, 2, nullptr);
    }

    AudioCodec* GetAudioCodec() override {
        // MAX98357A speaker (16-bit, mono left) + INMP441 mic (32-bit, L/R=GND→LEFT)
        static NoAudioCodecSimplex codec(
            AUDIO_INPUT_SAMPLE_RATE, AUDIO_OUTPUT_SAMPLE_RATE,
            AUDIO_I2S_SPK_GPIO_BCLK, AUDIO_I2S_SPK_GPIO_LRCK, AUDIO_I2S_SPK_GPIO_DOUT,
            I2S_STD_SLOT_LEFT,
            AUDIO_I2S_MIC_GPIO_SCK, AUDIO_I2S_MIC_GPIO_WS, AUDIO_I2S_MIC_GPIO_DIN,
            I2S_STD_SLOT_LEFT);
        return &codec;
    }

    Display* GetDisplay() override { return display_; }

    // === MCP TOOLS — Comandi vocali ===
    void InitializeTools() {
        auto& mcp = McpServer::GetInstance();

        mcp.AddTool("self.robot.goto_table",
            "Porta il vassoio al tavolo specificato. Parametro: numero tavolo (1-99).",
            PropertyList({Property("table", kPropertyTypeInteger)}),
            [](const PropertyList& props) -> ReturnValue {
                int t = props["table"].value<int>();
                send_cmd(CMD_GOTO_TABLE, t);
                return std::string("Ok, vado al tavolo ") + std::to_string(t);
            });

        mcp.AddTool("self.robot.goto_kitchen",
            "Torna alla base in cucina.",
            PropertyList(),
            [](const PropertyList& props) -> ReturnValue {
                send_cmd(CMD_GOTO_KITCHEN);
                return std::string("Ok, torno in cucina");
            });

        mcp.AddTool("self.robot.stop",
            "Ferma tutti i motori.",
            PropertyList(),
            [](const PropertyList& props) -> ReturnValue {
                send_cmd(CMD_STOP);
                return std::string("Fermato");
            });

        mcp.AddTool("self.robot.move",
            "Muovi il robot. Azioni: forward, backward, left, right, rotate_left, rotate_right.",
            PropertyList({Property("action", kPropertyTypeString)}),
            [](const PropertyList& props) -> ReturnValue {
                const std::string& action = props["action"].value<std::string>();
                if (action == "forward")            send_cmd(CMD_FORWARD);
                else if (action == "backward")      send_cmd(CMD_BACKWARD);
                else if (action == "left")          send_cmd(CMD_LEFT);
                else if (action == "right")         send_cmd(CMD_RIGHT);
                else if (action == "rotate_left")   send_cmd(CMD_ROTATE_L);
                else if (action == "rotate_right")  send_cmd(CMD_ROTATE_R);
                else return std::string("Direzione non valida");
                return std::string("Mi muovo: ") + action;
            });

        mcp.AddTool("self.robot.speed",
            "Imposta velocita' del robot (60-255).",
            PropertyList({Property("speed", kPropertyTypeInteger)}),
            [](const PropertyList& props) -> ReturnValue {
                int s = props["speed"].value<int>();
                s = s < MIN_SPEED ? MIN_SPEED : (s > MAX_SPEED ? MAX_SPEED : s);
                send_cmd(CMD_SET_SPEED, s);
                return std::string("Velocita': ") + std::to_string(s);
            });

        mcp.AddTool("self.robot.status",
            "Stato robot: distanze sensori, peso vassoio, direzione, inclinazione, velocita', motori attivi.",
            PropertyList(),
            [](const PropertyList& props) -> ReturnValue {
                RobotState snap;
                portENTER_CRITICAL(&robot_state_mux);
                snap = robot_state;
                portEXIT_CRITICAL(&robot_state_mux);
                char b[400];
                snprintf(b, sizeof(b),
                    "Distanze: davanti %dcm, dietro %dcm, sinistra %dcm, destra %dcm. "
                    "Peso vassoio: %.0fg. Direzione: %.0f gradi. "
                    "Inclinazione: %.1f/%.1f. Motori: %s. Velocita': %d. "
                    "Consegne completate: %d. Stato consegna: %s. Tavolo corrente: %d.",
                    snap.dist_front, snap.dist_rear, snap.dist_left, snap.dist_right,
                    snap.weight_grams, snap.heading,
                    snap.pitch, snap.roll,
                    snap.motors_enabled ? "attivi" : "disabilitati",
                    snap.speed_setting,
                    snap.deliveries, snap.delivery_state, snap.current_table);
                return std::string(b);
            });

        mcp.AddTool("self.robot.dance",
            "Fai una danza del cameriere! Giri su te stesso con stile per intrattenere i clienti.",
            PropertyList(),
            [](const PropertyList& props) -> ReturnValue {
                send_cmd(CMD_DANCE);
                return std::string("Ecco la mia danza del cameriere!");
            });

        mcp.AddTool("self.robot.bow",
            "Fai un inchino elegante. Usalo per salutare i clienti o ringraziare per i complimenti.",
            PropertyList(),
            [](const PropertyList& props) -> ReturnValue {
                send_cmd(CMD_BOW);
                return std::string("Inchino di Enzo, al vostro servizio!");
            });

        // === ZOD — K230 Vision Navigation Tools ===

        mcp.AddTool("self.robot.navigate",
            "Navigazione intelligente con visione AI (K230 YOLO). Destinazione: 'table_N' (es. table_3) o 'kitchen'. "
            "Il robot evita ostacoli autonomamente usando computer vision.",
            PropertyList({Property("destination", kPropertyTypeString)}),
            [](const PropertyList& props) -> ReturnValue {
                K230State snap;
                portENTER_CRITICAL(&k230_state_mux);
                snap = k230_state;
                portEXIT_CRITICAL(&k230_state_mux);
                if (!snap.connected)
                    return std::string("K230 non connessa. Uso navigazione manuale.");
                const std::string& dest = props["destination"].value<std::string>();
                if (dest.rfind("table_", 0) == 0) {
                    int t = atoi(dest.c_str() + 6);
                    send_cmd(CMD_NAV_START, t);
                    return std::string("Navigazione AI verso tavolo ") + std::to_string(t) + " avviata!";
                } else if (dest == "kitchen") {
                    send_cmd(CMD_NAV_START, 0);
                    return std::string("Navigazione AI verso cucina avviata!");
                }
                return std::string("Destinazione non valida. Usa 'table_N' o 'kitchen'.");
            });

        mcp.AddTool("self.robot.scan",
            "Scansiona l'ambiente con la camera K230 (YOLO). Rileva persone, tavoli, ostacoli. "
            "Utile per sapere cosa c'e' intorno prima di muoversi.",
            PropertyList(),
            [](const PropertyList& props) -> ReturnValue {
                K230State snap;
                portENTER_CRITICAL(&k230_state_mux);
                snap = k230_state;
                portEXIT_CRITICAL(&k230_state_mux);
                if (!snap.connected)
                    return std::string("K230 non connessa. Scansione non disponibile.");
                send_cmd(CMD_SCAN);
                vTaskDelay(pdMS_TO_TICKS(1500));
                portENTER_CRITICAL(&k230_state_mux);
                snap = k230_state;
                portEXIT_CRITICAL(&k230_state_mux);
                char buf[512];
                int pos = snprintf(buf, sizeof(buf), "Scansione: %d oggetti. ", snap.num_objects);
                for (int i = 0; i < snap.num_objects && pos < 480; i++) {
                    pos += snprintf(buf + pos, sizeof(buf) - pos, "[%s %d%%] ",
                        snap.objects[i].label, snap.objects[i].confidence);
                }
                if (snap.scan_clear_path) pos += snprintf(buf + pos, sizeof(buf) - pos, "Percorso libero.");
                else pos += snprintf(buf + pos, sizeof(buf) - pos, "Ostacoli nel percorso.");
                return std::string(buf);
            });

        mcp.AddTool("self.robot.nav_status",
            "Stato della navigazione AI: progresso, ostacoli, K230 online/offline.",
            PropertyList(),
            [](const PropertyList& props) -> ReturnValue {
                RobotState rsnap;
                K230State ksnap;
                portENTER_CRITICAL(&robot_state_mux);
                rsnap = robot_state;
                portEXIT_CRITICAL(&robot_state_mux);
                portENTER_CRITICAL(&k230_state_mux);
                ksnap = k230_state;
                portEXIT_CRITICAL(&k230_state_mux);
                char buf[300];
                snprintf(buf, sizeof(buf),
                    "K230: %s. Navigazione: %s (%d%%). Tavolo: %d. "
                    "Oggetti rilevati: %d. Ostacolo visivo: %s. "
                    "Consegne: %d. FW K230: %s",
                    ksnap.connected ? "online" : "offline",
                    nav_state_str(rsnap.nav_state), rsnap.nav_progress,
                    rsnap.current_table,
                    ksnap.num_objects,
                    ksnap.vision_obstacle ? "si" : "no",
                    rsnap.deliveries,
                    ksnap.firmware_ver[0] ? ksnap.firmware_ver : "n/a");
                return std::string(buf);
            });

        mcp.AddTool("self.robot.nav_abort",
            "Annulla la navigazione in corso. Ferma i motori immediatamente.",
            PropertyList(),
            [](const PropertyList& props) -> ReturnValue {
                send_cmd(CMD_NAV_ABORT);
                return std::string("Navigazione annullata. Motori fermi.");
            });

        ESP_LOGI(TAG, "12 MCP tools registrati [ZOD]");
    }
};

DECLARE_BOARD(EnzoBotBoard);
