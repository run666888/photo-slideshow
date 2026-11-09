"""Generate a true-to-scale comparison of three ways to print a 16:9 photo on 6-inch paper."""
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_R = r"C:\Windows\Fonts\msyh.ttc"
FONT_B = r"C:\Windows\Fonts\msyhbd.ttc"

def F(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT_R, size)

# ---------- true physical scale ----------
PX_PER_CM = 60
PAPER_W_CM, PAPER_H_CM = 15.2, 10.2          # 6 inch = 4x6 in
PW, PH = int(PAPER_W_CM * PX_PER_CM), int(PAPER_H_CM * PX_PER_CM)   # 912 x 612

# borders in cm
EQ = 1.886                    # equal border for 16:9 on 3:2
TOP3, SIDE3, BOT3 = 1.2, 1.2, 1.8


def make_scene(w=1600, h=900):
    img = Image.new("RGB", (w, h))
    px = img.load()
    c_top, c_mid, c_low = (64, 98, 156), (243, 165, 120), (255, 226, 176)
    horizon = 0.60
    for y in range(h):
        t = y / (h - 1)
        if t <= horizon:
            k = t / horizon
            c = tuple(int(c_top[i] + (c_mid[i] - c_top[i]) * (k ** 0.75)) for i in range(3))
        else:
            k = (t - horizon) / (1 - horizon)
            c = tuple(int(c_mid[i] + (c_low[i] - c_mid[i]) * k) for i in range(3))
        for x in range(w):
            px[x, y] = c

    # sun + glow
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    sx, sy, r = int(0.70 * w), int(0.50 * h), 78
    for i in range(26, 0, -1):
        rr = int(r * (1 + i * 0.22))
        gd.ellipse([sx - rr, sy - rr, sx + rr, sy + rr], fill=(255, 214, 150, 5))
    gd.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(255, 246, 214, 255))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")

    d = ImageDraw.Draw(img, "RGBA")

    def hill(base, amp, phase, color):
        pts = [(0, h), (0, base)]
        for x in range(0, w + 1, 6):
            u = x / w
            y = base - amp * math.sin(u * math.pi * 2.0 + phase) - amp * 0.45 * math.sin(u * math.pi * 5.1 + phase * 1.7)
            pts.append((x, y))
        pts.append((w, h))
        d.polygon(pts, fill=color)

    hill(int(0.72 * h), 34, 0.4, (96, 76, 96, 255))
    hill(int(0.80 * h), 42, 2.6, (58, 46, 66, 255))
    hill(int(0.90 * h), 26, 4.9, (34, 28, 42, 255))

    # tree near the left edge -> gets cropped in the full-bleed version
    tx, ty = int(0.036 * w), int(0.80 * h)
    d.rectangle([tx - 6, ty - 40, tx + 6, ty + 30], fill=(34, 28, 42, 255))
    for dx, dy, rr in [(-22, -58, 34), (16, -66, 30), (-2, -92, 28)]:
        d.ellipse([tx + dx - rr, ty + dy - rr, tx + dx + rr, ty + dy + rr], fill=(34, 28, 42, 255))

    # birds near the right edge -> also cropped
    def bird(cx, cy, s):
        d.arc([cx - s, cy - s, cx, cy + s], 200, 340, fill=(40, 34, 48, 255), width=4)
        d.arc([cx, cy - s, cx + s, cy + s], 200, 340, fill=(40, 34, 48, 255), width=4)

    bird(int(0.955 * w), int(0.26 * h), 26)
    bird(int(0.905 * w), int(0.20 * h), 20)
    bird(int(0.60 * w), int(0.17 * h), 18)
    return img


def photo_crop(scene, box_w, box_h):
    """Center-crop the 16:9 scene to the target aspect, then resize (cover)."""
    sw, sh = scene.size
    target = box_w / box_h
    if sw / sh > target:                       # source too wide -> trim sides
        nw = int(sh * target)
        off = (sw - nw) // 2
        crop = scene.crop((off, 0, off + nw, sh))
    else:
        nh = int(sw / target)
        off = (sh - nh) // 2
        crop = scene.crop((0, off, sw, off + nh))
    return crop.resize((box_w, box_h), Image.LANCZOS)


def photo_fit(scene, box_w, box_h):
    return scene.resize((box_w, box_h), Image.LANCZOS)


def shadow_paper(canvas, xy):
    x, y = xy
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle([x, y + 5, x + PW, y + PH + 7], 4, fill=(30, 26, 24, 55))
    sh = sh.filter(ImageFilter.GaussianBlur(10))
    canvas.alpha_composite(sh)


scene = make_scene()

MARGIN, GUTTER = 80, 96
TITLE_H = 196
CAPTION_H = 196
W = MARGIN * 2 + PW * 3 + GUTTER * 2
H = TITLE_H + PH + CAPTION_H
canvas = Image.new("RGBA", (W, H), (246, 244, 240, 255))
draw = ImageDraw.Draw(canvas)

draw.text((MARGIN, 54), "16:9 照片洗 6 寸：三种留白方式", font=F(46, True), fill=(40, 40, 46))
draw.text((MARGIN + 2, 122), "纸面 15.2 × 10.2 cm（3:2）· 同一张照片 · 按 1:1 实物比例绘制",
          font=F(23), fill=(122, 118, 114))

panels = [
    ("①  满版 · 不留白", "左右各裁掉 7.8%（合计 15.6%），边缘的树和鸟会被切掉", "fill", 0),
    ("②  四边等宽", "白边四边各 1.9 cm，照片 11.4 × 6.4 cm（最“正”）", "eq", EQ),
    ("③  上窄下宽 · 推荐", "上/左右 1.2 cm，下 1.8 cm，照片 12.8 × 7.2 cm", "bw", TOP3),
]

for i, (title, detail, mode, b) in enumerate(panels):
    px0 = MARGIN + i * (PW + GUTTER)
    py0 = TITLE_H
    shadow_paper(canvas, (px0, py0))
    draw.rounded_rectangle([px0, py0, px0 + PW, py0 + PH], 3, fill=(255, 255, 255, 255))

    if mode == "fill":
        pic = photo_crop(scene, PW, PH)
        canvas.paste(pic, (px0, py0))
        draw.rectangle([px0, py0, px0 + PW, py0 + PH], outline=(208, 204, 198, 255), width=1)
        # crop markers
        cut = int(PW * 0.078)
        for cx in (px0 + cut, px0 + PW - cut):
            draw.line([(cx, py0), (cx, py0 + 26)], fill=(230, 90, 70, 255), width=3)

    elif mode == "eq":
        bpx = int(round(b * PX_PER_CM))
        w2, h2 = PW - 2 * bpx, PH - 2 * bpx
        pic = photo_fit(scene, w2, h2)
        canvas.paste(pic, (px0 + bpx, py0 + bpx))
        draw.text((px0 + bpx // 2 - 15, py0 + PH // 2 - 14), "1.9", font=F(19), fill=(168, 162, 156))
        draw.text((px0 + PW - bpx + 6, py0 + PH // 2 - 14), "1.9", font=F(19), fill=(168, 162, 156))
        draw.text((px0 + PW // 2 - 15, py0 + 6), "1.9", font=F(19), fill=(168, 162, 156))
        draw.text((px0 + PW // 2 - 15, py0 + PH - bpx + 10), "1.9", font=F(19), fill=(168, 162, 156))

    else:
        s, t, bo = int(SIDE3 * PX_PER_CM), int(TOP3 * PX_PER_CM), int(BOT3 * PX_PER_CM)
        w2, h2 = PW - 2 * s, PH - t - bo
        pic = photo_fit(scene, w2, h2)
        canvas.paste(pic, (px0 + s, py0 + t))
        draw.text((px0 + s // 2 - 15, py0 + PH // 2 - 14), "1.2", font=F(19), fill=(168, 162, 156))
        draw.text((px0 + PW - s + 6, py0 + PH // 2 - 14), "1.2", font=F(19), fill=(168, 162, 156))
        draw.text((px0 + PW // 2 - 15, py0 + 8), "1.2", font=F(19), fill=(168, 162, 156))
        draw.text((px0 + PW // 2 - 34, py0 + PH - bo + 26), "1.8", font=F(19), fill=(168, 162, 156))

    draw.text((px0, py0 + PH + 26), title, font=F(29, True), fill=(44, 44, 50))
    draw.text((px0, py0 + PH + 74), detail, font=F(20), fill=(124, 120, 116))

draw.text((MARGIN, H - 62), "白边越窄，两侧裁得越多；想完全不裁，四边就得留到 1.9 cm。",
          font=F(22), fill=(150, 145, 140))

canvas.convert("RGB").save("print_layout_compare.png", quality=95)
print("saved", canvas.size)
