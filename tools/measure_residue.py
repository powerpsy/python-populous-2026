# -*- coding: utf-8 -*-
"""Decompose les ecarts de ``check_render`` entre la 3e passe et l'ordre peintre.

``check_render`` compare deux rendus de la meme fenetre 8x8 et accepte jusqu'a
210 pixels de difference — un seuil venu de ``docs/map_generation.md`` §9.4
(1287 px sur 168 fenetres, 7,7 px/fenetre, max 202). Ce total melange deux
choses bien distinctes :

* le **residu connu** : la 3e passe ne peint les falaises que sur les bords de
  la fenetre, donc les falaises *interieures* manquent et laissent du NOIR —
  c'est l'optimisation de l'original, pas une erreur de transcription ;
* le reste : des pixels ou les **deux** rendus ont peint quelque chose mais
  different. Ce n'est pas le residu, et ``check_render`` ne le distingue pas.

Mesure (outils + fenetre (48,16)) :

.. code-block:: none

    sol graine  residu  vrai        sol graine  residu  vrai
      0      1      26     9          3      1      16    18
      0      7      36    12          3      7      36    24
      0     59      16    14          3     59      11    30
      1   1/7/59    <=5    0          4      1     439    18
      2   1/7/59    <=4    0          4      7     225    24
                                      4     59     189    25

Trois faits, tous mesures et non supposes :

1. **la carte ne depend pas du sol** — ``Terrain.ground`` est du state mort ;
   ``build_map(s, 0)`` et ``build_map(s, 4)`` donnent les memes ``blk``,
   ``disp_alt`` et ``bk2``. Les differences viennent donc des **tuiles**.
2. le sol 4 depasse le seuil 210 (jusqu'a 457 px) uniquement a cause du
   residu : 439 de ses 457 ecarts sont du NOIR sur la 3e passe.
3. le « vrai ecart » n'est pas propre au sol 4 — le sol 0 en a 9 a 14,
   le sol 3 en a 18 a 30. Il est donc anterieur a la Phase 53.

Usage : ``python tools\\measure_residue.py``
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from populous.render import SCREEN_H, SCREEN_W, Renderer  # noqa: E402
from populous.terrain import build_map  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "check_render", str(ROOT / "tools" / "check_render.py"))
cr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cr)

BLACK = (0, 0, 0)


def classe(r, t, xoff, yoff):
    a = pygame.Surface((SCREEN_W, SCREEN_H))
    a.fill(BLACK)
    r.draw_window(a, t, xoff, yoff)
    b = cr.painter_window(r, t, xoff, yoff)
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


def main() -> int:
    pygame.init()
    pygame.display.set_mode((SCREEN_W, SCREEN_H))
    lignes = ["sol graine  residu  vrai"]
    pire_vrai = (0, None)
    for g in range(5):
        r = Renderer(g)
        for s in (1, 7, 59, 112, 314):
            t, _ = build_map(s, g)
            residu, vrai = classe(r, t, 48, 16)
            lignes.append("%3d %6d %7d %5d%s"
                          % (g, s, residu, vrai,
                             "   <-- vrai ecart" if vrai else ""))
            if vrai > pire_vrai[0]:
                pire_vrai = (vrai, (g, s))
    print("\n".join(lignes))
    print()
    print("plus gros ecart NON residuel : %d px (sol %d, graine %d)"
          % (pire_vrai[0], pire_vrai[1][0], pire_vrai[1][1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
