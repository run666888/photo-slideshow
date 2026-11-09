# -*- coding: utf-8 -*-
"""
把 out_3x2 的照片合成 1920x1080 视频，逐帧渲染后直接管道给 ffmpeg 编码。

画面与 PPTX 一致：同图模糊压暗铺底 + 原图居中（白细边）+ 右下角日期。
照片只缩小不放大：1080p 下横图 1380x920（原生 1800x1200 的 0.77 倍），
竖图 613x920，因此不会产生插值放大的糊边。

    python make_video.py            # 全片
    python make_video.py 5          # 只跑前 5 张（测速用）
"""
import argparse
import csv
import os
import subprocess
import sys
import time

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

FFMPEG = r"D:\yingjian_video\tools\ffmpeg\bin\ffmpeg.exe"
SRC = r"D:\love_memory\out_3x2"
REPORT = r"D:\love_memory\report.csv"

W, H, FPS = 1920, 1080, 30
PHOTO_H = 920
HOLD = 2.5            # 每张停留秒数
FADE = 0.45           # 交叉淡入秒数
TITLE_HOLD = 2.5
END_HOLD = 2.5
CRF = 16
PRESET = "slow"

FONT_B = r"C:\Windows\Fonts\msyhbd.ttc"
FONT_R = r"C:\Windows\Fonts\msyh.ttc"
WHITE = (255, 255, 255)
DATE_C = (232, 230, 226)


def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT_R, size)


def cover(im, tw, th):
    w, h = im.size
    if w / h > tw / th:
        nw = int(h * tw / th)
        off = (w - nw) // 2
        im = im.crop((off, 0, off + nw, h))
    else:
        nh = int(w * th / tw)
        off = (h - nh) // 2
        im = im.crop((0, off, w, off + nh))
    return im.resize((tw, th), Image.Resampling.LANCZOS)


def backdrop(im, dark=0.45):
    """低分辨率模糊再放大，比直接对 1080p 高斯模糊快一个数量级，效果一致。"""
    bg = cover(im.convert("RGB"), 640, 360).filter(ImageFilter.GaussianBlur(16))
    bg = bg.resize((W, H), Image.Resampling.BICUBIC)
    return ImageEnhance.Brightness(bg).enhance(dark)


def photo_slide(path, date):
    im = Image.open(path).convert("RGB")
    canvas = backdrop(im)
    ar = im.width / im.height
    ph = PHOTO_H
    pw = int(round(ph * ar))
    pic = im.resize((pw, ph), Image.Resampling.LANCZOS)
    x, y = (W - pw) // 2, (H - ph) // 2
    canvas.paste(pic, (x, y))
    d = ImageDraw.Draw(canvas)
    d.rectangle([x - 3, y - 3, x + pw + 2, y + ph + 2], outline=WHITE, width=3)
    if date:
        d.text((W - 58, 1015), date, font=font(21), fill=DATE_C, anchor="rm")
    return canvas


def title_card(path, span, total):
    canvas = backdrop(Image.open(path).convert("RGB"), 0.28)
    d = ImageDraw.Draw(canvas)
    d.text((W // 2, 470), "我 们 的 照 片", font=font(118, True), fill=WHITE, anchor="mm")
    d.text((W // 2, 630), f"{span}   ·   共 {total} 张", font=font(40), fill=(228, 224, 218), anchor="mm")
    return canvas


def end_card(path, total):
    canvas = backdrop(Image.open(path).convert("RGB"), 0.28)
    d = ImageDraw.Draw(canvas)
    d.text((W // 2, 480), "未 完 待 续", font=font(96, True), fill=WHITE, anchor="mm")
    d.text((W // 2, 625), f"{total} 个瞬间，还在继续", font=font(36), fill=(226, 222, 216), anchor="mm")
    return canvas


def norm_date(s):
    s = (s or "").strip()
    return s[:10].replace(":", ".") if len(s) >= 10 and s[4] == ":" else ""


def main():
    ap = argparse.ArgumentParser(description="把照片合成 1080p 视频")
    ap.add_argument("--hold", type=float, default=HOLD, help="每张停留秒数")
    ap.add_argument("--fade", type=float, default=FADE, help="交叉淡入秒数")
    ap.add_argument("--title", type=float, default=TITLE_HOLD, help="封面秒数")
    ap.add_argument("--end", type=float, default=END_HOLD, help="结尾秒数")
    ap.add_argument("--crf", type=int, default=CRF)
    ap.add_argument("--limit", type=int, default=None, help="只处理前 N 张（测速用）")
    ap.add_argument("--out", default=r"D:\love_memory\我们的照片.mp4")
    a = ap.parse_args()

    rows = [r for r in csv.DictReader(open(REPORT, encoding="utf-8-sig"))
            if r["输出文件"] != "(失败)"]
    if a.limit:
        rows = rows[:a.limit]
    total = len(rows)
    dates = sorted({d for d in (norm_date(r["拍摄时间"]) for r in rows) if d})
    span = f"{dates[0][:7]} — {dates[-1][:7]}" if dates else ""

    out = a.out

    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", PRESET, "-tune", "stillimage", "-crf", str(a.crf),
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.2",
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
           "-movflags", "+faststart", "-an", out]

    errlog = open(r"D:\love_memory\_ffmpeg_err.txt", "wb")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errlog)
    stdin = proc.stdin

    t0 = time.time()
    nframes = 0
    fade_frames = int(round(a.fade * FPS))
    hold_frames = int(round(a.hold * FPS))

    def emit(img, count):
        nonlocal nframes
        buf = img.tobytes()
        for _ in range(count):
            stdin.write(buf)
            nframes += 1

    try:
        # 封面
        card = title_card(os.path.join(SRC, rows[0]["输出文件"]), span, total)
        emit(card, int(round(a.title * FPS)))
        prev = card

        for i, r in enumerate(rows, 1):
            cur = photo_slide(os.path.join(SRC, r["输出文件"]), norm_date(r["拍摄时间"]))
            for f in range(hold_frames):
                if f < fade_frames:
                    emit(Image.blend(prev, cur, (f + 1) / fade_frames), 1)
                else:
                    stdin.write(cur.tobytes())
                    nframes += 1
            prev = cur
            if i % 20 == 0 or i == total:
                el = time.time() - t0
                eta = el / i * (total - i)
                print(f"  {i}/{total}  已渲染 {nframes} 帧  {el:.0f}s  预计还需 {eta/60:.1f} 分钟", flush=True)

        # 结尾
        end = end_card(os.path.join(SRC, rows[-1]["输出文件"]), total)
        for f in range(int(round(a.end * FPS))):
            if f < fade_frames:
                emit(Image.blend(prev, end, (f + 1) / fade_frames), 1)
            else:
                stdin.write(end.tobytes())
                nframes += 1

        stdin.close()
        rc = proc.wait()
    except BrokenPipeError:
        rc = proc.wait()
        print("编码器提前退出", file=sys.stderr)
    finally:
        errlog.close()

    if rc != 0:
        print(open(r"D:\love_memory\_ffmpeg_err.txt", encoding="utf-8", errors="replace").read()[-2000:])
        sys.exit(rc)

    print(f"\n完成: {out}")
    print(f"帧数 {nframes}  时长 {nframes/FPS:.1f}s  用时 {(time.time()-t0)/60:.1f} 分钟")
    print(f"体积 {os.path.getsize(out)/1024/1024:.0f} MB")


if __name__ == "__main__":
    main()
