# -*- coding: utf-8 -*-
"""Table du dialogue ``GAME SETUP`` de ``_game_options`` (asm L12801).

`_game_options` est le handler du code 8 de `_do_action`, arme par l'entree
`(1,1)` de la barre d'icones. Ses dix-sept lignes de boite de dialogue sont
decrites par **un seul** tableau de 17 entrees de 0x2E (46) octets a partir de
`_game_text` (L24494) :

    +0x00  W   x de la ligne      (`_game_text`, L24494)
    +0x02  W   y de la ligne      (`LAB_51BDE`, L24496)
    +0x04  W   largeur du test    (`LAB_51BE0`, L24498)
    +0x06  40  la chaine ; l'octet 0 est la **coche**, $80 etant allumee
               (l'entree cochee) et $81 eteinte. Reecrit a chaque clic
               (L12987, L12992, ...)

Point d'asm qui meritait d'etre releve : `_game_text`, `LAB_51BDE` et
`LAB_51BE0` ne sont **pas** trois tables, mais trois vues du meme tableau,
indexees avec le pas 0x2E et decalees de 0, 2 et 4 octets :

    LAB_51BDE = 0x51bde = strGameSetup (0x51be2) - 4
    LAB_51BE0 = 0x51be0 = strGameSetup - 2
    _game_text = 0x51bdc = strGameSetup - 6

Chaque entree du listing porte d'ailleurs l'etiquette de sa vue : le
libelle `strOnePlayer` (L24508) est l'entree 1, `strGameSetup` (L24500) est
l'entree 0. Le bloc fait 782 octets, de 0x51bdc a 0x51eea, ou commence
`_c_text` (L24622).

Les dix premiere lignes sont cinq paires de boutons radio en deux colonnes
(x = 16 et x = 152) ; les sept dernieres sont les actions, centrees
(x = 80, largeur 128).

La verification est dans ``tools/check_game_setup.py``, qui relit le tableau
directement dans le listing.
"""
# transcrit de L24494-24620
GAME_SETUP_X = [112, 16, 152, 16, 152, 16, 152, 16, 152, 16, 152, 80,
                80, 80, 80, 80, 80]
GAME_SETUP_Y = [16, 36, 36, 46, 46, 56, 56, 66, 66, 76, 76, 95, 105, 115,
                125, 135, 145]
GAME_SETUP_W = [72, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 128, 128, 128, 128, 128,
                128]
GAME_SETUP_TEXTE = [
    "GAME SETUP",             # 0  : le titre, handler no-op (LAB_47D94)
    "\x80 ONE PLAYER",          # 1
    "\x80 TWO PLAYERS",         # 2
    "\x80 PLAY GAME",           # 3
    "\x80 PAINT MAP",           # 4
    "\x80 GOOD",                # 5
    "\x80 EVIL",                # 6
    "\x80 HUMAN VS AMIGA",      # 7
    "\x80 AMIGA VS AMIGA",      # 8
    "\x80 CONQUEST",            # 9
    "\x80 CUSTOM GAME",         # 10
    "\x80 GAME OPTIONS",        # 11
    "\x80 SAVE A GAME",         # 12
    "\x80 LOAD A GAME",         # 13
    "\x80 MOVE TO NEXT MAP",    # 14
    "\x80 RESTART THIS MAP",    # 15
    "\x80 SURRENDER THIS GAME",  # 16
]

# La boucle de trace (L12901-12924) va de 0 a 16 inclus : 17 entrees.
GAME_SETUP_NB = 17

# La table de sauts (L13292-13308) : handler de chaque ligne, dans l'ordre.
# La 0 est `LAB_47D94`, un simple `BRA` vers la sortie.
GAME_SETUP_HANDLERS = [
    "LAB_47D94",   # 0  titre : rien
    "LAB_47968",   # 1  ONE PLAYER
    "LAB_479CC",   # 2  TWO PLAYERS
    "LAB_47A1C",   # 3  PLAY GAME
    "LAB_47A4A",   # 4  PAINT MAP
    "LAB_47A7A",   # 5  GOOD
    "LAB_47B3E",   # 6  EVIL
    "LAB_47C04",   # 7  HUMAN VS AMIGA
    "LAB_47C5E",   # 8  AMIGA VS AMIGA
    "LAB_47CBA",   # 9  CONQUEST
    "LAB_47D00",   # 10 CUSTOM GAME
    "LAB_47D30",   # 11 GAME OPTIONS
    "LAB_47D3E",   # 12 SAVE A GAME
    "LAB_47D56",   # 13 LOAD A GAME
    "LAB_47D72",   # 14 MOVE TO NEXT MAP
    "LAB_47D7C",   # 15 RESTART THIS MAP
    "LAB_47D8A",   # 16 SURRENDER THIS GAME
]

# Hauteur de la boite : `_requester(d_screen, $10, $10, $120, $B0, ...)`
# (L12891-12896). Plus grande que celle d'`_options` ($A6) parce que la
# colonne de droite est a x = 152.
GAME_SETUP_BOXE = (0x10, 0x10, 0x120, 0xB0)

# L12974-12978 : en conquete (`_in_conquest != -1`) les neuf premieres
# lignes sont neutralisees - l'index saute a $13, au-dela du tableau, et
# `LAB_47DB8` retombe alors sur le no-op.
GAME_SETUP_CONQUEST_MAX = 9