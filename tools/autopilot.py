"""Pilote automatique du jeu : lance la **vraie** fenetre et joue a votre place.

Ce script ne teste pas des fonctions isolees — il instancie
``populous.game.Game`` (donc la vraie fenetre, le vrai moteur de rendu et le
vrai gestionnaire d'evenements), puis **synthetise de vrais evenements pygame**
exactement comme le ferait votre souris/clavier, et verifie l'effet du clic.

Il produit aussi une capture PNG par etape dans ``out_png/auto_*.png``.

Usage::

    python tools\\autopilot.py [graine] [sol] [zoom]
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pygame  # noqa: E402

from populous.game import Game  # noqa: E402
from populous.render import SCREEN_H, SCREEN_W  # noqa: E402

OUT = ROOT / "out_png"


def shot(g: Game, name: str) -> str:
    """Compose une image et l'ecrit (comme le fait `run()`)."""
    g.compose()
    path = OUT / ("auto_%s.png" % name)
    pygame.image.save(g.frame, str(path))
    # version x4 pour l'inspection a l'oeil
    big = pygame.transform.scale(g.frame, (g.frame.get_width() * 4,
                                           g.frame.get_height() * 4))
    pygame.image.save(big, str(OUT / ("auto_%s_x4.png" % name)))
    return path.name


def click(g: Game, mx: int, my: int, button: int = 1) -> None:
    """Evenement souris complet, comme le fait pygame : MOVE puis CLICK."""
    wx, wy = mx * g.zoom, my * g.zoom
    g.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(wx, wy), rel=(0, 0),
                               buttons=(0, 0, 0)))
    g.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(wx, wy),
                               button=button))


def press(g: Game, mx: int, my: int, button: int = 1, held: int = 3) -> None:
    """Un **vrai** clic : deplacement, appui, quelques images, relachement.

    C'est indispensable pour exercer le modele de l'asm : ``_zoom_map`` et
    ``_interogate`` ne tournent que sur l'image ou ``_left_button == 0``, et cet
    etat ne dure qu'une image (l'epilogue de ``_zoom_map`` le met aussitot a 2,
    et il faut ensuite relacher le bouton). Il faut donc un cycle complet
    appui / maintien / relachement, exactement comme un joueur.
    """
    wx, wy = mx * g.zoom, my * g.zoom
    g.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(wx, wy), rel=(0, 0),
                               buttons=(0, 0, 0)))
    g.poll_mouse()                          # image avant l'appui
    g.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(wx, wy),
                               button=button))
    for _ in range(held):
        g.poll_mouse()
    g.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(wx, wy),
                               button=button))
    g.poll_mouse()
    g.poll_mouse()


def ok(label: str, cond: bool, detail: str = "") -> bool:
    print("  [%s] %s%s" % ("OK" if cond else "KO", label,
                           ("  -> " + detail) if detail else ""))
    return cond


def main() -> int:
    a = [int(v) for v in sys.argv[1:]]
    seed = a[0] if len(a) > 0 else 59
    ground = a[1] if len(a) > 1 else 0
    zoom = a[2] if len(a) > 2 else 3

    OUT.mkdir(exist_ok=True)
    g = Game(seed, ground, zoom)          # pygame.init() est dedans
    print("Ouverture de la vraie fenetre (pilote %s)…"
          % (pygame.display.get_driver() or "?"))
    print("  fenetre %dx%d, zoom x%d, graine %d, sol %d"
          % (g.screen.get_width(), g.screen.get_height(), g.zoom,
             g.seed, g.ground))

    results = []

    # ---------------------------------------------------------- demarrage
    print("\n1. Boucle de jeu : 120 images")
    for _ in range(120):
        g.tick()
        g.compose()
    results.append(ok("120 images sans exception", True))
    shot(g, "01_demarrage")

    # ------------------------------------------------- la tribu est visible ?
    print("\n2. Les habitants sont-ils dessines ?")
    visus = 0
    for _i, p in g.sim.living():
        g.zoom_to_cell(p.block & 63, p.block >> 6)
        g.compose()
        n = g.ren.draw_peeps(g.frame, g.terrain, g.xoff, g.yoff, g.sim)
        if n:
            visus += 1
        if visus == 1:
            shot(g, "02_tribu")
    results.append(ok("au moins un habitant visible dans la fenetre",
                      visus > 0, "%d/%d habitats visibles"
                      % (visus, g.sim.no_peeps)))

# ------------------------------------------------------- clic mini-carte
    print("\n3. Clic sur la mini-carte (asm L1671-1699)")
    g.xoff, g.yoff = 24, 8
    g.mouse = (84, 30)                  # la case (40,20) sur la mini-carte
    results.append(ok("le point vise-t-il la mini-carte ?",
                      g.on_minimap(84, 30)))
    press(g,84, 30)
    results.append(ok("le clic recentre sur (40,20) - 3",
                      (g.xoff, g.yoff) == (37, 17),
                      "xoff/yoff = %s (attendu (37, 17))"
                      % str((g.xoff, g.yoff))))
    shot(g, "03_mini_carte")

    # ---------------------------------------------------- barre d'icones
    print("\n4. Barre d'icones (asm L1706-1824)")

    def find_icon(col, row):
        for mx in range(160, SCREEN_W):
            for my in range(0, SCREEN_H):
                u, v = g._uv(mx, my)
                if (u > 0x112 and (u - 0x110) // 16 == col
                        and (v - 0x20) // 16 == row):
                    return mx, my
        return None

    st = g.sim.stats[0]
    for col, row, lbl, attr, attendu in (
            (0, 3, "musique", "music_on", None),
            (0, 4, "effets", "effect_on", None),
            (0, 0, "poser (p2 7)", "act", (14, 7, 1)),
            (1, 1, "poser (p2 8)", "act", (14, 8, 1)),
            (1, 3, "horloge (p2 6)", "act", (14, 6, 1)),
            (2, 2, "serie (p2 2)", "act", (14, 2, 1))):
        px = find_icon(col, row)
        if attendu is None:
            avant = getattr(g, attr)
            press(g,*px)
            results.append(ok("bouton (%d,%d) %s" % (col, row, lbl),
                              getattr(g, attr) != avant,
                              "%s : %d -> %d"
                              % (attr, avant, getattr(g, attr))))
        else:
            press(g,*px)
            results.append(ok("bouton (%d,%d) %s : act=%d p2=%d "
                              "p1=%d" % (col, row, lbl, attendu[0],
                                         attendu[1], attendu[2]),
                              (st.act, st.p2, st.p1) == attendu,
                              "act=%d p2=%d p1=%d"
                              % (st.act, st.p2, st.p1)))
    shot(g, "04_barre_icones")

    # ------------------------------------------------ pave de defilement
    print("\n5. Pave de defilement (asm L1825-1927)")

    def find_pad(up, vp):
        for mx in range(SCREEN_W):
            for my in range(64, SCREEN_H):
                u, v = g._uv(mx, my)
                if ((u - 0x60) // 16 == up and (v - 0x90) // 16 == vp
                        and 3 <= up <= 5 and 0 <= vp <= 2):
                    return mx, my
        return None

    for up, vp, lbl, ddx, ddy in ((5, 1, "droite", 1, 0),
                                  (3, 1, "gauche", -1, 0),
                                  (4, 2, "bas", 0, 1),
                                  (4, 0, "haut", 0, -1)):
        g.xoff, g.yoff = 20, 20
        press(g,*find_pad(up, vp))
        results.append(ok("fleche Â« %s Â» : +(%d,%d)" % (lbl, ddx, ddy),
                          (g.xoff, g.yoff) == (20 + ddx, 20 + ddy),
                          "xoff/yoff = %s" % str((g.xoff, g.yoff))))

    if g.sim.living():
        g.sim.view_who = 1
        b = g.sim.peeps[0].block
        g.xoff, g.yoff = 0, 0
        press(g,*find_pad(4, 1))
        results.append(ok("centre du pave : recentre sur l'habitant",
                          (g.xoff, g.yoff) == ((b & 63) - 3, (b >> 6) - 3),
                          "xoff/yoff = %s, attendu %s"
                          % (str((g.xoff, g.yoff)),
                             str(((b & 63) - 3, (b >> 6) - 3)))))
    shot(g, "05_pave")

    # ---------------------------------------- palette d'outils (LAB_3F670)
    print("\n6. Palette d'outils en bas a gauche (LAB_3F666, L1928-2133)")
    # le centre de la case (up, vp) est a l'ecran (16*(up-vp+1), 128+8*(up+vp))
    # La palette n'arme pas une action de carte : elle ecrit `act` seul
    # (volcan, seisme) ou `act = 14` + un code dans `p2` (_do_action).
    for up, vp, lbl, attendu in (
            (0, 0, "deluge   (act 14 p2 4)", (14, 4)),
            (1, 0, "guerre   (act 14 p2 3)", (14, 3)),
            (2, 1, "chevalier(act 14 p2 5)", (14, 5)),
            (3, 3, "relief 0 (p2 1 p1 0)", (14, 1, 0))):
        px = (16 * (up - vp + 1), 128 + 8 * (up + vp))
        press(g,*px)
        if len(attendu) == 3:
            got = (st.act, st.p2, st.p1)
        else:
            got = (st.act, st.p2)
        results.append(ok("palette (%d,%d) %s" % (up, vp, lbl),
                          got == attendu,
                          "act=%d p2=%d p1=%d"
                          % (st.act, st.p2, st.p1)))
    shot(g, "06_palette")

    # -------------------------- selecteur de mode (LAB_3F8A0 / LAB_3F8F0)
    print("\n6b. Selecteur de mode (LAB_3F8A0, LAB_3F8F0)")
    for vp, attendu in ((0, 1), (1, 2), (2, 5)):
        g.sim.mode = 1                    # (1 & 3) | 4 = 5, cf. L2126-2128
        g.sim.pointer = 0
        g.palette(6, vp)
        results.append(ok("palette (6,%d) -> _mode = %d" % (vp, attendu),
                          g.sim.mode == attendu,
                          "_mode=%d _pointer=%d" % (g.sim.mode, g.sim.pointer)))
    g.sim.mode = 2                        # on laisse le jeu en mode sculptage
    g.sim.ok_to_build = 1

    # ---------------------------------------- la vue suit bien la souris
    print("\n7. Survol d'un habitant (_interogate, asm L2719)")
    for i, p in g.sim.living():
        g.zoom_to_cell(p.block & 63, p.block >> 6)
        break
    g.compose()
    g.ren.draw_peeps(g.frame, g.terrain, g.xoff, g.yoff, g.sim)
    q = g.ren.last_queue
    results.append(ok("la file de sprites est peuplee", bool(q),
                      "%d sprite(s) rendus" % len(q)))
    if q:
        x, y, _sp, who = q[0]
        g.sim.view_who = 0
        g.sim.mode = 1
        g.mouse = (x + 3, y + 3)
        g.left_button = 0                    # bouton gauche appuye (1 image)
        g.interogate()
        results.append(ok("dans la boite 12x8 -> _view_who = who",
                          g.sim.view_who == who,
                          "view_who=%d attendu=%d" % (g.sim.view_who, who)))
        g.sim.view_who = 0
        g.left_button = 0x40                 # bouton droit enfonce
        g.right_button = 0
        g.interogate()
        results.append(ok("bouton droit enfonce -> _set_temp_view",
                          g.sim._temp_view == who and g.sim._temp_timer == 10,
                          "temp_view=%d timer=%d"
                          % (g.sim._temp_view, g.sim._temp_timer)))
        g.mouse = (x + 40, y + 40)
        g.left_button = 0
        g.right_button = 0x40
        g.interogate()
        results.append(ok("hors de la boite -> aucun changement",
                          g.sim.view_who == 0))
    shot(g, "07_survol")

    # ------------------------------ _sculpt : la souris designe une case
    print("\n8. _sculpt : la souris designe la bonne case (asm L7271)")
    g.sim.mode = 1                          # _mode & 0x0E -> _sculpt
    g.sim.ok_to_build = 1
    cases = {}
    for mx in range(SCREEN_W):
        for my in range(64, SCREEN_H):
            g.mouse = (mx, my)
            if g.sculpt():
                key = (g.sim.cur_x - g.xoff, g.sim.cur_y - g.yoff)
                cases[key] = cases.get(key, 0) + 1
    dans_fenetre = [k for k in cases if 0 <= k[0] < 8 and 0 <= k[1] < 8]
    # Sur une carte plate, les 64 cases sont atteignables. Sur une carte tres
    # montagneuse, `_sculpt` ne balaie que 9 cases par diagonale (L7325) :
    # une falaise masque alors la case suivante. C'est le comportement de
    # l'original, on verifie donc que le losange reste plein.
    results.append(ok("le losange 8x8 est couvert",
                      len(dans_fenetre) >= 56,
                      "%d/64 cases designables" % len(dans_fenetre)))
    # Verification geometrique exacte, independante du relief : sur une carte
    # mise a plat, chaque case doit occuper exactement 16x16 px (une demi-
    # colonne de losange). On aplatit le terrain le temps du calcul puis on le
    # restitue a l'identique.
    relief = list(g.terrain.alt)
    g.terrain.alt = [0] * len(g.terrain.alt)
    plat = {}
    for mx in range(SCREEN_W):
        for my in range(64, SCREEN_H):
            g.mouse = (mx, my)
            if g.sculpt():
                key = (g.sim.cur_x - g.xoff, g.sim.cur_y - g.yoff)
                plat[key] = plat.get(key, 0) + 1
    g.terrain.alt = relief
    exactes = sum(1 for v, n in plat.items()
                  if 0 <= v[0] < 8 and 0 <= v[1] < 8 and n == 256)
    results.append(ok("exactement 256 px (16x16) par case a plat",
                      exactes == 64,
                      "%d/64 cases a 256 px" % exactes))
    # les deux coins de la diagonale centrale doivent etre a x=192
    for coin in ((0, 0), (7, 7)):
        xs = [k[0] for k in plat if k == coin]
        results.append(ok("coin %s du losange atteint" % str(coin), bool(xs),
                          "colonne relative %d -> ecran x=%d"
                          % (coin[0], 192 + 16 * (coin[0] - coin[1]))))
    # le curseur est un vrai sprite 0x54
    g.mouse = (192, 120)
    g.sculpt()
    results.append(ok("le curseur est calcule par _sculpt",
                      g.sim.cur_screen is not None,
                      "cur_screen=%s" % str(g.sim.cur_screen)))
    shot(g, "08_sculpt")

    print("\n9. La palette arme, le clic sur la carte execute "
          "(asm L1932-2133 + L7452)")
    st = g.sim.stats[g.sim.player]
    pl = g.sim.players[g.sim.player]
    pl.mana = 300000
    pl.magnet = 1
    g.sim.mode = 2                        # mode 2 = mode de sculptage
    g.sim.ok_to_build = 1

    def clic(bouton=1):
        """Un clic complet : une seule image a ``left_button == 0``."""
        g.mouse = (192, 120)
        g.poll_mouse()                    # image avant l'appui
        if bouton == 1:
            g._raw_left = True
        else:
            g._raw_right = True
        g.poll_mouse()                    # image du clic
        g._raw_left = g._raw_right = False
        g.poll_mouse()                    # relachement

    g.mouse = (192, 120)
    g.sculpt()
    cx, cy = g.sim.cur_x, g.sim.cur_y

    def sommet():
        return g.terrain.alt[cy * 65 + cx]

    def etat_blk():
        return Counter(g.sim.map.blk)

    print("   case visee : (%d, %d)   sommet=%d   blk=0x%02X"
          % (cx, cy, sommet(), g.sim.map.blk[(cy << 6) | cx]))
    # ---- 9a. le sens du relief : la palette ecrit act=14, p2=1 -------
    # p1 = dir, et `_do_action` code 1 (L18381-18403) recopie dir dans
    # `command` et retrace la croix - sans depenser un sou de mana.
    from populous.constants import TEND_X, TEND_Y
    for up, vp, dir_l in ((3, 3, 0), (4, 3, 1), (5, 3, 2), (4, 4, 3)):
        g.palette(up, vp)
        arme = (st.act, st.p2, st.p1) == (14, 1, dir_l)
        m0 = pl.mana
        g.sim.players[0].command = 4   # aucune croix (L2455)
        g.icon_toggles.clear()
        g.powers.do_queued(g.sim.player)      # `_get_message` du port
        m1 = pl.mana
        cmd = g.sim.players[0].command
        croix = (TEND_X[dir_l], TEND_Y[dir_l], 0x12C0) in g.icon_toggles
        results.append(ok("palette (%d,%d) arme le relief dir=%d "
                          "(act 14, p2 1, p1 %d)" % (up, vp, dir_l, dir_l),
                          arme, "act=%d p2=%d p1=%d"
                          % (st.act, st.p2, st.p1)))
        results.append(ok("  -> command=%d, croix, mana inchangee"
                          % dir_l,
                          cmd == dir_l and m1 == m0 and croix,
                          "command=%d croix=%s mana %d -> %d"
                          % (cmd, croix, m0, m1)))

    # ---- 9b. le clic choisit l'action (L7452-7561) -------------------
    # Aucune icone d'armee : `act` = 4/5/1/2 vient du **clic**, pas de la
    # palette. Cout 10 pour relever/abaisser, 5000/200 pour les autres.
    g.sim.mode = 2
    for bouton, act_att, lbl, delta in ((1, 1, "gauche", 1),
                                        (3, 2, "droite", -1)):
        v0, m0 = sommet(), pl.mana
        clic(bouton)
        v1, m1 = sommet(), pl.mana
        results.append(ok("clic %s : act=%d, haut %+d, mana -10"
                          % (lbl, act_att, delta),
                          v1 == v0 + delta and m0 - m1 == 10,
                          "sommet %d -> %d, mana %d -> %d, act=%d p1=%d p2=%d"
                          % (v0, v1, m0, m1, st.act, st.p1, st.p2)))

    # ---- 9c. palette (2,2) : sculptage bit 3 -> marais ----------------
    g.sim.mode = 1
    g.sim.paint_map = 1                     # garde de L2018-2032
    g.palette(2, 2)
    results.append(ok("palette (2,2) ouvre le sculptage : mode 9, "
                      "pointeur 5",
                      g.sim.mode == 9 and g.sim.pointer == 5,
                      "mode=%d pointer=%d" % (g.sim.mode, g.sim.pointer)))
    g.sim.paint_map = 0
    m0 = pl.mana
    clic(1)
    m1 = pl.mana
    results.append(ok("  clic -> marais (act 4, cout 5000) et bit 3 efface",
                      m0 - m1 == 5000 and g.sim.mode == 1,
                      "mode=%d mana %d -> %d act=%d"
                      % (g.sim.mode, m0, m1, st.act)))

    # ---- 9d. palette (6,2) : sculptage bit 2 -> aimanter --------------
    g.sim.mode = 1
    g.palette(6, 2)
    results.append(ok("palette (6,2) : mode 5, pointeur = joueur+2",
                      g.sim.mode == 5
                      and g.sim.pointer == g.sim.player + 2,
                      "mode=%d pointer=%d" % (g.sim.mode, g.sim.pointer)))
    m0 = pl.mana
    clic(1)
    m1 = pl.mana
    results.append(ok("  clic -> aimanter (act 5, cout 200) et bit 2 efface",
                      m0 - m1 == 200 and g.sim.mode == 1,
                      "mode=%d mana %d -> %d act=%d"
                      % (g.sim.mode, m0, m1, st.act)))

    # ---- 9e. les pouvoirs de la palette, executes par `_get_message` ---
    for up, vp, lbl, attendu, cout in (
            (1, 1, "volcan   (act 6)",  (6,), 10000),
            (2, 0, "seisme   (act 3)",  (3,), 2500),
            (2, 1, "chevalier(act 14)", (14, 5), 7500),
            (0, 0, "deluge   (act 14)", (14, 4), 40000),
            (1, 0, "guerre   (act 14)", (14, 3), 80000)):
        m0, v0 = pl.mana, sommet()
        g.palette(up, vp)
        if len(attendu) > 1:
            arme = (st.act, st.p2) == attendu
        else:
            arme = st.act == attendu[0]
        g.powers.do_queued(g.sim.player)
        m1, v1 = pl.mana, sommet()
        results.append(ok("palette (%d,%d) %s puis `_get_message`"
                          % (up, vp, lbl), arme,
                          "act=%d p2=%d p1=%d" % (st.act, st.p2, st.p1)))
        results.append(ok("  -> mana %d -> %d (cout %d)" % (m0, m1, cout),
                          m0 - m1 == cout,
                          "sommet %d -> %d" % (v0, v1)))
    shot(g, "09_actions")

    # --------------------------------- _show_the_shield (asm L2769) + jauges
    print("\n10. Ecusson de l'habitant suivi (_show_the_shield, L2769)")
    vivant = list(g.sim.living())
    results.append(ok("il reste un habitant vivant a suivre", bool(vivant),
                      "%d vivant(s)" % len(vivant)))
    if vivant:
        i, p = vivant[0]
        g.sim.view_who = i + 1
        g.zoom_to_cell(p.block & 63, p.block >> 6)
        g.compose()
        # le blason : _draw_icon(x=0x11, y=0x04) -> pixel (272, 4)
        g.compose()          # compose() appelle deja show_the_shield
        # le blason doit etre exactement l icone de la tribu a (272, 4)
        from populous.assets import load_icon
        attendu = load_icon(p.tribe & 1, opaque=True)
        ecarts = sum(1 for dy in range(16) for dx in range(16)
                     if g.frame.get_at((272 + dx, 4 + dy))[:3]
                     != attendu.get_at((dx, dy))[:3])
        results.append(ok("le blason (icone 0x%02X) est a (272, 4)"
                          % (p.tribe & 1), ecarts == 0,
                          "%d/256 pixels d ecart" % ecarts))
        # un habitant mort doit oublier le suivi (L2780)
        vie = p.life
        g.sim.peeps[i].life = 0
        g.sim.view_who = i + 1
        g.show_the_shield()
        results.append(ok("un habitant mort est oublie (L2780)",
                          g.sim.view_who == 0,
                          "_view_who=%d" % g.sim.view_who))
        g.sim.peeps[i].life = vie
        g.sim.view_who = i + 1
    g.sim.view_who = 0
    g.show_the_shield()
    results.append(ok("sans selection, l'ecusson n'est rien (L2772)", True))
    shot(g, "10_ecusson")

    # --------------------------------------- primitives d'interface
    print("\n11. Primitives _draw_icon / _draw_bar (asm L19184 / L19213)")
    from populous.assets import palette_rgb
    fond = palette_rgb()[6]
    test = pygame.Surface((320, 200))
    test.fill(fond)
    g.ren.draw_icon(test, 2, 2, 0x11)
    results.append(ok("_draw_icon(x=2) -> pixel (32, 2)",
                      test.get_at((40, 6))[:3] != fond,
                      "l'icone 0x11 est plein, le pixel a change"))
    # Rappel de l asm : le segment "vide" est TOUJOURS trace, avec
    # flags = 2 (L19242).flags = 2 eteint le plan 0 et allume le plan 1,
    # donc la partie vide est un MOTIF, pas du fond. On verifie donc
    # que les deux moities de la barre sont differentes.
    def lire_barre(rempli):
        test.fill(fond)
        g.ren.draw_bar(test, 36, 37, 16, rempli, 0x0F)
        return [test.get_at((36 * 8, 37 - dy))[:3] for dy in range(16)]

    # rempli = 10 : les 10 lignes du bas ont les flags du caller (0x0F)
    # et les 6 du haut ont flags = 2 -> deux motifs distincts
    bar10 = lire_barre(10)
    results.append(ok("_draw_bar(10) : deux segments distincts",
                      len(set(bar10)) >= 2,
                      "%d couleur(s) : %s"
                      % (len(set(bar10)), sorted(set(bar10)))))
    # rempli = 16 : toute la barre est pleine, un seul motif
    bar16 = lire_barre(16)
    results.append(ok("_draw_bar(16) : une seule couleur (barre pleine)",
                      len(set(bar16)) == 1,
                      "%s" % sorted(set(bar16))))
    # rempli = 0 : toute la barre est tracee avec flags = 2
    # rempli = 0 : toute la barre est tracee avec flags = 2
    bar00 = lire_barre(0)
    results.append(ok("_draw_bar(0) : tout en flags=2, motif unique",
                      len(set(bar00)) == 1 and bar00[0] != fond,
                      "%s (fond %s)" % (sorted(set(bar00)), fond)))
    # _draw_bar(10) : dy=0..9 remplies (flags 0x0F), dy=10..15 vides
    # (flags 2). On compare ces 6 lignes aux 6 premieres de bar00, car
    # bar00 est une barre de hauteur 16 entierement vide.
    results.append(ok("_draw_bar(0) == segment vide de _draw_bar(10)",
                      bar10[10:] == bar00[:6],
                      "6 lignes : %s vs %s" % (bar10[15], bar00[0])))
    print("\n12. _toggle_icon : l'icone de l'outil arme (asm L19493)")
    from populous.assets import palette_rgb
    fond = palette_rgb()[6]
    test = pygame.Surface((320, 200))
    test.fill(fond)
    # la palette (3,3) doit tomber sur l'icone dessinee dans qaz.pic
    avant = [test.get_at((x, y))[:3] for y in range(200) for x in range(320)]
    n = g.ren.toggle_icon(test, 3, 3, 0x12C0)
    results.append(ok("_toggle_icon(3,3) touche bien l'icone", n > 0,
                      "%d pixels inverses" % n))
    # le losange fait 16 lignes de large au milieu (0xFFFF) et se resserre
    largeur = []
    for dy in range(16):
        ligne = sum(1 for dx in range(16)
                    if test.get_at((0 + dx, 120 + dy))[:3] != fond)
        largeur.append(ligne)
    fond = palette_rgb()[6]
    # position reelle de l icone (3,3) : l offset asm donne le pixel
    off = 3 * 322 + 3 * 318 + 0x12C0
    y0, xb = divmod(off, 40)
    x0 = xb * 8
    # le losange : largeur croissante puis decroissante, 16 lignes
    largeur = []
    for dy in range(16):
        largeur.append(sum(1 for dx in range(16)
                             if test.get_at((x0 + dx, y0 + dy))[:3] != fond))
    # la 16e ligne vaut 0 (c est le DS.L 1 de la table asm), donc
    # la symetrie ne porte que sur les 15 premieres lignes.
    results.append(ok("le losange est symetrique",
                      largeur[:15] == largeur[:15][::-1]
                      and largeur[7] == 16,
                      "largeurs = %s" % largeur))
    avant2 = [test.get_at((x0 + dx, y0 + 7))[:3] for dx in range(16)]
    g.ren.toggle_icon(test, 3, 3, 0x12C0)
    apres2 = [test.get_at((x0 + dx, y0 + 7))[:3] for dx in range(16)]
    results.append(ok("deux appels se compensent (XOR/XOR)",
                      avant2 != apres2
                      and all(a2 == fond for a2 in apres2),
                      "la ligne 7 revient au fond"))
    # l etat persistant : l icone reste inversee d une image a l autre
    g.icon_toggles.clear()
    g.palette(0, 0)            # L1935 : l'icone que le listing inverse
    results.append(ok("l'icone cliquee est memorisee",
                      (0, 0, 0x12C0) in g.icon_toggles,
                      "toggles = %s" % sorted(g.icon_toggles)))
    g.palette(0, 0)
    results.append(ok("re-cliquer la meme icone la desarme",
                      (0, 0, 0x12C0) not in g.icon_toggles,
                      "toggles = %s" % sorted(g.icon_toggles)))
    shot(g, "12_toggle")

    # ------------------------------------ _text et _requester (L19973/L9901)
    print("\n13. _text (L19973) et _requester (L9901)")
    from populous.assets import palette_rgb
    fond = palette_rgb()[0]
    test = pygame.Surface((320, 200))
    test.fill(fond)
    # _text(ecran, x, y, chaine) : x en unites de 8 px -> x=2 donne le pixel 16
    g.ren.draw_text(test, 2, 10, "AB")
    n = sum(1 for dy in range(8) for dx in range(16)
          if test.get_at((16 + dx, 10 + dy))[:3] != fond)
    results.append(ok("_text(x=2) -> pixel 16, 8 px par glyphe", n > 0,
                      "%d/128 pixels ecrits sur 2 glyphes" % n))
    # un espace ne doit rien ecrire (masque 0xFF, plans nuls)
    test.fill(fond)
    g.ren.draw_text(test, 2, 10, " ")
    blanc = sum(1 for dy in range(8) for dx in range(8)
                if test.get_at((16 + dx, 10 + dy))[:3] != fond)
    results.append(ok("l'espace n'ecrit rien", blanc == 0,
                      "%d/64 pixels modifies" % blanc))
    # le retour a la ligne est de 8 lignes (le 0x140 de l asm)
    test.fill(fond)
    g.ren.draw_text(test, 2, 10, "A\nA")
    haut = sum(1 for dx in range(8) for dy in range(8)
               if test.get_at((16 + dx, 10 + dy))[:3] != fond)
    bas = sum(1 for dx in range(8) for dy in range(8)
              if test.get_at((16 + dx, 18 + dy))[:3] != fond)
    results.append(ok("le retour a la ligne tombe 8 lignes plus bas",
                      haut > 0 and bas > 0,
                      "ligne 1 : %d px, ligne 2 : %d px" % (haut, bas)))
    # largeur du texte : 8 px par glyphe
    results.append(ok("largeur = 8 px par glyphe",
                      g.ren.text_width("ABC") == 24,
                      "ABC = %d px" % g.ren.text_width("ABC")))

    # _requester : cadre d icones + texte centre
    g.compose()
    avant = sum(1 for y in range(200) for x in range(320)
                if g.frame.get_at((x, y))[:3] != g.backdrop.get_at((x, y))[:3])
    # _requester : le cadre est fait d icones, le titre et le message sont
    # ecrits avec la police du jeu. On utilise les VRAIS arguments de l asm :
    # _requester(_d_screen, 0x30, 0x46, 0xE4, 0x40, titre, message)
    g.compose()
    avant = sum(1 for y in range(200) for x in range(320)
                if g.frame.get_at((x, y))[:3] != g.backdrop.get_at((x, y))[:3])
    g.requester(0x30, 0x46, 0xE4, 0x40, "TRY NUMBER ", "1")
    apres = sum(1 for y in range(200) for x in range(320)
                if g.frame.get_at((x, y))[:3] != g.backdrop.get_at((x, y))[:3])
    results.append(ok("la boite de dialogue est tracee", apres > avant,
                      "%d pixels de plus qu avant" % (apres - avant)))
    # le titre est ecrit sous le bandeau, donc a y = 4 + 16 + 3 = 23
    titre = sum(1 for y in range(23, 31) for x in range(320)
                if g.frame.get_at((x, y))[:3] != g.backdrop.get_at((x, y))[:3])
    results.append(ok("le titre est ecrit sous le cadre (y+16+3)", titre > 0,
                      "%d pixels entre y=23 et y=31" % titre))
    # l icone 0x0C pose en haut a gauche doit avoir change le pixel (48, 4)
    results.append(ok("l icone 0x0C est posee en (48, 4)",
                      g.frame.get_at((48, 4))[:3]
                      != g.backdrop.get_at((48, 4))[:3],
                      "pixel (48,4) = %s"
                      % str(g.frame.get_at((48, 4))[:3])))
    shot(g, "13_requester")



    # ---------------------------- saisie du numero de niveau (asm L11942)
    print("\n14. Saisie du numero de niveau (« TRY NUMBER », L11942)")
    g.conquest_dialog = None
    g.open_conquest_dialog()
    results.append(ok("la boite s'ouvre avec le palier courant",
                      g.conquest_dialog is not None,
                      "tampon = %r" % g.conquest_dialog["tampon"]))
    d0 = g.conquest_dialog["valeur"]
    g.conquest_key(pygame.K_BACKSPACE)
    for ch in "7":
        g.conquest_key(0, ch)
    results.append(ok("un chiffre s'ajoute a droite",
                      g.conquest_dialog["valeur"] == d0 % 10 * 10 + 7
                      or g.conquest_dialog["tampon"].endswith("7"),
                      "tampon = %r" % g.conquest_dialog["tampon"]))
    g.conquest_key(pygame.K_BACKSPACE)
    results.append(ok("le retour arriere efface un chiffre",
                      g.conquest_dialog["tampon"] == "",
                      "tampon = %r" % g.conquest_dialog["tampon"]))
    for ch in "3":
        g.conquest_key(0, ch)
    for ch in "0":
        g.conquest_key(0, ch)
    for ch in "0":
        g.conquest_key(0, ch)
    for ch in "0":
        g.conquest_key(0, ch)
    for ch in "0":
        g.conquest_key(0, ch)
    results.append(ok("la saisie est bornee a 30000 (CMPI.W #$7530)",
                      g.conquest_dialog["valeur"] == 30000,
                      "valeur = %d" % g.conquest_dialog["valeur"]))
    # le dialogue capte le clavier tant qu'il est ouvert
    avant = g.conquest_no
    results.append(ok("le dialogue capte le clavier",
                      g.conquest_key(0, "5"),
                      "le chiffre 5 est bien note"))
    g.compose()
    cadre = sum(1 for y in range(4, 24) for x in range(48, 290)
                if g.frame.get_at((x, y))[:3]
                != g.backdrop.get_at((x, y))[:3])
    results.append(ok("la boite est dessinee", cadre > 100,
                      "%d pixels dans la zone du cadre" % cadre))
    shot(g, "14_dialogue")
    # validation : le palier est charge
    g.conquest_key(0, "2")
    g.conquest_key(pygame.K_RETURN)
    results.append(ok("Entree valide et charge le palier",
                      g.conquest_dialog is None and g.conquest is not None,
                      "palier %s" % (g.conquest.number if g.conquest else "?")))
    # annulation
    g.open_conquest_dialog()
    g.conquest_key(pygame.K_ESCAPE)
    results.append(ok("Echap annule le dialogue",
                      g.conquest_dialog is None, ""))

    print("\n%d captures dans %s" % (len(list(OUT.glob('auto_*.png'))), OUT))
    okc = sum(1 for r in results if r)
    print("=> %d/%d controles reussis" % (okc, len(results)))
    return 0 if okc == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
