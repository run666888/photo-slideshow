# -*- coding: utf-8 -*-
"""
把 pic/ 里的照片统一制作成 3:2，输出 6 寸 300dpi 文件（1800x1200 / 1200x1800）。

用法：
    python make_3x2.py

改这 4 个常量就能换规格：
    OUTPUT_MODE  "full" = 满版裁切 ; "mat" = 6 寸白边版（照片 1512x850 + 白边 142/142/213）
    OUT_W/OUT_H  输出像素，1800x1200 = 6 寸 300dpi
    CROP_BIAS_Y  裁切位置 -1..1，0 = 居中；+0.2 表示保留更多上半部分
    ROTATE_PORTRAIT  竖图是否也保持竖版（True = 竖图输出 2:3）
"""
import csv
import io
import os
import re
import shutil
import sys
import time
from math import ceil

from PIL import Image, ImageCms, ImageDraw, ImageFont, ImageOps

# ------------------------------------------------------------------ 配置
SRC_DIR       = r"D:\love_memory\pic"
OUT_DIR       = r"D:\love_memory\out_3x2"
PREVIEW_DIR   = r"D:\love_memory\preview"

OUTPUT_MODE   = "full"        # "full" 或 "mat"
OUT_W, OUT_H  = 1800, 1200    # 6 寸 300dpi，3:2
MAT_BOX       = (1512, 850)   # mat 模式下的照片尺寸
MAT_BORDER    = (142, 142, 213)   # mat 模式：左右 / 上 / 下 白边（px）
CROP_BIAS_Y   = 0.0           # 纵向裁切偏移，0 = 居中
ROTATE_PORTRAIT = True        # 竖图保持竖版
JPEG_QUALITY  = 95
SUBSAMPLING   = 0             # 0 = 4:4:4 不降色度，适合印刷

SHEET_COLS, SHEET_ROWS = 6, 9  # 联系表每页 54 张

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".mpo"}
FONT_R = r"C:\Windows\Fonts\msyh.ttc"
FONT_B = r"C:\Windows\Fonts\msyhbd.ttc"


def F(size, bold=False):
    try:
        return ImageFont.truetype(FONT_B if bold else FONT_R, size)
    except OSError:
        return ImageFont.load_default()


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def ratio_label(r):
    for name, v in (("16:9", 16 / 9), ("3:2", 1.5), ("4:3", 4 / 3), ("1:1", 1.0),
                    ("5:4", 1.25), ("2:1", 2.0)):
        if abs(r - v) < 0.02:
            return name
    return f"{r:.2f}:1"


def crop_to_ratio(im, target_r, bias_y=0.0):
    """居中裁切到目标比例（保留原方向）。返回 (image, 面积损失比例, 裁切方向)。"""
    w, h = im.size
    r = w / h
    if abs(r - target_r) < 0.004:
        return im, 0.0, "无需裁切"
    if r > target_r:                       # 太宽 -> 裁左右
        nw = max(1, int(round(h * target_r)))
        x0 = (w - nw) // 2
        loss = 1 - nw / w
        return im.crop((x0, 0, x0 + nw, h)), loss, f"左右各裁 {loss/2*100:.1f}%"
    nh = max(1, int(round(w / target_r)))  # 太高 -> 裁上下
    y0 = int(round((h - nh) * (1 - bias_y) / 2))
    loss = 1 - nh / h
    return im.crop((0, y0, w, y0 + nh)), loss, f"上下各裁 {loss/2*100:.1f}%"


def to_srgb(im, icc_bytes):
    """内嵌 P3 / BT.709 等配置 -> sRGB，避免印厂按 sRGB 解读导致偏色。"""
    if not icc_bytes:
        return im, "sRGB(假定)"
    try:
        src = ImageCms.ImageCmsProfile(io.BytesIO(icc_bytes))
        name = ImageCms.getProfileDescription(src).strip()
        dst = ImageCms.createProfile("sRGB")
        im = ImageCms.profileToProfile(im, src, dst, outputMode="RGB",
                                       renderingIntent=0)  # 0 = perceptual
        return im, name
    except Exception as e:
        return im, f"转换失败({type(e).__name__})"


def srgb_bytes():
    try:
        return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    except Exception:
        return None


def main():
    if not os.path.isdir(SRC_DIR):
        sys.exit(f"找不到源目录: {SRC_DIR}")

    files = []
    for dp, _, fs in os.walk(SRC_DIR):
        for f in fs:
            if os.path.splitext(f)[1].lower() in EXTS:
                files.append(os.path.join(dp, f))
    files.sort(key=lambda p: natural_key(os.path.relpath(p, SRC_DIR)))
    if not files:
        sys.exit("源目录里没有图片")

    for d in (OUT_DIR, PREVIEW_DIR):
        os.makedirs(d, exist_ok=True)

    SRGB = srgb_bytes()
    rows = []
    t0 = time.time()
    heavy = []

    for i, p in enumerate(files, 1):
        rel = os.path.relpath(p, SRC_DIR)
        stem = os.path.splitext(os.path.basename(p))[0]
        out_name = f"{i:03d}_{stem}.jpg"
        out_path = os.path.join(OUT_DIR, out_name)

        try:
            with Image.open(p) as raw:
                icc = raw.info.get("icc_profile")
                shot = None
                try:
                    ex = raw.getexif()
                    shot = ex.get(36867) or ex.get(306)
                except Exception:
                    pass

                # 全分辨率解码再 LANCZOS 缩小：画质最干净。
                # （曾试过 draft() 降采样解码，但 PIL 的语义是"至少这么大"，
                #   传入 2600 对 6560 宽的图不会触发，实测像素完全一致，故去掉。）
                im = ImageOps.exif_transpose(raw)
                im = im.convert("RGB")

            ow, oh = im.size
            orig_r = ow / oh if ow >= oh else oh / ow
            portrait = oh > ow
            target_r = (2 / 3) if (portrait and ROTATE_PORTRAIT) else (3 / 2)

            im, loss, how = crop_to_ratio(im, target_r, CROP_BIAS_Y)

            if OUTPUT_MODE == "mat":
                im = im.resize(MAT_BOX, Image.Resampling.LANCZOS)
                canvas = Image.new("RGB", (OUT_W, OUT_H), (255, 255, 255))
                canvas.paste(im, (MAT_BORDER[0], MAT_BORDER[1]))
                im = canvas
            else:
                box = (OUT_W, OUT_H) if not (portrait and ROTATE_PORTRAIT) else (OUT_H, OUT_W)
                im = im.resize(box, Image.Resampling.LANCZOS)

            im, icc_src = to_srgb(im, icc)

            save_kw = dict(format="JPEG", quality=JPEG_QUALITY, subsampling=SUBSAMPLING,
                           optimize=True, progressive=False)
            if SRGB:
                save_kw["icc_profile"] = SRGB
            im.save(out_path, **save_kw)

            pct = loss * 100
            if pct >= 20:
                heavy.append((out_name, f"{pct:.0f}%"))

            rows.append({
                "序号": i,
                "输出文件": out_name,
                "原文件": rel,
                "原始尺寸": f"{ow}x{oh}",
                "原始比例": ratio_label(orig_r),
                "方向": "竖" if portrait else "横",
                "处理": how if loss else "原样",
                "裁掉面积": f"{pct:.1f}%",
                "色彩": icc_src,
                "拍摄时间": shot or "",
            })

        except Exception as e:
            rows.append({
                "序号": i, "输出文件": "(失败)", "原文件": rel, "原始尺寸": "",
                "原始比例": "", "方向": "", "处理": f"错误: {type(e).__name__}: {e}",
                "裁掉面积": "", "色彩": "", "拍摄时间": "",
            })
            print(f"  !! {rel}: {type(e).__name__}: {e}")

        if i % 20 == 0 or i == len(files):
            el = time.time() - t0
            print(f"  {i}/{len(files)}  {el:.0f}s  ({el/i*1000:.0f} ms/张)", flush=True)

    # ---------------- CSV 报告
    csv_path = os.path.join(os.path.dirname(OUT_DIR), "report.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---------------- 联系表
    sheets = build_sheets([r for r in rows if r["输出文件"] != "(失败)"])
    print(f"\n完成: {len(rows)} 张, 用时 {time.time()-t0:.0f}s")
    print(f"输出: {OUT_DIR}")
    print(f"报告: {csv_path}")
    print(f"联系表: {sheets} 张 -> {PREVIEW_DIR}")
    if heavy:
        print(f"\n裁切超过 20% 的 {len(heavy)} 张（建议人工过目）:")
        for n, v in heavy:
            print(f"  {n}  裁掉 {v}")


def build_sheets(rows, title="3:2 裁切预览", note="输出 1800×1200（6 寸 300dpi）"):
    per = SHEET_COLS * SHEET_ROWS
    pages = []
    if not rows:
        return pages
    cw, ch = 330, 296
    pad = 40
    head = 78
    W = SHEET_COLS * cw + pad * 2
    H = head + SHEET_ROWS * ch + pad
    total_pages = ceil(len(rows) / per)

    for pg in range(total_pages):
        chunk = rows[pg * per:(pg + 1) * per]
        sheet = Image.new("RGB", (W, H), (250, 249, 247))
        d = ImageDraw.Draw(sheet)
        d.text((pad, 26), title, font=F(30, True), fill=(40, 40, 46))
        d.text((pad + 210, 34), f"第 {pg+1}/{total_pages} 页 · 共 {len(rows)} 张 · {note}",
               font=F(20), fill=(130, 126, 122))

        for k, r in enumerate(chunk):
            cx = pad + (k % SHEET_COLS) * cw
            cy = head + (k // SHEET_COLS) * ch
            tw, th = 300, 200
            d.rectangle([cx, cy, cx + tw, cy + th], fill=(255, 255, 255), outline=(219, 215, 209))
            try:
                with Image.open(os.path.join(OUT_DIR, r["输出文件"])) as t:
                    t.thumbnail((tw, th), Image.Resampling.LANCZOS)
                    sheet.paste(t, (cx + (tw - t.width) // 2, cy + (th - t.height) // 2))
            except Exception:
                pass

            pct = float(r["裁掉面积"].rstrip("%") or 0)
            dot = (86, 150, 96) if pct < 10 else (216, 150, 60) if pct < 20 else (200, 80, 60)
            d.ellipse([cx + 6, cy + th + 10, cx + 18, cy + th + 22], fill=dot)

            name = r["原文件"]
            if len(name) > 26:
                name = name[:12] + "…" + name[-12:]
            d.text((cx + 26, cy + th + 6), f"#{r['序号']}  {name}", font=F(17), fill=(60, 58, 62))
            d.text((cx + 26, cy + th + 30), f"{r['原始比例']} · {r['裁掉面积']} · {r['方向']}",
                   font=F(16), fill=(140, 136, 132))

        path = os.path.join(PREVIEW_DIR, f"contact_{pg+1:02d}.jpg")
        sheet.save(path, quality=88, optimize=True)
        pages.append(path)
    return pages


if __name__ == "__main__":
    main()
