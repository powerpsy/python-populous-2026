# -*- coding: utf-8 -*-
"""Controle d'execution : l'equilibrage des deux tribus.

Phase 88. L'ancienne « note honnete » de ``docs/PROGRESSION.md`` affirmait
que, sur les cartes tres montagneuses, la seconde tribu pouvait s'eteindre,
et que « avec l'IA desactivee les deux tribus sont parfaitement
symetriques ». Ces deux affirmations etaient **deduites**, non mesurees.

Ce controle les remplace par des chiffres, et verifie au passage que le port
ne rajoute aucun biais par-dessus celui que le listing a deja construit.

Trois faits, verifies ici :

1. les deux tribus ne sont **pas** symetriques, et c'est le ``.data`` du
   listing qui le decide : ``threshold`` vaut ``$0001`` a ``LAB_516B0`` et
   ``$0005`` a ``LAB_516DE`` (L24171-24232), et ``_place_first_people``
   en tire ``n = 2*(threshold>4)+1`` (L7668-7678) -- un villageois contre
   trois. ``period`` vaut ``$0001`` (``LAB_516B4``) et ``$0003``
   (``LAB_516E2``) : la tribu 1 decide un tour sur trois ;
2. ``population()`` est la **somme des vies** (asm 3472-3474), non un
   decompte : au depart chaque peep porte ``life = 45``, d'ou ``45`` et
   ``135``. Ce n'est pas un biais du port ;
3. la seconde tribu **ne s'eteint pas** : sur N graines, elle l'emporte
   toujours en configuration monojoueur sans entree humaine -- ce qui est
   exactement ce que le ``.data`` annonce, puisque la tribu 0 a
   ``can_build = 0`` et ne prend donc aucune decision seule.

Le controle ne tourne que si ``--graines N`` est donne : les parties sont
longues. Sans argument, il ne verifie que le point structurel (1 et 2),
qui est instantane.

Usage :
    python tools\\check_equilibre.py                # point structurel seul
    python tools\\check_equilibre.py --graines 40 --tours 1200
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from populous.game import Game                    # noqa: E402

ECHECS = []


def chk(cond, msg):
    print(("  ok    " if cond else "  ECHEC ") + msg)
    if not cond:
        ECHECS.append(msg)


def structurel() -> None:
    """Le depart, lu tel quel dans le listing, sans tour joue."""
    g = Game(1, 0, 3)
    sim = g.sim

    chk(sim.no_peeps == 4,
        "_place_first_people pose 1 villageois pour la tribu 0 et 3 pour la "
        "tribu 1 : no_peeps == 4 ( L7668-7678 : n = 2*(threshold>4)+1 )")
    vies = {}
    for _, p in sim.living():
        vies[p.tribe] = vies.get(p.tribe, 0) + p.life
    chk(all(p.life == 45 for _, p in sim.living()),
        "chaque villageois de depart porte life = 45 ( %s )"
        % sorted({p.life for _, p in sim.living()}))
    chk(vies[0] == 45 and vies[1] == 135,
        "population() est une somme de VIES ( asm 3472-3474 ) : 45 et 135, "
        "soit 1 x 45 et 3 x 45 ( %d et %d )" % (vies[0], vies[1]))

    st0, st1 = sim.stats[0], sim.stats[1]
    chk(st0.threshold == 1 and st1.threshold == 5,
        ".data de _stats : threshold $0001 a LAB_516B0 et $0005 a "
        "LAB_516DE ( L24184 / L24222 ) : %d et %d"
        % (st0.threshold, st1.threshold))
    chk(st0.period == 1 and st1.period == 3,
        ".data de _stats : period $0001 a LAB_516B4 et $0003 a LAB_516E2 : "
        "%d et %d" % (st0.period, st1.period))
    chk(st0.can_build == 0 and st1.can_build == 1,
        "can_build : 0 pour la tribu jouee, 1 pour l'Amiga ( L11256-11259 )")
    chk(st0.power_mask == st1.power_mask == 0xFFFF,
        "power_mask $FFFF des deux cotes ( LAB_516B2 / LAB_516E0 )")
    chk(sim.player == 0 and sim.not_player == 1,
        "en 3 joueurs : player = 0, not_player = 1")


def mesure(nb: int, tours: int) -> None:
    """N graines : qui gagne, et la seconde tribu s'eteint-elle ?"""
    print()
    print("mesure : %d graines x %d tours" % (nb, tours))
    j_gagne = a_gagne = egal = eteinte = 0
    asy = 0
    for i in range(nb):
        seed, ground = 1 + i * 37, i % 4
        g = Game(seed, ground, 3)
        sim = g.sim
        p0, p1 = sim.population(0), sim.population(1)
        if p0 != p1:
            asy += 1
        for _ in range(tours):
            g.tick()
        p0, p1 = sim.population(0), sim.population(1)
        if p0 > p1:
            j_gagne += 1
        elif p1 > p0:
            a_gagne += 1
        else:
            egal += 1
        if p1 == 0 and p0 > 0:
            eteinte += 1

    print("  departs asymetriques           : %d/%d  ( c'est le .data )"
          % (asy, nb))
    chk(eteinte == 0,
        "la seconde tribu ne s'eteint sur aucune graine ( %d/%d )"
        % (eteinte, nb))
    chk(a_gagne == nb,
        "tribu 1 l'emporte sur les %d graines : tribu 0 gagne %d, "
        "egalite %d ( tribu 0 a can_build = 0, elle n'agit donc jamais seule )"
        % (nb, j_gagne, egal))


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--graines", type=int, default=0,
                    help="combien de graines mesurer ( 0 = rien )")
    ap.add_argument("--tours", type=int, default=1200,
                    help="tours par partie")
    args = ap.parse_args(argv)

    structurel()
    if args.graines > 0:
        mesure(args.graines, args.tours)

    print()
    if ECHECS:
        print("%d ECHEC(S) :" % len(ECHECS))
        for m in ECHECS:
            print("  - " + m)
        return 1
    print("OK - tous les controles passent")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
