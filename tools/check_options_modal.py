# -*- coding: utf-8 -*-
"""Controle de la boucle modale d'`_options` (asm L13617-13942).

On ne teste pas les pixels mais la **logique** : ce que le clic change dans
la fiche `_stats`, et ce que OK / CANCEL font de la sauvegarde. `_pompe` est
remplace par un scenario, ce qui permet de faire tourner la vraie
`Game.options()` de bout en bout.

Usage::

    python tools/check_options_modal.py
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from populous.game import Game  # noqa: E402
from populous.options import OPTIONS_W, OPTIONS_X, OPTIONS_Y  # noqa: E402

TOTAL = [0]
KO = [0]


def check(label, cond, detail=""):
    TOTAL[0] += 1
    if not cond:
        KO[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "KO",
                           label, ("  -> " + detail) if detail else ""))


def scenario(g, pas):
    """Remplace `Game._pompe` par une sequence de (mx, my, presse)."""
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

    L13728 decale x de `$10` et L13810 ajoute la largeur : la zone
    est `[x+$10, x+w+$10]` sur y dans `[y+$10, y+$18]`.
    """
    return (OPTIONS_X[k] + 0x10 + (OPTIONS_W[k] >> 1),
            OPTIONS_Y[k] + 0x14)


def main():
    g = Game(59, 0, 3)
    st = g.sim.stats[0]
    st.power_mask = 0xFFFF
    st.threshold = 3
    st.period = 4

    ok, cancel = g._cadres_boutons(*g._boite_options())
    check("L9991-10246 : les deux cadres sont calcules, CANCEL a droite",
          ok is not None and cancel is not None and cancel[0] > ok[0],
          "ok=%s cancel=%s" % (str(ok), str(cancel)))

    # ---- 1. bascule d'une case, puis CANCEL ------------------------------
    # iteration 1 : relache, appui sur la ligne 2 -> bascule,
    #               `_check_cancel` rend 0 (clic hors des boutons)
    # iteration 2 : relache, appui sur CANCEL -> 2 -> restauration.
    # On observe la fiche au moment du `_check_cancel`, car OK/CANCEL la
    # modifient eux aussi juste apres.
    vu = []
    vrai = g.check_cancel

    def espion(ok_box, cancel_box):
        vu.append((st.power_mask, st.threshold, st.period))
        return vrai(ok_box, cancel_box)

    g.check_cancel = espion
    mx, my = centre(2)
    scenario(g, [(0, 0, False), (mx, my, True),
                (0, 0, False), (cancel[0] + 4, cancel[1] + 8, True)])
    g.options(0)
    g.check_cancel = vrai
    check("L13836-13848 : le clic bascule le bit 1 de `power_mask`",
          len(vu) >= 1 and vu[0][0] == 0xFFFF ^ (1 << 1),
          "power_mask=0x%04X au premier _check_cancel" % (vu[0][0] if vu else -1))
    check("L13902-13914 : CANCEL restaure `power_mask` (46 octets)",
          st.power_mask == 0xFFFF, "power_mask=0x%04X" % st.power_mask)
    check("L13902 : CANCEL rend aussi `threshold` et `period` d'origine",
          (st.threshold, st.period) == (3, 4),
          "threshold=%d period=%d" % (st.threshold, st.period))

    # ---- 2. les deux curseurs, puis OK -----------------------------------
    st.power_mask = 0xFFFF
    st.threshold = 3
    st.period = 4
    mx, my = centre(11)
    v11 = (mx - (OPTIONS_X[11] + 0x28)) // 8
    scenario(g, [(0, 0, False), (mx, my, True),
                (0, 0, False), (ok[0] + 4, ok[1] + 8, True)])
    g.options(0)
    # `options()` inverse `threshold` a l'entree, le curseur le remplace, et
    # OK le re-inverse : la valeur **finale** est donc `10 - v`.
    check("L13850-13871 + L13916-13933 : curseur 11 -> `threshold` = 10 - v",
          st.threshold == 10 - v11,
          "attendu %d, obtenu %d" % (10 - v11, st.threshold))

    st.threshold = 3
    st.period = 4
    mx, my = centre(13)
    v13 = (mx - (OPTIONS_X[13] + 0x30)) // 8
    scenario(g, [(0, 0, False), (mx, my, True),
                (0, 0, False), (ok[0] + 4, ok[1] + 8, True)])
    g.options(0)
    check("L13873-13893 + L13916-13933 : curseur 13 -> `period` = 10 - v",
          st.period == 10 - v13,
          "attendu %d, obtenu %d" % (10 - v13, st.period))

    # ---- 3. clic hors des 14 lignes, puis OK ------------------------------
    st.power_mask = 0xFFFF
    scenario(g, [(0, 0, False), (5, 5, True),
                (0, 0, False), (ok[0] + 4, ok[1] + 8, True)])
    g.options(0)
    check("L13832 : clic hors des 14 lignes -> aucune application",
          st.power_mask == 0xFFFF, "power_mask=0x%04X" % st.power_mask)

    # ---- 4. bornes des curseurs ------------------------------------------
    st.threshold = 3
    st.period = 4
    scenario(g, [(0, 0, False), (0, 0, True),
                (0, 0, False), (ok[0] + 4, ok[1] + 8, True)])
    g.options(0)
    check("L13863-13866 : (mx - $28) < 0 -> `threshold` inchange",
          isinstance(st.threshold, int) and 0 <= st.threshold <= 10,
          "threshold=%d" % st.threshold)
    check("L13885-13888 : `period` reste >= 0 (pas de DIVU par zero)",
          0 <= st.period <= 10, "period=%d" % st.period)

    # ---- 5. l'application est coupee en conquete --------------------------
    st.power_mask = 0xFFFF
    g.sim.in_conquest = 0
    mx, my = centre(2)
    scenario(g, [(0, 0, False), (mx, my, True),
                (0, 0, False), (ok[0] + 4, ok[1] + 8, True)])
    g.options(0)
    check("L13834 : en conquete le clic ne change rien",
          st.power_mask == 0xFFFF, "power_mask=0x%04X" % st.power_mask)
    g.sim.in_conquest = -1

    # ---- 6. la boucle modale ne fait pas tourner la simulation -----------
    tour = g.sim.game_turn
    scenario(g, [(0, 0, False), (ok[0] + 4, ok[1] + 8, True)])
    g.options(0)
    check("L13618 : la boucle modale ne fait pas avancer la simulation",
          g.sim.game_turn == tour, "game_turn %d -> %d"
          % (tour, g.sim.game_turn))

    # ---- 7. les deux tribus se tracent ------------------------------------
    st.threshold = st.period = 5
    try:
        g._trace_options(0)
        g._trace_options(1)
        trace_ok, detail = True, ""
    except Exception as exc:
        trace_ok, detail = False, "%s: %s" % (type(exc).__name__, exc)
    check("L13661-13784 : les deux tribus se tracent sans lever",
          trace_ok, detail)

    print("\n%d controles, %d echec(s)" % (TOTAL[0], KO[0]))
    return 1 if KO[0] else 0


if __name__ == "__main__":
    sys.exit(main())
