"""Essais cibles : decodage d'un enregistrement de sprites4.dat et de
mouths.pic en tant qu'image planaire, avec grossissement pour lecture.
"""
import os

from PIL import Image, ImageDraw

SRC = r"S:\OpenCode\Populous\extracted"
OUT = r"S:\OpenCode\Populous\out_png"

PAL = [0x000000, 0x0000AA, 0xAA0000, 0xAAAA00, 0x00AA00, 0xAA5500,
       0x5500AA, 0x555555, 0x5555FF, 0x55FF55, 0x55FFFF, 0xFF5555,
       0xFF55FF, 0xFFFF55, 0xFFAA00, 0xFFFFFF]


def planar(data, width, height, planes, layout="interleaved"):
    img = Image.new("P", (width, height))
    px = img.load()
    rb = width // 8
    for y in range(height):
        for x in range(width):
            bi, bit = x // 8, 7 - (x % 8)
            val = 0
            for p in range(planes):
                off = ((y * planes + p) if layout == "interleaved"
                       else (p * height + y)) * rb + bi
                if off < len(data) and (data[off] >> bit) & 1:
                    val |= 1 << p
            px[x, y] = val
    flat = []
    for c in PAL:
        flat += [c >> 16 & 255, c >> 8 & 255, c & 255]
    img.putpalette(flat)
    return img


def sheet(items, path, cols=5, cell=200, zoom=4):
    rows = (len(items) + cols - 1) // cols
    W = cols * (cell + 10)
    H = rows * (cell + 24)
    sh = Image.new("RGB", (W, H), (25, 25, 25))
    d = ImageDraw.Draw(sh)
    for i, (label, im) in enumerate(items):
        cx = (i % cols) * (cell + 10) + 5
        cy = (i // cols) * (cell + 24) + 20
        im2 = im.resize((im.width * zoom, im.height * zoom),
                        Image.NEAREST)
        if im2.width > cell or im2.height > cell:
            im2.thumbnail((cell, cell), Image.NEAREST)
        sh.paste(im2, (cx, cy))
        d.text((cx, cy - 14), label, fill=(255, 255, 0))
    sh.save(path)
    return path


def main():
    b = open(os.path.join(SRC, "sprites4.dat"), "rb").read()
    rec = b[:160]
    items = []
    for planes in (4, 8):
        for rb in (1, 2, 4, 5, 8, 10, 20, 40):
            total = planes * rb
            if total and 160 % total == 0:
                rows = 160 // total
                items.append((f"p{planes} {8*rb}x{rows}",
                              planar(rec, 8 * rb, rows, planes)))
    sheet(items, os.path.join(OUT, "rec0_sprites.png"), cols=5, zoom=4)

    # variantes : 2 records collés (320 octets) pour voir un dessin plus grand
    items2 = []
    for planes in (4,):
        for rb in (40, 20, 10):
            total = planes * rb
            if 320 % total == 0:
                rows = 320 // total
                items2.append((f"2rec p{planes} {8*rb}x{rows}",
                               planar(b[:320], 8 * rb, rows, planes)))
    # image entiere en 4 plans interlaces 320x146
    items2.append(("full p4 320x146", planar(b, 320, 146, 4)))
    items2.append(("full p4 seq 320x146", planar(b, 320, 146, 4,
                                                 "plane_major")))
    sheet(items2, os.path.join(OUT, "sprites_full.png"), cols=3, zoom=1)

    # ---- mouths.pic : ligne de 24 octets ----
    m = open(os.path.join(SRC, "mouths.pic"), "rb").read()
    items3 = []
    for block in (24, 48, 96, 168):
        for planes in (1, 2, 3, 4, 6, 8):
            if block % planes:
                continue
            rb = block // planes
            rows = len(m) // block
            items3.append((f"p{planes} {8*rb}x{rows} blk{block}",
                           planar(m, 8 * rb, rows, planes)))
            items3.append((f"p{planes} seq {8*rb}x{rows} blk{block}",
                           planar(m, 8 * rb, rows, planes,
                                  "plane_major")))
    sheet(items3, os.path.join(OUT, "mouths_try.png"), cols=6, zoom=2)
    print("ok")


if __name__ == "__main__":
    main()
