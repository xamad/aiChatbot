# XAMAD Server Protocol Specification

Complete specification for XiaoZhi ESP32-S3 DIY server implementation.

## 1. OTA API Endpoint

**URL:** `POST /xiaozhi/ota/`
**Example:** `https://chatai.xamad.net/xiaozhi/ota/`

### Request Headers (from device)

| Header | Example | Description |
|--------|---------|-------------|
| Device-Id | `80:b5:4e:c6:02:f4` | MAC address |
| Client-Id | `uuid-string` | Unique device UUID |
| User-Agent | `XiaoZhi/1.0.0 (ESP32-S3)` | Firmware version |
| Accept-Language | `it-IT` | Device language |
| Content-Type | `application/json` | Always JSON |

### Response (JSON)

```json
{
  "firmware": {
    "version": "1.0.1",
    "url": "https://server.com/firmware.bin",
    "force": 0
  },
  "websocket": {
    "url": "wss://chatai.xamad.net/xiaozhi/v1/",
    "token": "Bearer your-jwt-token",
    "version": 3
  },
  "server_time": {
    "timestamp": 1704931200000,
    "timezone_offset": 60
  },
  "activation": {
    "message": "Device activated",
    "code": "123456",
    "timeout_ms": 30000
  }
}
```

### Minimal Response (no update)

```json
{
  "websocket": {
    "url": "wss://chatai.xamad.net/xiaozhi/v1/",
    "token": "your-token"
  }
}
```

---

## 2. WebSocket Protocol

### Connection

Device connects to `websocket.url` from OTA response.

**Headers:**
```
Authorization: Bearer <token>
Protocol-Version: 3
Device-Id: 80:b5:4e:c6:02:f4
Client-Id: <uuid>
```

### Handshake

**Client → Server (hello):**
```json
{
  "type": "hello",
  "version": 3,
  "transport": "websocket",
  "features": {
    "mcp": true,
    "aec": false
  },
  "audio_params": {
    "format": "opus",
    "sample_rate": 16000,
    "channels": 1,
    "frame_duration": 60
  }
}
```

**Server → Client (hello):**
```json
{
  "type": "hello",
  "transport": "websocket",
  "session_id": "session-uuid",
  "audio_params": {
    "sample_rate": 24000,
    "frame_duration": 60
  }
}
```

---

## 3. Message Types (Server → Client)

### TTS (Text-to-Speech state)

```json
{"type": "tts", "state": "start"}
```
```json
{"type": "tts", "state": "sentence_start", "text": "Hello, how can I help?"}
```
```json
{"type": "tts", "state": "stop"}
```

### STT (Speech-to-Text result)

```json
{"type": "stt", "text": "what time is it"}
```

### LLM (Emotion/Expression)

```json
{"type": "llm", "emotion": "happy"}
```

**Available emotions:**
- `neutral` - Default face
- `happy` - Smiling
- `laughing` - LOL
- `sad` - Unhappy
- `angry` - Mad
- `crying` - Tears
- `thinking` - Pondering
- `surprised` - Shocked
- `cool` - Sunglasses
- `loving` - Heart eyes
- `embarrassed` - Blushing
- `sleepy` - Tired
- `confused` - Puzzled
- `winking` - Wink
- `delicious` - Yummy
- `silly` - Tongue out

### Alert (Notification)

```json
{
  "type": "alert",
  "status": "Error",
  "message": "Connection lost",
  "emotion": "sad"
}
```

### System Command

```json
{"type": "system", "command": "reboot"}
```

---

## 4. Audio Streaming

### Binary Protocol (version 3)

Audio is sent as binary WebSocket frames:

```
| type (1 byte) | reserved (1 byte) | payload_size (2 bytes BE) | payload |
```

- **type:** 0 = audio
- **payload:** Opus encoded audio

### Audio Parameters

| Direction | Format | Sample Rate | Channels | Frame Duration |
|-----------|--------|-------------|----------|----------------|
| Client → Server | Opus | 16000 Hz | 1 | 60 ms |
| Server → Client | Opus | 24000 Hz | 1 | 60 ms |

---

## 5. Future Extensions (Not Yet Implemented)

### Image Display

```json
{
  "type": "image",
  "format": "jpeg",
  "width": 128,
  "height": 160,
  "data": "<base64-encoded-jpeg>"
}
```

### GIF Animation

```json
{
  "type": "gif",
  "format": "jpeg_frames",
  "frames": ["<base64-frame1>", "<base64-frame2>"],
  "durations": [100, 100]
}
```

### Audio Playback (MP3 URL)

```json
{
  "type": "audio_play",
  "action": "play",
  "url": "https://example.com/sound.mp3"
}
```
```json
{
  "type": "audio_play",
  "action": "stop"
}
```

---

## 6. Error Codes

| Code | Description |
|------|-------------|
| -32769 | SSL/TLS connection failed |
| 401 | Unauthorized (bad token) |
| 404 | Endpoint not found |
| 500 | Server error |

---

## 7. Device Info

| Property | Value |
|----------|-------|
| MCU | ESP32-S3-N8R8 |
| Display | ST7735 128x160 |
| Audio In | INMP441 I2S 16kHz |
| Audio Out | MAX98357A I2S 24kHz |
| Wake Word | "Sophia" |
| Language | Italian (it-IT) |
