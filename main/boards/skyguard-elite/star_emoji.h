#pragma once

#include "display/lvgl_display/emoji_collection.h"
#include "display/lvgl_display/lvgl_image.h"
#include <lvgl.h>

// RGB565 color helpers — stored as little-endian (no byte swap needed for LVGL)
namespace star_colors {
    static constexpr uint16_t RGB565(uint8_t r, uint8_t g, uint8_t b) {
        return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3);
    }

    static constexpr uint16_t STAR_BODY   = RGB565(255, 200, 50);   // Gold
    static constexpr uint16_t STAR_EDGE   = RGB565(200, 150, 20);   // Darker gold edge
    static constexpr uint16_t EYES        = RGB565(40, 30, 20);     // Dark brown
    static constexpr uint16_t MOUTH       = RGB565(40, 30, 20);     // Dark brown
    static constexpr uint16_t BLUSH       = RGB565(255, 130, 80);   // Blush/orange
    static constexpr uint16_t HEART       = RGB565(220, 50, 50);    // Red
    static constexpr uint16_t TEAR        = RGB565(80, 140, 220);   // Blue tear
    static constexpr uint16_t TONGUE      = RGB565(220, 80, 80);    // Pink tongue
    static constexpr uint16_t SUNGLASSES  = RGB565(30, 30, 30);     // Black
    static constexpr uint16_t HIGHLIGHT   = RGB565(255, 230, 120);  // Bright gold
    static constexpr uint16_t WHITE       = RGB565(255, 255, 255);
    static constexpr uint16_t INNER_MOUTH = RGB565(60, 20, 20);     // Dark interior
}

// Star-shaped emoji collection for SkyGuard AI — 64x64 px
class StarEmoji32 : public EmojiCollection {
public:
    StarEmoji32();
    ~StarEmoji32() override;

private:
    struct StarImage {
        uint8_t* pixels;
        lv_image_dsc_t descriptor;
    };

    static constexpr int SIZE = 64;
    static constexpr int STRIDE = SIZE * 2;
    static constexpr int RGB_SIZE = SIZE * STRIDE;
    static constexpr int ALPHA_SIZE = SIZE * SIZE;
    static constexpr int TOTAL_SIZE = RGB_SIZE + ALPHA_SIZE;

    static void GenerateStarMask(uint8_t* alpha);
    static void FillStarColor(uint8_t* rgb, const uint8_t* alpha,
                              uint16_t body_color, uint16_t outline_color);

    static void DrawPixel(uint8_t* rgb, int x, int y, uint16_t color);
    static void DrawDot(uint8_t* rgb, int cx, int cy, int r, uint16_t color);
    static void DrawLine(uint8_t* rgb, int x0, int y0, int x1, int y1, uint16_t color);
    static void DrawArc(uint8_t* rgb, int cx, int cy, int r,
                        int start_deg, int end_deg, uint16_t color);

    // Eye expressions
    static void DrawEyesNormal(uint8_t* rgb);
    static void DrawEyesHappy(uint8_t* rgb);
    static void DrawEyesSad(uint8_t* rgb);
    static void DrawEyesAngry(uint8_t* rgb);
    static void DrawEyesSurprised(uint8_t* rgb);
    static void DrawEyesLoving(uint8_t* rgb);
    static void DrawEyesCool(uint8_t* rgb);
    static void DrawEyesSleepy(uint8_t* rgb);
    static void DrawEyesWinking(uint8_t* rgb);
    static void DrawEyesThinking(uint8_t* rgb);
    static void DrawEyesCrying(uint8_t* rgb);

    // Mouth expressions
    static void DrawMouthNeutral(uint8_t* rgb);
    static void DrawMouthSmile(uint8_t* rgb);
    static void DrawMouthSad(uint8_t* rgb);
    static void DrawMouthOpen(uint8_t* rgb);
    static void DrawMouthGrin(uint8_t* rgb);
    static void DrawMouthKiss(uint8_t* rgb);
    static void DrawMouthTongue(uint8_t* rgb);

    StarImage* CreateStarEmoji(void (*drawEyes)(uint8_t*),
                                void (*drawMouth)(uint8_t*));

    static constexpr int MAX_IMAGES = 21;
    StarImage images_[MAX_IMAGES];
    int image_count_ = 0;
};
