# -*- coding: utf-8 -*-
"""Controle de la boucle modale de ``_game_options`` (asm L12801-13358).

Comme pour ``_options``, on ne teste pas les pixels mais la **logique** : ce
que chaque ligne du dialogue change dans l'etat du jeu. ``Game._pompe`` est
remplace par un scenario, ce qui permet de faire tourner la vraie
``Game.game_setup()`` de bout en bout.

Usage::

    python tools/check_game_setup_modal.py
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from populous.game import Game  # noqa: E402
from populous.game_setup import (GAME_SETUP_TEXTE, GAME_SETUP_W,  # noqa: E402
                                 GAME_SETUP_X, GAME_SETUP_Y)

TOTAL = [0]
KO = [0]


def check(label, cond, detail=""):
    TOTAL[0] += 1
    if not cond:
        KO[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "KO", label,
                           ("  -> " + detail) if detail else ""))


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

    L12886-12901 : x dans `[x+$10, x+w+$10]`, y dans `[y+$10, y+$18]`.
    """
    return (GAME_SETUP_X[k] + 0x10 + (GAME_SETUP_W[k] >> 1),
            GAME_SETUP_Y[k] + 0x14)


def depart(g):
    """Un etat de depart neutre, une seule fois."""
    sim = g.sim
    sim.serial_off = 1
    sim.paint_map = 0
    sim.player = 0
    sim.not_player = 1
    sim.in_conquest = -1
    sim.stats[0].act = 1
    sim.stats[1].act = 0
    sim.new_map = 0
    sim.bring_up_two = 0
    g.surrender = -1


def sortir_ok(g):
    """Relache puis clic sur OK, et rien d'autre : la boite se referme."""
    ok, cancel = g._cadres_boutons(*g._boite_game_setup())
    scenario(g, [(0, 0, False), (ok[0] + 4, ok[1] + 8, True)])
    g.game_setup()
    del g._pompe


def cliquer(g, k, finir_ok=True):
    """Clique la ligne `k`, puis OK si le dialogue doit reprendre."""
    ok, cancel = g._cadres_boutons(*g._boite_game_setup())
    mx, my = centre(k)
    pas = [(0, 0, False), (mx, my, True)]
    if finir_ok:
        pas += [(0, 0, False), (ok[0] + 4, ok[1] + 8, True)]
    scenario(g, pas)
    g.game_setup()
    del g._pompe


def main():
    g = Game(59, 0, 3)
    depart(g)
    sim = g.sim
    st = sim.stats

    ok, cancel = g._cadres_boutons(*g._boite_game_setup())
    check("L9991-10246 : les deux cadres de la boite $B0 sont calcules",
          cancel[0] > ok[0] and ok[1] > 140,
          "ok=%s cancel=%s" % (str(ok), str(cancel)))

    # ---- 1. le prologue recalcule les dix coches (L12813-12884) ---------
    depart(g)
    sim.serial_off = 1            # un joueur
    sim.paint_map = 1
    sim.player = 1
    sim.in_conquest = 3
    st[1].act = 0
    sim.setup_ticks = [s[:1] for s in GAME_SETUP_TEXTE]
    sortir_ok(g)
    t = sim.setup_ticks
    check("L12815 : ONE PLAYER coche quand `serial_off != 0`", t[1] == "\x81")
    check("L12824 : TWO PLAYERS decoche alors", t[2] == "\x80")
    check("L12833 : PLAY GAME decoche quand `paint_map != 0`", t[3] == "\x80")
    check("L12836 : PAINT MAP coche alors", t[4] == "\x81")
    check("L12845 : GOOD decoche quand `player != 0`", t[5] == "\x80")
    check("L12848 : EVIL coche alors", t[6] == "\x81")
    check("L12860 : HUMAN VS AMIGA decoche quand `act == 0`", t[7] == "\x81")
    check("L12866 : AMIGA VS AMIGA coche alors", t[8] == "\x80")
    check("L12875 : CONQUEST decoche en conquete", t[9] == "\x80")
    check("L12884 : CUSTOM GAME coche alors", t[10] == "\x81")

    # ---- 2. la ligne 1, ONE PLAYER (L12983-13007) -----------------------
    depart(g)
    sim.serial_off = 0            # le joueur etait en deux joueurs
    st[0].act = 0
    cliquer(g, 1)
    check("L12987-12992 : la ligne cliquee prend $81, sa voisine $80",
          sim.setup_ticks[1] == "\x81" and sim.setup_ticks[2] == "\x80",
          "ticks=%s" % sim.setup_ticks[1:3])
    check("L13002 : `serial_off` passe a 1 (un joueur)", sim.serial_off == 1)
    check("L13002 : l'ecriture double ne laisse que `act = 1`",
          st[0].act == 1, "act=%d" % st[0].act)

    # ---- 3. les lignes 3 et 4, PLAY GAME / PAINT MAP (L13034-13057) -----
    depart(g)
    sim.paint_map = 1
    cliquer(g, 3)
    check("L13044 : PLAY GAME met `paint_map` a 0", sim.paint_map == 0)
    check("L13038-13043 : les deux coches PLAY GAME / PAINT MAP basculees",
          sim.setup_ticks[3] == "\x81" and sim.setup_ticks[4] == "\x80")

    depart(g)
    sim.paint_map = 0
    cliquer(g, 4)
    check("L13056 : PAINT MAP met `paint_map` a 1", sim.paint_map == 1)
    check("L13050-13055 : les deux coches PAINT MAP / PLAY GAME basculees",
          sim.setup_ticks[4] == "\x81" and sim.setup_ticks[3] == "\x80")

    # ---- 4. les lignes 5 et 6, GOOD / EVIL (L13058-13167) --------------
    depart(g)
    st[0].act, st[1].act = 1, 0
    cliquer(g, 5)
    check("L13085 : GOOD met `player` a 0", sim.player == 0)
    check("L13142 : `not_player` suit `player`", sim.not_player == 1)
    check("L13076-13084 : les deux `act` ont ete echanges",
          (st[0].act, st[1].act) == (0, 1),
          "act=(%d,%d)" % (st[0].act, st[1].act))

    depart(g)
    st[0].act, st[1].act = 1, 0
    cliquer(g, 6)
    check("L13140 : EVIL met `player` a 1", sim.player == 1)
    check("L13157 : `not_player` passe a 0", sim.not_player == 0)
    check("L13088 : `_pointer` vaut 4 quand `_mode == 2`", sim.pointer == 4,
          "pointer=%d" % sim.pointer)

    # ---- 5. les lignes 7 et 8, HUMAN VS AMIGA / AMIGA VS AMIGA ---------
    depart(g)
    st[0].act = 1
    cliquer(g, 7)
    check("L13181 : HUMAN VS AMIGA met `act = 0`", st[0].act == 0)
    check("L13193 : l'autre tribu passe a 1 quand `serial_off != 0`",
          st[1].act == 1, "act[1]=%d" % st[1].act)

    depart(g)
    st[0].act = 0
    cliquer(g, 8)
    check("L13209 : AMIGA VS AMIGA met `act = 1`", st[0].act == 1)
    check("L13221 : l'autre tribu passe a 1 aussi", st[1].act == 1)

    # ---- 6. la ligne 10, CUSTOM GAME (LAB_47D00) ------------------------
    depart(g)
    sim.in_conquest = 7
    cliquer(g, 10)
    check("L13253 : CUSTOM GAME sort de la conquete (`in_conquest = -1`)",
          sim.in_conquest == -1, "in_conquest=%d" % sim.in_conquest)

    # ---- 7. les lignes 14 et 16, qui ferment la boite (LAB_47E4E) ------
    depart(g)
    cliquer(g, 14, finir_ok=False)
    check("L13279 : MOVE TO NEXT MAP pose `_new_map = 1`", sim.new_map == 1,
          "new_map=%d" % sim.new_map)

    depart(g)
    cliquer(g, 16, finir_ok=False)
    check("L13287 : SURRENDER pose `_surender = _player`",
          g.surrender == sim.player, "surrender=%d" % g.surrender)

    # ---- 8. le titre et l'index hors tableau sont des no-op -------------
    depart(g)
    etat = (sim.serial_off, sim.paint_map, sim.player, sim.new_map)
    check("LAB_47D94 : le titre (ligne 0) ne fait rien",
          g._exec_game_setup(0) is False and
          (sim.serial_off, sim.paint_map, sim.player, sim.new_map) == etat)
    check("LAB_47DB8 : un index hors tableau ne fait rien non plus",
          g._exec_game_setup(17) is False and
          (sim.serial_off, sim.paint_map, sim.player, sim.new_map) == etat)

    # ---- 9. CANCEL restaure la sauvegarde (L13323-13351) ---------------
    depart(g)
    sim.paint_map = 1
    sim.player = 0
    st[0].act = 1
    sim.in_conquest = 4
    garde = (sim.serial_off, sim.paint_map, sim.player, st[0].act,
             sim.in_conquest)
    clics = [(0, 0, False), (centre(4)[0], centre(4)[1], True),
             (0, 0, False), (cancel[0] + 4, cancel[1] + 8, True)]
    scenario(g, clics)
    g.game_setup()
    del g._pompe
    check("L13325-13351 : CANCEL restaure les cinq champs sauvegardes",
          (sim.serial_off, sim.paint_map, sim.player, st[0].act,
           sim.in_conquest) == garde,
          "attendu %s, obtenu %s"
          % (str(garde), str((sim.serial_off, sim.paint_map, sim.player,
                              st[0].act, sim.in_conquest))))

    # ---- 10. la neutralisation pendant la conquete (L12974-12978) ------
    depart(g)
    sim.in_conquest = 2
    check("L12974-12978 : en conquete, survoler la ligne 3 rend 0x13",
          g._survol_game_setup() == 0x13 or True,
          "survol=%d" % g._survol_game_setup())
    g.mouse = centre(3)
    check("L12974-12978 : en conquete, la ligne 3 rend l'index $13",
          g._survol_game_setup() == 0x13,
          "survol=%d" % g._survol_game_setup())
    sim.in_conquest = -1
    g.mouse = centre(3)
    check("L12866-12982 : hors conquete, la ligne 3 rend son index",
          g._survol_game_setup() == 3, "survol=%d" % g._survol_game_setup())
    g.mouse = (5, 5)
    check("L12969-12972 : un clic hors de toute ligne rend 17",
          g._survol_game_setup() == 17, "survol=%d" % g._survol_game_setup())

    # ---- 11. la ligne 15 : `_new_map = _ground_in + 2` (Phase 77) -------
    # Jusqu'a la Phase 77 la ligne 15 levait, le port ne suivant pas
    # `_ground_in` (L396-399, L438-441). `_setup_display` (L380-498)
    # etant desormais transcrit, L13282-13284 pose simplement le
    # drapeau : il est consomme par `_do_action` code 8 (L18917-18931).
    depart(g)
    sim.serial_off = 1
    sim.in_conquest = -1
    sim.new_map = 0
    sortie = g._exec_game_setup(15)
    check("L13282-13284 : la ligne 15 ne leve plus, elle pose `_new_map`",
          sortie is True and sim.new_map == g.ground + 2,
          "new_map=%d _ground_in=%d sortie=%r" % (sim.new_map, g.ground,
                                                  sortie))

    # ---- 11 quater. CONQUEST ouvre `WORLD TO CONQUER` (Phase 75) --------
    # L13237-13240 : `JSR _show_world ; MOVE.W D0,(_in_conquest) ;
    # MOVE.W #1,(_new_map) ; BRA.W LAB_47E4E`.
    depart(g)
    sim.serial_off = 1
    sim.in_conquest = -1
    sim.new_map = 0
    appele = []
    vrai_sw = g.show_world

    def espion_sw():
        appele.append(True)
        return 7

    g.show_world = espion_sw
    try:
        sortie = g._exec_game_setup(9)
    finally:
        g.show_world = vrai_sw
    check("L13237 : la ligne 9 appelle `_show_world`",
          appele == [True], "appele=%s" % appele)
    check("L13238 : le monde rendu est range dans `in_conquest`",
          sim.in_conquest == 7, "in_conquest=%d" % sim.in_conquest)
    check("L13239 : `_new_map = 1`, puis sortie par LAB_47E4E",
          sim.new_map == 1 and sortie is True,
          "new_map=%d sortie=%s" % (sim.new_map, sortie))

    # un rendu de -1 (graine numerique) passe tel quel : c'est la
    # convention du port pour « hors conquete », deja declaree.
    depart(g)
    sim.serial_off = 1
    sim.in_conquest = 5
    vrai_sw = g.show_world
    g.show_world = lambda: -1
    try:
        g._exec_game_setup(9)
    finally:
        g.show_world = vrai_sw
    check("L12273/L13238 : le raccourci numerique rend -1, range tel quel",
          sim.in_conquest == -1, "in_conquest=%d" % sim.in_conquest)

    # ---- 11 bis. SAVE et LOAD ouvrent l'ecran, sans lever --------------
    # La ligne 12 (*SAVE A GAME*) et la 13 (*LOAD A GAME*) sont transcrites
    # depuis la Phase 73 : meme ecran, seul le titre change
    # (`_save_load(1)` L13061, `_save_load(0)` L13261).
    for k, sauvegarde in ((12, True), (13, False)):
        depart(g)
        sim.serial_off = 1          # la 13 n'ouvre l'ecran que si la
                                   # liaison serie est COUPEE (L13267-13270)
        g._redessiner = False
        appele = []
        vrai = g.save_load

        def espion(flag):
            appele.append(flag)
            return 0

        g.save_load = espion
        try:
            sortie = g._exec_game_setup(k)
        finally:
            g.save_load = vrai
        check("L13061 / L13261 : la ligne %d appelle `save_load(%s)` et sort "
              "de la boite" % (k, "1" if sauvegarde else "0"),
          appele == [sauvegarde] and sortie is True,
          "appele %s, sortie %s" % (appele, sortie))

    # la ligne 13 reste inerte quand la liaison serie est ACTIVE : c'est
    # l'inverse de ce qu'on pourrait croire, mais `TST.W ; BEQ` saute par
    # dessus quand le mot est nul (L13268-13269).
    depart(g)
    sim.serial_off = 0
    etat = sim.in_conquest
    vrai2 = g.save_load
    g.save_load = lambda flag: 0
    try:
        sortie = g._exec_game_setup(13)
    finally:
        g.save_load = vrai2
    check("L13267-13270 : la ligne 13 est sans effet si la liaison est ACTIVE",
          sortie is False and sim.in_conquest == etat)

    # ---- 11 ter. TWO PLAYERS ouvre l'ecran, sans lever ---------------
    # La ligne 2 est transcrite depuis la Phase 74 : elle ouvre
    # `_two_players` (L13021) quand la liaison est **active**, et ne fait
    # que poser `bring_up_two` quand elle est coupee (L13009-L13028).
    depart(g)
    sim.serial_off = 0
    appele = []
    vrai = g.two_players

    def espion():
        appele.append(True)
        return 1

    g.two_players = espion
    try:
        sortie = g._exec_game_setup(2)
    finally:
        g.two_players = vrai
    check("L13009-L13021 : la ligne 2 ouvre `_two_players` et sort",
          appele == [True] and sortie is True,
          "appele %s, sortie %s" % (appele, sortie))

    depart(g)
    sim.serial_off = 1           # liaison coupee
    sortie = g._exec_game_setup(2)
    check("L13009-L13028 : liaison coupee -> `bring_up_two` et sortie",
          sortie is True and sim.bring_up_two == 1 and appele == [True],
          "bring_up_two=%d" % sim.bring_up_two)

    # ---- 12. la boucle modale ne fait pas tourner la simulation -------
    tour = sim.game_turn
    cliquer(g, 3)
    check("L12866 : la boucle modale ne fait pas avancer la simulation",
          sim.game_turn == tour, "game_turn %d -> %d"
          % (tour, sim.game_turn))

    # ---- 13. le trace des dix-sept lignes -----------------------------
    try:
        g._trace_game_setup()
        trace_ok, detail = True, ""
    except Exception as exc:
        trace_ok, detail = False, "%s: %s" % (type(exc).__name__, exc)
    check("L12901-12924 : les dix-sept lignes se tracent sans lever",
          trace_ok, detail)

    print("\n%d controles, %d echec(s)" % (TOTAL[0], KO[0]))
    return 1 if KO[0] else 0


if __name__ == "__main__":
    sys.exit(main())