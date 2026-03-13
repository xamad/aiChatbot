#include "skyguard_http.h"
#include <esp_log.h>
#include <esp_http_client.h>
#include <esp_heap_caps.h>
#include <esp_crt_bundle.h>
#include <cstring>
#include <cstdlib>

#define TAG "SkyGuardHTTP"

// Per-request context — thread-safe (no static buffers)
struct HttpCtx {
    char* buf;
    int len;
    int max_len;
};

static esp_err_t sg_http_event_handler(esp_http_client_event_t* evt) {
    auto* ctx = (HttpCtx*)evt->user_data;
    if (!ctx) return ESP_OK;

    switch (evt->event_id) {
        case HTTP_EVENT_ON_DATA:
            if (ctx->len + evt->data_len < ctx->max_len - 1) {
                memcpy(ctx->buf + ctx->len, evt->data, evt->data_len);
                ctx->len += evt->data_len;
                ctx->buf[ctx->len] = '\0';
            }
            break;
        default:
            break;
    }
    return ESP_OK;
}

bool SkyGuardHttp::Get(const char* url, char* response, int max_len, int timeout_ms) {
    HttpCtx ctx = { response, 0, max_len };
    response[0] = '\0';

    esp_http_client_config_t config = {};
    config.url = url;
    config.method = HTTP_METHOD_GET;
    config.timeout_ms = timeout_ms;
    config.event_handler = sg_http_event_handler;
    config.user_data = &ctx;
    config.crt_bundle_attach = esp_crt_bundle_attach;  // HTTPS certificate validation
    config.disable_auto_redirect = false;               // Follow HTTP redirects

    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) {
        ESP_LOGE(TAG, "Failed to init HTTP client");
        return false;
    }

    esp_err_t err = esp_http_client_perform(client);
    int status = esp_http_client_get_status_code(client);
    esp_http_client_cleanup(client);

    if (err != ESP_OK) {
        ESP_LOGE(TAG, "HTTP GET failed: %s", esp_err_to_name(err));
        return false;
    }

    if (status != 200) {
        ESP_LOGW(TAG, "HTTP GET status %d for %s", status, url);
        return false;
    }

    ESP_LOGI(TAG, "HTTP GET OK: %d bytes from %s", ctx.len, url);
    return true;
}

bool SkyGuardHttp::Post(const char* url, const char* json_body, char* response, int max_len, int timeout_ms, const char* api_key) {
    HttpCtx ctx = { response, 0, max_len };
    response[0] = '\0';

    esp_http_client_config_t config = {};
    config.url = url;
    config.method = HTTP_METHOD_POST;
    config.timeout_ms = timeout_ms;
    config.event_handler = sg_http_event_handler;
    config.user_data = &ctx;
    config.crt_bundle_attach = esp_crt_bundle_attach;
    config.disable_auto_redirect = false;

    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) {
        ESP_LOGE(TAG, "Failed to init HTTP client for POST");
        return false;
    }

    esp_http_client_set_header(client, "Content-Type", "application/json");
    if (api_key && api_key[0]) {
        esp_http_client_set_header(client, "X-API-Key", api_key);
    }
    esp_http_client_set_post_field(client, json_body, strlen(json_body));

    esp_err_t err = esp_http_client_perform(client);
    int status = esp_http_client_get_status_code(client);
    esp_http_client_cleanup(client);

    if (err != ESP_OK) {
        ESP_LOGE(TAG, "HTTP POST failed: %s", esp_err_to_name(err));
        return false;
    }

    if (status != 200 && status != 201) {
        ESP_LOGW(TAG, "HTTP POST status %d for %s", status, url);
        return false;
    }

    ESP_LOGI(TAG, "HTTP POST OK: status=%d, %d bytes response from %s", status, ctx.len, url);
    return true;
}

bool SkyGuardHttp::Put(const char* url, const char* form_body, char* response, int max_len, int timeout_ms) {
    HttpCtx ctx = { response, 0, max_len };
    response[0] = '\0';

    esp_http_client_config_t config = {};
    config.url = url;
    config.method = HTTP_METHOD_PUT;
    config.timeout_ms = timeout_ms;
    config.event_handler = sg_http_event_handler;
    config.user_data = &ctx;
    config.disable_auto_redirect = false;

    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) {
        ESP_LOGE(TAG, "Failed to init HTTP client for PUT");
        return false;
    }

    esp_http_client_set_header(client, "Content-Type", "application/x-www-form-urlencoded");
    if (form_body && form_body[0]) {
        esp_http_client_set_post_field(client, form_body, strlen(form_body));
    }

    esp_err_t err = esp_http_client_perform(client);
    int status = esp_http_client_get_status_code(client);
    esp_http_client_cleanup(client);

    if (err != ESP_OK) {
        ESP_LOGE(TAG, "HTTP PUT failed: %s", esp_err_to_name(err));
        return false;
    }

    if (status != 200) {
        ESP_LOGW(TAG, "HTTP PUT status %d for %s", status, url);
        return false;
    }

    return true;
}

// Binary event handler — no null terminator, handles large payloads
struct BinaryCtx {
    uint8_t* buf;
    int len;
    int max_len;
};

static esp_err_t sg_http_binary_handler(esp_http_client_event_t* evt) {
    auto* ctx = (BinaryCtx*)evt->user_data;
    if (!ctx) return ESP_OK;

    if (evt->event_id == HTTP_EVENT_ON_DATA) {
        int space = ctx->max_len - ctx->len;
        int copy = (evt->data_len < space) ? evt->data_len : space;
        if (copy > 0) {
            memcpy(ctx->buf + ctx->len, evt->data, copy);
            ctx->len += copy;
        }
    }
    return ESP_OK;
}

bool SkyGuardHttp::GetBinary(const char* url, uint8_t** out_buf, int* out_len, int max_len, int timeout_ms) {
    *out_buf = nullptr;
    *out_len = 0;

    uint8_t* buf = (uint8_t*)heap_caps_malloc(max_len, MALLOC_CAP_SPIRAM);
    if (!buf) {
        buf = (uint8_t*)malloc(max_len);
    }
    if (!buf) {
        ESP_LOGE(TAG, "GetBinary: OOM for %d bytes", max_len);
        return false;
    }

    BinaryCtx ctx = { buf, 0, max_len };

    esp_http_client_config_t config = {};
    config.url = url;
    config.method = HTTP_METHOD_GET;
    config.timeout_ms = timeout_ms;
    config.event_handler = sg_http_binary_handler;
    config.user_data = &ctx;
    config.crt_bundle_attach = esp_crt_bundle_attach;
    config.disable_auto_redirect = false;

    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) {
        free(buf);
        ESP_LOGE(TAG, "GetBinary: Failed to init client");
        return false;
    }

    // Set User-Agent (required by tile servers like OSM)
    esp_http_client_set_header(client, "User-Agent", "SkyGuard-Elite/1.0 ESP32");

    esp_err_t err = esp_http_client_perform(client);
    int status = esp_http_client_get_status_code(client);
    esp_http_client_cleanup(client);

    if (err != ESP_OK || status != 200) {
        free(buf);
        ESP_LOGE(TAG, "GetBinary: err=%s status=%d url=%s", esp_err_to_name(err), status, url);
        return false;
    }

    ESP_LOGI(TAG, "GetBinary OK: %d bytes from %s", ctx.len, url);
    *out_buf = buf;
    *out_len = ctx.len;
    return true;
}

char* SkyGuardHttp::AllocBuffer(size_t size) {
    // Try PSRAM first (ESP32-S3 has PSRAM)
    char* buf = (char*)heap_caps_malloc(size, MALLOC_CAP_SPIRAM);
    if (!buf) {
        // Fallback to DRAM
        buf = (char*)malloc(size);
    }
    if (buf) {
        buf[0] = '\0';
    }
    return buf;
}
