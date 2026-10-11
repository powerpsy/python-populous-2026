# -*- coding: utf-8 -*-
"""Table de l'ecran *SET GAME OPTIONS* de ``_set_options`` (asm L13362).

`_set_options` est appele par la ligne 11 (*GAME OPTIONS*) du dialogue
`GAME SETUP` (L13256). Ses onze lignes sont decrites par **un seul** tableau
de 11 entrees de 0x2E (46) octets a partir de `_set_text` (L24845) :

    +0x00  W   x de la ligne      (`_set_text`, L24845)
    +0x02  W   y de la ligne      (`LAB_523B0`, L24847)
    +0x04  W   largeur du test    (`LAB_523B2`, L24849)
    +0x06  40  la chaine ; l'octet 0 est la **coche**, $80 eteinte et $81
               allumee

Meme decoupage que `GAME SETUP` (Phase 69) : `_set_text` (0x523ae),
`LAB_523B0` (0x523b0) et `LAB_523B2` (0x523b2) sont trois vues du meme bloc
de **506 octets**, decalees de 0, 2 et 4 octets depuis `strGameOptions`
(0x523b4). Le bloc finit a 0x5259c.

L'entree 0 est le titre. Les dix autres sont **cinq paires** de choix
exclusifs, tous a x = 16, de meme y, et de largeur 8 - la zone cliquable
n'est donc que les **huit pixels de la coche**. Le choix actif de chaque paire
porte $81, l'autre $80, et correspond au bit `j` de `_game_mode` :

| paire | bit | coeffue | laisse |
|---|---|---|---|
| 1-2 | 0 | WATER IS HARMFUL | WATER IS FATAL |
| 3-4 | 1 | SWAMPS SHALLOW | SWAMPS BOTTOMLESS |
| 5-6 | 2 | CAN BUILD | CANNOT BUILD |
| 7-8 | 3 | BUILD UP AND DOWN | ONLY BUILD UP |
| 9-10 | 4 | BUILD NEAR PEOPLE | BUILD NEAR TOWNS |

Avec `_game_mode == 0` - sa valeur BSS, L24310 - les **cinq premiers** sont
actifs. L'octet 0 de chaque chaine du ROM porte deja la bonne coche pour
`_game_mode = 0`, mais le prologue de L13386-13446 la redessine de toute
facon.

La verification est dans ``tools/check_set_options.py``, qui relit le tableau
directement dans le listing.
"""
# transcrit de L24845-24913
SET_OPTIONS_X = [48, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16]
SET_OPTIONS_Y = [25, 40, 40, 50, 50, 60, 60, 70, 70, 80, 80]
SET_OPTIONS_W = [118, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8]
SET_OPTIONS_TEXTE = [
    "SET GAME OPTIONS",             # 0  : le titre
    "\x80 WATER IS HARMFUL",         # 1  paire 0, colonne 1
    "\x81 WATER IS FATAL",           # 2  paire 0, colonne 2
    "\x80 SWAMPS SHALLOW",           # 3  paire 1, colonne 1
    "\x81 SWAMPS BOTTOMLESS",        # 4  paire 1, colonne 2
    "\x80 CAN BUILD",                # 5  paire 2, colonne 1
    "\x81 CANNOT BUILD",             # 6  paire 2, colonne 2
    "\x80 BUILD UP AND DOWN",        # 7  paire 3, colonne 1
    "\x81 ONLY BUILD UP",            # 8  paire 3, colonne 2
    "\x80 BUILD NEAR PEOPLE",        # 9  paire 4, colonne 1
    "\x81 BUILD NEAR TOWNS",         # 10 paire 4, colonne 2
]

# L13384-13446 : la boucle va de j = 0 a 4, et pour chaque j deux colonnes
# (1 ou 2). L'index vaut `2*j + colonne`.
SET_OPTIONS_NB = 11
SET_OPTIONS_PAIRES = 5

# L13490-13587 : le survol n teste que les colonnes **impaires**
# (1, 3, 5, 7, 9) - `ADDQ.W #2` puis `CMPI.W #$000A` - parce que la colonne
# paire de la meme ligne porte la meme boite a la meme position.
SET_OPTIONS_SURVOL = (1, 3, 5, 7, 9)

# `_requester(d_screen, $20, $18, $100, $70, ...)` (L13367-13372)
SET_OPTIONS_BOXE = (0x20, 0x18, 0x100, 0x70)

# `_blank` (L24915) : onze carats, dessine par-dessus l'ancienne ligne pour
# l'effacer avant d'ecrire la coche. Ce n'est donc pas un espace.
SET_OPTIONS_BLANC = "^^^^^^^^^^^"

# Le listing marque L13447-13482 « new code added here » : une rustine de
# debug affiche le numero de terrain sous le titre. « LANDSCAPE NO » fait
# douze caracteres, le `strcpy` y ajoute un espace en position 12, et
# `_word_asc` ecrit le nombre a partir de `buf + 13` — donc juste apres cet
# espace, en recouvrant le zero de fin. La chaine rendue est donc
# « LANDSCAPE NO <n> ».
SET_OPTIONS_PASTICHE = ("LANDSCAPE NO ", 13)