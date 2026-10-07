# -*- coding: utf-8 -*-
"""Confrontation de ``Game.move_mana`` a une reecriture independante.

L'implementation vient de ``populous/game.py``. La reference ci-dessous est
reecrite DIRECTEMENT depuis le listing L3164-3241, en employant une
definition **differente** de la troncature vers zero : ``int(a / b)`` en
virgule flottante, au lieu de la normalisation des signes de ``divs_long``.
Les deux ne partagent donc aucun code ni aucune formule.

Hors table :
* ``d4 == 0``  -> la reference lit ``_mana_values[-1]`` = ``$00290029``
  (4 octets avant la table, dans ``_big_city``) ;
* ``mana > 2 000 063`` -> l'asm lirait ``_prot_num2 = $E0ED80A7`` (negatif),
  la boucle partirait en fuite. On le verifie separement : dans les deux cas
  ``D4 > 9``, donc sprite fixe.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from populous.constants import MANA_VALUES  # noqa: E402
from populous.game import Game  # noqa: E402

V_AVANT = 0x00290029          # $51870, 4 octets avant _mana_values


def valeur(i: int) -> int:
    """``_mana_values[i]``, y compris l'index -1 hors table."""
    if i < 0:
        return V_AVANT
    return MANA_VALUES[i]


def ref(mana: int) -> tuple[int, int, int]:
    """``_move_mana``, reecriture independante depuis le listing."""
    # ---- LAB_404D6-404FA : tant que mana > v[D4], D4 += 1 -------------
    d4 = 0
    while d4 < len(MANA_VALUES) and mana > valeur(d4):
        d4 += 1

    # ---- CMP.W #$0009,D4 / BGT -> LAB_4057A --------------------------
    if d4 > 9:
        return (0x137, 0x57, 0x45)

    # ---- LAB_40500-40548 : l'interposition dans le cran ---------------
    numer = mana - valeur(d4 - 1)            # SUB.L (0,A0,D1.L),D0
    numer = (numer << 3) & 0xFFFFFFFF        # ASL.L #3
    if numer >= 0x80000000:                  # reste un long SIGNE pour _divs
        numer -= 0x100000000
    denom = valeur(d4) - valeur(d4 - 1)      # SUB.L (0,A2,D2.L),D1

    # _divs : on definit la troncature vers zero autrement, en flottant.
    # Les deux operandes sont representables exactement, et le quotient
    # exact l'est aussi : l'arrondi IEEE donne donc le bon entier.
    d5 = int(numer / denom) & 0xFFFF         # MOVE.W D0,D5

    y = ((d4 - 1) * 8 + d5 + 8) & 0xFFFF     # L4054E-40556
    x = ((d4 - 1) * 16 + (d5 << 1) + 0xA0) & 0xFFFF   # L4055A-40566
    return (x, y, 0x45)


def mesure(g: Game, mana: int) -> tuple[int, int, int]:
    """Appelle la vraie ``move_mana`` et recoit (x, y, sprite)."""
    g.sim.players[g.sim.player].mana = mana
    cap: list[tuple[int, int, int]] = []
    reel = g._draw_sprite_at
    g._draw_sprite_at = lambda x, y, s: cap.append((x, y, s))  # type: ignore
    try:
        g.move_mana()
    finally:
        g._draw_sprite_at = reel          # type: ignore[assignment]
    return cap[0]


def main() -> int:
    random.seed(314159)
    g = Game(59, 0, 3)

    essais: list[int] = []
    for v in MANA_VALUES:
        essais += [v - 1, v, v + 1, v - 2, v + 2]
    essais += [-400, -300, -251, -250, -249, -1, 0, 1, 399, 400]
    essais += [random.randint(-400, 2_000_063) for _ in range(600)]

    ecarts = []
    pourcents = []
    for m in essais:
        if m > 2_000_063 or m <= -400:
            continue                     # traite a part, plus bas
        obtenu = mesure(g, m)
        attendu = ref(m)
        if obtenu != attendu:
            ecarts.append((m, obtenu, attendu))
        else:
            # ou se trouve le curseur, en pourcentage de la diagonale ?
            x, y, _ = obtenu
            pourcents.append((x, y))

    print("essais compares        : %d" % (len(essais) - len(ecarts)))
    if ecarts:
        print("ECARTS                 : %d" % len(ecarts))
        for e in ecarts[:8]:
            print("   mana=%-10d obtenu=%s attendu=%s" % e)
        return 1
    print("ECARTS                 : 0")

    # --- 2. le cas hors table doit finir sur le sprite fixe -------------
    dehors = [mesure(g, m)
              for m in (2_000_064, 2_000_100, 3_000_000, 10_000_000, 0x7FFFFFFF)]
    ok_dehors = all(p == (0x137, 0x57, 0x45) for p in dehors)
    print("mana > 2 000 063       : %s   (D4 > 9 -> sprite fixe)"
          % ("OK" if ok_dehors else "ECART"))
    if not ok_dehors:
        print("   ", dehors)
        return 1

    # --- 3. le cas D4 == 0 (mana == -250) ------------------------------
    p0 = mesure(g, -250)
    print("mana == -250 (D4=0)    : %-18s attendu (160, 8, 0x45)" % (p0,))
    if p0 != (0xA0, 0x08, 0x45):
        return 1

    # --- 4. bornes du curseur ------------------------------------------
    print("curseur min (D4=1)     : %s" % (mesure(g, -249),))
    print("curseur haut (D4=9)    : %s" % (mesure(g, 160_000),))

    # --- 5. _do_action codes 9/10 (LAB_4C0B8 / LAB_4C0EC, L18943-18959) -
    # Ce bloc n'est exerce NULLE PART ailleurs : autopilot ne passe jamais
    # par `do_action`. C'est donc ici le seul controle de la largeur des deux
    # operations — `___divs` est un `JMP _divs` (L24077), la division
    # **longue** ; et `ASL.L #1` travaille sur 32 bits, pas sur un `EXT.L`.
    def ref_action(mana: int, arg2: int) -> int:
        if arg2:                            # TST.W ($A,A5) / BEQ LAB_4C0CE
            return int(mana / 2)            # ___divs : troncature vers zero
        if mana >= 100_000:                 # CMPI.L #$186A0 / BGE
            return mana
        return mana * 2 + 500               # ASL.L #1 + ADD.L #$000001F4

    ecarts2 = []
    essais2 = [399, -250, 0, 1, 32767, 32768, 65535, 65536,
               99_999, 100_000, 100_001, 200_000, 300_000, 2_000_063]
    n2 = 0
    for code in (9, 10):                    # joueur 0 puis joueur 1
        cible = 0 if code == 9 else 1
        for mana0 in essais2:
            for arg2 in (0, 1):
                n2 += 1
                g.sim.players[cible].mana = mana0
                g.powers.do_action(0, arg2, code)
                obtenu = g.sim.players[cible].mana
                attendu = ref_action(mana0, arg2)
                if obtenu != attendu:
                    ecarts2.append((code, mana0, arg2, obtenu, attendu))
    print("do_action 9/10         : %d essais, %d ecart(s)"
          % (n2, len(ecarts2)))
    for e in ecarts2[:8]:
        print("   code=%d mana=%-9d arg2=%d obtenu=%s attendu=%s" % e)
    if ecarts2:
        return 1

    # --- 6. le curseur survit-il a draw_window ? -----------------------
    # On compose une image SANS le curseur, puis UNE AVEC, et on regarde si
    # la region du curseur a reellement change apres tout le rendu.
    g.sim.players[g.sim.player].mana = 5_000
    x, y, _ = mesure(g, 5_000)
    reell = g.move_mana
    g.move_mana = lambda: None          # type: ignore
    g.compose()
    sans = [[tuple(g.frame.get_at((px, py))[:3])
             for px in range(320)] for py in range(200)]
    g.move_mana = reell                 # type: ignore
    g.compose()
    avec = [[tuple(g.frame.get_at((px, py))[:3])
             for px in range(320)] for py in range(200)]
    zone = [(px, py) for py in range(y, min(y + 16, 200))
            for px in range(x, min(x + 16, 320))]
    changes = sum(1 for (px, py) in zone if avec[py][px] != sans[py][px])
    visibles = sum(1 for (px, py) in zone if avec[py][px] != (0, 0, 0))
    print()
    print("region du curseur      : x=%d y=%d  (%d px)" % (x, y, len(zone)))
    print("  differs avec/sans    : %d" % changes)
    print("  non noirs apres rendu: %d" % visibles)
    if changes == 0:
        print("  -> le sprite est RECOUVERT par draw_window")
        return 2
    print("  -> le curseur est visible dans l'image finale")
    return 0


if __name__ == "__main__":
    sys.exit(main())
