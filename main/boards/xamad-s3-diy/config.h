#ifndef _BOARD_CONFIG_H_
#define _BOARD_CONFIG_H_

#include <driver/gpio.h>

/*
 * XAMAD ESP32-S3 DIY Board
 * ========================
 * - TFT 1.8" ST7735 128x160 (8 pin SPI)
 * - INMP441 I2S Microphone (6 pin)
 * - MAX98357A I2S Amplifier (7 pin)
 *
 * OTA Server: https://chatai.xamad.net/xiaozhi/ota/
 * WebSocket:  wss://chatai.xamad.net/xiaozhi/v1/
 */

// Audio Configuration
#define AUDIO_INPUT_SAMPLE_RATE  16000
#define AUDIO_OUTPUT_SAMPLE_RATE 24000  // Match server sample rate

// Use separate I2S buses for mic and speaker
#define AUDIO_I2S_METHOD_SIMPLEX

// INMP441 Microphone I2S Pins
#define AUDIO_I2S_MIC_GPIO_WS   GPIO_NUM_15   // Word Select (LRCLK)
#define AUDIO_I2S_MIC_GPIO_SCK  GPIO_NUM_16   // Bit Clock (BCLK)
#define AUDIO_I2S_MIC_GPIO_DIN  GPIO_NUM_14   // Data In (SD)

// MAX98357A Speaker I2S Pins
#define AUDIO_I2S_SPK_GPIO_DOUT GPIO_NUM_18   // Data Out (DIN)
#define AUDIO_I2S_SPK_GPIO_BCLK GPIO_NUM_5    // Bit Clock (BCLK)
#define AUDIO_I2S_SPK_GPIO_LRCK GPIO_NUM_6    // L/R Clock (LRC)
#define AUDIO_CODEC_PA_PIN      GPIO_NUM_17   // Amplifier Enable (SD)

// Buttons
#define BUILTIN_LED_GPIO        GPIO_NUM_NC
#define BOOT_BUTTON_GPIO        GPIO_NUM_0
#define TOUCH_BUTTON_GPIO       GPIO_NUM_NC
#define VOLUME_UP_BUTTON_GPIO   GPIO_NUM_NC
#define VOLUME_DOWN_BUTTON_GPIO GPIO_NUM_NC

// TFT 1.8" ST7735 Display SPI Pins
#define DISPLAY_BACKLIGHT_PIN   GPIO_NUM_13   // Backlight (LED/BL)
#define DISPLAY_MOSI_PIN        GPIO_NUM_11   // SPI MOSI (SDA)
#define DISPLAY_CLK_PIN         GPIO_NUM_12   // SPI Clock (SCK)
#define DISPLAY_DC_PIN          GPIO_NUM_8    // Data/Command (DC/A0)
#define DISPLAY_RST_PIN         GPIO_NUM_9    // Reset (RESET)
#define DISPLAY_CS_PIN          GPIO_NUM_10   // Chip Select (CS)

// ST7735 128x160 Display Configuration
#define LCD_TYPE_ST7789_SERIAL
#define DISPLAY_WIDTH   128
#define DISPLAY_HEIGHT  160
#define DISPLAY_MIRROR_X true
#define DISPLAY_MIRROR_Y true
#define DISPLAY_SWAP_XY false
#define DISPLAY_INVERT_COLOR    false
#define DISPLAY_RGB_ORDER       LCD_RGB_ELEMENT_ORDER_RGB
#define DISPLAY_OFFSET_X  0
#define DISPLAY_OFFSET_Y  0
#define DISPLAY_BACKLIGHT_OUTPUT_INVERT false
#define DISPLAY_SPI_MODE 0

#endif // _BOARD_CONFIG_H_
