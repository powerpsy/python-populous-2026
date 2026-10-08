# -*- coding: utf-8 -*-
"""Controle d'execution de `_do_place_funny` (L8862-9013).

Phase 56, etape 2. La routine etait un stub ``**[APPROX]**`` qui se
contentait d'ecrire ``effect`` ; elle est maintenant transcrite ligne a
ligne. Ce controle existe pour que le changement soit **mesure** et non
suppose :

1. la table ``_peeps`` compte **212** fiches (``5424C - 53014 = 4664 =
   212 * 22``, ``_no_peeps`` suit immediatement, L25365-25392) - les
   fiches 209/210 ecrites par la routine doivent donc exister ;
2. les champs de la fiche egalent le listing : ``life=1`` (L8898),
   ``state=2`` (L8900), ``map_who[block] = idx+1`` (L8977),
   ``prev_block`` (L8982), ``offspring`` (L8987), ``weapons`` (L8992),
   ``face=1`` (L8994), ``w6=weapons`` (L8999), ``make_level_res=code``
   (L9001) ;
3. la table ``_funny`` vaut ``(0xFFC0,0,4) (0xFFBF,5,8) (0x0041,9,12)``
   (L24161-24169, relue octet a octet dans le binaire DAD) ;
4. la boucle **retourne des la premiere fiche vide remplie** (L9002) et
   ne tire **qu'un** ``newrand`` par remplissage (L8905) ; ``code > 2``
   sort sans rien tirer (L8864) ;
5. les quatre branches d'attribution de ``block`` (L8901-8970) ne
   produisent que des valeurs de la reference independamment recalculee
   ci-dessous ;
6. ``map_who`` n'est **jamais** ecrite hors des 4096 cases : c'est le
   seul ECART assume de la transcription (l'ecriture L8977 est sans
   borne, la branche ``arg2==1/bit0==0`` produit un ``block`` jusqu'a
   8000) ;
7. ``map_who`` valant 210/211 reste lisible par ``where_do_i_go``
   (``peeps[w-1]``, L4755) ;
8. le second site d'appel, ``_main`` a ``game_turn == $1000`` (L752-759),
   remplit bien la fiche 209 - et ne touche pas ``funny_done``, que seul
   L4006 ecrit.

Le deuxieme argument n'est **pas fourni** par les deux appels du listing
(L757 et L4003 ne poussent qu'un mot) : le port le rend explicite et le
passe a 0, decision de phase 56 consignee dans ``docs/PROGRESSION.md``.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from populous.constants import (MAP_CELLS, MAX_PEEPS, PEEP_SLOTS,  # noqa: E402
                                ST_EXPLORER)
from populous.rng import Rng  # noqa: E402
from populous.sim import Game as Sim  # noqa: E402

ECHECS = []


def chk(cond, msg):
    print(("  ok    " if cond else "  ECHEC ") + msg)
    if not cond:
        ECHECS.append(msg)


# --- 1 : taille de la table --------------------------------------------------
s = Sim(1234)
chk(len(s.peeps) == PEEP_SLOTS == 212, "len(peeps) == PEEP_SLOTS == 212")
chk(MAX_PEEPS == 208, "MAX_PEEPS reste 208 (borne de simulation)")

# --- 2 : premier appel, code=1, arg2=0 ---------------------------------------
seed0 = s.rng.seed
s.do_place_funny(1, 0)
p = s.peeps[0xD1]
chk(p.life == 1, "fiche 209 : life == 1 (L8898)")
chk(p.state == ST_EXPLORER, "fiche 209 : state == 2 (L8900)")
ref = {0x0FC0 + (v >> 1) for v in range(125)}
chk(p.block in ref, "fiche 209 : block %d == 4032+((rand%%125)>>1)" % p.block)
chk(s.map.who[p.block] == 0xD2, "map_who[%d] == 210 (L8977)" % p.block)
chk(p.prev_block == -65, "fiche 209 : prev_block %d (0xFFBF signe)" % p.prev_block)
chk(p.offspring == 8, "fiche 209 : offspring %d (L8987)" % p.offspring)
chk(p.weapons == 5, "fiche 209 : weapons %d (L8992)" % p.weapons)
chk(p.w6 == 5, "fiche 209 : w6 == weapons (L8996-8999)")
chk(p.face == 1, "fiche 209 : face == 1 (L8994)")
chk(p.make_level_res == 1, "fiche 209 : make_level_res == 1 (L9001)")
chk(s.no_peeps == 0, "_no_peeps intact (= %d)" % s.no_peeps)
r = Rng(seed0)
r.raw()
chk(s.rng.seed == r.seed, "exactement UN tirage newrand (L8905)")

# --- 3 : second appel, code=0 -> fiche 210 -----------------------------------
s.do_place_funny(0, 0)
q = s.peeps[0xD2]
chk(q.life == 1, "fiche 210 : life == 1")
chk(s.map.who[q.block] == 0xD3, "map_who[%d] == 211 (L8977)" % q.block)
chk(q.prev_block == -64, "fiche 210 : prev_block %d (0xFFC0 signe)" % q.prev_block)
chk(q.offspring == 4, "fiche 210 : offspring %d" % q.offspring)
chk(q.weapons == 0, "fiche 210 : weapons 0 (le DS.W 1 vaut 00 00, DAD $51683)")
chk(q.make_level_res == 0, "fiche 210 : make_level_res == 0")

# --- 4 : plus rien a faire, aucun tirage -------------------------------------
seed1 = s.rng.seed
s.do_place_funny(2, 0)
chk(s.rng.seed == seed1, "fiches completes : AUCUN tirage (L8896 -> LAB_449B0)")
s.do_place_funny(3, 0)
chk(s.rng.seed == seed1, "code > 2 : retour immediat (L8864-8868)")
chk(s.peeps[0xD1].prev_block == -65 and s.peeps[0xD2].weapons == 0,
    "les champs ne sont pas modifies")

# --- 5/6 : les quatre branches d'attribution du block ------------------------
# Reference recalculee ici, independamment du code teste.
b0 = {0x0FC0 + (v >> 1) for v in range(125)}
b1 = ({(v + 0x14) * 64 + 0x003F for v in range(43)}
      | {(v + 0x14) * 64 + 0x0FC0 for v in range(43)})
b2 = set(range(43)) | {v * 64 for v in range(43)}
for arg2, reference, nom in ((0, b0, "arg2==0"), (1, b1, "arg2==1"),
                             (2, b2, "arg2==2")):
    trouves = set()
    hors = 0
    for grain in range(120):
        t = Sim(grain)
        t.do_place_funny(0, arg2)
        blk = t.peeps[0xD1].block
        trouves.add(blk)
        ecrites = [v for v in t.map.who if v]
        if blk >= MAP_CELLS:
            hors += 1
            # ECART : la branche arg2==1/bit0==0 sort de la table, et
            # l'ecriture L8977 n'a aucune borne dans l'asm. On la saute.
            assert ecrites == [], "map_who ecrit malgre un block hors borne"
        else:
            assert ecrites == [0xD2], "exactement une case ecrite"
            assert t.map.who[blk] == 0xD2, "map_who non ecrit (%s)" % nom
    chk(trouves <= reference,
        "%s : %d blocks distincts tous dans la reference" % (nom, len(trouves)))
    print("        %s : %d/120 tirages hors des 4096 cases (branche morte)"
          % (nom, hors))

# --- 7 : map_who = 211 lisible par where_do_i_go -----------------------------
t = Sim(7)
t.do_place_funny(1, 0)
t.do_place_funny(0, 0)
t.map.who[:] = bytes([211]) * MAP_CELLS
p0 = t.peeps[0]
p0.life, p0.state, p0.tribe = 100, ST_EXPLORER, 0
p0.block, p0.prev_block, p0.frame = 0x820, 0, 0
t.no_peeps = 1
vivants = [i for i in range(MAX_PEEPS) if t.peeps[i].life > 0]
chk(bool(vivants), "%d peep(s) vivant(s) pour l'essai" % len(vivants))
try:
    for _ in range(20):
        for i in vivants:
            if t.peeps[i].life > 0:
                t.where_do_i_go(i, t.peeps[i])
    okidx = True
except IndexError as exc:                      # pragma: no cover
    okidx = False
    print("        IndexError : %s" % exc)
chk(okidx, "peeps[w-1] avec w == 211 : pas d'IndexError (L4755)")

# --- 8 : site d'appel `_main` (game_turn == $1000) ---------------------------
from populous.game import Game  # noqa: E402

g = Game(58, 0, 3)                 # 58 & 3 == 2 -> code 2
g.sim.game_turn = 0x1000
g.sim.funny_done = 0
g.compose()
chk(g.sim.peeps[0xD1].life == 1, "_main : fiche 209 remplie a game_turn $1000")
chk(g.sim.map.who[g.sim.peeps[0xD1].block] == 0xD2, "_main : map_who ecrit")
chk(g.sim.funny_done == 0, "_main ne touche PAS funny_done (seul L4006 le fait)")

g2 = Game(59, 0, 3)                # 59 & 3 == 3 -> code > 2
g2.sim.game_turn = 0x1000
g2.compose()
chk(g2.sim.peeps[0xD1].life == 0, "_main : seed&3 == 3 -> aucun peep (L8864)")

# --- synthese ---------------------------------------------------------------
print()
if ECHECS:
    print("%d ECHEC(S) :" % len(ECHECS))
    for m in ECHECS:
        print("  - " + m)
    sys.exit(1)
print("OK - tous les controles passent")
