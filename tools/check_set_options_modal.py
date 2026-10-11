# -*- coding: utf-8 -*-
"""Controle de la boucle modale de ``_set_options`` (asm L13362-13605).

Comme pour `_options` et `_game_options`, on teste la **logique** et non les
pixels : ce que chaque clic change dans `_game_mode`, et ce que OK / CANCEL
font de la sauvegarde. ``Game._pompe`` est remplace par un scenario.

Usage::

    python tools/check_set_options_modal.py
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from populous.game import Game  # noqa: E402
from populous.set_options import (SET_OPTIONS_TEXTE,  # noqa: E402
                                   SET_OPTIONS_W, SET_OPTIONS_X,
                                   SET_OPTIONS_Y)

TOTAL = [0]
KO = [0]


def check(label, cond, detail=""):
    TOTAL[0] += 1
    if not cond:
        KO[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "KO", label,
                           ("  -> " + detail) if detail else ""))


def scenario(g, pas):
    n = [0]

    def pompe():
        if n[0] >= len(pas):
            return
        mx, my, presse = pas[n[0]]
        n[0] += 1
        g.mouse = (mx, my)
        g._raw_left = presse
        g._read_buttons()

    g._pompe = pompe


def centre(k):
    """Au milieu de la zone cliquable de la ligne `k`.

    L13494-13529 : x dans `[x+$20, x+w+$20]`, y dans `[y+$18, y+$20]`.
    """
    return (SET_OPTIONS_X[k] + 0x20 + (SET_OPTIONS_W[k] >> 1),
            SET_OPTIONS_Y[k] + 0x1C)


def point_ok(g):
    """Un point a l'interieur du cadre OK mais hors des zones de ligne.

    Les deux colonnes d'une paire ont `x = 16`, donc leurs boites font
    `[48, 56]` en pixels. Le cadre OK fait `[48, 96]` : **il recouvre la
    neuvieme ligne**, qui est a `y` dans `[104, 112]` alors que OK couvre
    `[97, 113]`. C'est le listing - L13490 teste les lignes *avant*
    `_check_cancel` - donc cliquer OK au milieu de la ligne allumerait au
    passage la cinquieme paire. Le controle vise donc la droite du cadre.
    """
    ok, cancel = g._cadres_boutons(*g._boite_set_options())
    return (ok[0] + (ok[2] - ok[0]) - 4, ok[1] + 8)


def sortir_ok(g):
    mx, my = point_ok(g)
    scenario(g, [(0, 0, False), (mx, my, True)])
    g.set_options()
    del g._pompe


def cliquer(g, k, finir_ok=True):
    mx, my = centre(k)
    pas = [(0, 0, False), (mx, my, True)]
    if finir_ok:
        ox, oy = point_ok(g)
        pas += [(0, 0, False), (ox, oy, True)]
    scenario(g, pas)
    g.set_options()
    del g._pompe


def main():
    g = Game(59, 0, 3)
    sim = g.sim

    def neuf():
        sim.game_mode = 0
        sim.in_conquest = -1
        sim.set_option_ticks = [s[:1] for s in SET_OPTIONS_TEXTE]

    neuf()

    ok, cancel = g._cadres_boutons(*g._boite_set_options())
    check("L9991-10246 : les deux cadres de la boite $100 x $70 sont calcules",
          cancel[0] > ok[0],
          "ok=%s cancel=%s" % (str(ok), str(cancel)))

    # ---- 1. le prologue classe les coches d'apres `_game_mode` ---------
    sim.game_mode = 0b10101
    sortir_ok(g)
    t = sim.set_option_ticks
    paires = [(t[2 * j + 1], t[2 * j + 2]) for j in range(5)]
    check("L13386-13396 : `_game_mode` bit a 1 -> colonne 2 cochee",
          [c2 for _, c2 in paires] == ["\x81", "\x80", "\x81", "\x80", "\x81"],
          "paires=%s" % ["".join(p) for p in paires])
    check("L13386-13396 : bit a 0 -> colonne 1 decochee",
          all(c1 == "\x80" for c1, _ in paires))

    sim.game_mode = 0
    sortir_ok(g)
    t = sim.set_option_ticks
    check("L24310 : `_game_mode == 0` -> les cinq colonnes 1 decochees",
          all(t[2 * j + 1] == "\x80" and t[2 * j + 2] == "\x80"
              for j in range(5)))

    # ---- 2. un clic sur la colonne 1 bascule le bit de la paire --------
    neuf()
    cliquer(g, 1)                      # paire 0, colonne 1, bit 0 a 0
    check("L13536 : le clic fait `EOR.W` du bit de la paire",
          sim.game_mode == 1, "game_mode=%d" % sim.game_mode)
    check("L13537-13545 : le bit passe a 1, la coche part sur la colonne 2",
          sim.set_option_ticks[2] == "\x81"
          and sim.set_option_ticks[1] == "\x80",
          "ticks=%s" % sim.set_option_ticks[1:3])

    neuf()
    cliquer(g, 3)                      # paire 1, bit 1
    check("L13531-13534 : `i >> 1` donne le bit de la paire",
          sim.game_mode == 2, "game_mode=%d" % sim.game_mode)

    neuf()
    cliquer(g, 9)                      # paire 4, bit 4
    check("L13531-13534 : la cinquieme paire est le bit 4",
          sim.game_mode == 16, "game_mode=%d" % sim.game_mode)

    # ---- 3. recliquer annule le bit, et la coche revient en colonne 1 ---
    sim.game_mode = 1                  # colonne 2 active de la paire 0
    cliquer(g, 1)
    check("L13536 : recliquer sur la colonne 1 remet le bit a zero",
          sim.game_mode == 0, "game_mode=%d" % sim.game_mode)
    check("L13544-13545 : bit a 0 -> la coche revient sur la colonne 1",
          sim.set_option_ticks[1] == "\x80")

    # ---- 4. le survol ne teste que les colonnes impaires ----------------
    neuf()
    g.mouse = centre(1)
    check("L13490/L13585-13587 : la colonne 1 est testee",
          g._survol_set_options() == 1,
          "survol=%s" % g._survol_set_options())
    # Les deux colonnes d'une paire partagent x et y : tester l'index 2
    # revient donc a tester l'index 1 - c'est bien le listing, qui n'ouvre
    # que les colonnes impaires (`ADDQ.W #2`, `CMPI.W #$000A`, L13585-13586).
    g.mouse = centre(2)
    check("L13490 : la colonne 2 n'est pas listee, mais sa boite est la meme",
          g._survol_set_options() == 1,
          "survol=%s" % g._survol_set_options())
    g.mouse = (5, 5)
    check("L13584-13587 : un clic hors de toute ligne ne touche rien",
          g._survol_set_options() is None)

    # la conquete neutralise tout l'ecran (L13500-13501)
    sim.in_conquest = 3
    g.mouse = centre(1)
    check("L13500-13501 : en conquete le survol est neutralise",
          g._survol_set_options() is None)
    sim.in_conquest = -1
    g.mouse = centre(1)

    # ---- 5. CANCEL restaure `_game_mode` (L13595-13597) ---------------
    sim.game_mode = 0b01010
    garde = sim.game_mode
    clics = [(0, 0, False), (centre(1)[0], centre(1)[1], True),
             (0, 0, False), (cancel[0] + 4, cancel[1] + 8, True)]
    scenario(g, clics)
    g.set_options()
    del g._pompe
    check("L13597 : CANCEL restaure `_game_mode`",
          sim.game_mode == garde,
          "attendu %d, obtenu %d" % (garde, sim.game_mode))

    # ---- 6. OK conserve la bascule (L13602-13603) ---------------------
    neuf()
    cliquer(g, 7)                      # paire 3, bit 3
    check("L13594-13602 : OK valide la bascule",
          sim.game_mode == 8, "game_mode=%d" % sim.game_mode)

    # ---- 7. la boucle modale ne fait pas tourner la simulation -------
    neuf()
    tour = sim.game_turn
    cliquer(g, 5)
    check("L13484 : la boucle modale ne fait pas avancer la simulation",
          sim.game_turn == tour, "game_turn %d -> %d"
          % (tour, sim.game_turn))

    # ---- 8. le trace des onze lignes ---------------------------------
    sim.game_mode = 0b11011
    try:
        g._trace_set_options()
        trace_ok, detail = True, ""
    except Exception as exc:
        trace_ok, detail = False, "%s: %s" % (type(exc).__name__, exc)
    check("L13374-13479 : les onze lignes et la rustine se tracent sans lever",
          trace_ok, detail)

    # ---- 9. la ligne 11 de GAME SETUP appelle cet ecran ---------------
    # `_set_options` est une boucle modale : on la remplace par un spy pour
    # verifier que la ligne 11 l'appelle et qu'elle demande le redessin de la
    # boite GAME SETUP (L13256-13257).
    neuf()
    g._redessiner = False
    appele = []
    vrai = g.set_options

    def espion():
        appele.append(True)

    g.set_options = espion
    try:
        g._exec_game_setup(11)
    finally:
        g.set_options = vrai
    check("L13256 : la ligne 11 ouvre `SET GAME OPTIONS`",
          len(appele) == 1, "appels=%d" % len(appele))
    check("L13257 : elle demande le redessin de la boite GAME SETUP",
          g._redessiner is True)

    print("\n%d controles, %d echec(s)" % (TOTAL[0], KO[0]))
    return 1 if KO[0] else 0


if __name__ == "__main__":
    sys.exit(main())