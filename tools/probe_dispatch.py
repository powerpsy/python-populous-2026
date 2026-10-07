# -*- coding: utf-8 -*-
"""Compte les appels reels de ``PowerEngine.dispatch`` pendant une partie.

Question posee a l'origine : ``PowerEngine.do_action`` (transcription
fidele, Phases 46-49) avait-elle des appelants ?  Reponse mesuree en
Phase 50 : non — c'etait ``_sub_action``, une version ecrite a la main,
qui tournait.  ``_sub_action`` a ete supprime en Phase 51 ; le probe le
compte encore (toujours 0) pour garder la mesure d'origine lisible.

On espionne trois points :

* ``dispatch(tribe, act, x, y)``      — l'histogramme des ``act`` ;
* pour ``act == 14`` (``ACT_ACTION``) — l'histogramme de ``y``, qui EST le
  ``p2`` du listing, c'est-a-dire la sous-commande de ``_do_action`` ;
* ``do_action`` et ``_sub_action``   — qui est appele, et combien de fois.
"""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import populous.powers as P  # noqa: E402

hist_act = collections.Counter()
hist_p2 = collections.Counter()
n_dispatch = 0
n_sub = 0
n_do = 0
n_choose = 0
n_devil = 0
n_devil_act = 0

_orig_dispatch = P.PowerEngine.dispatch
# `_sub_action` n'existe plus depuis la Phase 51 : le probe le compte
# encore, mais ne peut plus l'espionner.
_orig_sub = None
_orig_do = P.PowerEngine.do_action
_orig_choose = P.PowerEngine.ai_choose
_orig_devil = P.PowerEngine.devil_effect

import populous.sim as S  # noqa: E402

n_grow = 0
n_battle = 0
age_hist = collections.Counter()
_orig_grow = S.Game.grow_peep
_orig_battle = S.Game.battle_over


def spy_grow(self, i, p, score):
    global n_grow
    n_grow += 1
    age = p.frame - 0x20                     # FRAME_AGE
    age_hist[max(0, min(10, age))] += 1
    return _orig_grow(self, i, p, score)


def spy_battle(self, winner, loser):
    global n_battle
    n_battle += 1
    return _orig_battle(self, winner, loser)


def spy_dispatch(self, tribe, act, x, y):
    global n_dispatch
    n_dispatch += 1
    hist_act[act] += 1
    if act == 14:
        hist_p2[y] += 1
    return _orig_dispatch(self, tribe, act, x, y)


def spy_sub(self, tribe, p1, p2):
    """Plus d'appelant depuis la Phase 51 : reste la pour le compter."""
    global n_sub
    n_sub += 1
    return None


def spy_do(self, tribe, arg2, code):
    global n_do
    n_do += 1
    return _orig_do(self, tribe, arg2, code)


def spy_choose(self, tribe):
    global n_choose
    n_choose += 1
    return _orig_choose(self, tribe)


def spy_devil(self, tribe):
    """Compte les appels, et ceux qui modifient vraiment ``st.act``."""
    global n_devil, n_devil_act
    n_devil += 1
    avant = self.g.sim.stats[tribe].act
    res = _orig_devil(self, tribe)
    if self.g.sim.stats[tribe].act != avant:
        n_devil_act += 1
    return res


P.PowerEngine.dispatch = spy_dispatch
P.PowerEngine.do_action = spy_do
P.PowerEngine.ai_choose = spy_choose
P.PowerEngine.devil_effect = spy_devil
S.Game.grow_peep = spy_grow
S.Game.battle_over = spy_battle

# smoke_sim ne pilote que `sim` : il n'atteint jamais `Game.image()`, donc
# jamais `_run_commands` -> `do_queued` -> `dispatch`. On pilote donc la
# vraie boucle d'image, qui est celle que le joueur execute.
from populous.game import Game  # noqa: E402

jeu = Game(int(sys.argv[1]) if len(sys.argv) > 1 else 59, 0, 3)
N_IMAGES = 4000
TRAJ = (50, 200, 1000, 3000, 4000)
print()
print("trajectoire de mana (chemin Game.image) :")
print("   %8s %10s %10s %8s %8s"
      % ("tour", "mana J", "mana A", "peeps", "habite"))
for n in TRAJ:
    while jeu.sim.game_turn < n:
        jeu.image()
    print("   %8d %10d %10d %8d %8d"
          % (jeu.sim.game_turn,
             jeu.sim.players[0].mana, jeu.sim.players[1].mana,
             sum(1 for p in jeu.sim.peeps if p.life > 0),
             sum(1 for v in jeu.sim.map.who if v)))
while jeu.sim.game_turn < N_IMAGES:
    jeu.image()
print("( %d tours via Game.image() )" % N_IMAGES)
jeu.running = False

NOM_ACT = {
    0: "nop", 1: "relever", 2: "abaisser", 3: "seisme", 4: "marais",
    5: "aimant", 6: "volcano", 7: "peuple 0", 8: "peuple 1",
    9: "aimant 0", 10: "aimant 1", 11: "arbre", 12: "rocher",
    13: "enlever", 14: "_do_action", 15: "??",
}
NOM_P2 = {
    0: "no-op", 1: "commande+icones", 2: "serie", 3: "guerre", 4: "inondation",
    5: "chevalier", 6: "pause", 7: "croise 7", 8: "croise 8",
    9: "mana joueur 0", 10: "mana joueur 1", 11: "rotation",
    12: "effacer carte", 13: "ground", 14: "no-op", 15: "triche",
}

print()
print("=" * 64)
print("SPIONNAGE DU DISPATCH")
print("=" * 64)
print("appels de dispatch()          : %d" % n_dispatch)
for act, n in sorted(hist_act.items()):
    print("   act=%-3d %-14s : %6d" % (act, NOM_ACT.get(act, "?"), n))
print("dont act=14 -> sous-commandes : %d" % sum(hist_p2.values()))
for p2, n in sorted(hist_p2.items()):
    print("   p2 =%-3d %-14s : %6d" % (p2, NOM_P2.get(p2, "?"), n))
print()
print("_sub_action (supprime Phase 51)      : %d fois" % n_sub)
print("do_action   (la transcription fidele)  : %d fois" % n_do)
print("ai_choose   appele                    : %d fois" % n_choose)
print("  dont _devil_effect appele           : %d fois" % n_devil)
print("  dont il a change st.act             : %d fois" % n_devil_act)
print()
manquants = sorted(set(NOM_P2) - set(hist_p2))
print("sous-commandes JAMAIS emises ici : %s"
      % ", ".join("%d (%s)" % (p, NOM_P2[p]) for p in manquants))
print()
print("etat final :")
for t in (0, 1):
    st = jeu.sim.stats[t]
    pl = jeu.sim.players[t]
    print("   tribu %d : act=%-3d p1=%-3d p2=%-3d queued=%d mana=%-9d"
          % (t, st.act, st.p1, st.p2, st.queued, pl.mana))
print("   cases habitees=%d  peeps vivants=%d"
      % (sum(1 for v in jeu.sim.map.who if v),
         sum(1 for p in jeu.sim.peeps if p.life > 0)))
print("   grow_peep appele            : %d fois" % n_grow)
print("   ages observes (frame-0x20)  : %s" % dict(sorted(age_hist.items())))
print("   mana_add                    : %s" % list(jeu.sim.land.mana_add))
print("   mana apporte par grow_peep  : %d"
      % sum(n * jeu.sim.land.mana_add[a] for a, n in age_hist.items()))
print("   battle_over appele          : %d fois" % n_battle)
print("   mana de base attendu        : 399 + %d x 0.5 = %s"
      % (jeu.sim.game_turn, 399 + jeu.sim.game_turn // 2))
