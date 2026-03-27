// === EnzoBot — Xiaozhi Custom Board Config ===
// ESP32-S3-DevKitC-1 N16R8
// 2x L298N (uno per motore NEMA17) + K230 Yahboom + sensori

#ifndef _BOARD_CONFIG_H_
#define _BOARD_CONFIG_H_

#include <driver/gpio.h>

// === AUDIO — INMP441 (mic) + MAX98357A (speaker) ===
// Simplex: mic e speaker su I2S bus separati
#define AUDIO_INPUT_SAMPLE_RATE     16000
#define AUDIO_OUTPUT_SAMPLE_RATE    24000

#define AUDIO_I2S_METHOD_SIMPLEX

#define AUDIO_I2S_MIC_GPIO_WS      GPIO_NUM_14
#define AUDIO_I2S_MIC_GPIO_SCK     GPIO_NUM_13
#define AUDIO_I2S_MIC_GPIO_DIN     GPIO_NUM_21
// Speaker: GPIO 16,17,48 (temporaneo — 16/17 saranno HX711 quando arriva)
#define AUDIO_I2S_SPK_GPIO_BCLK    GPIO_NUM_16
#define AUDIO_I2S_SPK_GPIO_LRCK    GPIO_NUM_17
#define AUDIO_I2S_SPK_GPIO_DOUT    GPIO_NUM_48

// === OLED SSD1306 128x64 (I2C) ===
#define DISPLAY_SDA_PIN             GPIO_NUM_8
#define DISPLAY_SCL_PIN             GPIO_NUM_9
#define DISPLAY_WIDTH               128
#define DISPLAY_HEIGHT              64
#define DISPLAY_MIRROR_X            true
#define DISPLAY_MIRROR_Y            true

// === BUTTONS ===
#define BOOT_BUTTON_GPIO            GPIO_NUM_0
#define BUILTIN_LED_GPIO            GPIO_NUM_NC

// === L298N SINGOLO — 2 motori DC (canale A = SX, canale B = DX) ===
#define MOT_L_ENA                   GPIO_NUM_1   // PWM velocità SX
#define MOT_L_IN1                   GPIO_NUM_2   // Direzione SX
#define MOT_L_IN2                   GPIO_NUM_3   // Direzione SX
#define MOT_R_IN1                   GPIO_NUM_4   // Direzione DX
#define MOT_R_IN2                   GPIO_NUM_5   // Direzione DX
#define MOT_R_ENA                   GPIO_NUM_6   // PWM velocità DX

// === SENSORI ULTRASUONI (3x HC-SR04) ===
#define US_REAR_TRIG                GPIO_NUM_7
#define US_REAR_ECHO                GPIO_NUM_15
#define US_LEFT_TRIG                GPIO_NUM_19
#define US_LEFT_ECHO                GPIO_NUM_20
#define US_RIGHT_TRIG               GPIO_NUM_38
#define US_RIGHT_ECHO               GPIO_NUM_47

// === CELLA DI CARICO HX711 ===
#define HX711_DT_PIN                GPIO_NUM_16
#define HX711_SCK_PIN               GPIO_NUM_17

// === UART K230 Yahboom ===
#define K230_TX_PIN                 GPIO_NUM_18
#define K230_RX_PIN                 GPIO_NUM_35
#define K230_BAUD                   115200

// === BUZZER / LED ===
// GPIO36/37 sono PSRAM octal su N16R8 — NON usabili come GPIO!
#define BUZZER_PIN                  GPIO_NUM_NC
#define LED_STATUS_PIN              GPIO_NUM_NC

// === MPU6050 (I2C condiviso con OLED) ===
#define MPU6050_ADDR                0x68

// === PARAMETRI MOTORI DC ===
#define MAX_SPEED                   255
#define CRUISE_SPEED                200
#define SLOW_SPEED                  120
#define MIN_SPEED                   80
#define PWM_FREQ_HZ                 5000
#define PWM_RESOLUTION_BITS         8

// === SOGLIE SENSORI ===
#define US_EMERGENCY_DIST           15
#define US_WARNING_DIST             30
#define WEIGHT_THRESHOLD            50.0f
#define WEIGHT_EMPTY                20.0f
#define TILT_THRESHOLD              30.0f

#endif // _BOARD_CONFIG_H_
