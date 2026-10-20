# -*- coding: utf-8 -*-
"""Controle d'execution de `_do_funny` (L8630-8858).

Phase 88. La routine existait dans le port sous forme de docstring seule :
elle n'etait pas transcrite, et surtout **pas appelee**. Le controle sert a
mesurer la difference, et non a la supposer :

1. ``FUNNY_DELTAS`` (``LAB_51686`` = ``_funny + 6``) est rebati ici a partir
   des seuls ``DC.L``/``DC.W`` de L24161-24170, puis compare aux neuf mots
   que la routine va relire ;
2. ``map_couleur`` est confrontee a ``render.map_colours`` : deux
   implementations independantes de la meme regle (boucle L4A348-4A36C plus
   ``DC.L $19191919`` de L5177E) ;
3. le **rebond** de ``w6`` est confronte a une reecriture independante sur
   un balayage qui couvre les deux bornes et leur dehors -- c'est le point
   ou ``docs/game_logic.md`` s'etait trompe de sens **et** de bornes ;
4. la cadence, un pas toutes les huit images ( ``frame > 7`` ), est
   mesuree ;
5. les **trois branches** de ``make_level_res`` (``bk2 = i+$32``,
   ``blk = $35``, ``blk = i+$2F`` + ``a_putpixel``) sont testees chacune,
   avec leurs ecritures **et** leurs cas de saut ;
6. l'ordre interne : ``map_who`` efface a ;445a2 **avant** la mort sur
   ``valid_move`` a ;445e0, ``prev_block`` repeint quand il vaut nul, et
   l'occupant de ``map_who[nb]`` tue ;
7. ``map_who[e.block] = idx + 1`` vaut 210 pour la fiche 209 et 211 pour
   la 210 ;
8. l'appel reel, par ``Game.tick()``, **avec** la garde
   ``_pause == 0`` / ``_paint_map == 0`` de ;3e942- ;3e94c, et l'ordre
   ``_do_funny`` puis ``_move_peeps`` de L680-681.

Le port n'ajoute ici que deux gardes ``0 <= x < borne`` : le 68000 lit et
ecrit sans borne. Ce sont les deux seuls ecarts assumes, comme pour
``_do_place_funny``.
"""
import os
import sys
import types
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from populous.constants import (FUNNY, FUNNY_DELTAS, MAX_PEEPS,  # noqa: E402
                                ST_EXPLORER)
from populous.m68k import s16  # noqa: E402
from populous.sim import Game as Sim  # noqa: E402

ECHECS = []


def chk(cond, msg):
    print(("  ok    " if cond else "  ECHEC ") + msg)
    if not cond:
        ECHECS.append(msg)


def funny(**champs):
    """Un Sim dont la fiche 209 est vivante et seule en piste."""
    t = Sim(champs.pop("seed", 1))
    t.peeps[0xD1].life = t.peeps[0xD2].life = 0
    p = t.peeps[0xD1]
    p.life, p.tribe, p.state = 1, 0, ST_EXPLORER
    p.block, p.prev_block, p.make_level_res = 0x142, -64, 0
    p.frame, p.face = 0, 1
    p.offspring, p.weapons, p.w6 = 4, 0, 0
    for k, v in champs.items():
        setattr(p, k, v)
    return t, p


# --- 1 : FUNNY_DELTAS rebati depuis le listing -------------------------------
# Seules les donnees de L24161-24170, dans l'ordre ou le listing les ecrit :
#   _funny:    DC.W $ffc0                    ;51680
#   LAB_51682: DS.W 1                        ;51682
#   LAB_51684: DC.W $0004                    ;51684
#   LAB_51686: DC.L $0000ffff,$0001ffbf,$00050008,$0000ffc0   ;51686
#              DC.L $ffff0041,$0009000c,$00000040             ;51696
#              DC.W $0001                                     ;516a2
_brut = (b"\xff\xc0"                       # _funny +0, le prev_block de 0
         + b"\x00\x00"                     # LAB_51682, un DS.W 1
         + b"\x00\x04"                     # LAB_51684, l'offspring de 0
         + b"\x00\x00\xff\xff\x00\x01\xff\xbf\x00\x05\x00\x08\x00\x00"
         b"\xff\xc0\xff\xff\x00\x41\x00\x09\x00\x0c\x00\x00\x00\x40"
         + b"\x00\x01")                    # fin de LAB_51686, avant _stats
chk(len(_brut) == 0x24, "_funny suivi de LAB_51686 tient $24 octets (%d)"
    % len(_brut))
_rebati = []
for _k in range(3):
    _base = 6 + _k * 12                   # LAB_51686 = _funny + 6
    _rebati.append(tuple(int.from_bytes(_brut[_base + _i * 2:
                                             _base + _i * 2 + 2], "big")
                         for _i in range(3)))
chk(tuple(_rebati) == FUNNY_DELTAS,
    "FUNNY_DELTAS == LAB_51686 relu octet a octet depuis L24161-24170 : %s"
    % (FUNNY_DELTAS,))
chk(FUNNY == ((0xFFC0, 0x00, 0x04), (0xFFBF, 0x05, 0x08), (0x0041, 0x09, 0x0C)),
    "_funny n'a pas bouge : %s" % (FUNNY,))
chk([s16(t[0]) for t in FUNNY] == [-64, -65, +65],
    "les trois prev_block valent -64, -65, +65 (0xFFC0/0xFFBF/0x0041 signes)")
chk(FUNNY_DELTAS[1][1] == 0xFFC0 and FUNNY_DELTAS[2][2] == 0x0001,
    "la fiche 1 remonte d'une ligne (0xFFC0) et la 2 descend (0x0040)")

# --- 2 : map_couleur, contre render.map_colours ------------------------------
s = Sim(1234)
from populous.render import map_colours  # noqa: E402

_ref = map_colours({"map_colour": s.land.map_colour})
chk(len(_ref) == 232, "render.map_colours rend bien 232 octets (%d)" % len(_ref))
_ecarts = [b for b in range(232) if s.map_couleur(b) != _ref[b]]
chk(not _ecarts,
    "map_couleur == render.map_colours sur les 232 cases de map_blk : "
    "%d ecart(s)" % len(_ecarts))
chk(s.map_couleur(0x2F) == s.map_couleur(0x30) == s.map_couleur(0x31) == 0x19,
    "les trois rochers valent $19 (DC.L $19191919, L5177E) : %d"
    % s.map_couleur(0x2F))
_tete = s.land.map_colour
chk(s.map_couleur(0) == _tete[0] and s.map_couleur(16) == _tete[0]
    and s.map_couleur(31) == _tete[15],
    "boucle L4A348-4A36C : _map_colour[i+16] == _map_colour[i]")


# --- reference independante du rebond ---------------------------------------
def ref_pas(w6, face, offspring, weapons):
    """Reecriture independante de ;44516-;44565.

    ``CMP.W`` suivi de ``BCC`` ( ;44540 ) puis ``BHI`` ( ;44556 ) : les deux
    tests sont **non signees**. ``NEG`` si ``w6 >= (+2)`` ou ``w6 <= (+3)``.
    """
    pas = face if face < 0x80 else face - 0x100
    nw = (w6 + pas) & 0xFFFF
    if nw >= offspring or nw <= weapons:      # BCC puis BHI
        return nw, (-pas) & 0xFF
    return nw, face


# --- 3 : le rebond, balayage complet ----------------------------------------
t = Sim(1)
p = t.peeps[0xD1]
p.life, p.tribe, p.state = 1, 0, ST_EXPLORER
p.block, p.prev_block = 0x1010, -64
cas = 0
for code, (prev, armes, petits) in enumerate(FUNNY):
    for face in (0x01, 0xFF):
        for w6 in (0, 1, 2, 3, 4, 5, 7, 8, 0xFF, 0x100, 0xFFFE, 0xFFFF):
            p.make_level_res, p.offspring, p.weapons = code, petits, armes
            p.w6, p.face, p.frame = w6, face, 0
            t.do_funny()
            e_w6, e_face = ref_pas(w6, face, petits, armes)
            cas += 1
            assert p.w6 == e_w6 and p.face == e_face, \
                "code %d w6=%04X face=%02X -> %04X/%02X, attendu %04X/%02X" \
                % (code, w6, face, p.w6, p.face, e_w6, e_face)
            assert p.frame == 1, "le pas seul n'atteint pas le corps"
chk(cas == 72,
    "rebond == reecriture independante sur %d cas (3 codes x 2 sens x 12 "
    "positions)" % cas)

# La creature part de la borne basse ( L8999 : w6 = weapons ) et atteint les
# deux extremites, sans jamais sortir.
for code, (prev, armes, petits) in enumerate(FUNNY):
    tt, pp = funny(seed=2 + code, make_level_res=code, prev_block=prev,
                   offspring=petits, weapons=armes, w6=armes, face=1)
    vus = []
    for _ in range(200):
        pp.frame = 0                          # on ne veut que le pas
        tt.do_funny()
        vus.append(pp.w6)
    chk(min(vus) == armes and max(vus) == petits
        and set(vus) <= set(range(armes, petits + 1)),
        "code %d : w6 oscille de %d (weapons,+3) a %d (offspring,+2) sans "
        "sortir ( %d valeurs )" % (code, armes, petits, len(set(vus))))

# Le rebond ignore les autres fiches, et une fiche morte est sautee.
t = Sim(3)
for i in range(MAX_PEEPS):
    q = t.peeps[i]
    q.life, q.tribe, q.state, q.block = 100, i & 1, ST_EXPLORER, 0x1010 + i
    q.w6, q.face, q.frame = 77, 1, 3
avant = [(t.peeps[i].w6, t.peeps[i].face, t.peeps[i].frame, t.peeps[i].life)
         for i in range(MAX_PEEPS)]
t.do_funny()
apres = [(t.peeps[i].w6, t.peeps[i].face, t.peeps[i].frame, t.peeps[i].life)
         for i in range(MAX_PEEPS)]
chk(avant == apres,
    "_do_funny ne touche que les fiches 209 et 210, pas les %d autres"
    % MAX_PEEPS)
chk(t.peeps[0xD1].life == 0 and t.peeps[0xD2].life == 0,
    "fiches mortes : la boucle les saute ( TST.W (4,A0) ;44502 )")
_ecrits = [i for i, v in enumerate(t.map.who) if v]
chk(not _ecrits, "map_who intact quand les deux fiches sont mortes (%s)"
    % _ecrits)

# --- 4 : la cadence, une image sur huit -------------------------------------
t, p = funny(seed=4, make_level_res=1, prev_block=-65, frame=0,
             offspring=8, weapons=5, w6=5)
vus = []
for n in range(1, 17):
    t.do_funny()
    vus.append((n, p.frame, p.block))
deplaces = [n for n, f, b in vus
            if b != (vus[n - 2][2] if n > 1 else 0x142)]
chk(deplaces == [8, 16],
    "le bloc ne bouge qu'une fois toutes les huit images : images %s"
    % deplaces)
chk([f for _, f, _ in vus][:9] == [1, 2, 3, 4, 5, 6, 7, 0, 1],
    "frame compte 1..8 puis retombe a 0 ( CMPI.W #7,(0xC) ;4456a ) : %s"
    % [f for _, f, _ in vus][:9])

# --- 5 : les trois branches --------------------------------------------------
# 5a. make_level_res == 0 : bk2 = i + $32 aux trois deltas 0, -1, +1.
t, p = funny(seed=5, make_level_res=0, prev_block=-64, frame=7)
for b, v in ((0x101, 0x20), (0x102, 0x42), (0x103, 0x0F)):
    t.map.blk[b] = v
t.do_funny()
chk(p.block == 0x102, "prev_block -64 porte le bloc de $142 a $102 (%d)"
    % p.block)
chk(t.map.bk2[0x102] == 0x32 and t.map.bk2[0x101] == 0x33
    and t.map.bk2[0x103] == 0x34,
    "branche 0 : bk2 = i+$32 aux trois deltas 0, -1, +1 ( %02X/%02X/%02X )"
    % (t.map.bk2[0x102], t.map.bk2[0x101], t.map.bk2[0x103]))
chk(t.map.blk[0x102] == 0x42 and t.map.blk[0x101] == 0x20
    and t.map.blk[0x103] == 0x0F,
    "branche 0 ne touche PAS a map_blk")

# 5a bis : meme branche, eau et $10 sur les memes deltas -> saut.
t, p = funny(seed=51, make_level_res=0, prev_block=-64, frame=7)
for b, v in ((0x101, 0x10), (0x102, 0x00), (0x103, 0x20)):
    t.map.blk[b] = v
t.do_funny()
chk(t.map.bk2[0x102] == 0 and t.map.bk2[0x101] == 0
    and t.map.bk2[0x103] == 0x34,
    "branche 0 : l'eau ($00) et $10 laissent bk2 a zero ( TST.B ;44692 / "
    "CMP #$10 ;446a6 ), seul $20 est ecrit ( %02X/%02X/%02X )"
    % (t.map.bk2[0x102], t.map.bk2[0x101], t.map.bk2[0x103]))

# 5b. make_level_res == 1 : blk = $35 sur $0F, $1F, $20 et $42.
t, p = funny(seed=6, block=0x243, make_level_res=1, prev_block=-65, frame=7,
             offspring=8, weapons=5, w6=5)
for b, v in ((0x202, 0x0F), (0x1C2, 0x1F), (0x201, 0x20)):
    t.map.blk[b] = v
t.do_funny()
chk(p.block == 0x202, "prev_block -65 porte le bloc de $243 a $202 (%d)"
    % p.block)
chk(t.map.blk[0x202] == 0x35 and t.map.blk[0x1C2] == 0x35
    and t.map.blk[0x201] == 0x35,
    "branche 1 : $0F, $1F et $20 deviennent $35 ( %02X/%02X/%02X )"
    % (t.map.blk[0x202], t.map.blk[0x1C2], t.map.blk[0x201]))

# 5b bis : $42 accepte, une valeur hors liste refusee.
t, p = funny(seed=61, block=0x243, make_level_res=1, prev_block=-65, frame=7,
             offspring=8, weapons=5, w6=5)
for b, v in ((0x202, 0x42), (0x1C2, 0x21), (0x201, 0x20)):
    t.map.blk[b] = v
avant_bk2 = bytes(t.map.bk2)
t.do_funny()
chk(t.map.blk[0x202] == 0x35 and t.map.blk[0x1C2] == 0x21
    and t.map.blk[0x201] == 0x35,
    "branche 1 : $42 ecrit, $21 refuse ( BNE.S LAB_4471A ) "
    "( %02X/%02X/%02X )" % (t.map.blk[0x202], t.map.blk[0x1C2],
                            t.map.blk[0x201]))
chk(bytes(t.map.bk2) == avant_bk2, "branche 1 ne touche PAS a map_bk2")

# 5c. make_level_res >= 2 : blk = i + $2F, puis a_putpixel avec la couleur
#     lue **apres** l'ecriture -- donc toujours $19.
t, p = funny(seed=7, block=0x0C1, make_level_res=2, prev_block=+65, frame=7,
             offspring=12, weapons=9, w6=9)
for b in (0x102, 0x142, 0x103):
    t.map.blk[b] = 0x20
pixels = []
t.minimap_pixel = lambda b, c: pixels.append((b, c))
t.do_funny()
chk(p.block == 0x102, "prev_block +65 porte le bloc de $C1 a $102 (%d)"
    % p.block)
chk(t.map.blk[0x102] == 0x2F and t.map.blk[0x142] == 0x30
    and t.map.blk[0x103] == 0x31,
    "branche 2 : blk = i+$2F sur les trois deltas 0, +64, +1 "
    "( %02X/%02X/%02X )" % (t.map.blk[0x102], t.map.blk[0x142],
                            t.map.blk[0x103]))
chk(pixels == [(0x102, 0x19), (0x142, 0x19), (0x103, 0x19)],
    "a_putpixel appele une fois par ecriture, avec _map_colour[$2F..$31] = "
    "$19 : %s" % pixels)

# 5c bis : eau et $10 laissent la case et le pixel de cote.
t, p = funny(seed=71, block=0x0C1, make_level_res=2, prev_block=+65, frame=7,
             offspring=12, weapons=9, w6=9)
for b, v in ((0x102, 0x20), (0x142, 0x00), (0x103, 0x10)):
    t.map.blk[b] = v
pixels = []
t.minimap_pixel = lambda b, c: pixels.append((b, c))
t.do_funny()
chk(t.map.blk[0x102] == 0x2F and t.map.blk[0x142] == 0x00
    and t.map.blk[0x103] == 0x10,
    "branche 2 : l'eau ($00) et $10 sont sautes ( BEQ.S LAB_44772 )")
chk(pixels == [(0x102, 0x19)],
    "un seul pixel pour une seule ecriture : %s" % pixels)

# --- 6 : ordre interne, mort, prev_block nul, occupant -----------------------
# 6a. valid_move == 1 -> la creature meurt sans bouger. A noter que
#     map_who est **deja efface** : le CLR de ;445a2 precede ;445e0.
t, p = funny(seed=8, block=0x0000, prev_block=-64, frame=7)
t.map.who[0x0000] = 0xD2
t.do_funny()
chk(p.life == 0 and p.block == 0x0000,
    "valid_move($0000,-64) == 1 : life = 0 et le bloc ne bouge pas "
    "( ;445e0- ;445fa )")
chk(t.map.who[0x0000] == 0,
    "map_who[$0000] est deja a zero : le CLR de ;445a2 precede la mort")

# 6b. prev_block nul -> repeint depuis _funny[make_level_res*12].
for code, (prev, armes, petits) in enumerate(FUNNY):
    t, p = funny(seed=9 + code, make_level_res=code, prev_block=0,
                 frame=7, offspring=petits, weapons=armes, w6=armes)
    t.do_funny()
    chk(p.prev_block == s16(prev),
        "prev_block nul est repeint depuis _funny[%d] : %d ( %d signe )"
        % (code, p.prev_block, s16(prev)))

# 6c. map_who[nb] != 0 -> l'occupant est tue.
t, p = funny(seed=20, make_level_res=0, prev_block=-64, frame=7)
for b in (0x101, 0x102, 0x103):
    t.map.blk[b] = 0x20
victime = t.peeps[5]
victime.life, victime.tribe, victime.state = 100, 1, ST_EXPLORER
victime.block, victime.prev_block = 0x101, 0
victime.offspring, victime.weapons = 0, 0
t.map.who[0x101] = 6
t.map.who[0x142] = 0xD2
t.do_funny()
chk(victime.life == 0,
    "map_who[$101] == 6 : la peep 5 est tuee par _zero_population "
    "( ;4477a- ;447ae )")
chk(t.map.who[0x101] == 0,
    "map_who[$101] remis a zero par _zero_population")
chk(t.map.who[0x142] == 0,
    "map_who de l'ancienne case efface au depart ( ;44580- ;445a2 )")
chk(t.map.who[0x102] == 0xD2,
    "map_who[e.block] = idx + 1 = 210 sur la nouvelle case "
    "( ;447c2- ;447d4 )")

# 6d. la seconde fiche ecrit 211. ``funny()`` rend la 209 : on la bannit et
#     on arme la 210 a la main.
t = Sim(21)
t.peeps[0xD1].life = 0
q = t.peeps[0xD2]
q.life, q.tribe, q.state = 1, 1, ST_EXPLORER
q.block, q.prev_block, q.make_level_res = 0x142, -64, 0
q.frame, q.face, q.offspring, q.weapons, q.w6 = 7, 1, 4, 0, 0
t.do_funny()
chk(t.peeps[0xD1].life == 0, "la fiche 209, morte, n'a rien ecrit")
chk(t.map.who[q.block] == 0xD3,
    "fiche 210 : map_who = 211 ( idx + 1, ;447d4 )")

# --- 7 : appel reel ----------------------------------------------------------
from populous.game import Game  # noqa: E402

g = Game(58, 0, 3)
g.sim.do_place_funny(1, 0)
p = g.sim.peeps[0xD1]
chk(p.life == 1, "le peep drole est pose par _do_place_funny")
f0 = p.frame
g.tick()
chk(p.frame == f0 + 1 and g.sim.game_turn == 1,
    "Game.tick() appelle bien _do_funny : frame %d -> %d, game_turn %d"
    % (f0, p.frame, g.sim.game_turn))

trace = []
_fa, _ma = g.sim.do_funny, g.sim.move_peeps
g.sim.do_funny = types.MethodType(
    lambda self: (trace.append("funny"), _fa())[1], g.sim)
g.sim.move_peeps = types.MethodType(
    lambda self: (trace.append("move"), _ma())[1], g.sim)
g.tick()
chk(trace[:2] == ["funny", "move"],
    "L680-681 : _do_funny appele AVANT _move_peeps ( %s )" % trace[:2])

# La garde de ;3e942- ;3e94c, sur les deux appels a la fois.
for nom in ("pause", "paint_map"):
    h = Game(58, 0, 3)
    h.sim.do_place_funny(1, 0)
    q = h.sim.peeps[0xD1]
    setattr(h.sim, nom, 1)
    b0, f0, t0 = q.block, q.frame, h.sim.game_turn
    h.tick()
    chk((q.block, q.frame, h.sim.game_turn) == (b0, f0, t0),
        "_%s != 0 : ni _do_funny ni _move_peeps ne tournent "
        "( ;3e942- ;3e94c )" % nom)
    setattr(h.sim, nom, 0)
    h.tick()
    chk(h.sim.game_turn == t0 + 1 and q.frame == f0 + 1,
        "_%s remis a zero : les deux appels reprennent" % nom)

# _run_commands reste hors garde : LAB_3EC88 de l'image n'est pas sous
# les memes tests.
h = Game(58, 0, 3)
h.sim.pause = 1
appels = []
h._run_commands = lambda: appels.append("cmd")
h.tick()
chk(appels == ["cmd"],
    "_run_commands tourne meme en pause ( LAB_3EC88 hors garde )")

# --- synthese ---------------------------------------------------------------
print()
if ECHECS:
    print("%d ECHEC(S) :" % len(ECHECS))
    for m in ECHECS:
        print("  - " + m)
    sys.exit(1)
print("OK - tous les controles passent")
