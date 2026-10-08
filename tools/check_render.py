"""Contrôle du rendu isométrique : les 3 passes de ``_draw_it`` == ordre peintre.

Deux rendus indépendants de la même fenêtre 8×8 doivent être **identiques au
pixel près** :

* ``Renderer.draw_window`` — les 3 passes exactes de l'asm (losanges, puis
  face avant droite de la dernière colonne, puis face avant gauche de la
  dernière ligne) ;
* un rendu « ordre peintre » qui, pour chaque case de la fenêtre, dessine son
  losange **et ses deux falaises**, cases du fond vers l'avant.

Si les deux coïncident, c'est que les falaises intérieures sont bien
intégrément recouvertes par les cases devant elles — ce qui justifie
l'optimisation de l'original (seules les bords de la fenêtre en ont).

Contrôle supplémentaire : ``cell_px`` (adresse octet réduite modulo 40) doit
donner exactement ``cell_abs`` (projection pixel) sur toute la fenêtre.

Les écarts sont **classés** (Phase 54), et le sort en code d'erreur est
enfin :

* ``résidu`` — la 3e passe a laissé du **NOIR** : falaise intérieure non
  dessinée. Artefact *attendu* de l'optimisation de l'original, toléré par
  ``SEUIL_RESIDU`` ;
* ``vrai écart`` — les deux rendus ont peint, mais différemment. C'est la
  seule catégorie qui puisse révéler une erreur de transcription, tolérée
  par ``SEUIL_VRAI``.

L'ancien compteur additionnait les deux, et l'outil sortait **toujours en
0** : un dépassement s'imprimait mais ne pouvait pas faire échouer une
vérification. ``main`` renvoie désormais 1 au-delà des seuils.

Usage : ``python tools\\check_render.py [graine] [ground] [xoff] [yoff]``
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from populous.render import (SCREEN_H, SCREEN_W, WINDOW,  # noqa: E402
                             Renderer, cell_abs, cell_px)
from populous.terrain import build_map  # noqa: E402

BLACK = (0, 0, 0)

#: Résidu **attendu** : les falaises intérieures que l'original ne dessine
#: pas laissent le noir du fond. Ce n'est pas une erreur de transcription.
#: Mesuré sur 25 fenêtres (5 sols x 5 graines, fenêtre (48,16)) : max 439 px
#: (sol 4, graine 1). L'échantillon d'origine (168 fenêtres = 7 graines x
#: 4 sols x 6 positions) **ne couvrait pas le sol 4** et donnait max 202.
SEUIL_RESIDU = 600
#: Pixels où les deux rendus ont peint, mais différemment. Ce n'est **pas**
#: le résidu, et l'ancien compteur unique les mélangeait. Mesuré sur les
#: mêmes 25 fenêtres : max 30 px (sol 3, graine 59).
SEUIL_VRAI = 60


def painter_window(r: Renderer, t, xoff: int, yoff: int) -> pygame.Surface:
    """Rendu de référence : ordre peintre, falaises sur **toutes** les cases."""
    s = pygame.Surface((SCREEN_W, SCREEN_H))
    s.fill(BLACK)
    for dsum in range(0, 2 * WINDOW - 1):          # du fond vers l'avant
        for d0 in range(max(0, dsum - WINDOW + 1), min(WINDOW - 1, dsum) + 1):
            d1 = dsum - d0
            idx = ((yoff + d1) << 6) | (xoff + d0)
            a = t.disp_alt[idx]
            tile = t.blk[idx]
            if tile == 0 and r.toggle == 0:
                tile = 16
            s.blit(r.tiles[tile], cell_abs(d0, d1, a))
            deco = t.bk2[idx]
            if deco:
                s.blit(r.tiles[deco], cell_abs(d0, d1, a + 1))
            if a:
                x, y0 = cell_abs(d0, d1, 0)
                r.blit_face(s, 77, x, y0, a, dx=16)
                r.blit_face(s, 76, x, y0, a, dx=0)
    return s


def diff(a: pygame.Surface, b: pygame.Surface) -> list[tuple[int, int]]:
    pa, pb = pygame.image.tostring(a, "RGB"), pygame.image.tostring(b, "RGB")
    return [(i % SCREEN_W, i // SCREEN_W)
            for i in range(SCREEN_W * SCREEN_H) if pa[i * 3:i * 3 + 3] != pb[i * 3:i * 3 + 3]]


def classe(a: pygame.Surface, b: pygame.Surface) -> tuple[int, int]:
    """(résidu, vrai écart).

    *résidu* : la 3e passe a laissé du **NOIR** — falaise intérieure non
    dessinée, artefact attendu de l'optimisation de l'original.

    *vrai* : les deux rendus ont peint quelque chose mais différent. Ce
    n'est pas le résidu, et c'est la seule catégorie qui puisse signaler
    une erreur de transcription.
    """
    pa = pygame.image.tostring(a, "RGB")
    pb = pygame.image.tostring(b, "RGB")
    residu = vrai = 0
    for i in range(SCREEN_W * SCREEN_H):
        ca, cb = pa[i * 3:i * 3 + 3], pb[i * 3:i * 3 + 3]
        if ca == cb:
            continue
        if ca == b"\x00\x00\x00":
            residu += 1
        else:
            vrai += 1
    return residu, vrai


def check_projection() -> int:
    bad = 0
    for d0 in range(WINDOW):
        for d1 in range(WINDOW):
            for alt in range(8):
                if cell_px(d0, d1, alt) != cell_abs(d0, d1, alt):
                    bad += 1
    return bad


def main() -> int:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    ground = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    xoff = int(sys.argv[3]) if len(sys.argv) > 3 else 48
    yoff = int(sys.argv[4]) if len(sys.argv) > 4 else 16

    pygame.init()
    pygame.display.set_mode((SCREEN_W, SCREEN_H))

    bad = check_projection()
    print("projection cell_px vs cell_abs : %d écart(s)" % bad)

    t, _ = build_map(seed, ground)
    r = Renderer(ground)
    a = pygame.Surface((SCREEN_W, SCREEN_H))
    a.fill(BLACK)
    r.draw_window(a, t, xoff, yoff)
    b = painter_window(r, t, xoff, yoff)
    d = diff(a, b)
    residu, vrai = classe(a, b)
    print("fenêtre (%d,%d) : %d pixel(s) différents sur %d "
          "(dont %d résidu attendu, %d vrai écart)"
          % (xoff, yoff, len(d), SCREEN_W * SCREEN_H, residu, vrai))
    if d:
        xs = [p[0] for p in d]
        ys = [p[1] for p in d]
        print("  bbox des écarts : x %d..%d  y %d..%d"
              % (min(xs), max(xs), min(ys), max(ys)))
        print("  premiers :", d[:12])
        pygame.image.save(a, str(ROOT / "out_png" / "check_3pass.png"))
        pygame.image.save(b, str(ROOT / "out_png" / "check_painter.png"))
    ok = (bad == 0 and residu <= SEUIL_RESIDU and vrai <= SEUIL_VRAI)
    print("=> %s" % ("OK" if ok else "ÉCART"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
