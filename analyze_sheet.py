"""Planche d'essais : genere plusieurs interpretations de chaque fichier
graphique et les assemble en une image unique (contact sheet) pour
inspection visuelle rapide.
"""
import os

from PIL import Image, ImageDraw

SRC = r"S:\OpenCode\Populous\extracted"
OUT = r"S:\OpenCode\Populous\out_png"

PAL = [0x000000, 0x0000AA, 0xAA0000, 0xAAAA00,
       0x00AA00, 0xAA0000 + 0x005500, 0xAA5500, 0x555555,
       0x5555FF, 0x55FF55, 0x55FFFF, 0xFF5555,
       0xFF55FF, 0xFFFF55, 0xFFFFAA, 0xFFFFFF]


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


def bitplane1(data, width, height):
    return planar(data, width, height, 1)


def chunky4(data, width, height):
    img = Image.new("P", (width, height))
    px = img.load()
    i = 0
    for y in range(height):
        for x in range(width):
            if i >= len(data):
                break
            px[x, y] = (data[i] >> 4) & 0xF
            i += 1
            if i >= len(data):
                break
    flat = []
    for c in PAL:
        flat += [c >> 16 & 255, c >> 8 & 255, c & 255]
    img.putpalette(flat)
    return img


def gray8(data, width, height):
    return Image.frombytes("L", (width, height),
                           data[:width * height]).convert("RGB")


def sheet(items, path, cols=4, cell=(320, 200)):
    """items : [(label, PIL.Image)]"""
    rows = (len(items) + cols - 1) // cols
    W = cols * (cell[0] + 8)
    H = rows * (cell[1] + 20)
    sh = Image.new("RGB", (W, H), (30, 30, 30))
    d = ImageDraw.Draw(sh)
    for i, (label, im) in enumerate(items):
        cx = (i % cols) * (cell[0] + 8) + 4
        cy = (i // cols) * (cell[1] + 20) + 16
        sh.paste(im.resize(cell), (cx, cy))
        d.text((cx, cy - 14), label, fill=(255, 255, 0))
    sh.save(path)
    return path


def try_land4():
    b = open(os.path.join(SRC, "land4"), "rb").read()
    items = []
    for off in (0, 4, 14, 94, 96):
        for w in (160, 200, 128):
            if (len(b) - off) % (w // 8) or w % 8:
                continue
            h = (len(b) - off) // (w // 8)
            items.append((f"1bit {w}x{h} off{off}",
                          bitplane1(b[off:], w, h)))
    for off in (0, 96, 100, 104):
        for w in (160, 128, 80):
            h = (len(b) - off) // w
            if h <= 0:
                continue
            items.append((f"4bpp {w}x{h} off{off}",
                          chunky4(b[off:], w, h)))
    return items


def try_sprites():
    b = open(os.path.join(SRC, "sprites4.dat"), "rb").read()
    items = []
    # 160 octets par ligne -> 146 lignes
    items.append(("1bit 1280x146", bitplane1(b, 1280, 146)))
    items.append(("1bit 640x292", bitplane1(b, 640, 292)))
    for off in (0, 320, 640, 32):
        d = b[off:]
        items.append((f"p4 int 320x{len(d)//160} off{off}",
                      planar(d, 320, len(d) // 160, 4)))
        if len(d) % 160 == 0:
            items.append((f"p8 int 160x{len(d)//160} off{off}",
                          planar(d, 160, len(d) // 160, 8)))
    for off in (0, 32):
        d = b[off:]
        for w in (160, 80, 320):
            h = len(d) // w
            if h:
                items.append((f"4bpp {w}x{h} off{off}", chunky4(d, w, h)))
    return items


def try_mouths():
    b = open(os.path.join(SRC, "mouths.pic"), "rb").read()
    items = [("1bit 192x210", bitplane1(b, 192, 210)),
             ("1bit 96x420", bitplane1(b, 96, 420)),
             ("p2 int 96x105", planar(b, 96, 105, 2)),
             ("p3 int 64x70", planar(b, 64, 70, 3)),
             ("p6 int 32x35", planar(b, 32, 35, 6)),
             ("p2 seq 96x105", planar(b, 96, 105, 2, "plane_major")),
             ("p3 seq 64x70", planar(b, 64, 70, 3, "plane_major")),
             ("4bpp 168x60", chunky4(b, 168, 60)),
             ("4bpp 126x80", chunky4(b, 126, 80)),
             ("4bpp 84x120", chunky4(b, 84, 120)),
             ("4bpp 63x160", chunky4(b, 63, 160)),
             ("gray 84x60", gray8(b, 84, 60)),
             ("gray 126x40", gray8(b, 126, 40)),
             ("gray 140x36", gray8(b, 140, 36)),
             ("gray 70x72", gray8(b, 70, 72)),
             ("gray 56x90", gray8(b, 56, 90))]
    return items


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (("land4", try_land4), ("sprites4", try_sprites),
                     ("mouths", try_mouths)):
        items = fn()
        p = sheet(items, os.path.join(OUT, f"sheet_{name}.png"))
        print("ecrit", p, len(items), "essais")


if __name__ == "__main__":
    main()
