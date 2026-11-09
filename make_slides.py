# -*- coding: utf-8 -*-
"""
把 out_3x2 里的照片做成 16:9 幻灯片（PPTX）。
每页：同图高斯模糊铺底 + 原图居中（1.25pt 白边）+ 右下角拍摄日期。
"""
import csv
import os
import shutil
import tempfile
import time

from lxml import etree
from PIL import Image, ImageEnhance, ImageFilter
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

SRC = r"D:\love_memory\out_3x2"
REPORT = r"D:\love_memory\report.csv"
OUT = r"D:\love_memory\我们的照片.pptx"

SLIDE_W, SLIDE_H = 13.333, 7.5
PHOTO_H = 6.35          # 照片占版面高度（英寸）
BG_W, BG_H = 1600, 900
BG_BLUR = 46
BG_BRIGHT = 0.45
PHOTO_EDGE = 1440       # 嵌入照片长边
PHOTO_Q = 87
FONT = "微软雅黑"


def set_run(run, text, size, color, bold=False):
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = FONT
    rPr = run.font._rPr
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = etree.SubElement(rPr, qn("a:ea"))
    ea.set("typeface", FONT)


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


def fit(im, max_edge):
    w, h = im.size
    s = min(1.0, max_edge / max(w, h))
    if s < 1.0:
        im = im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.Resampling.LANCZOS)
    return im


def make_bg(im, path, dark=BG_BRIGHT):
    bg = cover(im.convert("RGB"), BG_W, BG_H)
    bg = bg.filter(ImageFilter.GaussianBlur(BG_BLUR))
    bg = ImageEnhance.Brightness(bg).enhance(dark)
    bg = ImageEnhance.Color(bg).enhance(0.92)
    bg.save(path, "JPEG", quality=72, optimize=True)


def add_bg(slide, prs, path):
    return slide.shapes.add_picture(path, 0, 0, width=prs.slide_width, height=prs.slide_height)


def norm_date(s):
    s = (s or "").strip()
    if len(s) >= 10 and s[4] == ":" and s[7] == ":":
        return s[:10].replace(":", ".")
    return ""


def textbox(slide, x, y, w, h, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    tf.paragraphs[0].alignment = align
    return tf


def main():
    rows = list(csv.DictReader(open(REPORT, encoding="utf-8-sig")))
    rows = [r for r in rows if r["输出文件"] != "(失败)"]
    total = len(rows)

    dates = sorted({d for d in (norm_date(r["拍摄时间"]) for r in rows) if d})
    span = ""
    if dates:
        span = f"{dates[0][:7]} — {dates[-1][:7]}"

    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W)
    prs.slide_height = Inches(SLIDE_H)
    blank = prs.slide_layouts[6]

    tmp = tempfile.mkdtemp(prefix=".dsh-slides-", dir=r"D:\love_memory")
    t0 = time.time()

    try:
        # ---------------- 封面
        first = Image.open(os.path.join(SRC, rows[0]["输出文件"]))
        bgp = os.path.join(tmp, "bg_title.jpg")
        make_bg(first, bgp, 0.30)
        s = prs.slides.add_slide(blank)
        add_bg(s, prs, bgp)
        tf = textbox(s, 1.0, 2.45, SLIDE_W - 2.0, 1.4)
        set_run(tf.paragraphs[0].add_run(), "我 们 的 照 片", 56, RGBColor(255, 255, 255), True)
        tf2 = textbox(s, 1.0, 4.05, SLIDE_W - 2.0, 0.5)
        set_run(tf2.paragraphs[0].add_run(), f"{span}　·　共 {total} 张", 20, RGBColor(226, 222, 216))

        # ---------------- 正文
        for i, r in enumerate(rows, 1):
            p = os.path.join(SRC, r["输出文件"])
            with Image.open(p) as im:
                im = im.convert("RGB")
                bgp = os.path.join(tmp, "bg.jpg")
                make_bg(im, bgp)

                ph = fit(im, PHOTO_EDGE)
                pw_path = os.path.join(tmp, "p.jpg")
                ph.save(pw_path, "JPEG", quality=PHOTO_Q, optimize=True, progressive=False)

            s = prs.slides.add_slide(blank)
            add_bg(s, prs, bgp)

            ar = ph.width / ph.height
            h_in = PHOTO_H
            w_in = h_in * ar
            if w_in > SLIDE_W - 1.2:                 # 极宽图兜底
                w_in = SLIDE_W - 1.2
                h_in = w_in / ar
            x = (SLIDE_W - w_in) / 2
            y = (SLIDE_H - h_in) / 2

            pic = s.shapes.add_picture(pw_path, Inches(x), Inches(y), Inches(w_in), Inches(h_in))
            pic.line.color.rgb = RGBColor(255, 255, 255)
            pic.line.width = Pt(1.25)

            d = norm_date(r["拍摄时间"])
            if d:
                tf = textbox(s, SLIDE_W - 3.3, SLIDE_H - 0.62, 2.9, 0.36, PP_ALIGN.RIGHT)
                set_run(tf.paragraphs[0].add_run(), d, 10.5, RGBColor(228, 226, 222))

            if i % 40 == 0 or i == total:
                print(f"  {i}/{total}  {time.time()-t0:.0f}s", flush=True)

        # ---------------- 结尾
        last = Image.open(os.path.join(SRC, rows[-1]["输出文件"]))
        bgp = os.path.join(tmp, "bg_end.jpg")
        make_bg(last, bgp, 0.30)
        s = prs.slides.add_slide(blank)
        add_bg(s, prs, bgp)
        tf = textbox(s, 1.0, 3.05, SLIDE_W - 2.0, 1.0)
        set_run(tf.paragraphs[0].add_run(), "未 完 待 续", 44, RGBColor(255, 255, 255), True)
        tf2 = textbox(s, 1.0, 4.15, SLIDE_W - 2.0, 0.5)
        set_run(tf2.paragraphs[0].add_run(), f"{total} 个瞬间，还在继续", 18, RGBColor(224, 220, 214))

        prs.save(OUT)
        print(f"\n已生成: {OUT}")
        print(f"幻灯片: {len(prs.slides.__iter__.__self__._sldIdLst)} 张, "
              f"{os.path.getsize(OUT)/1024/1024:.1f} MB, 用时 {time.time()-t0:.0f}s")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
