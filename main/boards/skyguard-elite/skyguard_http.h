#ifndef SKYGUARD_HTTP_H
#define SKYGUARD_HTTP_H

#include <cstdint>
#include <cstddef>

/**
 * SkyGuard AI - Thread-safe HTTP GET helper
 *
 * Uses esp_http_client with per-call context (no static buffers).
 * Response allocated from PSRAM when available, otherwise DRAM.
 */
class SkyGuardHttp {
public:
    /**
     * HTTP GET request.
     * @param url         Full URL
     * @param response    Output buffer (caller-allocated)
     * @param max_len     Size of output buffer
     * @param timeout_ms  Timeout in ms (default 10s)
     * @return true on HTTP 200 success
     */
    static bool Get(const char* url, char* response, int max_len, int timeout_ms = 10000);

    /**
     * HTTP POST request with JSON body.
     * @param url         Full URL
     * @param json_body   JSON string to POST
     * @param response    Output buffer (caller-allocated)
     * @param max_len     Size of output buffer
     * @param timeout_ms  Timeout in ms (default 10s)
     * @return true on HTTP 200/201 success
     */
    static bool Post(const char* url, const char* json_body, char* response, int max_len, int timeout_ms = 10000, const char* api_key = nullptr);

    /**
     * HTTP PUT request with form-encoded body (for ASCOM Alpaca).
     * @param url         Full URL
     * @param form_body   URL-encoded form data (e.g., "ClientID=1&ClientTransactionID=1&RightAscension=18.6")
     * @param response    Output buffer (caller-allocated)
     * @param max_len     Size of output buffer
     * @param timeout_ms  Timeout in ms (default 5s)
     * @return true on HTTP 200 success
     */
    static bool Put(const char* url, const char* form_body, char* response, int max_len, int timeout_ms = 5000);

    /**
     * HTTP GET binary data (for images, etc).
     * @param url         Full URL
     * @param out_buf     Output: pointer to PSRAM-allocated buffer (caller must free)
     * @param out_len     Output: number of bytes downloaded
     * @param max_len     Maximum bytes to download
     * @param timeout_ms  Timeout in ms (default 15s)
     * @return true on HTTP 200 success
     */
    static bool GetBinary(const char* url, uint8_t** out_buf, int* out_len, int max_len = 512 * 1024, int timeout_ms = 15000);

    /**
     * Allocate a buffer from PSRAM (fallback DRAM).
     * Caller must free() the result.
     */
    static char* AllocBuffer(size_t size);
};

#endif // SKYGUARD_HTTP_H
