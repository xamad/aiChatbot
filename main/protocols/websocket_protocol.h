#ifndef _WEBSOCKET_PROTOCOL_H_
#define _WEBSOCKET_PROTOCOL_H_


#include "protocol.h"

#include <web_socket.h>
#include <freertos/FreeRTOS.h>
#include <freertos/event_groups.h>
#include <freertos/timers.h>

#define WEBSOCKET_PROTOCOL_SERVER_HELLO_EVENT (1 << 0)

// Keep-alive ping interval in milliseconds (30 seconds)
#define WEBSOCKET_KEEPALIVE_INTERVAL_MS 30000

class WebsocketProtocol : public Protocol {
public:
    WebsocketProtocol();
    ~WebsocketProtocol();

    bool Start() override;
    bool SendAudio(std::unique_ptr<AudioStreamPacket> packet) override;
    bool OpenAudioChannel() override;
    void CloseAudioChannel() override;
    bool IsAudioChannelOpened() const override;

    // Keep-alive management
    void EnableKeepAlive(bool enable);
    bool IsConnectionAlive() const;

private:
    EventGroupHandle_t event_group_handle_;
    std::unique_ptr<WebSocket> websocket_;
    int version_ = 1;

    // Keep-alive state
    bool keepalive_enabled_ = false;
    bool audio_channel_active_ = false;
    TimerHandle_t keepalive_timer_ = nullptr;

    void ParseServerHello(const cJSON* root);
    bool SendText(const std::string& text) override;
    std::string GetHelloMessage();

    // Keep-alive timer callback
    static void KeepAliveTimerCallback(TimerHandle_t timer);
    void SendKeepAlivePing();
    void StartKeepAliveTimer();
    void StopKeepAliveTimer();
};

#endif
