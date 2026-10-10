"""Etat du jeu en l'etat : vraies images (donc vrais tours), puis un tour de
partie complet a la souris. Corrige le premie jet, qui n'appelait que
`poll_mouse()` : sans `image()` il n'y a pas de tour, donc pas de
`ok_to_build`, donc pas de clic sur la carte."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from populous.game import Game  # noqa: E402


def icone(g, col, row):
    for mx in range(160, g.screen.get_width()):
        for my in range(0, g.screen.get_height()):
            u, v = g._uv(mx, my)
            if (u > 0x112 and (u - 0x110) // 16 == col
                    and (v - 0x20) // 16 == row):
                return mx, my
    return None


def pave(g, up, vp):
    for mx in range(g.screen.get_width()):
        for my in range(96, g.screen.get_height()):
            u, v = g._uv(mx, my)
            if ((u - 0x60) // 16 == up and (v - 0x90) // 16 == vp):
                return mx, my
    return None


def clic(g, mx, my, bouton=1, n=3):
    g.mouse = (mx, my)
    g.poll_mouse()
    if bouton == 1:
        g._raw_left = True
    else:
        g._raw_right = True
    for _ in range(n):
        g.poll_mouse()
    g._raw_left = g._raw_right = False
    g.poll_mouse()
    g.poll_mouse()


def main():
    g = Game(59, 0, 3)
    sim = g.sim
    pl = sim.players[sim.player]
    print("fenetre %dx%d zoom x%d graine %d sol %d   mana=%d  mode=%d"
          % (g.screen.get_width(), g.screen.get_height(), g.zoom,
             g.seed, g.ground, pl.mana, sim.mode))

    # ---- 1. le jeu tourne tout seul -------------------------------------
    for i in range(300):
        g.image()
        if i in (0, 50, 149, 299):
            print("  image %3d : tour=%3d  vivants=%2d  villes=%s  mana=%s"
                  % (i, sim.game_turn, sum(1 for q in sim.peeps if q.life > 0),
                     [p.town_count for p in sim.players],
                     [p.mana for p in sim.players]))
    print("  ok_to_build=%d" % sim.ok_to_build)

    # ---- 2. tour de partie a la souris -----------------------------------
    pl.mana = 500000
    print("\n--- partie manuelle (mana=%d) ---" % pl.mana)

    # (a) mini-carte
    px = (32, 40)          # u,v < 0x40 -> mini-carte
    clic(g, *px)
    print("mini-carte (%d,%d)      : xoff/yoff -> %s" % (px[0], px[1],
                                                         (g.xoff, g.yoff)))

    # (b) pave de defilement
    px = pave(g, 5, 1)
    x0, y0 = g.xoff, g.yoff
    clic(g, *px)
    print("pave fleche droite     : xoff/yoff -> %s (etait %s)"
          % ((g.xoff, g.yoff), (x0, y0)))

    # (c) palette : sens du relief
    g.palette(3, 3)
    st = sim.stats[sim.player]
    print("palette (3,3)          : act=%d p1=%d p2=%d"
          % (st.act, st.p1, st.p2))
    g.powers.do_queued(sim.player)
    print("                        -> command=%d  mana=%d (aucun cout)"
          % (sim.players[0].command, pl.mana))

    # (d) sur la carte : relever
    g.mouse = (192, 120)
    g.sculpt()
    cx, cy = sim.cur_x, sim.cur_y
    sommet = g.terrain.alt[cy * 65 + cx]
    mana = pl.mana
    clic(g, 192, 120)
    print("clic carte (%d,%d)      : sommet %d -> %d, mana %d -> %d, act=%d"
          % (cx, cy, sommet, g.terrain.alt[cy * 65 + cx], mana, pl.mana,
             st.act))

    # (e) clic droit : abaisser
    sommet = g.terrain.alt[cy * 65 + cx]
    mana = pl.mana
    clic(g, 192, 120, bouton=3)
    print("clic droit carte       : sommet %d -> %d, mana %d -> %d"
          % (sommet, g.terrain.alt[cy * 65 + cx], mana, pl.mana))

    # (f) colonne 7 : suivre l'aimant
    g.palette(7, 0, 1)
    print("palette (7,0)          : xoff/yoff -> %s  view_who=%d"
          % ((g.xoff, g.yoff), sim.view_who))

    # (g) barre d'icones
    m0, e0 = g.music_on, g.effect_on
    clic(g, *icone(g, 0, 3))
    clic(g, *icone(g, 0, 4))
    print("barre musique/effets   : %d->%d  %d->%d"
          % (m0, g.music_on, e0, g.effect_on))

    # (h) barre d'icones : les trois codes non transcrits
    for col, row in ((0, 0), (1, 1), (2, 2)):
        clic(g, *icone(g, col, row))
        lever = None
        try:
            g.powers.do_queued(sim.player)
            lever = "aucune exception !"
        except NotImplementedError as exc:
            lever = str(exc)
        print("barre (%d,%d)           : %s" % (col, row, lever))

    # ---- 3. on rend la main au jeu --------------------------------------
    for _ in range(300):
        g.image()
    print("\napres 600 tours : tour=%d vivants=%d villes=%s mana=%s"
          % (sim.game_turn, sum(1 for q in sim.peeps if q.life > 0),
             [p.town_count for p in sim.players],
             [p.mana for p in sim.players]))
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
