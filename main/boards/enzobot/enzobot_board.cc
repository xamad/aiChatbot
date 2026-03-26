/**
 * enzobot_board.cc — EnzoBot Custom Board per Xiaozhi ESP32
 *
 * Core 0: Xiaozhi (audio, WiFi, LLM, wake word, OLED)
 * Core 1: Task motori (L298N, sensori, UART K230, MPU6050)
 *
 * Basato su bread-compact-wifi come riferimento per OLED + I2S simplex.
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

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

#include <cstring>
#include <cmath>
#include <string>

#define TAG "EnzoBot"

// ============================================================
//  Comandi robot (coda thread-safe Core0 -> Core1)
// ============================================================

enum RobotCmdType {
    CMD_STOP = 0, CMD_FORWARD, CMD_BACKWARD,
    CMD_LEFT, CMD_RIGHT, CMD_ROTATE_L, CMD_ROTATE_R,
    CMD_SET_SPEED, CMD_GOTO_TABLE, CMD_GOTO_KITCHEN,
    CMD_ENABLE, CMD_DISABLE, CMD_BUZZER,
};

struct RobotCmd {
    RobotCmdType type;
    int value;
};

struct RobotState {
    int dist_rear = 999, dist_left = 999, dist_right = 999;
    int speed_left = 0, speed_right = 0;
    float weight_grams = 0;
    bool motors_enabled = true;
    char delivery_state[16] = "idle";
    int current_table = 0;
    int deliveries = 0;
    float heading = 0, pitch = 0, roll = 0;
    bool tilted = false, mpu_present = false;
};

static QueueHandle_t cmd_queue = nullptr;
static volatile RobotState robot_state = {};

// ============================================================
//  MOTORI L298N (2 board separate)
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

static void set_motors(int left, int right) {
    gpio_set_level(MOT_L_IN1, left > 0 ? 1 : 0);
    gpio_set_level(MOT_L_IN2, left < 0 ? 1 : 0);
    ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, abs(left));
    ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);

    gpio_set_level(MOT_R_IN1, right > 0 ? 1 : 0);
    gpio_set_level(MOT_R_IN2, right < 0 ? 1 : 0);
    ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_1, abs(right));
    ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_1);

    ((RobotState&)robot_state).speed_left = left;
    ((RobotState&)robot_state).speed_right = right;
}

// ============================================================
//  ULTRASUONI (3x HC-SR04, auto-detect)
// ============================================================

struct USSensor { gpio_num_t trig, echo; bool present; int dist; };
static USSensor us[3] = {
    {US_REAR_TRIG, US_REAR_ECHO, false, 999},
    {US_LEFT_TRIG, US_LEFT_ECHO, false, 999},
    {US_RIGHT_TRIG, US_RIGHT_ECHO, false, 999},
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

static void init_us() {
    const char* names[] = {"REAR", "LEFT", "RIGHT"};
    for (int i = 0; i < 3; i++) {
        gpio_set_direction(us[i].trig, GPIO_MODE_OUTPUT);
        gpio_set_direction(us[i].echo, GPIO_MODE_INPUT);
        for (int t = 0; t < 3 && !us[i].present; t++) {
            if (read_us_one(us[i].trig, us[i].echo) < 999) us[i].present = true;
            vTaskDelay(pdMS_TO_TICKS(30));
        }
        ESP_LOGI(TAG, "US %s: %s", names[i], us[i].present ? "OK" : "---");
    }
}

static void read_us_round() {
    static int cur = 0;
    for (int a = 0; a < 3; a++) {
        if (us[cur].present) {
            us[cur].dist = read_us_one(us[cur].trig, us[cur].echo);
            break;
        }
        cur = (cur + 1) % 3;
    }
    cur = (cur + 1) % 3;
    ((RobotState&)robot_state).dist_rear  = us[0].present ? us[0].dist : 999;
    ((RobotState&)robot_state).dist_left  = us[1].present ? us[1].dist : 999;
    ((RobotState&)robot_state).dist_right = us[2].present ? us[2].dist : 999;
}

// ============================================================
//  MPU6050 — TODO fase 2 (richiede i2c_master nuovo driver)
// ============================================================

// MPU6050 sara' aggiunto quando il sensore sara' disponibile.
// Usera' il bus I2C condiviso con OLED (GPIO 8/9, addr 0x68).

// ============================================================
//  UART K230
// ============================================================

static bool k230_ok = false;

static void init_k230() {
    uart_config_t cfg = {};
    cfg.baud_rate = K230_BAUD;
    cfg.data_bits = UART_DATA_8_BITS;
    cfg.parity = UART_PARITY_DISABLE;
    cfg.stop_bits = UART_STOP_BITS_1;
    cfg.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    uart_param_config(UART_NUM_1, &cfg);
    uart_set_pin(UART_NUM_1, (int)K230_TX_PIN, (int)K230_RX_PIN, -1, -1);
    uart_driver_install(UART_NUM_1, 512, 512, 0, nullptr, 0);

    const char* ping = "{\"cmd\":\"ping\"}\n";
    uart_write_bytes(UART_NUM_1, ping, strlen(ping));
    vTaskDelay(pdMS_TO_TICKS(500));
    size_t len = 0;
    uart_get_buffered_data_len(UART_NUM_1, &len);
    k230_ok = (len > 0);
    uart_flush(UART_NUM_1);
    ESP_LOGI(TAG, "K230: %s", k230_ok ? "OK" : "---");
}

static void k230_send(const char* json) {
    if (!k230_ok) return;
    uart_write_bytes(UART_NUM_1, json, strlen(json));
    uart_write_bytes(UART_NUM_1, "\n", 1);
}

static void k230_send_sensors() {
    if (!k230_ok) return;
    char buf[256];
    snprintf(buf, sizeof(buf),
        "{\"dR\":%d,\"dL\":%d,\"dRt\":%d,\"spd\":%d,"
        "\"sL\":%d,\"sR\":%d,\"en\":%d,\"hdg\":%.1f}\n",
        robot_state.dist_rear, robot_state.dist_left, robot_state.dist_right,
        CRUISE_SPEED, robot_state.speed_left, robot_state.speed_right,
        robot_state.motors_enabled ? 1 : 0, robot_state.heading);
    uart_write_bytes(UART_NUM_1, buf, strlen(buf));
}

// ============================================================
//  MOTOR TASK — Core 1
// ============================================================

static void motor_task(void* arg) {
    ESP_LOGI(TAG, "Motor task su Core %d", xPortGetCoreID());

    // Init motori (non blocca, solo GPIO config)
    init_motors();
    ESP_LOGI(TAG, "Motori OK");

    // Buzzer e LED (skip se GPIO_NUM_NC — PSRAM octal usa GPIO33-37)
    if (BUZZER_PIN != GPIO_NUM_NC) gpio_set_direction(BUZZER_PIN, GPIO_MODE_OUTPUT);
    if (LED_STATUS_PIN != GPIO_NUM_NC) gpio_set_direction(LED_STATUS_PIN, GPIO_MODE_OUTPUT);
    if (LED_STATUS_PIN != GPIO_NUM_NC) gpio_set_level(LED_STATUS_PIN, 1);
    ESP_LOGI(TAG, "GPIO OK");

    // Ultrasuoni: skip auto-detect per ora, attiva lazy nel loop
    // (evita blocco da pulseIn su sensori non connessi)
    ESP_LOGI(TAG, "Sensori: auto-detect disabilitato (nessuno connesso)");

    // K230: skip init, attiva quando collegata
    ESP_LOGI(TAG, "K230: skip (non collegata)");

    ESP_LOGI(TAG, "Motor task pronto!");

    int spd = CRUISE_SPEED;
    uint32_t last_us = 0, last_k230 = 0;
    RobotCmd cmd;

    while (true) {
        uint32_t now = xTaskGetTickCount() * portTICK_PERIOD_MS;

        // Comandi dalla coda
        while (xQueueReceive(cmd_queue, &cmd, 0) == pdTRUE) {
            switch (cmd.type) {
                case CMD_STOP:      set_motors(0, 0); break;
                case CMD_FORWARD:   set_motors(spd, spd); break;
                case CMD_BACKWARD:  set_motors(-spd, -spd); break;
                case CMD_LEFT:      set_motors(-spd/2, spd); break;
                case CMD_RIGHT:     set_motors(spd, -spd/2); break;
                case CMD_ROTATE_L:  set_motors(-spd, spd); break;
                case CMD_ROTATE_R:  set_motors(spd, -spd); break;
                case CMD_SET_SPEED: spd = cmd.value; break;
                case CMD_GOTO_TABLE: {
                    char b[64]; snprintf(b, 64, "{\"cmd\":\"goto_table\",\"table\":%d}", cmd.value);
                    k230_send(b);
                    ((RobotState&)robot_state).current_table = cmd.value;
                    strncpy(((RobotState&)robot_state).delivery_state, "delivering", 15);
                    break;
                }
                case CMD_GOTO_KITCHEN: k230_send("{\"cmd\":\"goto_kitchen\"}"); break;
                case CMD_ENABLE:  ((RobotState&)robot_state).motors_enabled = true; break;
                case CMD_DISABLE: set_motors(0,0); ((RobotState&)robot_state).motors_enabled = false; break;
                case CMD_BUZZER:
                    if (BUZZER_PIN != GPIO_NUM_NC) {
                        for (int i = 0; i < cmd.value; i++) {
                            gpio_set_level(BUZZER_PIN, 1); esp_rom_delay_us(500);
                            gpio_set_level(BUZZER_PIN, 0); esp_rom_delay_us(500);
                        }
                    }
                    break;
                default: break;
            }
        }

        // Ultrasuoni: disabilitati finche' non inizializzati
        // TODO: aggiungere comando MCP per attivare sensori runtime

        // K230: disabilitata finche' non inizializzata
        // TODO: aggiungere init K230 lazy quando collegata

        vTaskDelay(pdMS_TO_TICKS(50));  // yield per watchdog IDLE1
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

        ESP_ERROR_CHECK(esp_lcd_new_panel_ssd1306(panel_io_, &panel_cfg, &panel_));
        ESP_ERROR_CHECK(esp_lcd_panel_reset(panel_));
        ESP_ERROR_CHECK(esp_lcd_panel_init(panel_));
        ESP_ERROR_CHECK(esp_lcd_panel_invert_color(panel_, false));
        ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel_, true));

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
        xTaskCreatePinnedToCore(motor_task_delayed, "motor", 6144, this, 5, nullptr, 1);

        // Boot button = toggle mute
        boot_button_.OnClick([this]() {
            auto& app = Application::GetInstance();
            app.ToggleChatState();
        });

        // Registra comandi vocali robot
        InitializeTools();

        // TODO: boot sound (enzobot.ogg va aggiunto come EMBED_FILES nel CMakeLists)
        ESP_LOGI(TAG, "EnzoBot ready (boot sound skipped)");
    }

    AudioCodec* GetAudioCodec() override {
        // MAX98357A speaker (16-bit, mono left) + INMP441 mic (32-bit)
        // INMP441: L/R=GND→LEFT, L/R=VCC→RIGHT. Try BOTH via slot mask.
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
            "Stato robot: distanze sensori, peso vassoio, direzione, inclinazione.",
            PropertyList(),
            [](const PropertyList& props) -> ReturnValue {
                char b[300];
                snprintf(b, sizeof(b),
                    "Distanze: dietro %dcm, sinistra %dcm, destra %dcm. "
                    "Peso: %.0fg. Direzione: %.0f gradi. "
                    "Inclinazione: %.1f/%.1f. Consegne: %d. Stato: %s.",
                    robot_state.dist_rear, robot_state.dist_left, robot_state.dist_right,
                    robot_state.weight_grams, robot_state.heading,
                    robot_state.pitch, robot_state.roll,
                    robot_state.deliveries, robot_state.delivery_state);
                return std::string(b);
            });

        ESP_LOGI(TAG, "6 MCP tools registrati");
    }
};

DECLARE_BOARD(EnzoBotBoard);
