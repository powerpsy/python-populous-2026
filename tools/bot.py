#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Joueur virtuel : un programme qui joue a Populous et essaie de gagner.

Deux modes, parce qu'un bot qui bloque ne dit pas **ou** :

* **par defaut**, le bot conduit la tribu 0 par la couche d'entree reelle —
  souris -> ``handle`` -> ``poll_mouse`` -> ``sculpt``/``zoom_map`` ->
  ``palette`` -> ``_do_actions`` -> ``powers.do_queued``. L'IA du listing
  conduit deja la tribu 1 (``stats[1].can_build = 1``, ecrit par
  ``_settle_peoples`` game.py L358-360) : c'est elle qui l'emporte toujours
  sans intervention humaine (voir ``tools/check_equilibre.py``) ;
* ``--reference`` : les **deux** tribus passent sous l'IA du listing
  (``stats[0].can_build = 1``). C'est la ligne de base.

Le bot n'agit que par la souris : aucun ``do_raise_point`` ni ``palette``
appele en direct. Un blocage releve donc soit de l'interface, soit de la
simulation — et la comparaison des deux modes tranche.

.. code-block:: none

    python tools\\bot.py [graine] [sol] [zoom] [--reference]
                         [--tours N] [--pas N] [--rendu]

Sortie : une ligne d'etat periodique, puis le bilan. Code retour 0 si le
bot **gagne**, 1 s'il est bloque, 2 en cas d'erreur.
"""

import argparse
import os
import sys
import time

# `--visible` se lit avant argparse, comme `--intro` dans game.py (L4328) :
# le driver `dummy` est pose au chargement du module, donc trop tard sinon.
# Sans cette option le bot tourne en tete, ce qui est ce qu'on veut pour une
# mesure, et exactement ce qu'on ne veut pas pour regarder l'IA jouer.
if "--visible" not in sys.argv:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame

from populous.game import Game
from populous.constants import (BLK_FLAT, BLK_RUINS, BLK_TRIBE0, BLK_TRIBE1)


# --------------------------------------------------------------- couche entree
def press(g: Game, mx: int, my: int, button: int = 1, held: int = 3) -> None:
    """Un **vrai** clic : deplacement, appui, quelques images, relachement.

    Repris a l'identique de ``tools/autopilot.py`` (L52-72). Le cycle est
    indispensable : ``_left_button == 0`` ne dure qu'une image — l'epilogue
    de ``_zoom_map`` le remmet aussitot a 2 — et il faut ensuite relacher
    pour pouvoir re-cliquer (anti-rebond, L2445-2450).
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


def point_uv(u: int, v: int) -> tuple[int, int]:
    """``u``/``v`` -> coordonnees souris. Inverse exact de ``_uv`` (L1743) :

        mousex = u - v + 0x40        mousey = (u + v) >> 1
    """
    return u - v + 0x40, (u + v) >> 1


def point_palette(g: Game, up: int, vp: int) -> tuple[int, int]:
    """Le point d'ecran du centre de la case ``(up, vp)`` de la palette.

    Formule donnee par le port elle-meme (game.py L2061-2062) :

        mx = 16*(up - vp + 1)        my = 128 + 8*(up + vp)

    Verifiee par ``_uv`` : ``up = (u - 0x60) // 16``, ``vp = (v - 0x90) // 16``
    quand ``v >= 0x92`` et ``u <= 0x112`` (sinon la barre ou la mini-carte
    captent le clic, zoom_map L1971-1974).
    """
    return 16 * (up - vp + 1), 128 + 8 * (up + vp)


def mini_carte(g: Game, cx: int, cy: int) -> bool:
    """Clic sur la mini-carte pour amener la vue sur ``(cx, cy)``.

    ``zoom_map`` : ``0 <= u < 0x40`` -> ``xoff = clamp(u - 3)`` (L1972).
    Pour un centre en ``(cx, cy)`` il faut donc ``u = cx``, ``v = cy``.

    Le succes se juge au fait que la case **soit en vue**, pas a l'egalite
    exacte de la fenetre : l'inversion de ``_uv`` (``mx = u - v + 0x40`` puis
    ``u = (mx>>1) + my - 0x20``) perd un bit quand ``u + v`` est impair, ce
    qui laisse la vue decalee d'une case sans jamais laisser la cible hors
    fenetre. Exiger l'egalite donnait 100 faux echecs pour 100 clics valides.
    """
    mx, my = point_uv(cx, cy)
    if not g.on_minimap(mx, my):
        return False
    press(g, mx, my)
    return g.xoff <= cx < g.xoff + 8 and g.yoff <= cy < g.yoff + 8


def viser(g: Game, cx: int, cy: int, pas: int = 2) -> tuple[int, int] | None:
    """Position souris qui designe la case ``(cx, cy)`` a ``_sculpt``.

    On ne recalcule pas la geometrie isometrique : on balaye l'ecran et on
    **laisse** ``_sculpt`` repondre, ce qui exerce pour de vrai la boucle de
    balayage (L7357-7392). Les deux boutons sont bloques en *relache* sinon
    chaque case trouvee declencherait ``_on_cell`` au passage.
    """
    g.left_button, g.right_button = 2, 2
    for my in range(0, 200, pas):
        for mx in range(0, 320, pas):
            g.mouse = (mx, my)
            if g.sculpt() and g.sim.cur_x == cx and g.sim.cur_y == cy:
                return (mx, my)
    return None


# ------------------------------------------------------------------- l'agent
class Bot:
    """La strategie. Trois temps, chacun signale quand il bloque."""

    # seuils de mana du listing : 5000 pour le marais (L15116 / L24296)
    SEUIL_MANA = 0x1388

    def __init__(self, g: Game):
        self.g = g
        self.stats = {}
        self.dernier_gain_tour = 0
        self.dernier_gain_pop = None
        self.actions = 0
        self.echecs = []

    # ------------------------------------------------------------- observation
    def pop(self, t: int) -> int:
        return self.g.sim.population(t)

    def ennemis(self) -> list[tuple[int, int]]:
        """Les cases (x, y) de la tribu adverse, groupees par densite."""
        g = self.g
        adv = g.sim.not_player
        cases: dict[int, int] = {}
        for _, p in g.sim.living():
            if p.tribe == adv:
                cases[p.block] = cases.get(p.block, 0) + 1
        # la case qui porte le plus d'ennemis ; a egalite, la plus centree
        if not cases:
            return []
        best = max(cases.values())
        return [(b & 63, b >> 6) for b, n in sorted(cases.items())
                if n == best]

    # ---------------------------------------------------------------- actions
    def puissance(self, up: int, vp: int, verif=None) -> bool:
        """Clic sur la palette — la voie normale d'un joueur.

        ``verif`` dit **ce que la case ecrit**, et c'est essentiel : la
        majorite des entrees pose ``act``/``p1``/``p2``, mais ``(2, 2)`` n'ecrit
        QUE ``mode |= 0x08`` et ``pointer`` (game.py L2137-2145). Sans ce
        critere on declare un echec alors que l'arme est bien levee — c'est le
        defaut que le premier jet du bot avait.
        """
        g = self.g
        mx, my = point_palette(g, up, vp)
        if not (0 <= mx < 320 and 0 <= my < 200):
            self.echecs.append("palette (%d,%d) hors ecran : (%d,%d)"
                               % (up, vp, mx, my))
            return False
        if verif is None:
            st0 = g.sim.stats[g.sim.player]
            before = (st0.act, st0.p1, st0.p2)

            def verif():
                st = g.sim.stats[g.sim.player]
                return (st.act, st.p1, st.p2) != before
        press(g, mx, my)
        if not verif():
            self.echecs.append("palette (%d,%d) sans effet" % (up, vp))
            return False
        self.actions += 1
        return True

    def cible_marais(self) -> tuple[int, int] | None:
        """La ou un marais a une chance de **tombre** : ``(x, y)`` vide.

        `_do_swamp` ne convertit que les cases de `blk` dans
        ``{0x0F, 0x1F, 0x20, 0x42}`` **et** `who == 0` (listing L8364-8378,
        port powers.py L254-262). Viser la case d'un habitant ou d'un
        batiment en place est donc inutile : le mana part et rien ne se
        pose — c'est ce que le premier jet du bot faisait, et il a fallu le
        mesurer pour s'en apercevoir.

        Le tirage est aleatoire dans un carre 7x7, donc on retient la
        position qui en **contient le plus**, la plus proche de l'ennemi.
        """
        g = self.g
        ok = (BLK_FLAT, BLK_TRIBE0, BLK_TRIBE1, BLK_RUINS)

        def libre(x: int, y: int) -> bool:
            if not (0 <= x < 0x40 and 0 <= y < 0x40):
                return False
            b = (y << 6) | x
            return g.sim.map.blk[b] in ok and g.sim.map.who[b] == 0

        # Tous les amas d'ennemis, pas seulement le plus dense : un groupe
        # reduit a une ile de roches ne donne aucune case convertible, un
        # autre en donne. `best[0][0] >= 20` arrete des que la terre suffit.
        best = None
        for _, p in g.sim.living():
            if p.tribe != g.sim.not_player:
                continue
            bx, by = p.block & 63, p.block >> 6
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    x, y = bx + dx, by + dy
                    n = 0
                    for j in range(-3, 4):
                        for i in range(-3, 4):
                            n += libre(x + i, y + j)
                    cle = (n, -abs(dx) - abs(dy))
                    if best is None or cle > best[0]:
                        best = (cle, (x, y))
            if best is not None and best[0][0] >= 20:
                break
        if best is None or best[0][0] == 0:
            return None
        return best[1]

    def frapper(self, cx: int, cy: int) -> bool:
        """Arme le marais puis vise ``(cx, cy)`` : ``palette(2,2)`` + clic.

        `palette(2,2)` pose ``mode |= 0x08`` (game.py L2144) si
        ``_may_paint()`` (mana > 5000 **et** bit 4 du ``power_mask``,
        L3690-3702). Le clic suivant tombe alors dans la branche marais de
        ``_on_cell`` (L1916-1921, ``ACT_SWAMP`` en ``(x-1, y-1)``).
        """
        g = self.g
        if not g._may_paint():
            self.echecs.append("marais refuse : mana=%d < %d ou sans bit 4"
                               % (g.sim.players[g.sim.player].mana,
                                  self.SEUIL_MANA))
            return False
        if not self.puissance(2, 2, verif=lambda: bool(g.sim.mode & 0x08)):
            return False
        pos = viser(g, cx, cy)
        if pos is None:
            self.echecs.append("aucune souris ne designe la case (%d,%d) "
                               "depuis la vue (%d,%d)" % (cx, cy, g.xoff, g.yoff))
            return False
        avant = g.sim.players[g.sim.player].mana
        press(g, pos[0], pos[1])
        self.actions += 1
        if g.sim.players[g.sim.player].mana >= avant:
            self.echecs.append("clic marais (%d,%d) sans effet sur le mana"
                               % (cx, cy))
            return False
        return True

    # ----------------------------------------------------------------- boucle
    def pas(self, tour: int, reference: bool) -> str | None:
        """Une decision. Renvoie ``"gagne"``, ``"perdu"`` ou ``None``."""
        g = self.g
        if g.game_ended:
            return "gagne" if g.victory else "perdu"
        if reference:
            return None

        cibles = self.ennemis()
        if not cibles:
            return None

        # la ou le marais pourra tomber, puis la fenetre **sur cette
        # la** : la fenetre ne fait que 8x8 et une cible choisie apres le
        # recentrage peut en tomber hors, d'ou 75 "aucune souris ne
        # designe la case" sur le premier jet.
        vise = self.cible_marais()
        if vise is None:
            # pas de case libre dans le carre 7x7 : le marais ne poserait
            # rien et le mana partirait quand meme. Mieux vaut le dire.
            self.echecs.append("pas de case libre autour de (%d,%d)" % cibles[0])
            return None
        cx, cy = vise
        if not (g.xoff <= cx < g.xoff + 8 and g.yoff <= cy < g.yoff + 8):
            if not mini_carte(g, cx, cy):
                self.echecs.append("mini-carte: clic refuse pour (%d,%d)"
                                   % (cx, cy))
                return None
        return "frapper" if self.frapper(cx, cy) else None


# ----------------------------------------------------------------------- main
def etat(g: Game) -> str:
    sim = g.sim
    return ("tour %5d  pop J=%4d A=%4d  mana=%6d  villes J=%d A=%d  "
            "mode=0x%02X  o2b=%d  paint=%d"
            % (sim.game_turn, sim.population(sim.player),
               sim.population(sim.not_player),
               sim.players[sim.player].mana,
               sim.stats[sim.player].towns, sim.stats[sim.not_player].towns,
               sim.mode, sim.ok_to_build, sim.paint_map))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Joueur virtuel : essaie de gagner une partie.")
    ap.add_argument("graine", nargs="?", type=int, default=1)
    ap.add_argument("sol", nargs="?", type=int, default=0)
    ap.add_argument("zoom", nargs="?", type=int, default=3)
    ap.add_argument("--reference", action="store_true",
                    help="les deux tribus sous l'IA du listing")
    ap.add_argument("--tours", type=int, default=25000)
    ap.add_argument("--pas", type=int, default=25,
                    help="un tour de decision tous les N tours")
    ap.add_argument("--rendu", action="store_true",
                    help="compose chaque image (plus lent, pour inspecter)")
    ap.add_argument("--visible", action="store_true",
                    help="ouvre la fenetre et plafonne a 30 tours/s, "
                         "pour regarder jouer au lieu de mesurer")
    a = ap.parse_args(argv)

    g = Game(a.graine, a.sol, a.zoom)
    if a.reference:
        # meme ecriture que _settle_peoples, mais pour la tribu joueur :
        # c'est le mode « AMIGA VS AMIGA » du listing (L13196-13221)
        g.sim.stats[g.sim.player].can_build = 1

    bot = Bot(g)
    print("mode          : %s"
          % ("REFERENCE (IA du listing des deux cotes)"
             if a.reference else "BOT humain contre l'IA du listing"))
    print("depart        : %s" % etat(g))

    t0 = time.time()
    prochain = a.pas
    while g.sim.game_turn < a.tours and not g.game_ended:
        g.poll_mouse()                       # meme ordre que run() L4290
        if g.sim.game_turn >= prochain:
            prochain += a.pas
            bot.pas(g.sim.game_turn, a.reference)
            if a.rendu:
                g.compose()
            elif g.sim.game_turn % (a.pas * 8) == 0:
                print("  %s" % etat(g))
        g.image()
        if a.visible:
            # sans plafond la partie file a ~400 tours/s : impossible a
            # suivre des yeux
            g.clock.tick(30)

    # ------------------------------------------------------------- bilan
    sim = g.sim
    print()
    print("etat final    : %s" % etat(g))
    print("actions       : %d (dont %d echecs signales)"
          % (bot.actions, len(bot.echecs)))
    duree = time.time() - t0
    print("duree         : %.1fs" % duree)

    if bot.echecs:
        # regroupes par type : 581 messages « mana trop bas » ne disent pas
        # grand-chose, un compte par cause dit tout
        groupes: dict[str, int] = {}
        for e in bot.echecs:
            cle = e.split(" :")[0].split(" (")[0]
            groupes[cle] = groupes.get(cle, 0) + 1
        print("\nechecs signales (%d au total) :" % len(bot.echecs))
        for cle, n in sorted(groupes.items(), key=lambda kv: -kv[1]):
            print("  [KO] x%-4d %s" % (n, cle))
        print("\npremiers details :")
        for e in bot.echecs[:5]:
            print("  [KO] %s" % e)

    if g.game_ended:
        ok = g.victory
        if a.reference:
            # ligne de base : le bot n'agit pas, c'est tout son principe.
            # Dire « sans jamais agir » ici serait un faux KO.
            print("\n[OK] ligne de base, sans aucune entree humaine : la "
                  "tribu %s l'emporte au tour %d"
                  % ("jouee ( 0 )" if ok else "Amiga ( 1 )", sim.game_turn))
            return 0
        # un bot qui gagne sans avoir agi ne prouve rien : il faut le dire
        if ok and bot.actions == 0:
            print("\n[KO] le bot a GAGNE **sans jamais agir** (%d tour) : "
                  "la victoire vient de la simulation, pas du jeu."
                  % sim.game_turn)
            return 1
        print("\n[OK] le bot a GAGNE en %d actions" % bot.actions
              if ok else "\n[KO] le bot a PERDU")
        return 0 if ok else 1

    print("\n[KO] partie non terminee en %d tours" % sim.game_turn)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(2)
