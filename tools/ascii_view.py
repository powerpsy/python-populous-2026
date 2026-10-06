"""Analyse ASCII d'une image 320x200 (aperçu sans vision).

Usage : ``python tools\\ascii_view.py image.png [pas]``
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

# bucket -> caractere (les 16 couleurs de la palette du jeu)
RAMP = " .:-=+*#%@<>?/~^$"


def bucket(r: int, g: int, b: int) -> str:
    if r < 24 and g < 24 and b < 24:
        return " "                                   # noir
    if b > r + 40 and b > g + 20:
        return "~"                                   # bleu / eau
    if g > r + 30 and g > b + 20:
        return "Y" if g > 140 else "y"               # vert
    if r > g + 50 and r > b + 50:
        return "R"                                   # rouge
    if abs(r - g) < 30 and abs(g - b) < 30:
        v = (r + g + b) // 3
        return RAMP[min(len(RAMP) - 1, v * len(RAMP) // 256)]
    if r > b + 40 and g > b + 20:
        return "O"                                   # jaune/orange/marron
    if b > 120 and r > 100:
        return "C"                                   # cyan clair
    return "?"


def main() -> None:
    p = Path(sys.argv[1])
    step = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    im = Image.open(p).convert("RGB")
    w, h = im.size
    px = im.load()
    print(p.name, w, "x", h, " pas", step)
    print("    " + "".join(str((x // step) % 10) for x in range(0, w, step)))
    for y in range(0, h, step):
        row = "".join(bucket(*px[x, y]) for x in range(0, w, step))
        print("%3d %s" % (y, row))


if __name__ == "__main__":
    main()
