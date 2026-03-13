#include "star_emoji.h"
#include <cstring>
#include <cmath>
#include <cstdlib>
#include <esp_log.h>
#include <esp_heap_caps.h>

#define TAG "StarEmoji"
using namespace star_colors;

// ============================================================================
// STAR SHAPE GENERATION — 64x64
// ============================================================================

void StarEmoji32::GenerateStarMask(uint8_t* alpha) {
    memset(alpha, 0, SIZE * SIZE);

    const float cx = 31.5f, cy = 31.5f;
    const float outer_r = 29.0f;
    const float inner_r = 18.0f;  // Chubby star — wider body for face features

    float vx[10], vy[10];
    for (int i = 0; i < 10; i++) {
        float angle = -M_PI / 2.0f + i * M_PI / 5.0f;
        float r = (i % 2 == 0) ? outer_r : inner_r;
        vx[i] = cx + r * cosf(angle);
        vy[i] = cy + r * sinf(angle);
    }

    for (int y = 0; y < SIZE; y++) {
        float intersections[20];
        int num = 0;
        for (int i = 0; i < 10; i++) {
            int j = (i + 1) % 10;
            float y0 = vy[i], y1 = vy[j];
            if ((y0 <= y && y1 > y) || (y1 <= y && y0 > y)) {
                float t = (y - y0) / (y1 - y0);
                if (num < 20) intersections[num++] = vx[i] + t * (vx[j] - vx[i]);
            }
        }
        for (int a = 0; a < num - 1; a++)
            for (int b = a + 1; b < num; b++)
                if (intersections[b] < intersections[a]) {
                    float tmp = intersections[a];
                    intersections[a] = intersections[b];
                    intersections[b] = tmp;
                }
        for (int k = 0; k + 1 < num; k += 2) {
            int xs = (int)(intersections[k] + 0.5f);
            int xe = (int)(intersections[k + 1] + 0.5f);
            if (xs < 0) xs = 0;
            if (xe > SIZE - 1) xe = SIZE - 1;
            for (int x = xs; x <= xe; x++)
                alpha[y * SIZE + x] = 255;
        }
    }

    // Anti-alias edges
    uint8_t* temp = (uint8_t*)malloc(SIZE * SIZE);
    if (temp) {
        memcpy(temp, alpha, SIZE * SIZE);
        for (int y = 1; y < SIZE - 1; y++) {
            for (int x = 1; x < SIZE - 1; x++) {
                if (temp[y * SIZE + x] == 255) {
                    if (temp[(y-1)*SIZE+x] == 0 || temp[(y+1)*SIZE+x] == 0 ||
                        temp[y*SIZE+x-1] == 0 || temp[y*SIZE+x+1] == 0) {
                        alpha[y * SIZE + x] = 180;
                    }
                }
            }
        }
        free(temp);
    }
}

// ============================================================================
// COLOR FILL — RGB565 stored little-endian
// ============================================================================

// Blend two RGB565 colors by factor t (0.0 = c1, 1.0 = c2)
static uint16_t BlendRGB565(uint16_t c1, uint16_t c2, float t) {
    if (t <= 0.0f) return c1;
    if (t >= 1.0f) return c2;
    int r1 = (c1 >> 11) & 0x1F, g1 = (c1 >> 5) & 0x3F, b1 = c1 & 0x1F;
    int r2 = (c2 >> 11) & 0x1F, g2 = (c2 >> 5) & 0x3F, b2 = c2 & 0x1F;
    int r = r1 + (int)((r2 - r1) * t);
    int g = g1 + (int)((g2 - g1) * t);
    int b = b1 + (int)((b2 - b1) * t);
    return ((r & 0x1F) << 11) | ((g & 0x3F) << 5) | (b & 0x1F);
}

void StarEmoji32::FillStarColor(uint8_t* rgb, const uint8_t* alpha,
                                 uint16_t body_color, uint16_t outline_color) {
    // Light source at top-left (20, 14)
    const float light_x = 20.0f, light_y = 14.0f;
    const float cx = 31.5f, cy = 31.5f;

    // Darker shade for bottom-right shadow
    static const uint16_t SHADOW = star_colors::RGB565(160, 110, 10);
    // Bright specular color
    static const uint16_t SPECULAR = star_colors::RGB565(255, 245, 200);

    for (int y = 0; y < SIZE; y++) {
        for (int x = 0; x < SIZE; x++) {
            int idx = (y * SIZE + x) * 2;
            uint8_t a = alpha[y * SIZE + x];
            if (a == 0) {
                rgb[idx] = rgb[idx + 1] = 0;
                continue;
            }

            // Edge pixels get outline color
            if (a < 255) {
                rgb[idx]     = outline_color & 0xFF;
                rgb[idx + 1] = (outline_color >> 8) & 0xFF;
                continue;
            }

            // Distance from light source (normalized 0..1)
            float dx = (x - light_x) / (float)SIZE;
            float dy = (y - light_y) / (float)SIZE;
            float dist_light = sqrtf(dx * dx + dy * dy);

            // Gradient: near light = bright body, far = shadow
            float shade = dist_light * 1.4f;  // Scale so bottom-right gets darker
            if (shade > 1.0f) shade = 1.0f;
            uint16_t base = BlendRGB565(body_color, SHADOW, shade * 0.55f);

            // Specular highlight — small bright spot near light source
            if (dist_light < 0.18f) {
                float spec = 1.0f - (dist_light / 0.18f);
                spec = spec * spec;  // Quadratic falloff for sharp highlight
                base = BlendRGB565(base, SPECULAR, spec * 0.85f);
            }

            // Secondary soft highlight — broader area
            if (dist_light < 0.35f) {
                float soft = 1.0f - (dist_light / 0.35f);
                base = BlendRGB565(base, HIGHLIGHT, soft * 0.3f);
            }

            // Edge darkening — pixels near alpha boundary get slightly darker
            // Check if any neighbor is transparent
            bool near_edge = false;
            for (int ey = -2; ey <= 2 && !near_edge; ey++)
                for (int ex = -2; ex <= 2 && !near_edge; ex++) {
                    int nx = x + ex, ny = y + ey;
                    if (nx >= 0 && nx < SIZE && ny >= 0 && ny < SIZE) {
                        if (alpha[ny * SIZE + nx] == 0)
                            near_edge = true;
                    }
                }
            if (near_edge) {
                base = BlendRGB565(base, outline_color, 0.4f);
            }

            rgb[idx]     = base & 0xFF;
            rgb[idx + 1] = (base >> 8) & 0xFF;
        }
    }
}

// ============================================================================
// DRAWING PRIMITIVES — all coords for 64x64
// ============================================================================

void StarEmoji32::DrawPixel(uint8_t* rgb, int x, int y, uint16_t color) {
    if (x < 0 || x >= SIZE || y < 0 || y >= SIZE) return;
    int idx = (y * SIZE + x) * 2;
    rgb[idx]     = color & 0xFF;
    rgb[idx + 1] = (color >> 8) & 0xFF;
}

void StarEmoji32::DrawDot(uint8_t* rgb, int cx, int cy, int r, uint16_t color) {
    for (int dy = -r; dy <= r; dy++)
        for (int dx = -r; dx <= r; dx++)
            if (dx * dx + dy * dy <= r * r)
                DrawPixel(rgb, cx + dx, cy + dy, color);
}

void StarEmoji32::DrawLine(uint8_t* rgb, int x0, int y0, int x1, int y1, uint16_t color) {
    int dx = abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
    int dy = -abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
    int err = dx + dy;
    while (true) {
        DrawPixel(rgb, x0, y0, color);
        if (x0 == x1 && y0 == y1) break;
        int e2 = 2 * err;
        if (e2 >= dy) { err += dy; x0 += sx; }
        if (e2 <= dx) { err += dx; y0 += sy; }
    }
}

void StarEmoji32::DrawArc(uint8_t* rgb, int cx, int cy, int r,
                           int start_deg, int end_deg, uint16_t color) {
    for (int deg = start_deg; deg <= end_deg; deg += 2) {
        float rad = deg * M_PI / 180.0f;
        DrawPixel(rgb, cx + (int)(r * cosf(rad) + 0.5f),
                       cy + (int)(r * sinf(rad) + 0.5f), color);
    }
}

// ============================================================================
// EYE EXPRESSIONS — scaled to 64x64 (roughly 2x the 32x32 coords)
// ============================================================================

void StarEmoji32::DrawEyesNormal(uint8_t* rgb) {
    DrawDot(rgb, 22, 28, 3, EYES);
    DrawDot(rgb, 41, 28, 3, EYES);
}

void StarEmoji32::DrawEyesHappy(uint8_t* rgb) {
    DrawArc(rgb, 22, 28, 5, 200, 340, EYES);
    DrawArc(rgb, 22, 28, 4, 200, 340, EYES);
    DrawArc(rgb, 41, 28, 5, 200, 340, EYES);
    DrawArc(rgb, 41, 28, 4, 200, 340, EYES);
}

void StarEmoji32::DrawEyesSad(uint8_t* rgb) {
    DrawDot(rgb, 22, 30, 3, EYES);
    DrawDot(rgb, 41, 30, 3, EYES);
    // Sad eyebrows
    DrawLine(rgb, 17, 23, 27, 21, EYES);
    DrawLine(rgb, 17, 24, 27, 22, EYES);
    DrawLine(rgb, 36, 21, 46, 23, EYES);
    DrawLine(rgb, 36, 22, 46, 24, EYES);
}

void StarEmoji32::DrawEyesAngry(uint8_t* rgb) {
    DrawDot(rgb, 22, 30, 3, EYES);
    DrawDot(rgb, 41, 30, 3, EYES);
    // Angry eyebrows (furrowed)
    DrawLine(rgb, 16, 22, 27, 26, EYES);
    DrawLine(rgb, 16, 23, 27, 27, EYES);
    DrawLine(rgb, 36, 26, 47, 22, EYES);
    DrawLine(rgb, 36, 27, 47, 23, EYES);
}

void StarEmoji32::DrawEyesSurprised(uint8_t* rgb) {
    DrawDot(rgb, 22, 28, 5, EYES);
    DrawDot(rgb, 41, 28, 5, EYES);
    // White highlight
    DrawDot(rgb, 20, 26, 1, WHITE);
    DrawDot(rgb, 39, 26, 1, WHITE);
}

void StarEmoji32::DrawEyesLoving(uint8_t* rgb) {
    // Left heart
    DrawDot(rgb, 20, 26, 2, HEART);
    DrawDot(rgb, 24, 26, 2, HEART);
    for (int x = 18; x <= 26; x++) DrawPixel(rgb, x, 28, HEART);
    for (int x = 19; x <= 25; x++) DrawPixel(rgb, x, 29, HEART);
    for (int x = 20; x <= 24; x++) DrawPixel(rgb, x, 30, HEART);
    for (int x = 21; x <= 23; x++) DrawPixel(rgb, x, 31, HEART);
    DrawPixel(rgb, 22, 32, HEART);
    // Right heart
    DrawDot(rgb, 39, 26, 2, HEART);
    DrawDot(rgb, 43, 26, 2, HEART);
    for (int x = 37; x <= 45; x++) DrawPixel(rgb, x, 28, HEART);
    for (int x = 38; x <= 44; x++) DrawPixel(rgb, x, 29, HEART);
    for (int x = 39; x <= 43; x++) DrawPixel(rgb, x, 30, HEART);
    for (int x = 40; x <= 42; x++) DrawPixel(rgb, x, 31, HEART);
    DrawPixel(rgb, 41, 32, HEART);
}

void StarEmoji32::DrawEyesCool(uint8_t* rgb) {
    // Sunglasses - thicker for 64x64
    for (int y = 26; y <= 32; y++) {
        for (int x = 15; x <= 27; x++) DrawPixel(rgb, x, y, SUNGLASSES);
        for (int x = 36; x <= 48; x++) DrawPixel(rgb, x, y, SUNGLASSES);
    }
    // Bridge
    for (int y = 28; y <= 30; y++)
        DrawLine(rgb, 28, y, 35, y, SUNGLASSES);
}

void StarEmoji32::DrawEyesSleepy(uint8_t* rgb) {
    DrawLine(rgb, 17, 28, 27, 28, EYES);
    DrawLine(rgb, 17, 29, 27, 29, EYES);
    DrawLine(rgb, 36, 28, 46, 28, EYES);
    DrawLine(rgb, 36, 29, 46, 29, EYES);
}

void StarEmoji32::DrawEyesWinking(uint8_t* rgb) {
    DrawDot(rgb, 22, 28, 3, EYES);
    DrawLine(rgb, 36, 28, 46, 28, EYES);
    DrawLine(rgb, 36, 29, 46, 29, EYES);
}

void StarEmoji32::DrawEyesThinking(uint8_t* rgb) {
    DrawDot(rgb, 22, 28, 3, EYES);
    DrawDot(rgb, 41, 26, 3, EYES);  // Looking up
    // Raised eyebrow
    DrawArc(rgb, 41, 20, 6, 200, 340, EYES);
    DrawArc(rgb, 41, 21, 6, 200, 340, EYES);
}

void StarEmoji32::DrawEyesCrying(uint8_t* rgb) {
    DrawDot(rgb, 22, 28, 3, EYES);
    DrawDot(rgb, 41, 28, 3, EYES);
    // Tears streaming down
    for (int y = 32; y <= 40; y++) {
        DrawPixel(rgb, 22, y, TEAR);
        DrawPixel(rgb, 23, y, TEAR);
        DrawPixel(rgb, 41, y, TEAR);
        DrawPixel(rgb, 42, y, TEAR);
    }
    // Sad eyebrows
    DrawLine(rgb, 17, 23, 27, 21, EYES);
    DrawLine(rgb, 36, 21, 46, 23, EYES);
}

// ============================================================================
// MOUTH EXPRESSIONS — scaled to 64x64
// ============================================================================

void StarEmoji32::DrawMouthNeutral(uint8_t* rgb) {
    DrawLine(rgb, 26, 43, 37, 43, MOUTH);
    DrawLine(rgb, 26, 44, 37, 44, MOUTH);
}

void StarEmoji32::DrawMouthSmile(uint8_t* rgb) {
    DrawArc(rgb, 31, 39, 8, 20, 160, MOUTH);
    DrawArc(rgb, 31, 39, 7, 20, 160, MOUTH);
}

void StarEmoji32::DrawMouthSad(uint8_t* rgb) {
    DrawArc(rgb, 31, 47, 7, 200, 340, MOUTH);
    DrawArc(rgb, 31, 47, 6, 200, 340, MOUTH);
}

void StarEmoji32::DrawMouthOpen(uint8_t* rgb) {
    DrawDot(rgb, 31, 43, 4, MOUTH);
    DrawDot(rgb, 31, 43, 2, INNER_MOUTH);
}

void StarEmoji32::DrawMouthGrin(uint8_t* rgb) {
    DrawArc(rgb, 31, 39, 10, 10, 170, MOUTH);
    DrawArc(rgb, 31, 39, 9, 10, 170, MOUTH);
    DrawLine(rgb, 21, 39, 41, 39, MOUTH);
    for (int x = 24; x <= 38; x++) {
        DrawPixel(rgb, x, 40, INNER_MOUTH);
        DrawPixel(rgb, x, 41, INNER_MOUTH);
    }
}

void StarEmoji32::DrawMouthKiss(uint8_t* rgb) {
    DrawDot(rgb, 31, 43, 3, TONGUE);
    DrawDot(rgb, 31, 43, 1, INNER_MOUTH);
}

void StarEmoji32::DrawMouthTongue(uint8_t* rgb) {
    DrawArc(rgb, 31, 39, 8, 20, 160, MOUTH);
    DrawArc(rgb, 31, 39, 7, 20, 160, MOUTH);
    // Tongue
    for (int y = 45; y <= 49; y++) {
        DrawPixel(rgb, 30, y, TONGUE);
        DrawPixel(rgb, 31, y, TONGUE);
        DrawPixel(rgb, 32, y, TONGUE);
    }
}

// ============================================================================
// STAR IMAGE CREATION
// ============================================================================

StarEmoji32::StarImage* StarEmoji32::CreateStarEmoji(
    void (*drawEyes)(uint8_t*), void (*drawMouth)(uint8_t*)) {

    if (image_count_ >= MAX_IMAGES) {
        ESP_LOGE(TAG, "Too many star images!");
        return nullptr;
    }

    StarImage* img = &images_[image_count_];
    img->pixels = (uint8_t*)heap_caps_calloc(1, TOTAL_SIZE, MALLOC_CAP_DEFAULT);
    if (!img->pixels) {
        ESP_LOGE(TAG, "Failed to allocate star image (%d bytes)", TOTAL_SIZE);
        return nullptr;
    }

    uint8_t* rgb_data = img->pixels;
    uint8_t* alpha_data = img->pixels + RGB_SIZE;

    GenerateStarMask(alpha_data);
    FillStarColor(rgb_data, alpha_data, STAR_BODY, STAR_EDGE);

    if (drawEyes) drawEyes(rgb_data);
    if (drawMouth) drawMouth(rgb_data);

    image_count_++;
    return img;
}

// ============================================================================
// CONSTRUCTOR
// ============================================================================

StarEmoji32::StarEmoji32() {
    ESP_LOGI(TAG, "Creating star emoji collection (%dx%d)", SIZE, SIZE);

    struct EmotionDef {
        const char* name;
        void (*eyes)(uint8_t*);
        void (*mouth)(uint8_t*);
    };

    static const EmotionDef emotions[] = {
        { "neutral",      DrawEyesNormal,    DrawMouthNeutral },
        { "happy",        DrawEyesHappy,     DrawMouthSmile   },
        { "laughing",     DrawEyesHappy,     DrawMouthGrin    },
        { "funny",        DrawEyesHappy,     DrawMouthGrin    },
        { "sad",          DrawEyesSad,       DrawMouthSad     },
        { "angry",        DrawEyesAngry,     DrawMouthSad     },
        { "crying",       DrawEyesCrying,    DrawMouthSad     },
        { "loving",       DrawEyesLoving,    DrawMouthSmile   },
        { "embarrassed",  DrawEyesNormal,    DrawMouthSmile   },
        { "surprised",    DrawEyesSurprised, DrawMouthOpen    },
        { "shocked",      DrawEyesSurprised, DrawMouthOpen    },
        { "thinking",     DrawEyesThinking,  DrawMouthNeutral },
        { "winking",      DrawEyesWinking,   DrawMouthSmile   },
        { "cool",         DrawEyesCool,      DrawMouthSmile   },
        { "relaxed",      DrawEyesHappy,     DrawMouthSmile   },
        { "delicious",    DrawEyesHappy,     DrawMouthTongue  },
        { "kissy",        DrawEyesWinking,   DrawMouthKiss    },
        { "confident",    DrawEyesNormal,    DrawMouthSmile   },
        { "sleepy",       DrawEyesSleepy,    DrawMouthNeutral },
        { "silly",        DrawEyesWinking,   DrawMouthTongue  },
        { "confused",     DrawEyesThinking,  DrawMouthSad     },
    };

    for (const auto& emo : emotions) {
        StarImage* img = CreateStarEmoji(emo.eyes, emo.mouth);
        if (img) {
            if (strcmp(emo.name, "embarrassed") == 0) {
                DrawDot(img->pixels, 16, 38, 4, BLUSH);
                DrawDot(img->pixels, 47, 38, 4, BLUSH);
            }
            AddEmoji(emo.name, new LvglAllocatedImage(
                img->pixels, TOTAL_SIZE, SIZE, SIZE, STRIDE,
                LV_COLOR_FORMAT_RGB565A8));
            img->pixels = nullptr;
        }
    }

    ESP_LOGI(TAG, "Star emoji collection ready (%d emotions)", image_count_);
}

StarEmoji32::~StarEmoji32() {
    for (int i = 0; i < image_count_; i++) {
        if (images_[i].pixels) {
            heap_caps_free(images_[i].pixels);
            images_[i].pixels = nullptr;
        }
    }
}
