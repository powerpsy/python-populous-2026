"""Compare les **deux** lectures du masque des tuiles/sprites, côte à côte.

L'asm (``SUB_49938``, ``populous_prg.asm`` L15771) fait

    ecran = (ecran AND masque) OR donnees

donc un pixel dont le bit de masque vaut 0 est **entièrement réécrit** — y
compris en indice 0 (noir) si les 4 plans y sont nuls. La première version du
décodeur traitait au contraire « données = 0 » comme transparent.

Ce script affiche les deux rendus + un agrandissement ×4 d'une zone choisie pour
que leDifference soit visible à l'œil.

Usage::

    python tools\\compare_blit.py [graine] [sol] [xoff] [yoff] [zoom_x] [zoom_y] [w] [h]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from populous import assets  # noqa: E402
from populous.render import Renderer, map_colours  # noqa: E402
from populous.terrain import build_map  # noqa: E402

PAL = assets.palette_rgb()
ZOOM = 4
LBL_W = 150


def draw_bar(dest: pygame.Surface, x_bytes: int, y: int, total: int,
             value: int, colour: int) -> None:
    value = max(0, min(total, value))
    px = x_bytes * 8 + 2
    for i in range(value):
        if 0 <= y - i < 200:
            for k in range(4):
                dest.set_at((px + k, y - i), PAL[colour & 15])
    for i in range(total - value):
        if 0 <= y - value - i < 200:
            for k in range(4):
                dest.set_at((px + k, y - value - i), PAL[2])


def frame_for(terr, ground: int, xoff: int, yoff: int) -> pygame.Surface:
    ren = Renderer(ground)
    f = pygame.Surface((320, 200))
    f.blit(assets.load_pic("qaz.pic"), (0, 0))
    ren.draw_minimap(f, terr, colours=map_colours(ren.header))
    ren.draw_window(f, terr, xoff, yoff)
    draw_bar(f, 0x20, 31, 32, 12345 * 31 // 50000 + 1, 0x0F)
    draw_bar(f, 0x27, 31, 32, 4321 * 31 // 50000 + 1, 8)
    return f


def window_only(terr, ground: int, xoff: int, yoff: int) -> pygame.Surface:
    """La fenêtre 8×8 seule sur un fond **coloré** : révèle tous les « trous ».

    Sur l'écran réel (rangée du haut) les trous ne changent rien car qaz.pic est
    noir à 97 % sous le losange ; ici on force une couleur de fond pour voir
    exactement ce que la variante B laisserait voir.
    """
    ren = Renderer(ground)
    f = pygame.Surface((320, 200))
    f.fill((90, 0, 110))
    ren.draw_window(f, terr, xoff, yoff)
    return f


def upscale(surf: pygame.Surface, box: tuple[int, int, int, int]) -> pygame.Surface:
    """Agrandit une boîte de (x, y, w, h) en ZOOM × ZOOM."""
    x, y, w, h = box
    out = pygame.Surface((w * ZOOM, h * ZOOM))
    for j in range(h * ZOOM):
        for i in range(w * ZOOM):
            out.set_at((i, j), surf.get_at((x + i // ZOOM, y + j // ZOOM))[:3])
    return out


def main() -> None:
    a = [int(v) for v in sys.argv[1:]]
    seed = a[0] if len(a) > 0 else 1
    ground = a[1] if len(a) > 1 else 0
    xoff = a[2] if len(a) > 2 else 24
    yoff = a[3] if len(a) > 3 else 8
    zx = a[4] if len(a) > 4 else 200
    zy = a[5] if len(a) > 5 else 100
    zw = a[6] if len(a) > 6 else 30
    zh = a[7] if len(a) > 7 else 20

    pygame.init()
    pygame.display.set_mode((320, 200))
    font = pygame.font.Font(None, 20)

    terr, _ = build_map(seed, ground)

    shots = {}
    bare = {}
    for mode, key in ((True, "masque"), (False, "donnees")):
        assets.OPAQUE_FROM_MASK = mode
        shots[key] = frame_for(terr, ground, xoff, yoff)
        bare[key] = window_only(terr, ground, xoff, yoff)
    assets.OPAQUE_FROM_MASK = True

    def stats(a: pygame.Surface, b: pygame.Surface) -> int:
        pa = pygame.image.tostring(a, "RGB")
        pb = pygame.image.tostring(b, "RGB")
        return sum(1 for i in range(320 * 200)
                   if pa[i * 3:i * 3 + 3] != pb[i * 3:i * 3 + 3])

    print("ecran complet  A/B : %d pixel(s) differents / 64000"
          % stats(shots["masque"], shots["donnees"]))
    print("fenetre sur fond couleur  A/B : %d pixel(s) differents / 64000"
          % stats(bare["masque"], bare["donnees"]))

    panels = []
    for key, title, sub in (
        ("masque", "A - masque (fidele)", "ecran = (ecran AND m) OR d"),
        ("donnees", "B - donnees nulles", "d == 0 => transparent"),
    ):
        col = pygame.Surface((320 + LBL_W, 200))
        col.blit(shots[key], (LBL_W, 0))
        col.blit(font.render(title, True, (255, 255, 255)), (6, 8))
        col.blit(font.render(sub, True, (170, 170, 170)), (6, 28))
        for i, t in enumerate(("ecran complet 320x200", "qaz.pic + fenetre 8x8",
                               "+ mini-carte + barres")):
            col.blit(font.render(t, True, (120, 120, 120)), (6, 62 + i * 14))
        panels.append(col)

    strip = pygame.Surface((panels[0].get_width() * 2 + 12, 200))
    strip.fill((40, 40, 40))
    strip.blit(panels[0], (0, 0))
    strip.blit(panels[1], (panels[0].get_width() + 12, 0))

    # ---- 2e rangée : fenêtre seule sur fond coloré -------------------------
    row2 = pygame.Surface((panels[0].get_width() * 2 + 12, 200))
    row2.fill((40, 40, 40))
    for i, key in enumerate(("masque", "donnees")):
        ox = LBL_W + i * (320 + 12)
        row2.blit(bare[key], (ox, 0))
        row2.blit(font.render("%s - sans qaz.pic" % ("A" if i == 0 else "B"),
                              True, (200, 200, 120)), (6, 12 + i * 14))
    row2.blit(font.render("fond violet = tout trou", True, (170, 120, 200)),
              (LBL_W, 8))

    # ---- bandeau d'agrandissement ------------------------------------------
    ups = []
    for key in ("masque", "donnees"):
        ups.append(upscale(bare[key], (zx, zy, zw, zh)))
    ubox = pygame.Surface((ups[0].get_width() * 2 + 12 + 2 * LBL_W,
                           ups[0].get_height() + 44))
    ubox.fill((40, 40, 40))
    for i, key in enumerate(("masque", "donnees")):
        ox = LBL_W + i * (ups[0].get_width() + 12)
        ubox.blit(ups[i], (ox, 26))
        ubox.blit(font.render("%s x%d" % ("A" if i == 0 else "B", ZOOM),
                              True, (255, 255, 255)), (6, 14 + i * 12))
    ubox.blit(font.render("zoom x%d  boite (%d,%d) %dx%d" % (ZOOM, zx, zy, zw, zh),
                          True, (150, 150, 150)), (LBL_W, 32))
    ubox.blit(font.render("(fenetre seule, fond violet)", True, (150, 150, 150)),
              (LBL_W + 150, 32))

    canvas = pygame.Surface((max(strip.get_width(), ubox.get_width()),
                             strip.get_height() + row2.get_height()
                             + ubox.get_height() + 16))
    canvas.fill((20, 20, 20))
    canvas.blit(strip, (0, 0))
    canvas.blit(row2, (0, strip.get_height() + 8))
    canvas.blit(ubox, (0, strip.get_height() + row2.get_height() + 16))

    out = ROOT / "out_png" / ("compare_blit_s%d_g%d_x%dy%d.png"
                              % (seed, ground, xoff, yoff))
    pygame.image.save(canvas, str(out))
    big = upscale(canvas, (0, 0, canvas.get_width(), canvas.get_height()))
    big2 = ROOT / "out_png" / ("compare_blit_s%d_g%d_x%dy%d_x2.png"
                               % (seed, ground, xoff, yoff))
    pygame.image.save(big, str(big2))
    print("graine=%d sol=%d fenetre=(%d,%d)" % (seed, ground, xoff, yoff))
    print("  ->", out)
    print("  ->", big2)


if __name__ == "__main__":
    main()