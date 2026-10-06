"""Essais de decodage des fichiers graphiques extraits (PNG de controle).

lord.pic  : 32032 octets  -> hypotheese 32 octets d'entete + 32000
            = 40 octets/ligne * 800 = 200 lignes * 4 plans (320x200x16)
mouths.pic: 5040 octets
sprites4  : 23360 octets

On genere plusieurs interpretations et on les ecrit dans out_png/ pour
inspection visuelle.
"""
import os

from PIL import Image

SRC = r"S:\OpenCode\Populous\extracted"
OUT = r"S:\OpenCode\Populous\out_png"

# palette Amiga typique (couleurs de base 0..15)
EHB = [0x000000, 0x0000AA, 0xAA0000, 0xAAAA00,
       0x00AA00, 0xAAAAAA, 0xAA5500, 0x555555,
       0x5555FF, 0x55FF55, 0x55FFFF, 0xFF5555,
       0xFF55FF, 0xFFFF55, 0xFFFFAA, 0xFFFFFF]


def planar_to_img(rows_bytes, width, height, planes, layout="interleaved"):
    """rows_bytes: bytes bruts. layout 'interleaved' = plan par plan de ligne,
    'sequential' = tous les plans d'une ligne d'abord? non :
      interleaved : ligne0 plan0, ligne0 plan1, ..., ligne0 planN, ligne1...
      plane_major : plan0 complet, puis plan1, ...
    """
    img = Image.new("P", (width, height))
    px = img.load()
    row_bytes = width // 8
    for y in range(height):
        for x in range(width):
            byte_i = x // 8
            bit = 7 - (x % 8)
            val = 0
            for p in range(planes):
                if layout == "interleaved":
                    off = (y * planes + p) * row_bytes + byte_i
                elif layout == "plane_major":
                    off = (p * height + y) * row_bytes + byte_i
                else:  # row_of_planes? same as interleaved
                    off = (y * planes + p) * row_bytes + byte_i
                if off < len(rows_bytes) and (rows_bytes[off] >> bit) & 1:
                    val |= 1 << p
            px[x, y] = val
    img.putpalette([c for col in EHB for c in
                    (col >> 16 & 255, col >> 8 & 255, col & 255)] * 1)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)

    # ---- lord.pic ----
    b = open(os.path.join(SRC, "lord.pic"), "rb").read()
    print("lord.pic header(40):", b[:40].hex(" "))
    data = b[32:]
    print("data len", len(data), "/40 =", len(data) / 40)
    for lay in ("interleaved", "plane_major"):
        img = planar_to_img(data, 320, 200, 4, lay)
        img.save(os.path.join(OUT, f"lord_{lay}.png"))
    # sans entete
    for lay in ("interleaved", "plane_major"):
        img = planar_to_img(b[:32000], 320, 200, 4, lay)
        img.save(os.path.join(OUT, f"lord0_{lay}.png"))

    # ---- mouths.pic ----
    m = open(os.path.join(SRC, "mouths.pic"), "rb").read()
    print("mouths.pic len", len(m), "head:", m[:32].hex(" "))
    print("  /40 =", len(m) / 40, " /20 =", len(m) / 20, " /16 =", len(m) / 16)
    # essais : 4 plans interlaces de 40 octets -> 126/4 lignes = 31.5 (non)
    # essai : 1 plan, 40 octets/ligne, 126 lignes
    for w, h, pl in ((320, 126, 1), (320, 63, 2), (320, 31, 4),
                     (160, 252, 1), (160, 63, 4), (80, 126, 2),
                     (64, 157, 1), (40, 252, 1)):
        rb = w // 8
        if rb * h * pl > len(m):
            continue
        img = planar_to_img(m, w, h, pl, "interleaved")
        img.save(os.path.join(OUT, f"mouths_{w}x{h}p{pl}.png"))
    print("ecrits:", os.listdir(OUT))


if __name__ == "__main__":
    main()
