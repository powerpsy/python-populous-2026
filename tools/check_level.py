# -*- coding: utf-8 -*-
"""Controle d'execution du decodage de ``level.dat`` (Phase 57a).

Le decodage des colonnes n'est pas une opinion : le listing donne, pour
chaque colonne, **l'instruction qui la lit** et, dans son en-tete
commente, **la liste exhaustive des valeurs admises**. Ce controle
relit les deux dans ``populous_prg.asm`` et les confronte au port :

1. les listes de valeurs admises sont extraites de L12324-12338 ;
2. chaque octet des 99 entrees y appartient - le fichier et
   l'en-tete sont donc coh�rents, et la colonne 8-9 forme bien un
   **mot** de la liste de L24327 ;
3. :class:`ConquestLevel` range chaque octet au rang que le listing
   lui donne (``conq_08_seed`` en 8-9, ``conq_03_yourpow`` en 3,
   ``conq_02_enemypow`` en 2, ``conq_05_terrain`` en 5) ;
4. l'ancien decodage (graine = ``data[3]``) serait **rejetable** par la
   meme liste : c'est ce qui prouve que les deux interpretations ne
   sont pas indiscernables ;
5. :func:`apply_display` rend la graine de L388-391,
   ``(in_conquest & 7) + conq_08_seed`` ;
6. les quatre ecritures de ``_setup_display`` (L407-423) arrivent sur la
   **bonne** fiche apres reconstruction de la partie, et il n'y a
   **aucune** mana de depart par niveau : les deux joueurs restent a 399
   (L1070).

::

    python tools\\check_level.py
"""
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from populous.conquest import (LEVEL_COUNT, apply_display, level,   # noqa: E402
                               load_levels)
from populous.game import Game  # noqa: E402
from populous.sim import Game as SimGame  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ASM = ROOT / "reference" / "tetracorp" / "populous_prg.asm"
DATA = ROOT / "reference" / "original" / "extracted" / "level.dat"

ECHECS = []
TOTAL = [0]


def chk(cond, msg):
    TOTAL[0] += 1
    print(("  ok    " if cond else "  ECHEC ") + msg)
    if not cond:
        ECHECS.append(msg)


# --- 1 : les listes de valeurs admises, prises dans le listing --------------
lignes = ASM.read_text(encoding="utf-8").splitlines()
# "Load level data / Valid numbers for each column" : L12324-12338.
colonnes: dict[int, set[int]] = {}
courante = None
for ln in lignes[12320:12338]:
    m = re.match(r"^; (\d+) ([0-9a-f][0-9a-f ]*)\s*$", ln)
    if m:
        courante = int(m.group(1))
        colonnes[courante] = {int(t, 16) for t in m.group(2).split()}
        continue
    m = re.match(r"^;   ([0-9a-f][0-9a-f ]*)\s*$", ln)      # continuation
    if m and courante is not None:
        colonnes[courante] |= {int(t, 16) for t in m.group(1).split()}

chk(len(colonnes) == 9, "listes extraites du listing : %d colonnes (0 a 8)"
    % len(colonnes))
chk(colonnes[5] == {0, 1, 2, 3}, "colonne 5 = {00,01,02,03} (L24323)")
chk(0x6302 in colonnes[8] and 0x0019 in colonnes[8],
    "colonne 8-9 est une liste de MOTS (L24327 : 0019 ... 6302 ...)")
chk(len(colonnes[8]) > 40, "%d graines admises en 8-9" % len(colonnes[8]))

# --- 2 : le fichier obéit a ses propres listes -------------------------------
brut = DATA.read_bytes()
chk(len(brut) == 990, "level.dat = 990 octets (%d)" % len(brut))
entrees = [brut[i * 10:(i + 1) * 10] for i in range(len(brut) // 10)]
chk(len(entrees) == 99, "99 entrees de 10 octets (%d)" % len(entrees))

hors = []
for n, d in enumerate(entrees):
    for c in range(8):
        if d[c] not in colonnes[c]:
            hors.append("entree %d col %d = %02X" % (n, c, d[c]))
    mot = (d[8] << 8) | d[9]
    if mot not in colonnes[8]:
        hors.append("entree %d col 8-9 = %04X" % (n, mot))
chk(not hors, "toutes les entrees sont dans les listes admises (%d ecarts)"
    % len(hors))
for h in hors[:5]:
    print("        ", h)

# --- 3 : le port range chaque octet ou le listing le lit --------------------
lvs = load_levels()
chk(len(lvs) == LEVEL_COUNT // 5 == 99, "99 objets ConquestLevel")
mauvais = []
for n, (d, lv) in enumerate(zip(entrees, lvs)):
    attendu = {
        "threshold": d[0],        # L407-408  _conquest
        "ai_period": d[1],        # L410-411  conq_01_speed
        "enemypow": d[2],         # L414-418  conq_02_enemypow
        "yourpow": d[3],          # L419-423  conq_03_yourpow
        "mode": d[4],             # L425-427  conq_04_mode
        "terrain": d[5] & 3,      # L395-399  conq_05_terrain
        "yourpop": d[6],          # L7660     conq_06_yourpop
        "enemypop": d[7],         # L7762     conq_07_enemypop
        "seed": (d[8] << 8) | d[9],   # L388-391 conq_08_seed (MOT)
    }
    for nom, val in attendu.items():
        if getattr(lv, nom) != val:
            mauvais.append("entree %d .%s = %r != %r" % (n, nom,
                                                         getattr(lv, nom), val))
chk(not mauvais, "les 99 entrees sont rangees comme le listing (%d ecarts)"
    % len(mauvais))
for m in mauvais[:5]:
    print("        ", m)

# --- 4 : l'ancien decodage serait refusable ---------------------------------
d0 = entrees[0]
ancien = d0[3]                            # l'interpretation retiree : data[3]
mot = (d0[8] << 8) | d0[9]
chk(mot in colonnes[8], "entree 0 : la graine vaut %04X (octets 8-9)" % mot)
chk(ancien not in colonnes[8],
    "entree 0 : l'ancienne 'graine' %04X (octet 3) n'est PAS une graine"
    % ancien)
nb = sum(1 for d in entrees if (d[8] << 8) | d[9] != d[3])
chk(nb == 99, "les deux lectures different sur %d/99 entrees (le correctif "
    "change quelque chose)" % nb)

# --- 5 : la graine de L388-391 ---------------------------------------------
mauvais = []
for n in range(1, LEVEL_COUNT // 5 + 1):
    lv = level(n)
    d = entrees[n - 1]
    attendu = ((n & 7) + ((d[8] << 8) | d[9])) & 0xFFFF   # ADD.W, L390
    if (apply_display(n)["seed"] & 0xFFFF) != attendu:
        mauvais.append("palier %d" % n)
    if lv.seed != (d[8] << 8) | d[9]:
        mauvais.append("palier %d seed" % n)
chk(not mauvais, "seed = (in_conquest & 7) + conq_08_seed pour les 99 "
    "paliers (%d ecarts)" % len(mauvais))

# --- 6 : les ecritures L407-423 sur la vraie partie -------------------------
g = Game(59, 0, 3)                          # pygame.init() est dedans
lv = level(1)
assert lv is not None
chk(g.load_conquest(1), "load_conquest(1) accepte le palier 1")
s = g.sim.stats
chk(s[1].threshold == lv.threshold,
    "stats[1].threshold = %d (L407-408, _conquest[0] = %d)"
    % (s[1].threshold, lv.threshold))
chk(s[1].period == lv.ai_period,
    "stats[1].period = %d (L410-411, conq_01_speed = %d)"
    % (s[1].period, lv.ai_period))
chk(s[1].power_mask == ((lv.enemypow << 3) | 7),
    "stats[1].power_mask = 0x%04X (L414-418, (enemypow %02X << 3) | 7)"
    % (s[1].power_mask, lv.enemypow))
chk(s[0].power_mask == ((lv.yourpow << 3) | 7),
    "stats[0].power_mask = 0x%04X (L419-423, (yourpow %02X << 3) | 7)"
    % (s[0].power_mask, lv.yourpow))
chk(g.seed == ((1 & 7) + lv.seed) & 0xFFFFFFFF,
    "seed = (1 & 7) + %d = %d (L388-391)" % (lv.seed, g.seed))
chk(all(pl.mana == 399 for pl in g.sim.players),
    "mana = 399 pour les deux tribus (L1070) : %s"
    % [pl.mana for pl in g.sim.players])
chk(lv.threshold != 0, "palier 1 : _conquest[0] = %d != 0 : stats[1].threshold "
    "vient donc de L407-408, pas de Tribe.__init__ (0), donc APRES "
    "set_ground" % lv.threshold)

# --- 7 : bit de commande de `_one_block_flat` (L9172) -----------------------
for col in (0x00, 0x20, 0x3F):
    masque = (col << 3) | 7
    chk(bool(masque & 0x100) == bool(col & 0x20),
        "col %02X -> masque 0x%04X, bit 8 %s (L416/L421 + L9172)"
        % (col, masque, "pose" if masque & 0x100 else "nul"))

# --- 8 : la valeur par defaut, hors mode conquest ---------------------------
# `.data` de `_stats` (L24171-24230) : les deux fiches sont initialisees
# avant toute partie. Tribu 0 -> $FFFF / 1 / 1, tribu 1 -> $FFFF / 5 / 3,
# et `LAB_518A7` (L24311-24312, `DC.B $10`) -> 0x10.
g2 = Game(60, 0, 3)
for t, (seuil, periode) in enumerate(((1, 1), (5, 3))):
    s2 = g2.sim.stats[t]
    chk(s2.power_mask == 0xFFFF,
        "defaut hors conquest : stats[%d].power_mask = 0x%04X "
        "(L24186 / L24224)" % (t, s2.power_mask))
    chk(s2.threshold == seuil,
        "defaut hors conquest : stats[%d].threshold = %d "
        "(L24184 / L24222)" % (t, s2.threshold))
    chk(s2.period == periode,
        "defaut hors conquest : stats[%d].period = %d "
        "(L24188 / L24226)" % (t, s2.period))
chk(g2.sim.flags == 0x10,
    "defaut hors conquest : LAB_518A7 = 0x%02X (L24311-24312, DC.B $10)"
    % g2.sim.flags)

# --- 9 : le reste du `.data` (L24171-24230) ---------------------------------
# `act/p1/p2` valent $61/$62/$63 (dc.b de L24172 pour la fiche 0, `strABC`
# de L24212 pour la fiche 1) : des codes sans effet, le dispatch sautant a
# LAB_4B818 des que `act >= $0F` (L18219-18220). `can_build` 0/1 veut dire
# « l'Amiga conduit la tribu 1 » ; `queued` 1/1 vient des deux
# `DC.L $00010000` de L24181 et L24219.
for t in (0, 1):
    s3 = g2.sim.stats[t]
    chk((s3.act, s3.p1, s3.p2) == (0x61, 0x62, 0x63),
        "defaut hors conquest : stats[%d].act/p1/p2 = %02X/%02X/%02X "
        "(L24172 / L24212)" % (t, s3.act, s3.p1, s3.p2))
chk((g2.sim.stats[0].can_build, g2.sim.stats[1].can_build) == (0, 1),
    "defaut hors conquest : can_build = %d/%d (L24177-24180 / L24215-24218)"
    % (g2.sim.stats[0].can_build, g2.sim.stats[1].can_build))
chk((g2.sim.stats[0].queued, g2.sim.stats[1].queued) == (1, 1),
    "defaut hors conquest : queued = %d/%d (L24181 / L24219)"
    % (g2.sim.stats[0].queued, g2.sim.stats[1].queued))
# `colour` : le `.data` porte 5/1 (L24203 / L24229). `_settle_peoples`
# reecrit ensuite le champ en 11/14 — L408 et L12070 font de meme dans
# l'asm, avec une table de palettes differente de celle du port. L'ecart
# est donc **assume** : on verifie la valeur `.data` sur une fiche nue,
# et l'ecart declare sur la partie complete.
g2b = SimGame(62)
chk((g2b.stats[0].colour, g2b.stats[1].colour) == (5, 1),
    "data .data : colour = %d/%d (L24203 / L24229)"
    % (g2b.stats[0].colour, g2b.stats[1].colour))
chk((g2.sim.stats[0].colour, g2.sim.stats[1].colour) == (11, 14),
    "ECART assume : _settle_peoples pose colour = %d/%d (table du port)"
    % (g2.sim.stats[0].colour, g2.sim.stats[1].colour))
# --- 10 : la periode de `queued` (L17934-17951) ----------------------------
# Le SEUL vidage de `queued` de tout le listing exige `can_build == 1` ET
# `game_turn % period == 0`. La fiche 1 (Amiga, `period = 3`) est donc
# liberee tous les 3 tours ; la fiche 0 (humaine, `can_build = 0`) ne
# l'est **jamais** — c'est ce qui eteint toute son IA.
g3 = Game(61, 0, 3)
for t in (0, 1):
    g3.sim.stats[t].queued = 1
g3.sim.game_turn = 3                  # 3 % 3 == 0
g3._run_commands()
chk(g3.sim.stats[1].queued == 0,
    "periode : queued[1] = %d a game_turn = 3, can_build == 1 (L17950)"
    % g3.sim.stats[1].queued)
chk(g3.sim.stats[0].queued == 1,
    "periode : queued[0] = %d — can_build == 0, jamais vide (L17940)"
    % g3.sim.stats[0].queued)

g4 = Game(61, 0, 3)
g4.sim.stats[1].queued = 1
g4.sim.game_turn = 4                  # 4 % 3 == 1
g4._run_commands()
chk(g4.sim.stats[1].queued == 1,
    "periode : queued[1] = %d a game_turn = 4, 4 %% 3 == 1 (L17949)"
    % g4.sim.stats[1].queued)

# `_clear_send` (L18234-18254) ne vide que `act/p1/p2` : apres un tour,
# les trois octets sont retombes, `queued` non.
g5 = Game(61, 0, 3)
s5 = g5.sim.stats[1]
s5.act, s5.p1, s5.p2 = 0x61, 0x62, 0x63
g5._run_commands()
chk((s5.act, s5.p1, s5.p2) == (15, 0, 0),
    "clear_send : act/p1/p2 = %d/%d/%d apres un tour (L18234-18254)"
    % (s5.act, s5.p1, s5.p2))

print()
if ECHECS:
    print("%d ECHEC(S) sur %d controles" % (len(ECHECS), TOTAL[0]))
    for m in ECHECS:
        print("  -", m)
    sys.exit(1)
print("check_level : %d controles, tout passe" % TOTAL[0])
