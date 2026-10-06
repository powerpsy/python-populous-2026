"""Extraction de ``_icon_data`` (30 icônes 16x16, 4 plans) depuis DAD.

Calibration : ``_font_data`` (asm 0x4F3CE) = glyphe '!' de font.dat, trouve
dans DAD a l'offset 0x11612-40 = 0x115EA  ->  base = 0x4F3CE - 0x115EA.
Comme ``_icon_data`` (asm 0x4E4C6) + 0xF00 + 8 (``_PROTECT1``) == ``_font_data``,
l'icone de depart doit etre a l'offset 0x106E2.

Chaque icone = 16 lignes x 4 mots (masque non inclu : le code ecrit 4 mots par
ligne, un par plan ; la transparence est geree par XOR/AND cote ecran).
"""
import json
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAD = os.path.join(ROOT, "reference", "original", "extracted", "DAD")
FONT = os.path.join(ROOT, "reference", "original", "extracted", "font.dat")
OUT_DIR = os.path.join(ROOT, "assets", "icons")

PALETTE = [
    (0x00, 0x00, 0x00), (0x44, 0x44, 0x44), (0x66, 0x66, 0x66), (0x88, 0x88, 0x88),
    (0xAA, 0xAA, 0xAA), (0xCC, 0xCC, 0xCC), (0x66, 0x22, 0x00), (0x88, 0x44, 0x00),
    (0xAA, 0x00, 0x00), (0xAA, 0x66, 0x00), (0xAA, 0xAA, 0x00), (0x44, 0xAA, 0x00),
    (0x22, 0x88, 0x00), (0x22, 0x66, 0x22), (0x22, 0x44, 0x88), (0x22, 0x66, 0xCC),
]


def decode_icon(data, idx, size=16):
    """128 octets -> grille size x size d'indices de couleur (0..15)."""
    grid = []
    off = idx * 128
    for y in range(size):
        words = data[off + y * 8: off + y * 8 + 8]
        line = []
        for px in range(size):
            bit = 15 - px
            c = 0
            for p in range(4):
                w = (words[p * 2] << 8) | words[p * 2 + 1]
                if w & (1 << bit):
                    c |= 1 << p
            line.append(c)
        grid.append(line)
    return grid


def main():
    dad = open(DAD, "rb").read()
    font = open(FONT, "rb").read()

    # calibration
    glyph_bang = font[40:80]
    pos = dad.find(glyph_bang)
    assert pos > 0, "glyphe '!' introuvable"
    font_off = pos - 40
    base = 0x4F3CE - font_off
    icon_off = 0x4E4C6 - base
    print("_font_data offset 0x%X, base 0x%X, _icon_data offset 0x%X"
          % (font_off, base, icon_off))

    icon_data = dad[icon_off:icon_off + 30 * 128]
    assert len(icon_data) == 30 * 128
    # coherence : les 8 octets suivants sont _PROTECT1 (puis font.dat suit)
    print("octets _PROTECT1 : %s"
          % dad[icon_off + 30 * 128: font_off].hex(" "))
    assert icon_off + 30 * 128 + 8 == font_off, "calibration incoherente"
    assert dad[font_off: font_off + 40] == font[:40], "font.dat non aligne"

    os.makedirs(OUT_DIR, exist_ok=True)
    cols, zoom, gap = 10, 4, 1
    sheet = Image.new("RGB", (cols * (16 + gap) * zoom, ((30 + cols - 1) // cols) * (16 + gap) * zoom),
                      (32, 32, 48))
    for i in range(30):
        grid = decode_icon(icon_data, i)
        im = Image.new("RGB", (16, 16))
        for y in range(16):
            for x in range(16):
                im.putpixel((x, y), PALETTE[grid[y][x]])
        im = im.resize((16 * zoom, 16 * zoom), Image.NEAREST)
        cx, cy = i % cols, i // cols
        sheet.paste(im, (cx * (16 + gap) * zoom, cy * (16 + gap) * zoom))
        json_path = os.path.join(OUT_DIR, "icon_%02d.json" % i)
        with open(json_path, "w") as f:
            json.dump(grid, f)
    out = os.path.join(OUT_DIR, "icon_sheet.png")
    sheet.save(out)
    print("ecrit:", out)


if __name__ == "__main__":
    main()
