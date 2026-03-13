#ifndef _BOARD_CONFIG_H_
#define _BOARD_CONFIG_H_

#include <driver/gpio.h>

/*
 * ESP32-S3 2.8" Touch Display Board
 * =================================
 * - ILI9341 2.8" TFT 240x320 (SPI)
 * - FT6336G Capacitive Touch (I2C)
 * - I2S Audio: Speaker FM8002E + MEMS Microphone
 * - MicroSD Card Slot (SDIO)
 * - RGB LED (WS2812)
 * - Battery Management with ADC
 *
 * Source: https://www.lcdwiki.com/2.8inch_ESP32-S3_Display
 */

// =============================================================================
// AUDIO CONFIGURATION
// =============================================================================

#define AUDIO_INPUT_SAMPLE_RATE  16000
#define AUDIO_OUTPUT_SAMPLE_RATE 16000  // ES8311 requires same rate

// Use duplex I2S (shared bus for mic and speaker)
#define AUDIO_I2S_METHOD_DUPLEX

// I2S Audio Pins (shared for mic and speaker)
#define AUDIO_I2S_GPIO_MCLK     GPIO_NUM_4    // Master Clock
#define AUDIO_I2S_GPIO_BCLK     GPIO_NUM_5    // Bit Clock
#define AUDIO_I2S_GPIO_WS       GPIO_NUM_7    // Word Select (LRC)
#define AUDIO_I2S_GPIO_DOUT     GPIO_NUM_8    // Data Out (to speaker) - VERIFIED WORKING!
#define AUDIO_I2S_GPIO_DIN      GPIO_NUM_6    // Data In (from mic)

// Amplifier Enable (FM8002E) - LOW = enabled, HIGH = disabled
#define AUDIO_CODEC_PA_PIN      GPIO_NUM_1

// ES8311 Audio Codec (per LCDWiki documentation)
// Uses same I2C bus as touch (GPIO 15/16)
#define ES8311_I2C_ADDR         0x18  // Standard address (AD0=LOW)

// =============================================================================
// DISPLAY CONFIGURATION (ILI9341 SPI)
// =============================================================================

#define DISPLAY_SPI_HOST        SPI2_HOST
#define DISPLAY_SPI_SCLK_PIN    GPIO_NUM_12   // SPI Clock
#define DISPLAY_SPI_MOSI_PIN    GPIO_NUM_11   // SPI Data Out
#define DISPLAY_SPI_MISO_PIN    GPIO_NUM_13   // SPI Data In
#define DISPLAY_SPI_CS_PIN      GPIO_NUM_10   // Chip Select
#define DISPLAY_DC_PIN          GPIO_NUM_46   // Data/Command
#define DISPLAY_RST_PIN         GPIO_NUM_NC   // Reset (shared with ESP32 RST)
#define DISPLAY_BL_PIN          GPIO_NUM_45   // Backlight (HIGH = on)

#define DISPLAY_WIDTH           240
#define DISPLAY_HEIGHT          320
#define DISPLAY_MIRROR_X        true
#define DISPLAY_MIRROR_Y        false
#define DISPLAY_SWAP_XY         false
#define DISPLAY_INVERT_COLOR    false

// SPI speed for display
#define DISPLAY_SPI_SPEED_HZ    40000000  // 40MHz

// =============================================================================
// TOUCH CONFIGURATION (FT6336G I2C)
// =============================================================================

#define TOUCH_I2C_SDA_PIN       GPIO_NUM_16
#define TOUCH_I2C_SCL_PIN       GPIO_NUM_15
#define TOUCH_RST_PIN           GPIO_NUM_18
#define TOUCH_INT_PIN           GPIO_NUM_17
#define TOUCH_I2C_ADDR          0x38          // FT6336G default address

// =============================================================================
// SD CARD CONFIGURATION (SDIO 4-bit mode)
// =============================================================================

#define SD_MMC_CLK_PIN          GPIO_NUM_38
#define SD_MMC_CMD_PIN          GPIO_NUM_40
#define SD_MMC_D0_PIN           GPIO_NUM_39
#define SD_MMC_D1_PIN           GPIO_NUM_41
#define SD_MMC_D2_PIN           GPIO_NUM_48
#define SD_MMC_D3_PIN           GPIO_NUM_47

// =============================================================================
// RGB LED CONFIGURATION (WS2812 / NeoPixel)
// =============================================================================

#define RGB_LED_PIN             GPIO_NUM_42
#define RGB_LED_COUNT           1

// =============================================================================
// BATTERY CONFIGURATION
// =============================================================================

#define BATTERY_ADC_PIN         GPIO_NUM_9

// =============================================================================
// BUTTONS CONFIGURATION
// =============================================================================

#define BOOT_BUTTON_GPIO        GPIO_NUM_0
#define BUILTIN_LED_GPIO        GPIO_NUM_NC
#define TOUCH_BUTTON_GPIO       GPIO_NUM_NC
#define VOLUME_UP_BUTTON_GPIO   GPIO_NUM_NC
#define VOLUME_DOWN_BUTTON_GPIO GPIO_NUM_NC

// =============================================================================
// EXPANSION GPIO (available for external peripherals)
// =============================================================================

#define EXPANSION_GPIO_1        GPIO_NUM_2
#define EXPANSION_GPIO_2        GPIO_NUM_3
#define EXPANSION_GPIO_3        GPIO_NUM_14
#define EXPANSION_GPIO_4        GPIO_NUM_21

// UART0 (USB Serial)
#define UART0_TX_PIN            GPIO_NUM_43
#define UART0_RX_PIN            GPIO_NUM_44

#endif // _BOARD_CONFIG_H_
