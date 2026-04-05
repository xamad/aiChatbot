#include "star_emoji.h"
#include <cstring>
#include <cmath>
#include <cstdlib>
#include <esp_log.h>
#include <esp_heap_caps.h>

#define TAG "StarEmoji"
using namespace star_colors;

// ============================================================================
// STAR SHAPE — Smooth polar star with rounded tips (like glossy 3D reference)
// ============================================================================

void StarEmoji32::GenerateStarMask(uint8_t* alpha) {
    memset(alpha, 0, SIZE * SIZE);

    const float cx = 31.5f, cy = 31.5f;
    const float outer_r = 29.0f;   // Tip radius
    const float inner_r = 21.0f;   // Valley radius (ratio ~0.72 = extra chubby)

    for (int y = 0; y < SIZE; y++) {
        for (int x = 0; x < SIZE; x++) {
            float dx = x - cx;
            float dy = y - cy;
            float dist = sqrtf(dx * dx + dy * dy);
            float angle = atan2f(dy, dx);

            // Rotate so top point faces up
            float a = angle + (float)M_PI * 0.5f;
            if (a < 0) a += (float)M_PI * 2.0f;

            // Smooth star function: cos(5*a) creates 5 peaks
            // t goes 0 (valley) to 1 (peak)
            float t = 0.5f * (1.0f + cosf(5.0f * a));

            // Mild rounding — keep star points visible but not sharp
            t = powf(t, 0.75f);

            float r = inner_r + (outer_r - inner_r) * t;

            // Anti-aliased edge with 1.8px gradient
            float edge = r - dist;
            if (edge > 1.8f)
                alpha[y * SIZE + x] = 255;
            else if (edge > 0)
                alpha[y * SIZE + x] = (uint8_t)(edge / 1.8f * 255.0f);
            else
                alpha[y * SIZE + x] = 0;
        }
    }
}

// ============================================================================
// 3D GLOSSY FILL — Multi-highlight shading like reference image
// ============================================================================

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

void StarEmoji32::FillStarColor(uint8_t* rgb, const uint8_t* alpha) {
    const float cx = 31.5f, cy = 31.5f;

    // Primary light: upper-left (matching reference highlights)
    const float lx1 = 18.0f, ly1 = 12.0f;
    // Secondary light: upper-right (subtle fill)
    const float lx2 = 44.0f, ly2 = 16.0f;

    for (int y = 0; y < SIZE; y++) {
        for (int x = 0; x < SIZE; x++) {
            int idx = (y * SIZE + x) * 2;
            uint8_t a = alpha[y * SIZE + x];
            if (a == 0) {
                rgb[idx] = rgb[idx + 1] = 0;
                continue;
            }

            // --- Base color: vertical gradient (bright top → deep gold bottom)
            float vert = (float)y / (float)SIZE;  // 0=top, 1=bottom
            uint16_t base;
            if (vert < 0.3f) {
                base = BlendRGB565(STAR_TOP, STAR_BODY, vert / 0.3f);
            } else {
                base = BlendRGB565(STAR_BODY, STAR_BOTTOM, (vert - 0.3f) / 0.7f);
            }

            // --- Shadow: distance from center, bottom-right darkening
            float dx_c = (x - cx) / 32.0f;
            float dy_c = (y - cy) / 32.0f;
            float center_dist = sqrtf(dx_c * dx_c + dy_c * dy_c);
            // Bottom-right shadow bias
            float shadow_bias = (dx_c * 0.3f + dy_c * 0.5f);
            if (shadow_bias > 0) {
                base = BlendRGB565(base, STAR_SHADOW, shadow_bias * 0.35f);
            }

            // --- Edge rim: pixels near alpha boundary get orange rim
            bool near_edge = false;
            int edge_dist = 99;
            for (int ey = -3; ey <= 3 && !near_edge; ey++) {
                for (int ex = -3; ex <= 3 && !near_edge; ex++) {
                    int nx = x + ex, ny = y + ey;
                    if (nx >= 0 && nx < SIZE && ny >= 0 && ny < SIZE) {
                        if (alpha[ny * SIZE + nx] == 0) {
                            near_edge = true;
                            int d = abs(ex) + abs(ey);
                            if (d < edge_dist) edge_dist = d;
                        }
                    }
                }
            }
            if (near_edge) {
                float rim_strength = (edge_dist <= 2) ? 0.6f : 0.3f;
                base = BlendRGB565(base, STAR_EDGE, rim_strength);
            }

            // Semi-transparent edge pixels: blend more toward rim color
            if (a < 255) {
                base = BlendRGB565(base, STAR_EDGE, 0.7f);
                rgb[idx]     = base & 0xFF;
                rgb[idx + 1] = (base >> 8) & 0xFF;
                continue;
            }

            // --- Primary specular highlight (upper-left, like reference)
            float dx1 = (x - lx1) / (float)SIZE;
            float dy1 = (y - ly1) / (float)SIZE;
            float d1 = sqrtf(dx1 * dx1 + dy1 * dy1);
            // Hot spot — very small, near-white
            if (d1 < 0.12f) {
                float s = 1.0f - (d1 / 0.12f);
                s = s * s * s;  // Cubic falloff for sharp glare
                base = BlendRGB565(base, SPECULAR_HOT, s * 0.9f);
            }
            // Medium glow around hot spot
            if (d1 < 0.25f) {
                float s = 1.0f - (d1 / 0.25f);
                s = s * s;
                base = BlendRGB565(base, SPECULAR_MID, s * 0.45f);
            }
            // Broad warm highlight
            if (d1 < 0.42f) {
                float s = 1.0f - (d1 / 0.42f);
                base = BlendRGB565(base, HIGHLIGHT, s * 0.25f);
            }

            // --- Secondary highlight (upper-right, subtle)
            float dx2 = (x - lx2) / (float)SIZE;
            float dy2 = (y - ly2) / (float)SIZE;
            float d2 = sqrtf(dx2 * dx2 + dy2 * dy2);
            if (d2 < 0.15f) {
                float s = 1.0f - (d2 / 0.15f);
                s = s * s;
                base = BlendRGB565(base, SPECULAR_MID, s * 0.35f);
            }

            // --- Bottom rim highlight (subtle reflected light, like reference)
            float dx3 = (x - 35.0f) / (float)SIZE;
            float dy3 = (y - 52.0f) / (float)SIZE;
            float d3 = sqrtf(dx3 * dx3 + dy3 * dy3);
            if (d3 < 0.1f) {
                float s = 1.0f - (d3 / 0.1f);
                s = s * s;
                base = BlendRGB565(base, HIGHLIGHT, s * 0.2f);
            }

            rgb[idx]     = base & 0xFF;
            rgb[idx + 1] = (base >> 8) & 0xFF;
        }
    }
}

// ============================================================================
// DRAWING PRIMITIVES
// ============================================================================

void StarEmoji32::DrawPixel(uint8_t* rgb, int x, int y, uint16_t color) {
    if (x < 0 || x >= SIZE || y < 0 || y >= SIZE) return;
    int idx = (y * SIZE + x) * 2;
    rgb[idx]     = color & 0xFF;
    rgb[idx + 1] = (color >> 8) & 0xFF;
}

void StarEmoji32::DrawPixelAlpha(uint8_t* rgb, int x, int y, uint16_t color, float a) {
    if (x < 0 || x >= SIZE || y < 0 || y >= SIZE || a <= 0.0f) return;
    if (a >= 1.0f) { DrawPixel(rgb, x, y, color); return; }
    int idx = (y * SIZE + x) * 2;
    uint16_t bg = rgb[idx] | (rgb[idx + 1] << 8);
    uint16_t blended = BlendRGB565(bg, color, a);
    rgb[idx]     = blended & 0xFF;
    rgb[idx + 1] = (blended >> 8) & 0xFF;
}

void StarEmoji32::DrawDot(uint8_t* rgb, int cx, int cy, int r, uint16_t color) {
    for (int dy = -r; dy <= r; dy++)
        for (int dx = -r; dx <= r; dx++)
            if (dx * dx + dy * dy <= r * r)
                DrawPixel(rgb, cx + dx, cy + dy, color);
}

// Anti-aliased filled circle (sub-pixel precision)
void StarEmoji32::DrawSoftDot(uint8_t* rgb, float cx, float cy, float r, uint16_t color) {
    int x0 = (int)(cx - r - 1), x1 = (int)(cx + r + 1);
    int y0 = (int)(cy - r - 1), y1 = (int)(cy + r + 1);
    for (int y = y0; y <= y1; y++) {
        for (int x = x0; x <= x1; x++) {
            float dx = x - cx, dy = y - cy;
            float dist = sqrtf(dx * dx + dy * dy);
            if (dist <= r - 0.8f) {
                DrawPixel(rgb, x, y, color);
            } else if (dist < r + 0.5f) {
                float a = 1.0f - (dist - (r - 0.8f)) / 1.3f;
                if (a > 0) DrawPixelAlpha(rgb, x, y, color, a);
            }
        }
    }
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
        float rad = deg * (float)M_PI / 180.0f;
        DrawPixel(rgb, cx + (int)(r * cosf(rad) + 0.5f),
                       cy + (int)(r * sinf(rad) + 0.5f), color);
    }
}

void StarEmoji32::DrawThickArc(uint8_t* rgb, int cx, int cy, float r, float thickness,
                                int start_deg, int end_deg, uint16_t color) {
    for (int deg = start_deg; deg <= end_deg; deg += 1) {
        float rad = deg * (float)M_PI / 180.0f;
        float px = cx + r * cosf(rad);
        float py = cy + r * sinf(rad);
        DrawSoftDot(rgb, px, py, thickness * 0.5f, color);
    }
}

// ============================================================================
// CUTE EYE — Kawaii style: black pupil + iris ring + white shine dots
// ============================================================================

void StarEmoji32::DrawCuteEye(uint8_t* rgb, int cx, int cy, int r, bool look_up) {
    int ey = look_up ? cy - 1 : cy;

    // Outer iris ring (dark brown, slightly larger)
    DrawSoftDot(rgb, cx, ey, r + 0.8f, EYE_BROWN);
    // Main pupil (deep black)
    DrawSoftDot(rgb, cx, ey, (float)r, EYE_BLACK);

    if (r >= 3) {
        // Primary shine — upper-left of pupil (large, bright white)
        DrawSoftDot(rgb, cx - r * 0.35f, ey - r * 0.4f, r * 0.4f, EYE_SHINE);
        // Secondary shine — lower-right (smaller, subtle)
        DrawSoftDot(rgb, cx + r * 0.3f, ey + r * 0.35f, r * 0.2f, EYE_SHINE2);
    } else {
        // Small eyes: just a single shine pixel
        DrawPixel(rgb, cx - 1, ey - 1, EYE_SHINE);
    }
}

void StarEmoji32::DrawClosedEye(uint8_t* rgb, int cx, int cy) {
    // Curved closed eye — arc with slight thickness
    DrawThickArc(rgb, cx, cy - 1, 5.0f, 2.0f, 10, 170, MOUTH);
}

// ============================================================================
// EYE EXPRESSIONS — cute kawaii style, 64x64
// ============================================================================

// Eye positions (tuned for puffy star body)
static constexpr int EL_X = 22, ER_X = 41, EY = 29;

void StarEmoji32::DrawEyesNormal(uint8_t* rgb) {
    DrawCuteEye(rgb, EL_X, EY, 4);
    DrawCuteEye(rgb, ER_X, EY, 4);
}

void StarEmoji32::DrawEyesHappy(uint8_t* rgb) {
    // Closed happy arcs (upside-down U) — "squint smile"
    DrawThickArc(rgb, EL_X, EY + 1, 5.0f, 2.2f, 200, 340, MOUTH);
    DrawThickArc(rgb, ER_X, EY + 1, 5.0f, 2.2f, 200, 340, MOUTH);
}

void StarEmoji32::DrawEyesSad(uint8_t* rgb) {
    DrawCuteEye(rgb, EL_X, EY + 1, 4);
    DrawCuteEye(rgb, ER_X, EY + 1, 4);
    // Sad eyebrows — inner ends up
    DrawThickArc(rgb, EL_X, EY - 6, 8.0f, 1.5f, 340, 380, MOUTH);
    DrawThickArc(rgb, ER_X, EY - 6, 8.0f, 1.5f, 160, 200, MOUTH);
}

void StarEmoji32::DrawEyesAngry(uint8_t* rgb) {
    DrawCuteEye(rgb, EL_X, EY + 1, 3);
    DrawCuteEye(rgb, ER_X, EY + 1, 3);
    // Angry furrowed brows — inner ends down
    DrawLine(rgb, 16, 22, 28, 26, MOUTH);
    DrawLine(rgb, 16, 23, 28, 27, MOUTH);
    DrawLine(rgb, 35, 26, 47, 22, MOUTH);
    DrawLine(rgb, 35, 27, 47, 23, MOUTH);
}

void StarEmoji32::DrawEyesSurprised(uint8_t* rgb) {
    // Big wide eyes — larger radius
    DrawCuteEye(rgb, EL_X, EY, 6);
    DrawCuteEye(rgb, ER_X, EY, 6);
}

void StarEmoji32::DrawEyesLoving(uint8_t* rgb) {
    // Heart eyes — two little hearts
    // Left heart
    DrawSoftDot(rgb, EL_X - 2.5f, 26, 2.5f, HEART);
    DrawSoftDot(rgb, EL_X + 2.5f, 26, 2.5f, HEART);
    for (int x = EL_X - 5; x <= EL_X + 5; x++) {
        DrawPixel(rgb, x, 28, HEART);
        DrawPixel(rgb, x, 29, HEART);
    }
    for (int x = EL_X - 4; x <= EL_X + 4; x++) DrawPixel(rgb, x, 30, HEART);
    for (int x = EL_X - 3; x <= EL_X + 3; x++) DrawPixel(rgb, x, 31, HEART);
    for (int x = EL_X - 2; x <= EL_X + 2; x++) DrawPixel(rgb, x, 32, HEART);
    for (int x = EL_X - 1; x <= EL_X + 1; x++) DrawPixel(rgb, x, 33, HEART);
    DrawPixel(rgb, EL_X, 34, HEART);
    // Shine on left heart
    DrawPixel(rgb, EL_X - 2, 25, EYE_SHINE);

    // Right heart
    DrawSoftDot(rgb, ER_X - 2.5f, 26, 2.5f, HEART);
    DrawSoftDot(rgb, ER_X + 2.5f, 26, 2.5f, HEART);
    for (int x = ER_X - 5; x <= ER_X + 5; x++) {
        DrawPixel(rgb, x, 28, HEART);
        DrawPixel(rgb, x, 29, HEART);
    }
    for (int x = ER_X - 4; x <= ER_X + 4; x++) DrawPixel(rgb, x, 30, HEART);
    for (int x = ER_X - 3; x <= ER_X + 3; x++) DrawPixel(rgb, x, 31, HEART);
    for (int x = ER_X - 2; x <= ER_X + 2; x++) DrawPixel(rgb, x, 32, HEART);
    for (int x = ER_X - 1; x <= ER_X + 1; x++) DrawPixel(rgb, x, 33, HEART);
    DrawPixel(rgb, ER_X, 34, HEART);
    DrawPixel(rgb, ER_X - 2, 25, EYE_SHINE);
}

void StarEmoji32::DrawEyesCool(uint8_t* rgb) {
    // Sleek sunglasses with lens reflection
    // Left lens
    for (int y = 26; y <= 33; y++)
        for (int x = 14; x <= 28; x++)
            DrawPixel(rgb, x, y, SUNGLASSES);
    // Right lens
    for (int y = 26; y <= 33; y++)
        for (int x = 35; x <= 49; x++)
            DrawPixel(rgb, x, y, SUNGLASSES);
    // Bridge
    for (int y = 28; y <= 31; y++)
        DrawLine(rgb, 29, y, 34, y, SUNGLASSES);
    // Lens reflections (subtle highlight stripe)
    DrawLine(rgb, 16, 27, 20, 27, SG_LENS);
    DrawLine(rgb, 37, 27, 41, 27, SG_LENS);
}

void StarEmoji32::DrawEyesSleepy(uint8_t* rgb) {
    // Gently closed — soft curved lines
    DrawThickArc(rgb, EL_X, EY, 5.0f, 2.0f, 10, 170, MOUTH);
    DrawThickArc(rgb, ER_X, EY, 5.0f, 2.0f, 10, 170, MOUTH);
}

void StarEmoji32::DrawEyesWinking(uint8_t* rgb) {
    // Left eye open, right eye closed wink
    DrawCuteEye(rgb, EL_X, EY, 4);
    DrawClosedEye(rgb, ER_X, EY);
}

void StarEmoji32::DrawEyesThinking(uint8_t* rgb) {
    DrawCuteEye(rgb, EL_X, EY, 4);
    DrawCuteEye(rgb, ER_X, EY - 2, 4, true);  // Looking up
    // Raised eyebrow on right
    DrawThickArc(rgb, ER_X, EY - 10, 7.0f, 1.5f, 200, 340, MOUTH);
}

void StarEmoji32::DrawEyesCrying(uint8_t* rgb) {
    DrawCuteEye(rgb, EL_X, EY, 4);
    DrawCuteEye(rgb, ER_X, EY, 4);
    // Sad eyebrows
    DrawThickArc(rgb, EL_X, EY - 6, 8.0f, 1.5f, 340, 380, MOUTH);
    DrawThickArc(rgb, ER_X, EY - 6, 8.0f, 1.5f, 160, 200, MOUTH);
    // Tear streams — tapered drops
    for (int t = 0; t < 10; t++) {
        float ty = EY + 5.0f + t;
        float tw = 1.5f - t * 0.1f;
        if (tw < 0.5f) tw = 0.5f;
        DrawSoftDot(rgb, EL_X + 2.0f, ty, tw, TEAR);
        DrawSoftDot(rgb, ER_X - 2.0f, ty, tw, TEAR);
    }
}

// ============================================================================
// MOUTH EXPRESSIONS — warmer, rounder
// ============================================================================

void StarEmoji32::DrawMouthNeutral(uint8_t* rgb) {
    // Gentle short line
    DrawThickArc(rgb, 31, 43, 0.1f, 2.0f, 0, 180, MOUTH);
    DrawLine(rgb, 27, 43, 36, 43, MOUTH);
    DrawLine(rgb, 27, 44, 36, 44, MOUTH);
}

void StarEmoji32::DrawMouthSmile(uint8_t* rgb) {
    // Soft smile curve
    DrawThickArc(rgb, 31, 39, 8.0f, 2.2f, 15, 165, MOUTH);
}

void StarEmoji32::DrawMouthSad(uint8_t* rgb) {
    // Downturned curve
    DrawThickArc(rgb, 31, 48, 7.0f, 2.0f, 200, 340, MOUTH);
}

void StarEmoji32::DrawMouthOpen(uint8_t* rgb) {
    // Round open mouth — "O" shape
    DrawSoftDot(rgb, 31, 43, 5.0f, MOUTH);
    DrawSoftDot(rgb, 31, 43, 3.0f, INNER_MOUTH);
}

void StarEmoji32::DrawMouthGrin(uint8_t* rgb) {
    // Wide grin with dark interior
    DrawThickArc(rgb, 31, 38, 10.0f, 2.2f, 10, 170, MOUTH);
    DrawLine(rgb, 21, 39, 41, 39, MOUTH);
    // Dark interior fill
    for (int y = 40; y <= 44; y++) {
        int hw = 9 - (y - 40) * 2;
        if (hw < 1) hw = 1;
        for (int x = 31 - hw; x <= 31 + hw; x++)
            DrawPixel(rgb, x, y, INNER_MOUTH);
    }
}

void StarEmoji32::DrawMouthKiss(uint8_t* rgb) {
    // Small puckered lips
    DrawSoftDot(rgb, 31, 43, 3.5f, TONGUE);
    DrawSoftDot(rgb, 31, 43, 1.8f, INNER_MOUTH);
    // Shine on lips
    DrawPixel(rgb, 30, 42, EYE_SHINE);
}

void StarEmoji32::DrawMouthTongue(uint8_t* rgb) {
    // Smile + tongue sticking out
    DrawThickArc(rgb, 31, 39, 8.0f, 2.2f, 15, 165, MOUTH);
    // Tongue (rounded)
    DrawSoftDot(rgb, 31, 47, 3.5f, TONGUE);
    DrawSoftDot(rgb, 31, 46, 3.0f, TONGUE);
    // Tongue center line
    DrawLine(rgb, 31, 44, 31, 49, INNER_MOUTH);
}

// ============================================================================
// CREATE STAR IMAGE
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
    FillStarColor(rgb_data, alpha_data);

    if (drawEyes) drawEyes(rgb_data);
    if (drawMouth) drawMouth(rgb_data);

    image_count_++;
    return img;
}

// ============================================================================
// CONSTRUCTOR — build all 21 emotion variants
// ============================================================================

StarEmoji32::StarEmoji32() {
    ESP_LOGI(TAG, "Creating glossy star emoji collection (%dx%d)", SIZE, SIZE);

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
                // Soft blush circles on cheeks
                DrawSoftDot(img->pixels, 15.0f, 38.0f, 4.5f, BLUSH);
                DrawSoftDot(img->pixels, 48.0f, 38.0f, 4.5f, BLUSH);
            }
            AddEmoji(emo.name, new LvglAllocatedImage(
                img->pixels, TOTAL_SIZE, SIZE, SIZE, STRIDE,
                LV_COLOR_FORMAT_RGB565A8));
            img->pixels = nullptr;
        }
    }

    ESP_LOGI(TAG, "Glossy star emoji collection ready (%d emotions)", image_count_);
}

StarEmoji32::~StarEmoji32() {
    for (int i = 0; i < image_count_; i++) {
        if (images_[i].pixels) {
            heap_caps_free(images_[i].pixels);
            images_[i].pixels = nullptr;
        }
    }
}
