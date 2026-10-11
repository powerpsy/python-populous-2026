# -*- coding: utf-8 -*-
"""Les panneaux de l'ecran deux joueurs — ``_two_players`` (asm L11265).

`_two_players` est l'ecran de **liaison serie** : il arme le port, choisit la
vitesse, passe en modem ou en datalink, et appelle `_try_serial` (L11903)
jusqu'a ce que les deux machines se voient. C'est une machine a etats : le
mot `(-40,A5)` est son etat, et chaque panneau de la table ci-dessous est ce
qu'elle affiche.

La table est, comme toutes les autres du jeu, **un seul bloc de 16 entrees
de 0x2E (46) octets** a partir de `_serial_text` (L24930) : 736 octets, de
0x525da a 0x528ba.

    +0x00  W   x du panneau    (`_serial_text`)
    +0x02  W   y du panneau    (`LAB_525DC`)
    +0x04  W   largeur         (`LAB_525DE`, effacee par `_blank`)
    +0x06  40  la chaine

Le trace est decalé : `_text(x + $20, y + $2E, ...)` (L11306-11317).

| i | texte | etat |
|---|---|---|
| 0 | STARTUP SERIAL | titre (L11326-11340, index `(-42)+$0C`) |
| 1 | SEND LOGIN | L11298-11320, index `(-44)+$0E` |
| 2 | BAUD RATE | le titre de la boite |
| 3-7 | DATALINK, FULL SERIAL CHECKING, I AM GOOD, USE THIS LANDSCAPE, CONNECT ME | les options **datalink** |
| 8-11 | MODEM, NO SERIAL CHECKING, I AM EVIL, USE SAVED LANDSCAPE | les options **modem** |
| 12-15 | HE'S TRYING TO BE GOOD, ... TO BE EVIL, NOT USING A SAVED GAME, USING A SAVED GAME | les messages d'etat |

Les options des deux series ont la meme place (`$80` ou `$81` = coche) et
changent selon `_use_modem` : les lignes 12-15 disent ce que l'autre machine
annonce pendant que `_try_serial` fait son travail.

La verification est dans ``tools/check_two_players.py``.
"""
# transcrit de L24930-25040
SERIAL_X = [16] * 16
SERIAL_Y = [16, 31, 41, 51, 61, 71, 81, 91, 51, 61, 71, 81, 101, 101, 101, 101]
SERIAL_W = [0, 208, 208, 80, 96, 88, 168, 96, 56, 88, 88, 176, 11, 11, 11, 11]
SERIAL_TEXTE = [
    "STARTUP SERIAL",                 # 0  titre du mode datalink
    "SEND LOGIN",                     # 1  titre de la saisie
    "BAUD RATE",                      # 2  titre de la boite
    "\x80 DATALINK",                   # 3
    "\x80 FULL SERIAL CHECKING",       # 4
    "\x80 I AM GOOD",                  # 5
    "\x81 USE THIS LANDSCAPE",         # 6
    "\x80 CONNECT ME",                 # 7
    "\x81 MODEM",                      # 8
    "\x81 NO SERIAL CHECKING",         # 9
    "\x81 I AM EVIL",                  # 10
    "\x81 USE SAVED LANDSCAPE",        # 11
    "HE'S TRYING TO BE GOOD",         # 12
    "HE'S TRYING TO BE EVIL",         # 13
    "HE'S NOT USING A SAVED GAME",    # 14
    "HE'S USING A SAVED GAME",        # 15
]

SERIAL_NB = 16

# Les deux series d'options : 3..7 quand la liaison est directe
# (`_use_modem == 0`), 8..11 quand elle passe par un modem.
SERIAL_OPTIONS_DATALINK = (3, 4, 5, 6, 7)
SERIAL_OPTIONS_MODEM = (8, 9, 10, 11)

# Les quatre messages d'etat, dans l'ordre du listing (L25017-25039).
SERIAL_ETATS = (12, 13, 14, 15)

# `_requester(d_screen, $20, $2E, $100, $80, ...)` (L11287-11294)
SERIAL_BOXE = (0x20, 0x2E, 0x100, 0x80)

# L11267 : l'etat demarre a $3E7 = 999. Ce n'est pas une duree en
# millisecondes, c'est un compteur que chaque branche de la machine remet a
# 1 ou a 0 ; il sert surtout de "je ne suis pas encore pret".
SERIAL_ETAT_INITIAL = 0x3E7

# Les vitesses proposees sont lues dans `_b_rates` (L11701-11702) par
# `_baud_rate << 1`. La table est dans le `.data` du binaire et n'a pas ete
# transcrite ici : elle ne sert qu'a commander `_set_baud_rate` (L11703),
# qui est de toute facon une routine serie non transcrite.