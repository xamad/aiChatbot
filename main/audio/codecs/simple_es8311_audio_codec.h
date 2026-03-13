#ifndef _SIMPLE_ES8311_AUDIO_CODEC_H
#define _SIMPLE_ES8311_AUDIO_CODEC_H

#include "audio_codec.h"
#include <driver/i2c_master.h>
#include <driver/gpio.h>

/**
 * Simple ES8311 Audio Codec
 *
 * Bypasses esp_codec_dev library and uses direct I2S + manual ES8311 configuration.
 * Based on the working TouchSynth_Test.ino approach.
 */
class SimpleEs8311AudioCodec : public AudioCodec {
private:
    i2c_master_bus_handle_t i2c_bus_;
    i2c_master_dev_handle_t i2c_dev_;
    gpio_num_t pa_pin_;
    bool codec_initialized_;

    // I2C communication
    bool WriteReg(uint8_t reg, uint8_t val);
    uint8_t ReadReg(uint8_t reg);

    // ES8311 initialization
    bool InitializeCodec();
    void ConfigureForOutput();
    void ConfigureForInput();

    virtual int Read(int16_t* dest, int samples) override;
    virtual int Write(const int16_t* data, int samples) override;

public:
    SimpleEs8311AudioCodec(
        i2c_master_bus_handle_t i2c_bus,
        int input_sample_rate,
        int output_sample_rate,
        gpio_num_t mclk,
        gpio_num_t bclk,
        gpio_num_t ws,
        gpio_num_t dout,
        gpio_num_t din,
        gpio_num_t pa_pin
    );

    virtual ~SimpleEs8311AudioCodec();

    virtual void SetOutputVolume(int volume) override;
    virtual void EnableInput(bool enable) override;
    virtual void EnableOutput(bool enable) override;
};

#endif // _SIMPLE_ES8311_AUDIO_CODEC_H
