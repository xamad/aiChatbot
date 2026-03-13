#ifndef _BOARD_CONFIG_H_
#define _BOARD_CONFIG_H_

#include <driver/gpio.h>

/*
 * SkyGuard AI — AI Astronomy Copilot
 * ======================================
 * Based on LCDWiki 2.8" ESP32-S3 Display Board
 * Hardware identical to esp32s3-28touch + external sensors
 *
 * - ILI9341 2.8" TFT 240x320 (SPI)
 * - FT6336G Capacitive Touch (I2C_NUM_0)
 * - ES8311 Audio Codec full-duplex (I2C_NUM_0)
 * - FM8002E PA + MEMS Mic LMA2718B381
 * - WS2812 RGB LED
 * - SD Card (SDIO 4-bit)
 * - Battery w/ charge circuit
 *
 * External sensors (via 1.25mm expansion connector):
 * - TSL2591 sky brightness (I2C_NUM_1, 0x29)
 * - AS7341 spectral 8-ch (I2C_NUM_1, 0x39)
 * - AHT20 temp/humidity (I2C_NUM_1, 0x38)
 * - GPS module (UART1)
 *
 * Source: https://www.lcdwiki.com/2.8inch_ESP32-S3_Display
 */

// =============================================================================
// AUDIO CONFIGURATION (identical to esp32s3-28touch)
// =============================================================================

#define AUDIO_INPUT_SAMPLE_RATE  16000
#define AUDIO_OUTPUT_SAMPLE_RATE 16000

#define AUDIO_I2S_METHOD_DUPLEX

#define AUDIO_I2S_GPIO_MCLK     GPIO_NUM_4
#define AUDIO_I2S_GPIO_BCLK     GPIO_NUM_5
#define AUDIO_I2S_GPIO_WS       GPIO_NUM_7
#define AUDIO_I2S_GPIO_DOUT     GPIO_NUM_8
#define AUDIO_I2S_GPIO_DIN      GPIO_NUM_6

#define AUDIO_CODEC_PA_PIN      GPIO_NUM_1    // FM8002E, active LOW

#define ES8311_I2C_ADDR         0x30          // 8-bit format! esp_codec_dev does >>1 internally

// =============================================================================
// DISPLAY CONFIGURATION (ILI9341 SPI — identical)
// =============================================================================

#define DISPLAY_SPI_HOST        SPI2_HOST
#define DISPLAY_SPI_SCLK_PIN    GPIO_NUM_12
#define DISPLAY_SPI_MOSI_PIN    GPIO_NUM_11
#define DISPLAY_SPI_MISO_PIN    GPIO_NUM_13
#define DISPLAY_SPI_CS_PIN      GPIO_NUM_10
#define DISPLAY_DC_PIN          GPIO_NUM_46
#define DISPLAY_RST_PIN         GPIO_NUM_NC
#define DISPLAY_BL_PIN          GPIO_NUM_45

#define DISPLAY_WIDTH           320
#define DISPLAY_HEIGHT          240
#define DISPLAY_MIRROR_X        false
#define DISPLAY_MIRROR_Y        false
#define DISPLAY_SWAP_XY         true
#define DISPLAY_INVERT_COLOR    false

#define DISPLAY_SPI_SPEED_HZ    40000000

// =============================================================================
// TOUCH CONFIGURATION (FT6336G — I2C_NUM_0)
// =============================================================================

#define TOUCH_I2C_SDA_PIN       GPIO_NUM_16
#define TOUCH_I2C_SCL_PIN       GPIO_NUM_15
#define TOUCH_RST_PIN           GPIO_NUM_18
#define TOUCH_INT_PIN           GPIO_NUM_17
#define TOUCH_I2C_ADDR          0x38

// Touch coordinate transformation (mirror applied BEFORE swap by esp_lcd_touch)
// With swap_xy=true: raw_X→screen_Y, raw_Y→screen_X
// So mirror_x flips screen Y, mirror_y flips screen X
#define TOUCH_SWAP_XY           true
#define TOUCH_MIRROR_X          true    // Fix: top/bottom inverted (raw X = screen Y after swap)
#define TOUCH_MIRROR_Y          false

// =============================================================================
// SD CARD (SDIO 4-bit — identical)
// =============================================================================

#define SD_MMC_CLK_PIN          GPIO_NUM_38
#define SD_MMC_CMD_PIN          GPIO_NUM_40
#define SD_MMC_D0_PIN           GPIO_NUM_39
#define SD_MMC_D1_PIN           GPIO_NUM_41
#define SD_MMC_D2_PIN           GPIO_NUM_48
#define SD_MMC_D3_PIN           GPIO_NUM_47

// =============================================================================
// RGB LED (WS2812)
// =============================================================================

#define RGB_LED_PIN             GPIO_NUM_42
#define RGB_LED_COUNT           1

// =============================================================================
// BATTERY
// =============================================================================

#define BATTERY_ADC_PIN         GPIO_NUM_9

// =============================================================================
// BUTTONS
// =============================================================================

#define BOOT_BUTTON_GPIO        GPIO_NUM_0
#define BUILTIN_LED_GPIO        GPIO_NUM_NC
#define TOUCH_BUTTON_GPIO       GPIO_NUM_NC
#define VOLUME_UP_BUTTON_GPIO   GPIO_NUM_NC
#define VOLUME_DOWN_BUTTON_GPIO GPIO_NUM_NC

// =============================================================================
// UART0 (USB Serial)
// =============================================================================

#define UART0_TX_PIN            GPIO_NUM_43
#define UART0_RX_PIN            GPIO_NUM_44

// =============================================================================
// SKYGUARD ELITE: SENSOR I2C BUS (I2C_NUM_1 — expansion connector)
// =============================================================================

#define SENSOR_I2C_SDA_PIN      GPIO_NUM_21   // Expansion pin 4
#define SENSOR_I2C_SCL_PIN      GPIO_NUM_14   // Expansion pin 3
#define SENSOR_I2C_PORT         I2C_NUM_1
#define SENSOR_I2C_SPEED_HZ     100000        // 100kHz — internal pullups (45kΩ) too weak for 400kHz

// Sensor I2C addresses (all on I2C_NUM_1)
#define TSL2591_I2C_ADDR        0x29          // Sky brightness
#define AS7341_I2C_ADDR         0x39          // Spectral 8-channel
#define AHT20_I2C_ADDR          0x38          // Temp/Humidity

// =============================================================================
// SKYGUARD ELITE: GPS UART (UART_NUM_1 — expansion connector)
// =============================================================================

#define GPS_UART_NUM            UART_NUM_1
#define GPS_UART_TX_PIN         GPIO_NUM_3    // Expansion pin 2 (to GPS RX)
#define GPS_UART_RX_PIN         GPIO_NUM_2    // Expansion pin 1 (from GPS TX)
#define GPS_UART_BAUD           9600
#define GPS_UART_BUF_SIZE       1024

#endif // _BOARD_CONFIG_H_
