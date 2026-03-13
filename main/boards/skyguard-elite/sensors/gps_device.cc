#include "gps_device.h"
#include <esp_log.h>
#include <cstring>
#include <cstdlib>
#include <cmath>
#include <ctime>

#define TAG "GPS"

GpsDevice::GpsDevice(uart_port_t uart, gpio_num_t tx_pin, gpio_num_t rx_pin,
                     int baud, int buf_size)
    : uart_(uart), tx_pin_(tx_pin), rx_pin_(rx_pin),
      baud_(baud), buf_size_(buf_size) {
}

GpsDevice::~GpsDevice() {
    StopTask();
}

bool GpsDevice::Initialize() {
    uart_config_t uart_config = {
        .baud_rate = baud_,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .rx_flow_ctrl_thresh = 0,
        .source_clk = UART_SCLK_DEFAULT,
    };

    esp_err_t ret = uart_driver_install(uart_, buf_size_ * 2, 0, 0, nullptr, 0);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "UART driver install failed: %s", esp_err_to_name(ret));
        return false;
    }

    ret = uart_param_config(uart_, &uart_config);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "UART param config failed");
        return false;
    }

    ret = uart_set_pin(uart_, tx_pin_, rx_pin_, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "UART set pin failed");
        return false;
    }

    ESP_LOGI(TAG, "GPS UART initialized (port=%d, TX=%d, RX=%d, baud=%d)",
             uart_, tx_pin_, rx_pin_, baud_);
    return true;
}

void GpsDevice::StartTask() {
    if (task_handle_) return;
    running_ = true;
    xTaskCreate(UartTask, "gps_task", 4096, this, 5, &task_handle_);
    ESP_LOGI(TAG, "GPS task started");
}

void GpsDevice::StopTask() {
    running_ = false;
    if (task_handle_) {
        vTaskDelay(pdMS_TO_TICKS(100));
        vTaskDelete(task_handle_);
        task_handle_ = nullptr;
    }
}

void GpsDevice::UartTask(void* param) {
    GpsDevice* gps = (GpsDevice*)param;
    uint8_t* buf = (uint8_t*)malloc(gps->buf_size_);
    char sentence[256];
    int sentence_len = 0;

    while (gps->running_) {
        int len = uart_read_bytes(gps->uart_, buf, gps->buf_size_, pdMS_TO_TICKS(100));
        if (len > 0) {
            for (int i = 0; i < len; i++) {
                char c = (char)buf[i];
                if (c == '$') {
                    sentence_len = 0;
                }
                if (sentence_len < 255) {
                    sentence[sentence_len++] = c;
                }
                if (c == '\n' && sentence_len > 0) {
                    sentence[sentence_len] = '\0';
                    gps->ProcessNmea(sentence);
                    sentence_len = 0;
                }
            }
        }
    }

    free(buf);
    vTaskDelete(nullptr);
}

bool GpsDevice::ValidateChecksum(const char* sentence) {
    if (sentence[0] != '$') return false;

    const char* star = strchr(sentence, '*');
    if (!star) return false;

    uint8_t calc = 0;
    for (const char* p = sentence + 1; p < star; p++) {
        calc ^= (uint8_t)*p;
    }

    uint8_t expected = (uint8_t)strtol(star + 1, nullptr, 16);
    return calc == expected;
}

void GpsDevice::ProcessNmea(const char* sentence) {
    if (!ValidateChecksum(sentence)) return;

    if (strncmp(sentence + 3, "GGA", 3) == 0) {
        ParseGGA(sentence);
    } else if (strncmp(sentence + 3, "RMC", 3) == 0) {
        ParseRMC(sentence);
    }
}

float GpsDevice::ParseCoord(const char* field, char direction) {
    if (!field || field[0] == '\0') return 0;

    double raw = atof(field);
    int degrees = (int)(raw / 100);
    double minutes = raw - degrees * 100;
    float result = (float)(degrees + minutes / 60.0);

    if (direction == 'S' || direction == 'W') result = -result;
    return result;
}

void GpsDevice::ParseGGA(const char* sentence) {
    // $GPGGA,hhmmss.ss,lat,N/S,lon,E/W,fix,sats,hdop,alt,M,...
    char buf[256];
    strncpy(buf, sentence, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = '\0';

    char* fields[15] = {};
    int field_count = 0;
    char* p = buf;
    while (*p && field_count < 15) {
        fields[field_count++] = p;
        p = strchr(p, ',');
        if (p) *p++ = '\0';
        else break;
    }

    if (field_count < 10) return;

    // Fix quality
    int fix = atoi(fields[6]);
    has_fix_ = (fix > 0);

    if (has_fix_) {
        latitude_ = ParseCoord(fields[2], fields[3][0]);
        longitude_ = ParseCoord(fields[4], fields[5][0]);
        satellites_ = (uint8_t)atoi(fields[7]);
        hdop_ = atof(fields[8]);
        altitude_ = atof(fields[9]);

        ESP_LOGD(TAG, "Fix: %.6f, %.6f, alt=%.1fm, sats=%d",
                 latitude_, longitude_, altitude_, satellites_);
    }
}

void GpsDevice::ParseRMC(const char* sentence) {
    // $GPRMC,hhmmss.ss,A,lat,N/S,lon,E/W,speed,course,ddmmyy,...
    char buf[256];
    strncpy(buf, sentence, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = '\0';

    char* fields[15] = {};
    int field_count = 0;
    char* p = buf;
    while (*p && field_count < 15) {
        fields[field_count++] = p;
        p = strchr(p, ',');
        if (p) *p++ = '\0';
        else break;
    }

    if (field_count < 10) return;

    // Status
    if (fields[2][0] != 'A') {
        has_fix_ = false;
        return;
    }

    // Time: hhmmss.ss
    if (strlen(fields[1]) >= 6) {
        hour_ = (fields[1][0] - '0') * 10 + (fields[1][1] - '0');
        minute_ = (fields[1][2] - '0') * 10 + (fields[1][3] - '0');
        second_ = (fields[1][4] - '0') * 10 + (fields[1][5] - '0');
    }

    // Date: ddmmyy
    if (strlen(fields[9]) >= 6) {
        day_ = (fields[9][0] - '0') * 10 + (fields[9][1] - '0');
        month_ = (fields[9][2] - '0') * 10 + (fields[9][3] - '0');
        year_ = 2000 + (fields[9][4] - '0') * 10 + (fields[9][5] - '0');
    }

    // Position
    latitude_ = ParseCoord(fields[3], fields[4][0]);
    longitude_ = ParseCoord(fields[5], fields[6][0]);
    has_fix_ = true;
}

uint32_t GpsDevice::GetUnixTime() const {
    if (year_ == 0) return 0;

    struct tm t = {};
    t.tm_year = year_ - 1900;
    t.tm_mon = month_ - 1;
    t.tm_mday = day_;
    t.tm_hour = hour_;
    t.tm_min = minute_;
    t.tm_sec = second_;

    return (uint32_t)mktime(&t);
}

double GpsDevice::GetJulianDate() const {
    if (year_ == 0) return 0;

    int y = year_;
    int m = month_;
    if (m <= 2) { y--; m += 12; }

    int A = y / 100;
    int B = 2 - A + A / 4;

    double JD = (int)(365.25 * (y + 4716)) +
                (int)(30.6001 * (m + 1)) +
                day_ + B - 1524.5;

    // Add fractional day
    JD += (hour_ + minute_ / 60.0 + second_ / 3600.0) / 24.0;

    return JD;
}

double GpsDevice::GetJulianDate0() const {
    // Julian Date at 0h UT
    if (year_ == 0) return 0;

    int y = year_;
    int m = month_;
    if (m <= 2) { y--; m += 12; }

    int A = y / 100;
    int B = 2 - A + A / 4;

    return (int)(365.25 * (y + 4716)) +
           (int)(30.6001 * (m + 1)) +
           day_ + B - 1524.5;
}

double GpsDevice::GetGMST() const {
    // Greenwich Mean Sidereal Time in degrees
    double JD = GetJulianDate();
    if (JD == 0) return 0;

    double T = (JD - 2451545.0) / 36525.0;
    double GMST = 280.46061837 +
                  360.98564736629 * (JD - 2451545.0) +
                  0.000387933 * T * T -
                  T * T * T / 38710000.0;

    return fmod(GMST, 360.0);
}

float GpsDevice::GetLST() const {
    // Local Sidereal Time in hours
    double gmst = GetGMST();
    if (gmst == 0) return 0;

    double lst = gmst + (double)longitude_;
    lst = fmod(lst, 360.0);
    if (lst < 0) lst += 360.0;

    return (float)(lst / 15.0);  // Convert degrees to hours
}
