# -*- coding: utf-8 -*-
"""`_check_cancel` (asm L12106-12159) - transcription + controle.

`_check_cancel(end_ok, end_cancel)` recoit deux **structures** de 3 mots :

    +0  x0     +2  y0     +4  x1

et renvoie :

    * `0` si `_left_button != 0` (pas de clic) ou si aucun des deux cadres
      n'est touche ;
    * `1` si la souris est dans le cadre OK ;
    * `2` si elle est dans le cadre CANCEL.

Le test de chaque cadre (L12110-12129 pour OK, L12134-12155 pour CANCEL) :

    x0 <= _mousex <= x1        et        y0 <= _mousey <= y0 + $10

soit une bande haute de 16 px. C'est le **seul** endroit du listing ou ces
deux structures sont lues.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

ENC = "utf-8"
TOTAL = [0]
KO = [0]


def check(label, cond, detail=""):
    TOTAL[0] += 1
    if not cond:
        KO[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "KO",
                           label, ("  -> " + detail) if detail else ""))


def reference(left, mx, my, ok, cancel):
    """Reecriture independante de L12106-12159, depuis le listing."""
    if left != 0:                       # L12108-12109
        return 0
    for code, box in ((1, ok), (2, cancel)):
        if box is None:                 # L12110 / L12135 : pointeur nul
            continue
        x0, y0, x1 = box
        if not (x0 <= mx <= x1):        # L12113-12119 / L12137-12143
            continue
        if my < y0:                     # L12120-12123 / L12144-12148
            continue
        if my > y0 + 0x10:              # L12124-12129 / L12149-12154
            continue
        return code
    return 0                            # L12157-12158


def main():
    from populous.game import Game
    g = Game(59, 0, 3)

    OK = (0x20, 0x50, 0x60)
    CANCEL = (0xC0, 0x50, 0xE0)
    cas = []
    for left in (0, 1, 2):
        for mx in (0x10, 0x1F, 0x20, 0x40, 0x60, 0x61, 0xBF, 0xC0, 0xD0,
                   0xE0, 0xE1):
            for my in (0x4F, 0x50, 0x58, 0x5F, 0x60, 0x61):
                cas.append((left, mx, my, OK, CANCEL))

    ecarts = 0
    for left, mx, my, ok, cancel in cas:
        g.left_button = left
        g.mouse = (mx, my)
        port = g.check_cancel(ok, cancel)
        ref = reference(left, mx, my, ok, cancel)
        if port != ref:
            ecarts += 1
            if ecarts <= 5:
                print("  ECART left=%d mouse=(%d,%d) : port=%d ref=%d"
                      % (left, mx, my, port, ref))

    check("%d cas : le port et la reecriture du listing donnent le meme code"
          % len(cas), ecarts == 0, "%d écart(s)" % ecarts)

    # les six cas particuliers du listing
    g.left_button = 1
    g.mouse = (0x40, 0x58)
    check("L12108 : `_left_button != 0` -> 0",
          g.check_cancel(OK, CANCEL) == 0)
    g.left_button = 0
    g.mouse = (0x40, 0x58)
    check("L12130 : dans OK -> 1", g.check_cancel(OK, CANCEL) == 1)
    g.mouse = (0xD0, 0x58)
    check("L12155 : dans CANCEL -> 2", g.check_cancel(OK, CANCEL) == 2)
    g.mouse = (0x40, 0x61)
    check("L12129 : my > y0+$10 -> 0", g.check_cancel(OK, CANCEL) == 0)
    g.mouse = (0x61, 0x58)
    check("L12119 : mx > x1 -> 0", g.check_cancel(OK, CANCEL) == 0)
    g.mouse = (0x90, 0x58)
    check("L12157 : entre les deux cadres -> 0",
          g.check_cancel(OK, CANCEL) == 0)
    check("L12110 : cadre OK nul -> 0 si hors du cadre CANCEL",
          g.check_cancel(None, CANCEL) is not None)
    g.mouse = (0x1F, 0x50)
    check("L12111 : x0 <= mx (borne basse)", g.check_cancel(OK, CANCEL) == 0)
    g.mouse = (0x20, 0x50)
    check("L12115 : x0 == mx ( borne inclusive )",
          g.check_cancel(OK, CANCEL) == 1)
    g.mouse = (0x60, 0x50)
    check("L12118 : x1 == mx ( borne inclusive )",
          g.check_cancel(OK, CANCEL) == 1)

    print("\n%d controles, %d echec(s)" % (TOTAL[0], KO[0]))
    return 1 if KO[0] else 0


if __name__ == "__main__":
    sys.exit(main())
