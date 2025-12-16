#!/usr/bin/env python3
"""
Convert an image to WebP format.

Usage:
  python3 picture-convert-to-webp.py PATH/PictureName.png

The output will be saved as:
  PATH/PictureName.webp

Supports common image formats (png, jpg, jpeg, bmp, tiff, gif, etc.).

---------------------------------------------
CONFIGURATION VIA COMMENTED SWITCHES

You can enable / disable features below by
commenting or uncommenting the options.
---------------------------------------------
"""

import sys
import os
from PIL import Image, ImageOps

# ============================================================
# BASIC WEBP SETTINGS
# ============================================================

WEBP_QUALITY = 80        # 有損壓縮品質 (0–100)
WEBP_METHOD = 6          # 壓縮強度: 0=最快, 6=最慢但檔案最小

# ============================================================
# FEATURE TOGGLES (comment / uncomment)
# ============================================================

# AUTO_LOSSLESS_FOR_ALPHA:
#   True  -> 圖片含透明(alpha)時，自動使用 lossless
#   False -> 永遠使用有損壓縮
AUTO_LOSSLESS_FOR_ALPHA = True

# STRIP_METADATA:
#   True  -> 移除 EXIF / Metadata (檔案更小、隱私較佳)
#   False -> 嘗試保留 Metadata
STRIP_METADATA = True

# SKIP_IF_LARGER:
#   True  -> 若轉成 WebP 後檔案更大，則不輸出
#   False -> 不管大小都輸出 WebP
SKIP_IF_LARGER = True

# OVERWRITE_EXISTING:
#   True  -> 若 .webp 已存在，直接覆蓋
#   False -> 已存在時直接跳過
OVERWRITE_EXISTING = True

# ============================================================


def convert_to_webp(input_path: str) -> None:
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"File not found: {input_path}")

    base, _ = os.path.splitext(input_path)
    output_path = base + ".webp"

    if os.path.exists(output_path) and not OVERWRITE_EXISTING:
        print(f"Skip (exists): {output_path}")
        return

    original_size = os.path.getsize(input_path)

    with Image.open(input_path) as img:
        # Fix EXIF orientation (very common pitfall)
        img = ImageOps.exif_transpose(img)

        has_alpha = img.mode in ("RGBA", "LA") or (
            img.mode == "P" and "transparency" in img.info
        )

        save_kwargs = {
            "format": "WEBP",
            "method": WEBP_METHOD,
        }

        if AUTO_LOSSLESS_FOR_ALPHA and has_alpha:
            save_kwargs["lossless"] = True
        else:
            save_kwargs["quality"] = WEBP_QUALITY

        if not STRIP_METADATA and "exif" in img.info:
            save_kwargs["exif"] = img.info.get("exif")

        img.save(output_path, **save_kwargs)

    if SKIP_IF_LARGER:
        webp_size = os.path.getsize(output_path)
        if webp_size >= original_size:
            os.remove(output_path)
            print(f"Skip (larger): {output_path}")
            return

    abs_out = os.path.abspath(output_path)
    webp_size = os.path.getsize(output_path)
    ratio = webp_size / original_size if original_size else 0
    print(f"{abs_out} | size: {webp_size / 1024:.1f} KB | ratio: {ratio:.2%}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 picture-convert-to-webp.py PATH/PictureName.png")
        sys.exit(1)

    input_path = sys.argv[1]

    try:
        convert_to_webp(input_path)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
