"""Extraction de ``_icon_data`` (30 icones 16x16, 4 plans) depuis le listing.

Les icones viennent du bloc ``_icon_data`` du listing (L21656), qui contient
les valeurs ``DC.L``/``DS.L`` telles quelles. L'extraction precedente passait
par DAD (dump memoire runtime) et donnait des icones erronees (les donnees
runtime a l'adresse calibree ne correspondaient pas a la table statique du
listing) ; la reference visuelle (``reference/blason.png``) confirme que la
table statique est la bonne (91,8 % de pixels identiques sur l'icone 0).

    python tools\\extract_icon_data.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASM = os.path.join(ROOT, "reference", "tetracorp", "populous_prg.asm")
OUT_DIR = os.path.join(ROOT, "assets", "icons")

PALETTE = [
    (0x00, 0x00, 0x00), (0x44, 0x44, 0x44), (0x66, 0x66, 0x66), (0x88, 0x88, 0x88),
    (0xAA, 0xAA, 0xAA), (0xCC, 0xCC, 0xCC), (0x66, 0x22, 0x00), (0x88, 0x44, 0x00),
    (0xAA, 0x00, 0x00), (0xAA, 0x66, 0x00), (0xAA, 0xAA, 0x00), (0x44, 0xAA, 0x00),
    (0x22, 0x88, 0x00), (0x22, 0x66, 0x22), (0x22, 0x44, 0x88), (0x22, 0x66, 0xCC),
]


def _collect_bytes() -> bytearray:
    lines = open(ASM).readlines()
    start = end = None
    for i, l in enumerate(lines):
        if l.strip().startswith("_icon_data:"):
            start = i
        if start is not None and l.strip().startswith("_PROTECT1:"):
            end = i
            break
    assert start is not None and end is not None
    data = bytearray()
    for l in lines[start + 1:end]:
        s = l.strip()
        if not s or s.startswith(";"):
            continue
        m = re.search(r"DC\.L\s+(.*)", s)
        if m:
            rest = m.group(1).split(";")[0]
            for t in rest.split(","):
                t = t.strip()
                if t:
                    data += int(t.lstrip("$"), 16).to_bytes(4, "big")
            continue
        m = re.search(r"DS\.L\s+(\$?[0-9a-fA-F]+)", s)
        if m:
            v = m.group(1)
            n = int(v.lstrip("$"), 16) if v.startswith("$") else int(v)
            data += b"\x00" * (n * 4)
            continue
        m = re.search(r"DC\.B\s+(.*)", s)
        if m:
            rest = m.group(1).split(";")[0]
            for t in rest.split(","):
                t = t.strip()
                if t:
                    data += bytes([int(t.lstrip("$"), 16)])
            continue
        m = re.search(r"DS\.B\s+(\$?[0-9a-fA-F]+)", s)
        if m:
            v = m.group(1)
            n = int(v.lstrip("$"), 16) if v.startswith("$") else int(v)
            data += b"\x00" * n
            continue
        raise RuntimeError("directive non geree : %r" % s)
    assert len(data) == 30 * 128, "taille inattendue : %d" % len(data)
    return data


def decode_icon(data, idx, size=16):
    grid = []
    off = idx * 128
    for y in range(size):
        words = list(data[off + y * 8:off + y * 8 + 8])
        line = []
        for px in range(size):
            bit = size - 1 - px
            c = 0
            for p in range(4):
                w = (words[p * 2] << 8) | words[p * 2 + 1]
                if w & (1 << bit):
                    c |= 1 << p
            line.append(c)
        grid.append(line)
    return grid


def main():
    data = _collect_bytes()
    os.makedirs(OUT_DIR, exist_ok=True)
    from PIL import Image
    cols, zoom, gap = 10, 4, 1
    sheet = Image.new("RGB", (cols * (16 + gap) * zoom,
                              ((30 + cols - 1) // cols) * (16 + gap) * zoom),
                      (32, 32, 48))
    for i in range(30):
        grid = decode_icon(data, i)
        with open(os.path.join(OUT_DIR, "icon_%02d.json" % i), "w") as f:
            json.dump(grid, f)
        im = Image.new("RGB", (16, 16))
        for y in range(16):
            for x in range(16):
                im.putpixel((x, y), PALETTE[grid[y][x]])
        im = im.resize((16 * zoom, 16 * zoom), Image.NEAREST)
        cx, cy = i % cols, i // cols
        sheet.paste(im, (cx * (16 + gap) * zoom, cy * (16 + gap) * zoom))
    sheet.save(os.path.join(OUT_DIR, "icon_sheet.png"))
    print("ecrit : %s (30 icones)" % OUT_DIR)


if __name__ == "__main__":
    main()
