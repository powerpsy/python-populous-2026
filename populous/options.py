# -*- coding: utf-8 -*-
"""Table des options de ``_options`` (asm L13617, ouv par l'entree (0,0)
de la barre d'icones - Phase 67).

Les quatorze lignes de la boite de dialogue vivent dans une table de 14
entrees de 0x2E (46) octets a partir de ``_option_text`` (L24363) :

    +0x00  W   x de la ligne     (``_option_text``)
    +0x02  W   y de la ligne     (``LAB_51912``)
    +0x04  W   largeur du test   (``LAB_51914``)
    +0x06  40  la chaine, octet 0 = la **coche** ($80 eteinte, $81 allumee)

La verification est dans ``tools/check_options.py``, qui relit la table
directement dans le listing.
"""
# transcrit de L24363-24462 ; x, y, w et chaine brute de chaque entree
OPTIONS_X = [36, 32, 32, 32, 32, 32, 32, 32, 32, 32, 100, 72, 120, 64]
OPTIONS_Y = [16, 32, 41, 50, 59, 67, 76, 85, 94, 103, 122, 131, 141, 150]
OPTIONS_W = [128, 8, 8, 8, 8, 8, 8, 8, 8, 8, 32, 104, 32, 112]
OPTIONS_TEXTE = [
    "OPTIONS FOR EVIL",                       # 0 : + le nom, strcpy L13671
    "\x80 CAN MODIFY LAND",                     # 1
    "\x80 CAN ATTACK TOWNS",                    # 2
    "\x80 CAN ATTACK LEADER",                   # 3
    "\x80 CAN USE EARTHQUAKES",                 # 4
    "\x80 CAN USE SWAMP",                       # 5
    "\x80 CAN USE KNIGHT",                      # 6
    "\x80 CAN USE VOLCANO",                     # 7
    "\x80 CAN USE FLOOD",                       # 8
    "\x80 CAN USE ARMAGEDDON",                  # 9
    "AGGRESSION",                              # 10 : etiquette
    "LOW\x84\x85\x85\x85\x85\x85\x85\x85\x85\x86HIGH",   # 11 : curseur
    "RATE",                                    # 12 : etiquette
    "SLOW\x84\x85\x85\x85\x85\x85\x85\x85\x85\x86FAST",  # 13 : curseur
]

# les 9 cases a cocher (entrees 1..9) masquent le mot `power_mask`
# (`LAB_516B2`, `_stats + 0x0E`) bit par bit : la boucle L13690-13710
# part de `1` et decale a gauche a chaque entree.
OPTIONS_CASES = 9
