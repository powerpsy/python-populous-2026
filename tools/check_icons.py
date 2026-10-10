"""Controle independant de la barre d'icones et de la palette d'outils.

Ce **n'est pas** une relecture du port : les tables ci-dessous sont ecrites
directement depuis le listing tetracorp, avec le numero de ligne de chaque
ecriture, et le script compare ensuite ce que la vraie fenetre a produit.
Une divergence est un echec, pas une notice.

Usage::

    python tools/check_icons.py [graine] [sol] [zoom]
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from populous.game import Game  # noqa: E402
from populous.render import SCREEN_W  # noqa: E402

# ---------------------------------------------------------------------------
# reference, tiree ligne a ligne du listing
# ---------------------------------------------------------------------------

# _zoom_map, zone A : `u > 0x112` (L1706), col = (u-0x110)/16, row =
# (v-0x20)/16, DIVS donc troncature vers zero (L1711/L1716).
#   colonne 0 : L1718 ; ligne 0 -> L1729 act=14, L1731 p2=7, L1733 p1=d0
#                        ligne 3 -> L1744 musique ; ligne 4 -> L1744 effets
#   colonne 1 : L1784 ; ligne 1 -> L1795 p2=8, L1797 act=14
#                        ligne 3 -> L1803 act=14, L1805 p2=6
#   colonne 2 : L1809 ; ligne 2 -> L1820 p2=2, L1822 act=14
ZONE_A = [
    (0, 0, 14, "d0", 7, "L1729/L1731/L1733"),
    (1, 1, 14, None, 8, "L1795/L1797"),
    (1, 3, 14, None, 6, "L1803/L1805"),
    (2, 2, 14, None, 2, "L1820/L1822"),
]

# LAB_3F666, table de saut LAB_3FC92 (L2408-2417) indexee par `up` puis
# test sur `vp`. "xoff"/"yoff" = l'octet bas du mot (LAB_52DDF/LAB_52DE1,
# L25313-25318), None = l'octet n'est pas ecrit par cette branche.
PALETTE = [
    (0, 0, 14, None, 4, "L1935/L1942/L1944"),
    (1, 0, 14, None, 3, "L1952/L1959/L1961"),
    (1, 1, 6, "xoff", "yoff", "L1965/L1972/L1974/L1976"),
    (2, 0, 3, "xoff", "yoff", "L1982/L1989/L1991/L1993"),
    (2, 1, 14, None, 5, "L1998/L2005/L2007"),
    (3, 3, 14, 0, 1, "L2049/L2051/L2053"),
    (4, 3, 14, 1, 1, "L2060/L2062/L2064"),
    (4, 4, 14, 3, 1, "L2070/L2072/L2074"),
    (5, 3, 14, 2, 1, "L2081/L2083/L2085"),
]

# _set_mode_icons (L2526-2567) : le seul test porte sur l'octet bas de
# `_mode` (`bitfield_51645`, L24141), puis l'icone (x, y) si x >= 0.
MODE_ICONS = [(0x04, 6, 2, "L2528-2534"), (0x08, 2, 2, "L2538-2544")]

# _sculpt, une fois la case designee (L7452-7561) : le clic choisit
# l'action, la palette ne fait que choisir le **sens** du relief.
CLIC = [
    (0x08, 4, 5000, "L7454-7489"),
    (0x04, 5, 200, "L7491-7526"),
    (0x00, 1, 10, "L7527-7540"),
    (0x00, 2, 10, "L7542-7561"),      # clic droit
]

TOTAL = [0]
KO = [0]


def check(label: str, cond: bool, detail: str = "") -> None:
    TOTAL[0] += 1
    if not cond:
        KO[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "KO",
                           label, ("  -> " + detail) if detail else ""))


def press(g: Game, mx: int, my: int, button: int = 1, held: int = 3) -> None:
    """Un vrai clic : deplacement, appui, quelques images, relachement."""
    wx, wy = mx * g.zoom, my * g.zoom
    g.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(wx, wy), rel=(0, 0),
                                buttons=(0, 0, 0)))
    g.poll_mouse()
    g.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(wx, wy),
                               button=button))
    for _ in range(held):
        g.poll_mouse()
    g.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(wx, wy),
                               button=button))
    g.poll_mouse()
    g.poll_mouse()


def clique(g: Game, bouton: int = 1) -> None:
    """Clic sur la meme case, sans passer par la souris systeme."""
    g.mouse = (192, 120)
    g.poll_mouse()
    if bouton == 1:
        g._raw_left = True
    else:
        g._raw_right = True
    g.poll_mouse()
    g._raw_left = g._raw_right = False
    g.poll_mouse()


def find_icon(g: Game, col: int, row: int):
    """Un pixel de l'ecran dont la barre d'icones dit (col, row)."""
    for mx in range(160, SCREEN_W):
        for my in range(0, g.screen.get_height()):
            u, v = g._uv(mx, my)
            if (u > 0x112 and (u - 0x110) // 16 == col
                    and (v - 0x20) // 16 == row):
                return mx, my
    return None


def find_palette(g: Game, up: int, vp: int):
    """Un pixel de l'ecran dont la palette dit (up, vp)."""
    for mx in range(SCREEN_W):
        for my in range(96, g.screen.get_height()):
            u, v = g._uv(mx, my)
            if ((u - 0x60) // 16 == up and (v - 0x90) // 16 == vp):
                return mx, my
    return None


def attendu(g: Game, valeur):
    """La valeur attendue, "d0"/"xoff"/"yoff" etant resolus ici."""
    if valeur == "d0":
        return 1                      # (9,A5) = octet bas de d0, L1733
    if valeur == "xoff":
        return g.xoff & 0xFF          # LAB_52DDF = _xoff + 1
    if valeur == "yoff":
        return g.yoff & 0xFF          # LAB_52DE1 = _yoff + 1
    return valeur


def main() -> int:
    a = [int(v) for v in sys.argv[1:]]
    seed, ground, zoom = (a + [59, 0, 3])[:3]
    g = Game(seed, ground, zoom)
    print("fenetre %dx%d, zoom x%d, graine %d, sol %d"
          % (g.screen.get_width(), g.screen.get_height(), g.zoom,
             g.seed, g.ground))

    st = g.sim.stats[g.sim.player]
    pl = g.sim.players[g.sim.player]

    print("\nA. barre d'icones, zone A (L1706-1824)")
    for col, row, act, p1, p2, lignes in ZONE_A:
        px = find_icon(g, col, row)
        if px is None:
            check("icone (%d,%d) atteignable a l'ecran" % (col, row), False,
                  "aucun pixel")
            continue
        press(g, *px)
        want_p1 = "inchange" if p1 is None else str(attendu(g, p1))
        want_p2 = str(attendu(g, p2))
        check("icone (%d,%d) %s : act=%d p1=%s p2=%s"
              % (col, row, lignes, act, want_p1, want_p2),
              st.act == act and st.p2 == attendu(g, p2)
              and (p1 is None or st.p1 == attendu(g, p1)),
              "act=%d p1=%d p2=%d" % (st.act, st.p1, st.p2))
    # un clic sur la barre ne doit PAS armer d'action de carte : `act` vaut
    # 14, `p2` porte le code, et `tgt_dirty` reste faux (pas de case visee).
    check("clic sur la barre : aucune case visee",
          not g.sim.tgt_dirty, "tgt_dirty=%s" % g.sim.tgt_dirty)

    print("\nB. palette d'outils (LAB_3F666, L1928-2133)")
    for up, vp, act, p1, p2, lignes in PALETTE:
        px = find_palette(g, up, vp)
        if px is None:
            check("palette (%d,%d) atteignable a l'ecran" % (up, vp), False,
                  "aucun pixel")
            continue
        press(g, *px)
        want_p1 = "inchange" if p1 is None else str(attendu(g, p1))
        want_p2 = str(attendu(g, p2))
        check("palette (%d,%d) %s : act=%d p1=%s p2=%s"
              % (up, vp, lignes, act, want_p1, want_p2),
              st.act == act and st.p2 == attendu(g, p2)
              and (p1 is None or st.p1 == attendu(g, p1)),
              "act=%d p1=%d p2=%d" % (st.act, st.p1, st.p2))

    print("\nC. selecteur de mode (L2088-2131)")
    for vp, mode_att, pointeur_att, lignes in ((0, 1, 0, "L2098-2100/L2115"),
                                               (1, 2, 1, "L2098-2100/L2103-2112"),
                                               (2, 5, 2, "L2125-2131")):
        g.sim.mode = 1
        g.sim.pointer = 0
        g.palette(6, vp)
        check("palette (6,%d) %s : mode=%d pointeur=%d"
              % (vp, lignes, mode_att, pointeur_att),
              g.sim.mode == mode_att and g.sim.pointer == pointeur_att,
              "mode=%d pointeur=%d" % (g.sim.mode, g.sim.pointer))

    print("\nD. _set_mode_icons (L2526-2567) : rappel de l'icone active")
    for mode, icon_x, icon_y, lignes in MODE_ICONS:
        g.sim.mode = mode | 0x01        # bit 0 = outil courant
        g.icon_toggles.clear()
        g.set_mode_icons(-1, -1)
        check("mode & %02X -> icone (%d, %d) %s"
              % (mode, icon_x, icon_y, lignes),
              (icon_x, icon_y, 0x12C0) in g.icon_toggles,
              "toggles=%s" % sorted(g.icon_toggles))
    g.sim.mode = 2
    g.icon_toggles.clear()
    g.set_mode_icons(-1, -1)
    check("mode=2 -> icone (6, 1) L2547-2554",
          (6, 1, 0x12C0) in g.icon_toggles,
          "toggles=%s" % sorted(g.icon_toggles))

    print("\nE. _sculpt : le clic choisit l'action (L7452-7561)")
    pl.mana = 300000
    pl.magnet = 1
    g.sim.ok_to_build = 1
    g.mouse = (192, 120)
    g.sculpt()
    sommet0 = g.terrain.alt[g.sim.cur_y * 65 + g.sim.cur_x]
    from populous.constants import COST_KNIGHT, COST_MAGNET, COST_QUAKE
    from populous.constants import COST_RAISE, COST_SWAMP, COST_VOLCANO
    from populous.constants import COST_FLOOD, COST_WAR

    # (a) aucun bit arme, clic gauche -> relever (cout 10, +1 sommet)
    g.sim.mode = 2
    g.sim.war = 0
    v0 = g.terrain.alt[g.sim.cur_y * 65 + g.sim.cur_x]
    m0 = pl.mana
    clique(g, 1)
    check("L7531 : act=1 (relever), cout 10, sommet +1",
          pl.mana == m0 - COST_RAISE
          and g.terrain.alt[g.sim.cur_y * 65 + g.sim.cur_x] == v0 + 1,
          "sommet %d -> %d, mana %d -> %d"
          % (v0, g.terrain.alt[g.sim.cur_y * 65 + g.sim.cur_x], m0, pl.mana))

    # (b) clic droit, mode 2 -> abaisser (cout 10, -1 sommet)
    v0 = g.terrain.alt[g.sim.cur_y * 65 + g.sim.cur_x]
    m0 = pl.mana
    clique(g, 3)
    check("L7553 : act=2 (abaisser), cout 10, sommet -1",
          pl.mana == m0 - COST_RAISE
          and g.terrain.alt[g.sim.cur_y * 65 + g.sim.cur_x] == v0 - 1,
          "sommet %d -> %d, mana %d -> %d"
          % (v0, g.terrain.alt[g.sim.cur_y * 65 + g.sim.cur_x], m0, pl.mana))

    # (c) bit 3 arme par la palette (2,2) -> marais, puis bit efface
    g.sim.mode = 1
    g.sim.paint_map = 1
    g.palette(2, 2)
    arme = (g.sim.mode & 0x03) | 0x08
    g.sim.paint_map = 0
    v0, m0 = sommet0, pl.mana
    clique(g, 1)
    check("L2040 + L7454-7489 : mode=%d -> act=4 (marais, cout %d)"
          % (arme, COST_SWAMP),
          pl.mana == m0 - COST_SWAMP and not (g.sim.mode & 0x08),
          "mana %d -> %d, mode=%d" % (m0, pl.mana, g.sim.mode))

    # (d) bit 2 arme par la palette (6,2) -> aimanter, puis bit efface
    g.sim.mode = 1
    g.palette(6, 2)
    arme = (g.sim.mode & 0x03) | 0x04
    v0, m0 = sommet0, pl.mana
    clique(g, 1)
    check("L2127 + L7491-7526 : mode=%d -> act=5 (aimanter, cout %d)"
          % (arme, COST_MAGNET),
          pl.mana == m0 - COST_MAGNET and not (g.sim.mode & 0x04),
          "mana %d -> %d, mode=%d" % (m0, pl.mana, g.sim.mode))

    print("\nF. les codes de `_do_action` (p2) et leurs couts")
    g.sim.war = 0
    for up, vp, lbl, act_att, cout in (
            (1, 1, "volcan", 6, COST_VOLCANO),
            (2, 0, "seisme", 3, COST_QUAKE),
            (2, 1, "chevalier", 14, COST_KNIGHT),
            (0, 0, "deluge", 14, COST_FLOOD),
            (1, 0, "guerre", 14, COST_WAR)):
        m0 = pl.mana
        g.palette(up, vp)
        arme_ok = st.act == act_att
        g.powers.do_queued(g.sim.player)       # `_get_message` du port
        check("palette (%d,%d) act=%d -> %s, cout %d"
              % (up, vp, act_att, lbl, cout),
              arme_ok and pl.mana == m0 - cout,
              "arme=%s mana %d -> %d" % (arme_ok, m0, pl.mana))
        g.sim.war = 0

    print("\nG. le sens du relief (L2046-2085 + L18381-18403)")
    for up, vp, dir_l, lignes in ((3, 3, 0, "L2049/L2051/L2053"),
                                  (4, 3, 1, "L2060/L2062/L2064"),
                                  (5, 3, 2, "L2081/L2083/L2085"),
                                  (4, 4, 3, "L2070/L2072/L2074")):
        from populous.constants import TEND_X, TEND_Y
        g.sim.players[0].command = 4      # aucune croix
        m0 = pl.mana
        g.palette(up, vp)
        arme_ok = (st.act, st.p2, st.p1) == (14, 1, dir_l)
        g.icon_toggles.clear()
        g.powers.do_queued(g.sim.player)
        croix = (TEND_X[dir_l], TEND_Y[dir_l], 0x12C0) in g.icon_toggles
        check("palette (%d,%d) %s : dir=%d, command=%d, croix, pas de cout"
              % (up, vp, lignes, dir_l, dir_l),
              arme_ok and g.sim.players[0].command == dir_l
              and croix and pl.mana == m0,
              "command=%d croix=%s mana %d -> %d"
              % (g.sim.players[0].command, croix, m0, pl.mana))

    print("\nH. colonnes 7 et 8 de la palette (L2134-2405)")
    from populous.constants import ST_BATTLE, ST_EXPLORER, ST_VILLAGER
    sim = g.sim
    joueur = sim.player
    pl = sim.players[joueur]
    # six peeps : 1 mort, 2 villageois (tribu du joueur), 3 temoin vivant,
    # 4 en bataille avec une cible, 5 de l'autre tribu
    sim.no_peeps = 6
    for j in range(len(sim.peeps)):
        pj = sim.peeps[j]
        pj.life = 0
        pj.state = 0
        pj.tribe = 1
        pj.target = -1
        pj.block = 0
    sim.peeps[2].life = 100
    sim.peeps[2].state = ST_VILLAGER
    sim.peeps[2].tribe = joueur
    sim.peeps[2].block = (20 << 6) | 30
    sim.peeps[3].life = 10
    sim.peeps[3].block = (5 << 6) | 12
    sim.peeps[3].tribe = joueur
    sim.peeps[4].life = 50
    sim.peeps[4].state = ST_BATTLE
    sim.peeps[4].tribe = joueur
    sim.peeps[4].target = 3
    sim.peeps[4].block = (10 << 6) | 40
    sim.peeps[5].life = 80
    sim.peeps[5].state = ST_VILLAGER
    sim.peeps[5].block = (2 << 6) | 3

    # ---- H1. (7,0) suivre l'aimant -------------------------------------
    pl.magnet = 0
    pl.magnet_to = (20 << 6) | 30
    g.xoff, g.yoff, sim.view_who, sim._temp_timer = 0, 0, 0, 0
    g.palette(7, 0, 1)
    check("L2135-2224 : magnet == 0 -> centre sur magnet_to, sans _set_temp_view",
          (g.xoff, g.yoff) == (27, 17) and sim.view_who == 0
          and sim._temp_timer == 0,
          "xoff/yoff=%s view_who=%d timer=%d"
          % (str((g.xoff, g.yoff)), sim.view_who, sim._temp_timer))
    pl.magnet = 4          # `_magnet` est un index + 1
    g.xoff, g.yoff, sim.view_who, sim._temp_timer = 0, 0, 7, 0
    g.palette(7, 0, 1)
    check("L2149-2207 : magnet != 0 -> centre sur le peep et _set_temp_view",
          (g.xoff, g.yoff) == (9, 2) and sim.view_who == 4
          and sim._temp_timer == 10 and sim.old_view_who == 7,
          "xoff/yoff=%s view_who=%d ancien=%d timer=%d"
          % (str((g.xoff, g.yoff)), sim.view_who, sim.old_view_who,
             sim._temp_timer))
    g.xoff, g.yoff = 0, 0
    g.palette(7, 0, 0)
    check("L2143 : sans clic gauche, rien ne bouge",
          (g.xoff, g.yoff) == (0, 0), "xoff/yoff=%s" % str((g.xoff, g.yoff)))

    # ---- H2. (7,1) prochaine bataille ----------------------------------
    for j in (1, 3, 5):
        sim.peeps[j].state = 0
    sim.view_fight = 0
    g.xoff, g.yoff = 0, 0
    g.palette(7, 1)
    check("L2228-2290 : balaye depuis _view_fight+1, retient state & 08",
          (g.xoff, g.yoff) == (37, 7) and sim.view_fight == 4
          and sim.view_who == 5,
          "xoff/yoff=%s view_fight=%d view_who=%d"
          % (str((g.xoff, g.yoff)), sim.view_fight, sim.view_who))
    sim.peeps[4].state = 0
    g.xoff, g.yoff = 0, 0
    check("L2236-2258 : sans bataille, rien ne bouge",
          (g.xoff, g.yoff) == (0, 0) and sim.view_fight == 4,
          "xoff/yoff=%s view_fight=%d" % (str((g.xoff, g.yoff)), sim.view_fight))
    sim.peeps[4].state = ST_BATTLE

    # ---- H3. (8,0) prochain habitant -----------------------------------
    sim.view_people = 0
    g.xoff, g.yoff = 0, 0
    g.palette(8, 0, 1)
    check("L2345-2370 : clic gauche -> peep avec une cible (TST.L LAB_53022)",
          (g.xoff, g.yoff) == (37, 7) and sim.view_people == 4
          and sim.view_who == 5,
          "xoff/yoff=%s view_people=%d view_who=%d"
          % (str((g.xoff, g.yoff)), sim.view_people, sim.view_who))
    sim.view_people = 0
    g.xoff, g.yoff = 0, 0
    g.palette(8, 0, 0)
    check("L2346-2370 : clic droit -> peep villageois (state == 1)",
          (g.xoff, g.yoff) == (27, 17) and sim.view_people == 2
          and sim.view_who == 3,
          "xoff/yoff=%s view_people=%d view_who=%d"
          % (str((g.xoff, g.yoff)), sim.view_people, sim.view_who))
    sim.view_people = 0
    for j in (2, 5):
        sim.peeps[j].state = ST_EXPLORER
    g.xoff, g.yoff = 0, 0
    g.palette(8, 0, 0)
    check("L2348-2350 : sans villageois, le clic droit ne trouve rien",
          (g.xoff, g.yoff) == (0, 0) and sim.view_people == 0,
          "xoff/yoff=%s view_people=%d" % (str((g.xoff, g.yoff)), sim.view_people))
    sim.peeps[2].state = ST_VILLAGER
    sim.peeps[5].state = ST_VILLAGER
    for jj in range(len(sim.peeps)):
        sim.peeps[jj].target = -1
    sim.view_people = 0
    g.xoff, g.yoff = 0, 0
    g.palette(8, 0, 1)
    check("L2378-2379 : aucun peep avec une cible -> clic gauche a vide",
          (g.xoff, g.yoff) == (0, 0) and sim.view_people == 0,
          "xoff/yoff=%s view_people=%d" % (str((g.xoff, g.yoff)),
                                              sim.view_people))
    sim.peeps[4].target = 3

    # ---- H4. les trois icones sont bien inversees -----------------------
    g.icon_toggles.clear()
    g.palette(7, 0, 1)
    g.palette(7, 1, 0)
    g.palette(8, 0, 1)
    check("L2137/L2230/L2300 : les trois icones (7,0)/(7,1)/(8,0)",
          sorted([k for k in g.icon_toggles if k[2] == 0x12C0])
          == [(7, 0, 0x12C0), (7, 1, 0x12C0), (8, 0, 0x12C0)],
          "toggles=%s" % sorted(g.icon_toggles))

    print("\n%d controles, %d echec(s)" % (TOTAL[0], KO[0]))
    return 1 if KO[0] else 0


if __name__ == "__main__":
    sys.exit(main())
