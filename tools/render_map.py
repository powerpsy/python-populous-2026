"""Rendu d'une carte générée : vue de jeu 320×200 + carte complète + mini-carte.

Usage::

    python tools\\render_map.py [graine] [ground] [xoff] [yoff]

Produit dans ``out_png/`` :

* ``view_seed<graine>_x<xoff>y<yoff>.png`` — ce que le joueur voit (fenêtre 8×8)
* ``map_seed<graine>_full.png``             — la carte entière, en ordre peintre
* ``map_seed<graine>_mini.png``             — le Book of Worlds (×3)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

from populous.render import (ORIGIN_X, ORIGIN_Y, SCREEN_H, SCREEN_W,  # noqa: E402
                             Renderer, WINDOW, cell_abs, cell_px)
from populous.terrain import build_map  # noqa: E402

OUT = ROOT / "out_png"


def view_image(r: Renderer, t, xoff: int, yoff: int) -> pygame.Surface:
    """Ce que ``_zoom_map`` affiche réellement : la fenêtre 8×8 centrée."""
    s = pygame.Surface((SCREEN_W, SCREEN_H))
    s.fill((0, 0, 0))
    r.draw_window(s, t, xoff, yoff)
    return s


def full_image(r: Renderer, t, scale: int = 1) -> Image.Image:
    """Carte entière en ordre peintre (fond → avant), avec toutes les falaises."""
    xs, ys = [], []
    for Y in range(64):
        for X in range(64):
            x, y0 = cell_abs(X, Y, 0)
            a = t.disp_alt[(Y << 6) + X]
            xs += [x, x + 32]
            ys += [y0 - 8 * a, y0 + 24 + 16]
    ox, oy = -min(xs), -min(ys)
    w, h = max(xs) + ox, max(ys) + oy
    s = pygame.Surface((w, h))
    s.fill((20, 20, 30))
    for ssum in range(0, 127):                 # ordre peintre : fond d'abord
        for X in range(max(0, ssum - 63), min(63, ssum) + 1):
            Y = ssum - X
            idx = (Y << 6) | X
            a = t.disp_alt[idx]
            x, y0 = cell_abs(X, Y, 0)           # ancrage « niveau de la mer »
            tile = t.blk[idx]
            if tile == 0 and r.toggle == 0:
                tile = 16
            s.blit(r.tiles[tile], cell_abs(X, Y, a))       # losange à altitude a
            deco = t.bk2[idx]
            if deco:
                s.blit(r.tiles[deco], cell_abs(X, Y, a + 1))
            if a:
                r.blit_face(s, 77, x, y0, a, dx=16)
                r.blit_face(s, 76, x, y0, a, dx=0)
    img = Image.frombytes("RGB", s.get_size(), pygame.image.tostring(s, "RGB"))
    return img.resize((w * scale, h * scale), Image.NEAREST) if scale != 1 else img


def mini_image(r: Renderer, t, scale: int = 3) -> Image.Image:
    s = pygame.Surface((128, 64))
    s.fill((0, 0, 0))
    r.draw_minimap(s, t)
    im = Image.frombytes("RGB", s.get_size(), pygame.image.tostring(s, "RGB"))
    return im.resize((128 * scale, 64 * scale), Image.NEAREST)


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    ground = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    xoff = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    yoff = int(sys.argv[4]) if len(sys.argv) > 4 else 0

    pygame.init()
    pygame.display.set_mode((SCREEN_W, SCREEN_H))
    OUT.mkdir(exist_ok=True)

    t, _ = build_map(seed, ground)
    st = t.stats()
    print("graine=%d sol=%d" % (seed, ground))
    print("  sommets de terre : %d/%d  altitude max %d  build_count=%d"
          % (st["land_verts"], st["verts"], st["max_alt"], st["build_count"]))
    print("  cases eau %d  plates %d  boîte %s"
          % (st["sea"], st["flat"], st["box"]))
    print("  map_blk :", st["blk_hist"])

    r = Renderer(ground)

    v = view_image(r, t, xoff, yoff)
    p = OUT / ("view_seed%d_x%dy%d.png" % (seed, xoff, yoff))
    pygame.image.save(v, str(p))
    print("  ->", p.name)

    im = full_image(r, t)
    p = OUT / ("map_seed%d_full.png" % seed)
    im.save(p)
    print("  -> %s  (%dx%d)" % (p.name, im.width, im.height))

    im = mini_image(r, t)
    p = OUT / ("map_seed%d_mini.png" % seed)
    im.save(p)
    print("  -> %s" % p.name)


if __name__ == "__main__":
    main()
