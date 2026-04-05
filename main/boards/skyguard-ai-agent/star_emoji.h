#pragma once

#include "display/lvgl_display/emoji_collection.h"
#include "display/lvgl_display/lvgl_image.h"
#include <lvgl.h>

// RGB565 color helpers — stored as little-endian (no byte swap needed for LVGL)
namespace star_colors {
    static constexpr uint16_t RGB565(uint8_t r, uint8_t g, uint8_t b) {
        return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3);
    }

    // Body gradient — bright yellow top → deep gold bottom (like reference)
    static constexpr uint16_t STAR_TOP     = RGB565(255, 230, 60);   // Bright yellow
    static constexpr uint16_t STAR_BODY    = RGB565(255, 200, 40);   // Rich gold
    static constexpr uint16_t STAR_BOTTOM  = RGB565(230, 165, 25);   // Deep gold
    static constexpr uint16_t STAR_EDGE    = RGB565(210, 140, 15);   // Orange rim
    static constexpr uint16_t STAR_SHADOW  = RGB565(180, 110, 10);   // Dark shadow
    static constexpr uint16_t SPECULAR_HOT = RGB565(255, 252, 230);  // Near-white highlight
    static constexpr uint16_t SPECULAR_MID = RGB565(255, 240, 160);  // Warm highlight
    static constexpr uint16_t HIGHLIGHT    = RGB565(255, 235, 120);  // Soft glow

    // Face features
    static constexpr uint16_t EYE_BLACK    = RGB565(25, 20, 15);     // Deep black pupil
    static constexpr uint16_t EYE_BROWN    = RGB565(60, 40, 20);     // Iris ring
    static constexpr uint16_t EYE_SHINE    = RGB565(255, 255, 255);  // Kawaii shine
    static constexpr uint16_t EYE_SHINE2   = RGB565(240, 240, 255);  // Secondary shine
    static constexpr uint16_t MOUTH        = RGB565(50, 30, 20);     // Warm dark brown
    static constexpr uint16_t INNER_MOUTH  = RGB565(70, 20, 20);     // Dark interior
    static constexpr uint16_t BLUSH        = RGB565(255, 140, 90);   // Warm blush
    static constexpr uint16_t HEART        = RGB565(220, 50, 50);    // Red heart
    static constexpr uint16_t TEAR         = RGB565(100, 170, 240);  // Blue tear
    static constexpr uint16_t TONGUE       = RGB565(230, 100, 100);  // Pink tongue
    static constexpr uint16_t SUNGLASSES   = RGB565(25, 25, 30);     // Cool black
    static constexpr uint16_t SG_LENS      = RGB565(50, 50, 70);     // Lens reflection
    static constexpr uint16_t WHITE        = RGB565(255, 255, 255);
}

// Star-shaped emoji collection for SkyGuard AI — 64x64 px
// Glossy 3D style inspired by smooth vector star graphics
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

public:
    // Shape generation — exposed for floating star avatar
    static void GenerateStarMask(uint8_t* alpha);
    static void FillStarColor(uint8_t* rgb, const uint8_t* alpha);
    static void DrawCuteEye(uint8_t* rgb, int cx, int cy, int r, bool look_up = false);
    static void DrawMouthNeutral(uint8_t* rgb);

private:

    // Drawing primitives
    static void DrawPixel(uint8_t* rgb, int x, int y, uint16_t color);
    static void DrawPixelAlpha(uint8_t* rgb, int x, int y, uint16_t color, float alpha);
    static void DrawDot(uint8_t* rgb, int cx, int cy, int r, uint16_t color);
    static void DrawSoftDot(uint8_t* rgb, float cx, float cy, float r, uint16_t color);
    static void DrawLine(uint8_t* rgb, int x0, int y0, int x1, int y1, uint16_t color);
    static void DrawArc(uint8_t* rgb, int cx, int cy, int r,
                        int start_deg, int end_deg, uint16_t color);
    static void DrawThickArc(uint8_t* rgb, int cx, int cy, float r, float thickness,
                             int start_deg, int end_deg, uint16_t color);

    // (DrawCuteEye declared in public section above)
    static void DrawClosedEye(uint8_t* rgb, int cx, int cy);

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

    // Mouth expressions (DrawMouthNeutral declared in public section above)
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
