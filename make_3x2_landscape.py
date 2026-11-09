# -*- coding: utf-8 -*-
"""
全部输出统一的 3:2 横版（1800x1200）。
竖图先顺时针转 90° 再裁 3:2，其余逻辑复用 make_3x2.py。

    python make_3x2_landscape.py

改 ROTATE 可换旋转方向：
    "cw"  顺时针 90°（默认）
    "ccw" 逆时针 90°
"""
import csv
import os
import re
import time
from math import ceil

from PIL import Image, ImageOps

import make_3x2 as M

SRC_DIR = M.SRC_DIR
OUT_DIR = r"D:\love_memory\out_3x2_landscape"
PREVIEW_DIR = r"D:\love_memory\preview_landscape"
ROTATE = "cw"          # cw / ccw
OUT_W, OUT_H = 1800, 1200


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def main():
    files = []
    for dp, _, fs in os.walk(SRC_DIR):
        for f in fs:
            if os.path.splitext(f)[1].lower() in M.EXTS:
                files.append(os.path.join(dp, f))
    files.sort(key=lambda p: natural_key(os.path.relpath(p, SRC_DIR)))

    for d in (OUT_DIR, PREVIEW_DIR):
        os.makedirs(d, exist_ok=True)

    SRGB = M.srgb_bytes()
    rows, t0, rotated_n = [], time.time(), 0

    for i, p in enumerate(files, 1):
        rel = os.path.relpath(p, SRC_DIR)
        stem = os.path.splitext(os.path.basename(p))[0]
        out_name = f"{i:03d}_{stem}.jpg"
        try:
            with Image.open(p) as raw:
                icc = raw.info.get("icc_profile")
                shot = None
                try:
                    ex = raw.getexif()
                    shot = ex.get(36867) or ex.get(306)
                except Exception:
                    pass
                im = ImageOps.exif_transpose(raw).convert("RGB")

            ow, oh = im.size
            rotated = oh > ow                      # 竖图 -> 转成横版
            if rotated:
                im = im.transpose(Image.Transpose.ROTATE_270 if ROTATE == "cw"
                                  else Image.Transpose.ROTATE_90)
                rotated_n += 1

            im, loss, how = M.crop_to_ratio(im, 1.5, M.CROP_BIAS_Y)
            im = im.resize((OUT_W, OUT_H), Image.Resampling.LANCZOS)
            im, icc_src = M.to_srgb(im, icc)

            kw = dict(format="JPEG", quality=M.JPEG_QUALITY, subsampling=M.SUBSAMPLING,
                      optimize=True, progressive=False)
            if SRGB:
                kw["icc_profile"] = SRGB
            im.save(os.path.join(OUT_DIR, out_name), **kw)

            pct = loss * 100
            rows.append({
                "序号": i, "输出文件": out_name, "原文件": rel,
                "原始尺寸": f"{ow}x{oh}",
                "原始比例": M.ratio_label(ow / oh if ow >= oh else oh / ow),
                "方向": "竖→转横" if rotated else "横",
                "处理": how if loss else "原样",
                "裁掉面积": f"{pct:.1f}%",
                "色彩": icc_src, "拍摄时间": shot or "",
            })
        except Exception as e:
            rows.append({"序号": i, "输出文件": "(失败)", "原文件": rel, "原始尺寸": "",
                         "原始比例": "", "方向": "", "处理": f"错误: {type(e).__name__}: {e}",
                         "裁掉面积": "", "色彩": "", "拍摄时间": ""})
            print(f"  !! {rel}: {e}")

        if i % 40 == 0 or i == len(files):
            el = time.time() - t0
            print(f"  {i}/{len(files)}  {el:.0f}s", flush=True)

    csv_path = os.path.join(os.path.dirname(OUT_DIR), "report_landscape.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    M.OUT_DIR = OUT_DIR
    M.PREVIEW_DIR = PREVIEW_DIR
    sheets = M.build_sheets([r for r in rows if r["输出文件"] != "(失败)"])

    print(f"\n完成 {len(rows)} 张，其中旋转 {rotated_n} 张，用时 {time.time()-t0:.0f}s")
    print("输出:", OUT_DIR)
    print("报告:", csv_path)
    print("联系表:", len(sheets), "张 ->", PREVIEW_DIR)


if __name__ == "__main__":
    main()
