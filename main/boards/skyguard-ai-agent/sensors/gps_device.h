#ifndef GPS_DEVICE_H
#define GPS_DEVICE_H

#include <driver/uart.h>
#include <driver/gpio.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <cstdint>

class GpsDevice {
public:
    GpsDevice(uart_port_t uart, gpio_num_t tx_pin, gpio_num_t rx_pin,
              int baud = 9600, int buf_size = 1024);
    ~GpsDevice();

    bool Initialize();
    void StartTask();
    void StopTask();

    // Position
    float GetLatitude() const { return latitude_; }
    float GetLongitude() const { return longitude_; }
    float GetAltitude() const { return altitude_; }
    bool HasFix() const { return has_fix_; }
    uint8_t GetSatellites() const { return satellites_; }
    float GetHdop() const { return hdop_; }

    // Time (UTC from GPS)
    int GetYear() const { return year_; }
    int GetMonth() const { return month_; }
    int GetDay() const { return day_; }
    int GetHour() const { return hour_; }
    int GetMinute() const { return minute_; }
    int GetSecond() const { return second_; }
    uint32_t GetUnixTime() const;

    // Astronomical calculations
    double GetJulianDate() const;
    double GetJulianDate0() const;  // 0h UT
    double GetGMST() const;         // Greenwich Mean Sidereal Time (degrees)
    float GetLST() const;           // Local Sidereal Time (hours)

private:
    static void UartTask(void* param);
    void ProcessNmea(const char* sentence);
    void ParseGGA(const char* sentence);
    void ParseRMC(const char* sentence);
    float ParseCoord(const char* field, char direction);
    bool ValidateChecksum(const char* sentence);

    uart_port_t uart_;
    gpio_num_t tx_pin_;
    gpio_num_t rx_pin_;
    int baud_;
    int buf_size_;
    TaskHandle_t task_handle_ = nullptr;
    volatile bool running_ = false;

    // Position data
    volatile float latitude_ = 0;
    volatile float longitude_ = 0;
    volatile float altitude_ = 0;
    volatile bool has_fix_ = false;
    volatile uint8_t satellites_ = 0;
    volatile float hdop_ = 99.0f;

    // Time data
    volatile int year_ = 0;
    volatile int month_ = 0;
    volatile int day_ = 0;
    volatile int hour_ = 0;
    volatile int minute_ = 0;
    volatile int second_ = 0;
};

#endif // GPS_DEVICE_H
