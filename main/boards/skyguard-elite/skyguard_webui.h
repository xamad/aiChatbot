#ifndef SKYGUARD_WEBUI_H
#define SKYGUARD_WEBUI_H

#include <esp_http_server.h>
#include <string>

/**
 * SkyGuard AI - Persistent WebUI with display mirror
 *
 * HTTP server on port 80 running during normal STA mode.
 * Provides: display mirror, full sensor status, configuration.
 */

// Callback type: board provides this to generate JSON status
typedef std::string (*StatusProviderFn)(void* ctx);

class SkyGuardWebUI {
public:
    SkyGuardWebUI();
    ~SkyGuardWebUI();

    void Start();
    void Stop();
    bool IsRunning() const { return server_ != nullptr; }

    // Board calls this to provide real-time sensor data
    void SetStatusProvider(StatusProviderFn fn, void* ctx) {
        status_fn_ = fn;
        status_ctx_ = ctx;
    }

    // Called after config is saved — board reloads keys from NVS
    typedef void (*ConfigSavedFn)(void* ctx);
    void SetConfigSavedCallback(ConfigSavedFn fn, void* ctx) {
        config_saved_fn_ = fn;
        config_saved_ctx_ = ctx;
    }

    StatusProviderFn status_fn_ = nullptr;
    void* status_ctx_ = nullptr;
    ConfigSavedFn config_saved_fn_ = nullptr;
    void* config_saved_ctx_ = nullptr;

private:
    httpd_handle_t server_ = nullptr;

    static esp_err_t HandleRoot(httpd_req_t* req);
    static esp_err_t HandleGetStatus(httpd_req_t* req);
    static esp_err_t HandleGetConfig(httpd_req_t* req);
    static esp_err_t HandlePostConfig(httpd_req_t* req);
    static esp_err_t HandlePostCommand(httpd_req_t* req);
};

#endif // SKYGUARD_WEBUI_H
