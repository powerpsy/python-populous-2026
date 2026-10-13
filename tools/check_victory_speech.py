# -*- coding: utf-8 -*-
"""Controle d'execution de l'ecran du Seigneur — `_won_conquest` (Phase 81).

Le discours de fin se joue sur trois details que l'on ne peut pas relire :
les **couleurs** de la bouche, sa **position**, et son **rythme**. Ce
controle confronte les trois au port, en execution.

Ce que le listing affirme et que l'on verifie ici
-------------------------------------------------

* ``_draw_mouth`` (L19894-19923) recopie des blocs de 48 pixels **sans
  masque** : il n'y a pas de transparence, l'index 0 est opaque. Un appel
  pose ``$0023 = 35`` lignes, ce qui couvre exactement les 35 lignes de
  l'image precedente — la « bouche qui parle » est un changement d'image,
  pas un defilement.
* ``_tcmap[0..15]`` est rempli par ``_read_lord`` avec les 16 mots de
  ``lord.pic`` (L16645-16648). La bouche se teinte donc avec la palette
  **du portrait**, pas avec ``_palette`` — c'est le point central de la
  Phase 81.
* Les deux appels du listing posent les **yeux** (bouche n. 5) en
  ``(x=$10, y=$4B)`` (L14652-14658) et la **bouche** en
  ``(x=$12, y=$87)`` (L14721-14727).
* Une iteration de la boucle d'attente vaut quatre vblanks (les quatre
  ``_waittof`` de L14717-14720).
* ``(-108)`` — la bouche courante — n'avance que si ``_check_effect(2)``
  rend **zero**, c'est-a-dire tant que la voie 2 sonne encore
  (L14731-14732), et rebrousse ``(-110)`` aux extremites 4 et 0
  (L14733-14740). Par ailleurs les deux branches « hors fenetre de mots »
  remettent ``(-108) = 0`` et ``(-110) = 1`` a chaque iteration
  (L14661-14662 et L14714-14715) : la bouche ne peut donc osciller que
  pendant les iterations ou l'on dit un mot, precisement celles ou
  ``c`` **n'avance pas** faute de canal libre. Les deux tables de mots,
  ``_end_words`` (L24783) et ``_words`` (L24786), sont lues de la meme
  facon.
* Les deux lignes d'en-tete sont des ``_text`` **nus** en ``x = 8`` pixels
  (le listing fait ``LSR.W #3``, L19978) et ``y = $B2`` / ``$BA``
  (L14526, L14588).

::

    python tools\\check_victory_speech.py
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

from populous.assets import FONT, load_mouths, load_portrait, palette_rgb  # noqa: E402
from populous.conquest_win import (BATTLE_OVER_TRY, BLOC_H, BLOC_X,  # noqa: E402
                                   BLOC_Y, END_WORDS, GENESIS,
                                   NOTES, NOW_BATTLE_AT, WELL_DONE,
                                   WELL_DONE_CONQ, YOU_CONQUERED, WORDS,
                                   YEUX_X, YEUX_Y,
                                   code_monde, note, texte_fin)
from populous.game import Game  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ASM = ROOT / "reference" / "tetracorp" / "populous_prg.asm"

ECHECS = []
TOTAL = [0]


def chk(cond, msg):
    TOTAL[0] += 1
    print(("  ok    " if cond else "  ECHEC ") + msg)
    if not cond:
        ECHECS.append(msg)


lignes = ASM.read_text(encoding="utf-8").splitlines()


def asm(n):
    return lignes[n - 1].strip()


# --- 1 : les faits du listing que le port est cense refaire -----------------
chk("MULU\t#$0348,D0" in asm(19906),
    "L19906 : une bouche = MULU #$0348 = 840 octets")
chk("(A1)+,(A0)" in asm(19911) and "(A1)+,($1F40,A0)" in asm(19913)
    and "(A1)+,($3E80,A0)" in asm(19915) and "(A1)+,($5DC0,A0)" in asm(19917),
    "L19911-19917 : les quatre plans vont dans _w_screen, +$1F40, +$3E80, "
    "+$5DC0, sans aucun test de masque")
chk("$00000028,A0" in asm(19919) and "DBF\tD0,LAB_4CCFC" in asm(19920),
    "L19919-19920 : A0 avance de $28 octets, une ligne d'ecran, et DBF "
    "repete $0023 = 35 fois — soit exactement l'image precedente")
# x de _draw_mouth est un offset d'octets : pas de LSR.W #3, contrairement
# a `_text` (L19978). C'est la difference qui met la bouche sur la figure.
chk("MOVE.W\t($C,A5),D0" in asm(19898) and "EXT.L\tD0" in asm(19899)
    and "ADDA.L\tD0,A0" in asm(19900),
    "L19898-19900 : `_draw_mouth` ajoute x tel quel a A0 — aucun `LSR.W #3`, "
    "donc x compte en **octets** (8 pixels), pas en pixels")
chk("($C,A5),D0" in lignes[19976] and "LSR.W\t#3,D0" in asm(19978),
    "L19978 : `_text`, lui, fait bien `LSR.W #3` — x y compte en pixels. "
    "Les deux routines ne prennent donc pas x dans la meme unite")
chk(BLOC_X == 0x12 and YEUX_X == 0x10 and BLOC_X * 8 == 144
    and YEUX_X * 8 == 128 and BLOC_Y == 0x87 and YEUX_Y == 0x4B,
    "le port convertit bien : bouche en x = $12 x 8 = 144 px, y = 135 ; "
    "yeux en x = $10 x 8 = 128 px, y = 75")
# les deux appels : yeux (5, 0x4B) puis bouche ((-108), 0x87)
yeux = "".join(asm(n) for n in range(14652, 14659))
bouche = "".join(asm(n) for n in range(14721, 14728))
chk("#$004b" in yeux and "#$0023" in yeux and "#$0005" in yeux,
    "L14652-14658 : les yeux = _draw_mouth(_w_screen, $10, $4b, $23, 5)")
chk("#$0087" in bouche and "#$0023" in bouche and "#$0012" in bouche,
    "L14721-14727 : la bouche = _draw_mouth(_w_screen, $12, $87, $23, (-108))")
chk(all(("(_waittof,PC)" in asm(n)) for n in range(14717, 14721)),
    "L14717-14720 : quatre `_waittof` par iteration, puis le dessin")
chk("TST.W\tD0" in asm(14731) and "BNE.S\tLAB_48F46" in asm(14732),
    "L14731-14732 : la bouche n'avance que si `_check_effect(2)` rend zero")
chk("BGE.S\tLAB_48F42" in asm(14736) and "BGT.S\tLAB_48F46" in asm(14738)
    and "NEG.W\t(-110,A5)" in asm(14740),
    "L14736-14740 : (-108) rebrousse a 4 et a 0 en inversant (-110)")
chk("CLR.W\t(-108,A5)" in asm(14590) and "_palette,A4),A0" in asm(14595)
    and "ADD.W\t#$0010,D1" in asm(14597) and "_tcmap,A4),A1" in asm(14600)
    and "CMPI.W\t#$0010,(-108,A5)" in asm(14603),
    "L14590-14603 : `_tcmap[16+i] = _palette[i]` — boucle une seule fois, "
    "avant `_make_copper` (L14610) qui ne tourne donc jamais en boucle")
chk("PEA\t$7D00.W" in asm(16640) and "_w_screen,A4),-(A7)" in asm(16641)
    and "PEA\t$20.W" in asm(16645) and "_tcmap,A4)" in asm(16646),
    "L16640-16646 : `_read_lord` lit 32000 octets dans `_w_screen` puis 32 "
    "octets — 16 mots — dans `_tcmap[0..15]`")

# --- 2 : les chaines du discours, prises dans les DC.B ----------------------
chk("WELL DONE " in asm(21396) and "YOU CONQUERED " in asm(21400),
    "L21396/L21400 : strWellDone et strYouConquered")
chk(WELL_DONE == "WELL DONE " and YOU_CONQUERED == " YOU CONQUERED ",
    "le port a les memes chaines : %r / %r" % (WELL_DONE, YOU_CONQUERED))
chk(WELL_DONE_CONQ == "WELL DONE YOU HAVE CONQUERED EVIL",
    "L21410 : strWellDoneConq = %r" % WELL_DONE_CONQ)
chk(BATTLE_OVER_TRY == "THE BATTLE IS OVER BUT TRY ",
    "L21416 : strBattleOverTry = %r" % BATTLE_OVER_TRY)
chk(NOW_BATTLE_AT == " NOW BATTLE AT ",
    "L21404 : strNowBattleAt = %r" % NOW_BATTLE_AT)
chk(asm(21356) == 'DC.B\t"MORTAL",0' and asm(21392) == 'DC.B\t"ETERNAL GOD",0',
    "L21356/L21392 : les bornes de `_con_text[0x18 + monde]`")
chk(note(0) == "MORTAL" and note(2250) == "ETERNAL GOD"
    and note(250) == NOTES[1],
    "note(monde) = `_con_text[0x18 + monde]` : MORTAL, IMMORTAL, ... ETERNAL GOD")
chk(END_WORDS == (0, 1, 3, 5, 6),
    "L24783-24785 : `_end_words` = %s" % (END_WORDS,))
chk(len(WORDS) == 20 and WORDS[0] == 9 and WORDS[1] == -1,
    "L24786-24789 : `_words` fait 20 mots, deux par monde, avec des $FFFF")
chk(code_monde(0) == "RING" + "OUT" + "HILL"
    and code_monde(0x1234) == "IMM" + "EA" + "MAR",
    "L14793-14889 : `_code` = _start[&31] + _mid[>>5] + _end[>>10]")

# --- 3 : les bouches, teintees par la palette du portrait -------------------
g = Game(59, 0, 3)                        # pygame.init() est dedans
portrait = load_portrait()
chk(portrait is not None, "lord.pic est lisible (32000 + 32 octets)")
fond, pal = portrait
chk(len(pal) == 16, "_tcmap compte 16 couleurs, reelles : %s" % (pal[:3],))
chk(pal != palette_rgb(),
    "la palette de lord.pic differe bien de `_palette` — c'est elle qui "
    "doit teinter la bouche")

jeu_palet = palette_rgb()
bouche_palet = load_mouths()               # sans argument : `_palette`
bouche_lord = load_mouths(pal)             # avec `_tcmap`
chk(len(bouche_palet) == 6,
    "load_mouths() sans argument retombe sur `_palette` (outillage)")
chk(len(bouche_lord) == 6, "6 bouches : 0..4 les bouches, 5 les yeux")
chk(all(s.get_size() == (48, 35) for s in bouche_lord),
    "chaque bouche fait 48 x 35 — 35 lignes de 48 pixels (L19919-19920)")
mal = []
b = (ROOT / "reference" / "original" / "extracted" / "mouths.pic").read_bytes()
if not b:
    b = (ROOT / "extracted" / "mouths.pic").read_bytes()
for k in range(6):
    d = b[k * 840:(k + 1) * 840]
    for y in (0, 17, 34):
        for x in (0, 7, 23, 47):
            base = y * 24
            idx = 0
            for q in range(4):
                if d[base + q * 6 + x // 8] >> (7 - x % 8) & 1:
                    idx |= 1 << q
            rgb = tuple(bouche_lord[k].get_at((x, y))[:3])
            if rgb != pal[idx]:
                mal.append((k, x, y, idx, rgb, pal[idx]))
chk(not mal,
    "chaque pixel des 6 bouches porte `_tcmap[idx]` et non `_palette[idx]` "
    "(%d ecarts sur les echantillons)" % len(mal))
if mal:
    print("        premier ecart :", mal[0])

# L19911-19917 ne teste aucun masque : le blit doit ecraser le fond.
fond_sol = pygame.Surface((48, 35))
fond_sol.fill((1, 2, 3))
fond_sol.blit(bouche_lord[0], (0, 0))
chk(fond_sol.get_at((0, 0))[:3] == tuple(bouche_lord[0].get_at((0, 0))[:3]),
    "un blit de bouche ecrase le fond : pas de transparence "
    "(L19911-19917 ne teste aucun masque)")
chk(BLOC_H == 0x23 == bouche_lord[0].get_height(),
    "$0023 = 35 lignes recopies = la hauteur exacte d'une bouche : l'appel "
    "couvre donc l'image precedente en entier")


# --- 4 : la boucle du discours, en execution --------------------------------
g.load_conquest(1)
g._end_game(False)                        # victoire en conquete
chk(g.game_ended and g.victory_speech,
    "`_end_game(gagne)` en conquete ouvre le discours (L14408-14416)")
chk(g.victory_texte[0].startswith(WELL_DONE) and g.victory_texte[0].endswith(
    YOU_CONQUERED),
    "premiere ligne = strWellDone + note + strYouConquered : %r"
    % g.victory_texte[0])
chk(g.victory_texte[1].endswith(NOW_BATTLE_AT + g._message),
    "seconde ligne = monde + strNowBattleAt + _message : %r"
    % g.victory_texte[1])
chk(g.victory_flag == g.conquest_fini,
    "(-122,A5) = le mode est boucle ou non")
chk(g.victory_mouth == 0 and g.victory_dir == 1 and g.victory_counter == 0,
    "(-108) = 0, (-110) = 1, (-120) = 0 au depart (L14615-14618)")
chk(len(g.victory_mouths) == 6 and g.victory_fond.get_size() == (320, 200),
    "portrait 320x200 pose dans `_w_screen`, plus les 6 bouches")

# 4a : cadence — une iteration = 4 images
# (`_check_effect(2)` est remplace par un stub : la boucle n'a pas besoin de
# carte son, et l'on veut controler la porte exactement.)
occupe = [False]
g.sound.check_effect = lambda voie: not occupe[0]     # CheckIO : fini ?
g.sound.play = lambda son, voie: None
g.victory_mouth = 3
g.victory_dir = -1
bruit = []
for _ in range(8):
    g.image()
    bruit.append((g.victory_counter, g.victory_mouth))
chk(bruit[0] == bruit[1] == bruit[2] == (0, 3),
    "les trois premieres images ne font rien : les 4 `_waittof` (L14717-14720)")
chk(bruit[3] == (1, 0) and bruit[7] == (2, 0),
    "une iteration par quatre images : %s" % (bruit,))

# 4b : l'oscillation — `(-108)` n'avance que si la voie 2 sonne encore
# Le point delicat du listing : la branche « c hors de [10..14] » **remet**
# `(-108) = 0` et `(-110) = 1` a chaque iteration (L14661-14662 et
# L14714-14715). Le bouche ne peut donc osciller que pendant les trois ou
# cinq iterations ou l'on dit un mot, precisement celles qui sautent ce
# remise : c'est la que la voie 2 est occupee par un echantillon.
g.victory_flag = True
g.victory_counter = 10
g.victory_mouth = 0
g.victory_dir = 1
g.victory_vblank = 3
occupe[0] = True                                      # la voie 2 sonne
suite = []
for _ in range(40):
    g.image()
    suite.append(g.victory_mouth)
chk(g.victory_counter == 10,
    "la voie sonne encore : `_check_effect(2) == 0`, le mot suivant n'est "
    "pas relance et c reste bloque a 10 (L14631-14632)")
# une iteration = 4 images : on ne garde qu'une bouche sur quatre
tri = suite[::4][:10]
attendu = [1, 2, 3, 4, 3, 2, 1, 0, 1, 2]
chk(tri == attendu,
    "(-108) oscille en triangle 1-2-3-4-3-2-1-0, une fois par iteration, et "
    "(-110) rebrousse bien a 4 et a 0 (L14733-14740) : %s" % (tri,))

# la voie se libere : le mot suivant part et la bouche se fige au repos
occupe[0] = False
for _ in range(8):
    g.image()
chk(g.victory_counter > 10, "voie libre : `_check_effect(2) != 0`, c avance")

# 4c : les mots, dans l'ordre, un par iteration
dits = []
g.sound.play = lambda son, voie: dits.append(son)
g.sound.check_effect = lambda voie: True              # la voie est toujours libre
g.victory_flag = False
g.victory_counter, g.victory_mouth, g.victory_dir = 0, 0, 1
g.victory_vblank = 3
for _ in range(80):                    # 20 iterations : c va de 0 a 19
    g.image()
chk(dits[:1] == [0], "c == 10 : `_PlaySound(0, 2)` sans condition "
    "(L14672-14676) : %s" % (dits,))
chk(dits[1:2] == [WORDS[0]] and -1 not in dits,
    "c == 11 : `_words[monde*2]` = %d ; c == 12 : `_words[monde*2+1]` = %d "
    "est negatif et n'est pas joue (L14691-14692) : %s"
    % (WORDS[0], WORDS[1], dits))
# et, la voie etant toujours libre, la bouche ne bouge jamais
chk(g.victory_mouth == 0,
    "voie toujours libre : `(-108)` est remis a 0 a chaque iteration "
    "(L14714) puisque `_check_effect(2) != 0`")

# 4d : la meme chose en mode « termine », avec `_end_words`
dits = []
g.sound.play = lambda son, voie: dits.append(son)
g.victory_flag = True
g.victory_counter = 9
g.victory_mouth, g.victory_dir = 0, 1
g.victory_vblank = 3
for _ in range(40):
    g.image()
chk(g.victory_counter > 9,
    "c == 9 : rien n'est joue, mais c avance jusqu'a 10 : %s" % (dits,))
chk(dits == list(END_WORDS),
    "c == 10..14 : `_end_words` dit ses 5 sons dans l'ordre : %s" % (dits,))
chk(g.victory_eyes, "c == 16 : les yeux (bouche n. 5) sont poses une fois "
                    "(L14650-14658)")

# --- 5 : le clic sort et fait avancer le palier -----------------------------
no = g.conquest_no
g._raw_left = False                                  # le bouton se relache
for _ in range(4):
    g.image()
g._raw_left = True                                   # puis il s'enfonce
for _ in range(5):
    g.image()
chk(g.victory_speech is False and g.game_ended is False,
    "le clic vide `_left_button` (L14620-14621) et rend la main (L14743-14744)")
chk(g.conquest_no == g.conquest_next or g.conquest_next == 0,
    "`_next_conquest` a tourne : palier %d -> %d" % (no, g.conquest_no))

# --- 6 : sans lord.pc, pas de discours mais le clic marche quand meme ------
g2 = Game(60, 0, 3)
g2.load_conquest(1)
import populous.assets as _a
_orig = _a.load_portrait
_a.load_portrait = lambda: None                         # LAB_48F84
try:
    g2._end_game(False)
finally:
    _a.load_portrait = _orig
chk(g2.game_ended and not g2.victory_speech,
    "sans lord.pic, `_read_lord` rend 0 et tout le discours saute (L14513)")
chk(g2.conquest_next == 0, "et le niveau avance est annule (L14760-14761)")
g2._raw_left = True
g2.image()
chk(g2.game_ended is False, "le clic d'attente de `_end_game` marche quand meme")

# --- 7 : les glyphes rendus dans `_tcmap` ----------------------------------
# `_text` ecrit dans l'ecran courant : sur l'ecran de victoire, le glyphe se
# teinte donc dans `_tcmap`, pas dans `_palette`. Le meme glyphe doit donc
# prendre deux couleurs selon la palette passee.
a = FONT.glyph(ord("A"))
b2 = FONT.glyph(ord("A"), None, pal)
diff = [p for p in range(64)
        if tuple(a.get_at((p % 8, p // 8))[:3])
        != tuple(b2.get_at((p % 8, p // 8))[:3])]
chk(diff, "`glyph(code, palette)` rend dans `_tcmap` : %d pixel(s) du glyphe "
           "A changent de couleur avec la palette de lord.pic" % len(diff))

print()
if ECHECS:
    print("%d/%d controle(s) en echec :" % (len(ECHECS), TOTAL[0]))
    for m in ECHECS:
        print("  -", m)
    sys.exit(1)
print("check_victory_speech : %d/%d OK" % (TOTAL[0], TOTAL[0]))
