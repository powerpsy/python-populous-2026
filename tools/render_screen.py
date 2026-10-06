"""Compose l'écran de jeu complet : qaz.pic + fenêtre 8×8 + mini-carte + barres.

Ordre exact de la boucle d'image (``populous_prg.asm`` L604-660) :

1. ``_clr_wsc``     copie ``_back_scr`` (**qaz.pic**) dans l'écran de travail
                    (L16282) — d'où l'importance du fond ;
2. ``_draw_it``     les 3 passes de la fenêtre 8×8 (L15794) ;
3. ``_draw_map``    la mini-carte, **écrite dans ``_back_scr``** (L1543) donc
                    persistante d'image à l'image ;
4. ``_draw_bar``    les barres d'état, écrites dans l'écran de travail (L19213).

``_draw_bar(screen, x_octets, y, total, valeur, couleur)`` : colonne de 4 px
(bits 2..5 de l'octet), ``valeur`` lignes **en partant de ``y`` vers le haut**
remplies avec ``couleur``, puis le reste avec la couleur 2 (gris).

Usage : ``python tools\\render_screen.py [graine] [ground] [xoff] [yoff]``
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from populous.assets import load_pic, palette_rgb  # noqa: E402
from populous.render import Renderer, map_colours  # noqa: E402
from populous.terrain import build_map  # noqa: E402

PAL = palette_rgb()


# ------------------------------------------------------------------ _draw_bar
def draw_bar(dest: pygame.Surface, x_bytes: int, y: int, total: int,
             value: int, colour: int) -> None:
    """``_draw_bar`` (L19213) : colonne de 4 px, remplissage par le bas."""
    value = max(0, min(total, value))
    px = x_bytes * 8 + 2                      # bits 2..5 de l'octet
    # valeur lignes depuis y vers le haut
    for i in range(value):
        yy = y - i
        if 0 <= yy < 200:
            for k in range(4):
                dest.set_at((px + k, yy), PAL[colour & 15])
    # reste vers le haut, couleur 2
    rest = total - value
    for i in range(rest):
        yy = y - value - i
        if 0 <= yy < 200:
            for k in range(4):
                dest.set_at((px + k, yy), PAL[2])


# ------------------------------------------------------------------- écran
def build_screen(terr, ren: Renderer, xoff: int, yoff: int,
                 good_pop: int = 0, bad_pop: int = 0) -> pygame.Surface:
    frame = pygame.Surface((320, 200))

    # 1. fond = qaz.pic (_back_scr)
    frame.blit(load_pic("qaz.pic"), (0, 0))

    # 2. mini-carte -> dessinée dans le fond (persistante)
    ren.draw_minimap(frame, terr, colours=map_colours(ren.header))

    # 3. la fenêtre 8×8 par-dessus
    ren.draw_window(frame, terr, xoff, yoff)

    # 4. barres d'état (écran de travail)
    #    population « bonne » : x=32 octets -> px 258..261, y=31, total 32
    draw_bar(frame, 0x20, 31, 32, good_pop * 31 // 50000 + 1 if good_pop else 0, 0x0F)
    #    population « mauvaise » : x=39 octets -> px 314..317
    draw_bar(frame, 0x27, 31, 32, bad_pop * 31 // 50000 + 1 if bad_pop else 0, 8)
    return frame


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    ground = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    xoff = int(sys.argv[3]) if len(sys.argv) > 3 else 24
    yoff = int(sys.argv[4]) if len(sys.argv) > 4 else 8

    pygame.init()
    pygame.display.set_mode((320, 200))

    terr, info = build_map(seed, ground)
    ren = Renderer(ground)
    out = ROOT / "out_png" / ("screen_seed%d_g%d_x%dy%d.png"
                              % (seed, ground, xoff, yoff))
    frame = build_screen(terr, ren, xoff, yoff, good_pop=12345, bad_pop=4321)
    pygame.image.save(frame, str(out))
    print("graine=%d sol=%d fenêtre=(%d,%d)" % (seed, ground, xoff, yoff))
    print("  ->", out)


if __name__ == "__main__":
    main()
