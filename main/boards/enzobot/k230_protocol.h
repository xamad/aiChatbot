/**
 * k230_protocol.h — Protocollo UART bidirezionale ESP32 ↔ K230 Yahboom
 * EnzoBot ZOD — Navigazione via Computer Vision (YOLO, no ArUco/line follow)
 *
 * Messaggi: JSON newline-delimited su UART1 a 115200 baud
 *
 * ESP32 → K230:
 *   {"cmd":"navigate","dest":"table_3"}
 *   {"cmd":"navigate","dest":"kitchen"}
 *   {"cmd":"scan"}
 *   {"cmd":"abort"}
 *   {"cmd":"sensors","dF":25,"dR":100,"dL":40,"dRt":50}
 *   {"cmd":"config","avoid_dist":30,"speed":"slow"}
 *   {"cmd":"ping"}
 *
 * K230 → ESP32:
 *   {"type":"nav_status","state":"navigating","progress":45,"target":"table_3"}
 *   {"type":"detections","objects":[{"label":"person","x":120,"y":80,"w":50,"h":120,"conf":85}]}
 *   {"type":"obstacle","detected":true,"dist":25,"dir":"front"}
 *   {"type":"motor_cmd","left":150,"right":150,"dur":500}
 *   {"type":"scan_result","objects":[...],"clear":true}
 *   {"type":"heartbeat","ver":"1.0","up":3600}
 *   {"type":"pong"}
 */

#ifndef _K230_PROTOCOL_H_
#define _K230_PROTOCOL_H_

#include <driver/uart.h>
#include <esp_log.h>
#include <cstring>
#include <cmath>
#include <algorithm>
#include "cJSON.h"  // ESP-IDF json component
#include "freertos/FreeRTOS.h"
#include "freertos/portmacro.h"

#define K230_TAG "K230"
#define K230_RX_BUF_SIZE 1024
#define K230_MAX_DETECTIONS 8

// ============================================================
//  Navigation State Machine
// ============================================================

enum NavState {
    NAV_IDLE = 0,
    NAV_NAVIGATING,
    NAV_ARRIVED,
    NAV_RETURNING,
    NAV_OBSTACLE,
    NAV_ERROR
};

static const char* nav_state_str(NavState s) {
    switch (s) {
        case NAV_IDLE:       return "idle";
        case NAV_NAVIGATING: return "navigating";
        case NAV_ARRIVED:    return "arrived";
        case NAV_RETURNING:  return "returning";
        case NAV_OBSTACLE:   return "obstacle";
        case NAV_ERROR:      return "error";
        default:             return "unknown";
    }
}

// ============================================================
//  K230 Vision Detection
// ============================================================

struct K230Detection {
    char label[16];
    int x, y, w, h;
    int confidence;
};

// ============================================================
//  K230 State (read from UART, written under spinlock)
// ============================================================

struct K230State {
    bool connected = false;
    NavState nav_state = NAV_IDLE;
    int nav_progress = 0;
    char nav_target[32] = "";

    // Vision
    int num_objects = 0;
    K230Detection objects[K230_MAX_DETECTIONS];
    bool vision_obstacle = false;
    int vision_obstacle_dist = 999;
    char vision_obstacle_dir[8] = "";

    // Motor command from K230 (for visual navigation)
    bool motor_cmd_pending = false;
    int motor_left = 0, motor_right = 0;
    int motor_dur_ms = 0;

    // Scan
    bool scan_ready = false;
    bool scan_clear_path = false;

    // Health
    uint32_t last_msg_ms = 0;
    uint32_t last_heartbeat_ms = 0;
    char firmware_ver[16] = "";
};

// ============================================================
//  K230 UART Controller
// ============================================================

class K230Uart {
public:
    bool ok = false;

    void Init(gpio_num_t tx_pin, gpio_num_t rx_pin, int baud) {
        uart_config_t cfg = {};
        cfg.baud_rate = baud;
        cfg.data_bits = UART_DATA_8_BITS;
        cfg.parity = UART_PARITY_DISABLE;
        cfg.stop_bits = UART_STOP_BITS_1;
        cfg.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
        uart_param_config(UART_NUM_1, &cfg);
        uart_set_pin(UART_NUM_1, (int)tx_pin, (int)rx_pin, -1, -1);
        uart_driver_install(UART_NUM_1, 2048, 512, 0, nullptr, 0);

        // Ping K230
        Send("{\"cmd\":\"ping\"}");
        vTaskDelay(pdMS_TO_TICKS(500));
        size_t len = 0;
        uart_get_buffered_data_len(UART_NUM_1, &len);
        ok = (len > 0);
        if (ok) {
            // Read and discard ping response
            uart_flush(UART_NUM_1);
            ESP_LOGI(K230_TAG, "K230 connessa! (%d bytes risposta)", (int)len);
        } else {
            ESP_LOGI(K230_TAG, "K230 non trovata (skip)");
        }
    }

    void Send(const char* json) {
        if (!ok) return;
        uart_write_bytes(UART_NUM_1, json, strlen(json));
        uart_write_bytes(UART_NUM_1, "\n", 1);
    }

    void SendNavigate(const char* dest) {
        char buf[64];
        snprintf(buf, sizeof(buf), "{\"cmd\":\"navigate\",\"dest\":\"%s\"}", dest);
        Send(buf);
    }

    void SendSensors(int dF, int dR, int dL, int dRt) {
        char buf[100];
        snprintf(buf, sizeof(buf), "{\"cmd\":\"sensors\",\"dF\":%d,\"dR\":%d,\"dL\":%d,\"dRt\":%d}", dF, dR, dL, dRt);
        Send(buf);
    }

    // Receive and parse all pending UART data.
    // Calls ProcessMessage for each complete JSON line.
    // Must be called from motor_task (Core 1).
    void Receive(K230State& state, portMUX_TYPE& mux) {
        size_t available = 0;
        uart_get_buffered_data_len(UART_NUM_1, &available);
        if (available == 0) return;

        int space = K230_RX_BUF_SIZE - rx_pos_ - 1;
        if (space <= 0) {
            ESP_LOGW(K230_TAG, "RX buffer full (%d bytes), no newline — reset", rx_pos_);
            rx_pos_ = 0;
            space = K230_RX_BUF_SIZE - 1;
        }

        int len = uart_read_bytes(UART_NUM_1, (uint8_t*)(rx_buf_ + rx_pos_),
                                  std::min((int)available, space), pdMS_TO_TICKS(10));
        if (len <= 0) return;
        rx_pos_ += len;
        rx_buf_[rx_pos_] = '\0';

        // Process complete lines
        char* start = rx_buf_;
        char* nl;
        while ((nl = strchr(start, '\n')) != nullptr) {
            *nl = '\0';
            if (nl > start) ProcessMessage(start, state, mux);
            start = nl + 1;
        }
        int remaining = rx_pos_ - (int)(start - rx_buf_);
        if (remaining > 0 && start != rx_buf_) memmove(rx_buf_, start, remaining);
        rx_pos_ = remaining;
    }

private:
    char rx_buf_[K230_RX_BUF_SIZE] = {};
    int rx_pos_ = 0;

    // Helper: safe string copy with guaranteed null termination
    static void safe_strcpy(char* dst, const char* src, size_t dst_size) {
        if (!src || dst_size == 0) return;
        strncpy(dst, src, dst_size - 1);
        dst[dst_size - 1] = '\0';
    }

    // Helper: get int from cJSON, default 0
    static int json_int(cJSON* parent, const char* key) {
        cJSON* item = cJSON_GetObjectItem(parent, key);
        return item ? item->valueint : 0;
    }

    void ProcessMessage(const char* json_str, K230State& state, portMUX_TYPE& mux) {
        cJSON* root = cJSON_Parse(json_str);
        if (!root) {
            ESP_LOGW(K230_TAG, "Bad JSON: %.60s", json_str);
            return;
        }

        const char* type = cJSON_GetStringValue(cJSON_GetObjectItem(root, "type"));
        if (!type) { cJSON_Delete(root); return; }

        uint32_t now = xTaskGetTickCount() * portTICK_PERIOD_MS;

        // Parse EVERYTHING into locals first (outside critical section)
        // Then copy into state under the lock (fast memcpy only)

        if (strcmp(type, "nav_status") == 0) {
            NavState ns = NAV_IDLE;
            int progress = 0;
            char target[32] = {};
            const char* s = cJSON_GetStringValue(cJSON_GetObjectItem(root, "state"));
            if (s) {
                if (strcmp(s, "idle") == 0)            ns = NAV_IDLE;
                else if (strcmp(s, "navigating") == 0)  ns = NAV_NAVIGATING;
                else if (strcmp(s, "arrived") == 0)     ns = NAV_ARRIVED;
                else if (strcmp(s, "returning") == 0)   ns = NAV_RETURNING;
                else if (strcmp(s, "obstacle") == 0)    ns = NAV_OBSTACLE;
                else if (strcmp(s, "error") == 0)       ns = NAV_ERROR;
            }
            progress = json_int(root, "progress");
            const char* t = cJSON_GetStringValue(cJSON_GetObjectItem(root, "target"));
            if (t) safe_strcpy(target, t, sizeof(target));

            portENTER_CRITICAL(&mux);
            state.last_msg_ms = now;
            state.nav_state = ns;
            state.nav_progress = progress;
            memcpy(state.nav_target, target, sizeof(state.nav_target));
            portEXIT_CRITICAL(&mux);
        }
        else if (strcmp(type, "detections") == 0) {
            K230Detection local_objs[K230_MAX_DETECTIONS] = {};
            int n = 0;
            cJSON* objs = cJSON_GetObjectItem(root, "objects");
            if (cJSON_IsArray(objs)) {
                n = std::min(cJSON_GetArraySize(objs), K230_MAX_DETECTIONS);
                for (int i = 0; i < n; i++) {
                    cJSON* o = cJSON_GetArrayItem(objs, i);
                    const char* lbl = cJSON_GetStringValue(cJSON_GetObjectItem(o, "label"));
                    if (lbl) safe_strcpy(local_objs[i].label, lbl, sizeof(local_objs[i].label));
                    local_objs[i].x = json_int(o, "x");
                    local_objs[i].y = json_int(o, "y");
                    local_objs[i].w = json_int(o, "w");
                    local_objs[i].h = json_int(o, "h");
                    local_objs[i].confidence = json_int(o, "conf");
                }
            }
            portENTER_CRITICAL(&mux);
            state.last_msg_ms = now;
            memcpy(state.objects, local_objs, sizeof(local_objs));
            state.num_objects = n;
            portEXIT_CRITICAL(&mux);
        }
        else if (strcmp(type, "obstacle") == 0) {
            bool det = cJSON_IsTrue(cJSON_GetObjectItem(root, "detected"));
            int dist = json_int(root, "dist");
            char dir[8] = {};
            const char* d = cJSON_GetStringValue(cJSON_GetObjectItem(root, "dir"));
            if (d) safe_strcpy(dir, d, sizeof(dir));

            portENTER_CRITICAL(&mux);
            state.last_msg_ms = now;
            state.vision_obstacle = det;
            state.vision_obstacle_dist = dist > 0 ? dist : 999;
            memcpy(state.vision_obstacle_dir, dir, sizeof(state.vision_obstacle_dir));
            portEXIT_CRITICAL(&mux);
        }
        else if (strcmp(type, "motor_cmd") == 0) {
            int ml = json_int(root, "left");
            int mr = json_int(root, "right");
            int md = json_int(root, "dur");

            portENTER_CRITICAL(&mux);
            state.last_msg_ms = now;
            state.motor_cmd_pending = true;
            state.motor_left = ml;
            state.motor_right = mr;
            state.motor_dur_ms = md;
            portEXIT_CRITICAL(&mux);
        }
        else if (strcmp(type, "scan_result") == 0) {
            bool clear = cJSON_IsTrue(cJSON_GetObjectItem(root, "clear"));
            K230Detection local_objs[K230_MAX_DETECTIONS] = {};
            int n = 0;
            cJSON* objs = cJSON_GetObjectItem(root, "objects");
            if (cJSON_IsArray(objs)) {
                n = std::min(cJSON_GetArraySize(objs), K230_MAX_DETECTIONS);
                for (int i = 0; i < n; i++) {
                    cJSON* o = cJSON_GetArrayItem(objs, i);
                    const char* lbl = cJSON_GetStringValue(cJSON_GetObjectItem(o, "label"));
                    if (lbl) safe_strcpy(local_objs[i].label, lbl, sizeof(local_objs[i].label));
                    local_objs[i].confidence = json_int(o, "conf");
                }
            }
            portENTER_CRITICAL(&mux);
            state.last_msg_ms = now;
            state.scan_ready = true;
            state.scan_clear_path = clear;
            memcpy(state.objects, local_objs, sizeof(local_objs));
            state.num_objects = n;
            portEXIT_CRITICAL(&mux);
        }
        else if (strcmp(type, "heartbeat") == 0) {
            char ver[16] = {};
            const char* v = cJSON_GetStringValue(cJSON_GetObjectItem(root, "ver"));
            if (v) safe_strcpy(ver, v, sizeof(ver));

            portENTER_CRITICAL(&mux);
            state.last_msg_ms = now;
            state.last_heartbeat_ms = now;
            state.connected = true;
            memcpy(state.firmware_ver, ver, sizeof(state.firmware_ver));
            portEXIT_CRITICAL(&mux);
        }
        else if (strcmp(type, "pong") == 0) {
            portENTER_CRITICAL(&mux);
            state.last_msg_ms = now;
            state.connected = true;
            state.last_heartbeat_ms = now;
            portEXIT_CRITICAL(&mux);
        }

        cJSON_Delete(root);
    }
};

#endif // _K230_PROTOCOL_H_
