#ifndef SKYGUARD_GIF_DECODE_H
#define SKYGUARD_GIF_DECODE_H

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <esp_heap_caps.h>

/**
 * Minimal GIF first-frame decoder for ESP32.
 * Decodes only the first image frame to RGB565 pixels.
 * Supports GIF87a/89a, global color table, LZW decompression.
 * Output is scaled to target width/height using nearest-neighbor.
 */

namespace GifDecode {

struct GifFrame {
    uint16_t* pixels;    // RGB565 output (caller must free)
    int width;           // Original GIF width
    int height;          // Original GIF height
    int out_w;           // Scaled output width
    int out_h;           // Scaled output height
};

// LZW decoder state
struct LzwState {
    const uint8_t* data;
    int data_len;
    int pos;             // Current byte position in data
    int bit_pos;         // Current bit position in current sub-block
    int block_size;      // Remaining bytes in current sub-block
    int block_start;     // Start of current sub-block data

    int min_code_size;
    int code_size;
    int clear_code;
    int end_code;
    int next_code;

    // Code table: prefix + suffix
    int prefix[4096];
    uint8_t suffix[4096];
    uint8_t stack[4096];
    int stack_top;
};

inline bool lzw_init(LzwState& s, const uint8_t* data, int data_len, int pos, int min_code_size) {
    s.data = data;
    s.data_len = data_len;
    s.pos = pos;
    s.bit_pos = 0;
    s.block_size = 0;
    s.block_start = 0;

    s.min_code_size = min_code_size;
    s.code_size = min_code_size + 1;
    s.clear_code = 1 << min_code_size;
    s.end_code = s.clear_code + 1;
    s.next_code = s.end_code + 1;
    s.stack_top = 0;

    // Initialize table with single-character entries
    for (int i = 0; i < s.clear_code; i++) {
        s.prefix[i] = -1;
        s.suffix[i] = (uint8_t)i;
    }
    return true;
}

// Read next sub-block byte, advancing through GIF sub-blocks
inline int lzw_next_byte(LzwState& s) {
    while (s.block_size == 0) {
        if (s.pos >= s.data_len) return -1;
        s.block_size = s.data[s.pos++];
        if (s.block_size == 0) return -1;  // Block terminator
        s.block_start = s.pos;
    }
    if (s.pos >= s.data_len) return -1;
    int b = s.data[s.pos++];
    s.block_size--;
    return b;
}

// Bit reader state for LZW decoding (no thread_local — safe for ESP32 FreeRTOS)
struct BitReader {
    int bit_buf = 0;
    int bits_in_buf = 0;
};

inline int lzw_read_code2(LzwState& s, BitReader& br) {
    int code = 0;
    int bits_needed = s.code_size;
    int bits_read = 0;

    while (bits_read < bits_needed) {
        if (br.bits_in_buf == 0) {
            int b = lzw_next_byte(s);
            if (b < 0) return -1;
            br.bit_buf = b;
            br.bits_in_buf = 8;
        }
        int take = bits_needed - bits_read;
        if (take > br.bits_in_buf) take = br.bits_in_buf;

        code |= (br.bit_buf & ((1 << take) - 1)) << bits_read;
        br.bit_buf >>= take;
        br.bits_in_buf -= take;
        bits_read += take;
    }
    return code;
}

/**
 * Decode first frame of a GIF to RGB565, scaled to out_w x out_h.
 * @param gif_data   Raw GIF file bytes
 * @param gif_len    Length of GIF data
 * @param out_w      Desired output width
 * @param out_h      Desired output height
 * @param frame      Output frame struct
 * @return true on success
 */
inline bool DecodeFirstFrame(const uint8_t* gif_data, int gif_len, int out_w, int out_h, GifFrame& frame) {
    frame.pixels = nullptr;
    if (gif_len < 13) return false;

    // Check GIF signature
    if (memcmp(gif_data, "GIF87a", 6) != 0 && memcmp(gif_data, "GIF89a", 6) != 0)
        return false;

    // Logical screen descriptor
    int gif_w = gif_data[6] | (gif_data[7] << 8);
    int gif_h = gif_data[8] | (gif_data[9] << 8);
    int packed = gif_data[10];
    int bg_color = gif_data[11];
    (void)bg_color;

    bool has_gct = (packed >> 7) & 1;
    int gct_size = has_gct ? (3 * (1 << ((packed & 7) + 1))) : 0;
    int color_depth = (packed & 7) + 1;
    int num_colors = 1 << color_depth;

    // Global color table
    int pos = 13;
    uint8_t gct[768] = {};  // Max 256 * 3
    if (has_gct) {
        if (pos + gct_size > gif_len) return false;
        memcpy(gct, gif_data + pos, gct_size);
        pos += gct_size;
    }

    // Skip extensions, find first image descriptor
    uint8_t* ct = gct;  // Active color table
    int ct_colors = num_colors;
    int transparent_idx = -1;
    (void)transparent_idx;

    while (pos < gif_len) {
        uint8_t block = gif_data[pos++];

        if (block == 0x3B) return false;  // Trailer — no image found

        if (block == 0x21) {
            // Extension block
            if (pos >= gif_len) return false;
            uint8_t ext_type = gif_data[pos++];

            if (ext_type == 0xF9 && pos + 4 < gif_len) {
                // Graphic control extension
                int block_len = gif_data[pos++];
                if (block_len >= 4) {
                    int gce_packed = gif_data[pos];
                    if (gce_packed & 1) {
                        transparent_idx = gif_data[pos + 3];
                    }
                    pos += block_len;
                }
            } else {
                // Skip other extensions
                while (pos < gif_len) {
                    int sub_len = gif_data[pos++];
                    if (sub_len == 0) break;
                    pos += sub_len;
                }
                continue;
            }

            // Skip sub-block terminator
            while (pos < gif_len) {
                int sub_len = gif_data[pos++];
                if (sub_len == 0) break;
                pos += sub_len;
            }
            continue;
        }

        if (block == 0x2C) {
            // Image descriptor
            if (pos + 9 > gif_len) return false;
            int img_left __attribute__((unused)) = gif_data[pos] | (gif_data[pos+1] << 8);
            int img_top __attribute__((unused)) = gif_data[pos+2] | (gif_data[pos+3] << 8);
            int img_w = gif_data[pos+4] | (gif_data[pos+5] << 8);
            int img_h = gif_data[pos+6] | (gif_data[pos+7] << 8);
            int img_packed = gif_data[pos+8];
            pos += 9;

            bool has_lct = (img_packed >> 7) & 1;
            bool interlaced = (img_packed >> 6) & 1;
            (void)interlaced;  // We handle interlace below

            if (has_lct) {
                int lct_colors = 1 << ((img_packed & 7) + 1);
                int lct_size = 3 * lct_colors;
                if (pos + lct_size > gif_len) return false;
                ct = (uint8_t*)(gif_data + pos);
                ct_colors = lct_colors;
                pos += lct_size;
            }

            // LZW minimum code size
            if (pos >= gif_len) return false;
            int min_code_size = gif_data[pos++];
            if (min_code_size < 2 || min_code_size > 11) return false;

            // Decode LZW to pixel indices
            int total_pixels = img_w * img_h;
            uint8_t* indices = (uint8_t*)heap_caps_malloc(total_pixels, MALLOC_CAP_SPIRAM);
            if (!indices) indices = (uint8_t*)malloc(total_pixels);
            if (!indices) return false;

            // Allocate LZW state from heap (too large for stack: ~24KB)
            LzwState* lzw_p = (LzwState*)heap_caps_malloc(sizeof(LzwState), MALLOC_CAP_SPIRAM);
            if (!lzw_p) lzw_p = (LzwState*)malloc(sizeof(LzwState));
            if (!lzw_p) { free(indices); return false; }
            LzwState& lzw = *lzw_p;
            lzw_init(lzw, gif_data, gif_len, pos, min_code_size);
            BitReader br;

            int pixel_idx = 0;
            int old_code = -1;

            while (pixel_idx < total_pixels) {
                int code = lzw_read_code2(lzw, br);
                if (code < 0 || code == lzw.end_code) break;

                if (code == lzw.clear_code) {
                    lzw.code_size = lzw.min_code_size + 1;
                    lzw.next_code = lzw.end_code + 1;
                    old_code = -1;
                    continue;
                }

                if (old_code == -1) {
                    // First code after clear
                    if (code < ct_colors) {
                        indices[pixel_idx++] = (uint8_t)code;
                    }
                    old_code = code;
                    continue;
                }

                int output_code = code;

                if (code >= lzw.next_code) {
                    // KwKwK special case: string = old_code_string + first_char(old_code_string)
                    // Find root (first char) of old_code by chasing prefix chain
                    int root = old_code;
                    while (root >= lzw.clear_code && root < 4096) root = lzw.prefix[root];
                    lzw.stack[lzw.stack_top++] = lzw.suffix[root < ct_colors ? root : 0];
                    output_code = old_code;
                }

                // Unwind code to stack
                while (output_code >= lzw.clear_code && lzw.stack_top < 4095) {
                    if (output_code >= 4096) break;  // Safety
                    lzw.stack[lzw.stack_top++] = lzw.suffix[output_code];
                    output_code = lzw.prefix[output_code];
                }
                uint8_t first_char = lzw.suffix[output_code < ct_colors ? output_code : 0];
                lzw.stack[lzw.stack_top++] = first_char;

                // Output stack in reverse
                while (lzw.stack_top > 0 && pixel_idx < total_pixels) {
                    indices[pixel_idx++] = lzw.stack[--lzw.stack_top];
                }

                // Add new code to table
                if (lzw.next_code < 4096 && old_code >= 0) {
                    lzw.prefix[lzw.next_code] = old_code;
                    lzw.suffix[lzw.next_code] = first_char;
                    lzw.next_code++;

                    if (lzw.next_code >= (1 << lzw.code_size) && lzw.code_size < 12) {
                        lzw.code_size++;
                    }
                }

                old_code = code;
            }

            free(lzw_p);  // Done with LZW state

            // Handle interlaced images — reorder rows
            uint8_t* ordered = indices;
            if (interlaced && img_h > 1) {
                ordered = (uint8_t*)heap_caps_malloc(total_pixels, MALLOC_CAP_SPIRAM);
                if (!ordered) ordered = (uint8_t*)malloc(total_pixels);
                if (ordered) {
                    // GIF interlace: pass 1 (rows 0,8,16...), pass 2 (4,12,20...),
                    // pass 3 (2,6,10...), pass 4 (1,3,5,7...)
                    static const int pass_start[] = {0, 4, 2, 1};
                    static const int pass_step[] = {8, 8, 4, 2};
                    int src_row = 0;
                    for (int pass = 0; pass < 4; pass++) {
                        for (int row = pass_start[pass]; row < img_h; row += pass_step[pass]) {
                            if (src_row < img_h) {
                                memcpy(ordered + row * img_w, indices + src_row * img_w, img_w);
                                src_row++;
                            }
                        }
                    }
                    free(indices);
                } else {
                    ordered = indices;  // Fallback: don't deinterlace
                }
            }

            // Scale and convert to RGB565
            frame.pixels = (uint16_t*)heap_caps_malloc(out_w * out_h * 2, MALLOC_CAP_SPIRAM);
            if (!frame.pixels) frame.pixels = (uint16_t*)malloc(out_w * out_h * 2);
            if (!frame.pixels) {
                free(ordered);
                return false;
            }

            frame.width = gif_w;
            frame.height = gif_h;
            frame.out_w = out_w;
            frame.out_h = out_h;

            // Nearest-neighbor scale from img area to output
            for (int y = 0; y < out_h; y++) {
                int src_y = (y * img_h) / out_h;
                if (src_y >= img_h) src_y = img_h - 1;
                for (int x = 0; x < out_w; x++) {
                    int src_x = (x * img_w) / out_w;
                    if (src_x >= img_w) src_x = img_w - 1;

                    int idx = ordered[src_y * img_w + src_x];
                    uint8_t r = ct[idx * 3];
                    uint8_t g = ct[idx * 3 + 1];
                    uint8_t b = ct[idx * 3 + 2];

                    // RGB565: RRRRRGGGGGGBBBBB
                    frame.pixels[y * out_w + x] = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3);
                }
            }

            free(ordered);
            return true;
        }

        // Unknown block — skip
        pos++;
    }

    return false;
}

}  // namespace GifDecode

#endif // SKYGUARD_GIF_DECODE_H
