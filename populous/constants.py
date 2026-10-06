"""Constantes exactes de Populous, extraites du désassemblage 68000.

Toutes ces tables sont dans la zone données de ``populous_prg.asm`` et ont été
relues octet par octet (adresses indiquées en commentaire).

Convention de la carte : index ``= y * 64 + x``, 64 x 64 cases.
Convention de décalage : ``offset = dy * 64 + dx``.
"""
from __future__ import annotations

MAP_W = 64
MAP_H = 64
MAP_CELLS = MAP_W * MAP_H          # 4096

MAX_PEEPS = 0xD0                   # 208 (L6984)
PEEP_LIFE0 = 0x2D                  # 45 (L7026)

# ---------------------------------------------------------------- tables voisins
# _offset_vector, $0005181A (asm 24274-24278) : 25 mots
#  0..8   = carré 3x3 (centre + 8 voisins)
#  9..16  = 8 cases à distance 2 (droites + diagonales)
#  17..24 = 8 cases en « L » (±2,±1 / ±1,±2)
OFFSET_VECTOR = [
    0, -64, 1, 64, -1, -63, 65, 63, -65,
    -128, 2, 128, -2, -126, 130, 126, -130,
    -127, -62, 66, 129, 127, 62, -66, -129,
]
N_NEIGHBOURS = 17                  # ville      (CMP #$11, ligne 5937)
N_BIG_NEIGHBOURS = 25              # grande ville (CMP #$19, lignes 5904/5978)

# _to_offset, $0005180A (asm 24272-24273) : 8 directions, ordre N NE E SE S SO O NO
TO_OFFSET = [-64, -63, 1, 65, 64, 63, -1, -65]

# _opposite, A4+$83BA : 8 mots, relus dans les OCTETS du DAD (offset
# fichier $14754). Chaque entree donne la direction opposee, et la
# contrainte « doit inverser le deplacement » suffit a la valider toute
# seule : 0<->4 (N/S), 1<->5 (NE/SO), 2<->6 (E/O), 3<->7 (SE/NO).
OPPOSITE = [4, 5, 6, 7, 0, 1, 2, 3]

# _dir_sprite, $00051850 (asm 24281-24282) : même chose, ordre NO N NE E SE S SO O
DIR_SPRITE = [-65, -64, -63, 1, 65, 64, 63, -1]

# _to_delta, $000517F8 (asm 24269-24271) : 9 mots
#
# Lecture **big-endian**, comme le 68000 — verifie par execution contre
# `_to_offset` ci-dessus, dont les huit valeurs sont exactes. Une premiere
# tentative avait inverse les paires en decodant les DC.L a la main ; le
# script de confrontation a montré que c'etait la tentative qui etait fausse.
# Ne pas relire ces DC.L a l oeil.
TO_DELTA = [7, 6, 5, 0, 0, 4, 1, 2, 3]

# _big_city, $00051862 (asm 24284-24286) : 9 sprites internes d'une grande ville
# _big_city, $00051862 (asm 24284-24286) : 9 mots
#   DC.L $002a002c,$002b002c,$002b0029,$00290029 ; DC.W $0029
BIG_CITY = [0x2A, 0x2C, 0x2B, 0x2C, 0x2B, 0x29, 0x29, 0x29, 0x29]

# _mana_values, $00051874 (asm 24287-24304) : les 11 crans de la jauge
MANA_VALUES = [
    -250, 10, 200, 2_500, 5_000, 7_500,
    10_000, 40_000, 80_000, 160_000, 2_000_063,
]

# Couts des pouvoirs : ce sont les **valeurs** des seuils de `_mana_values`
# (§4.1 de docs/game_logic.md), pas les indices.
COST_RAISE = 10           # 10
COST_MAGNET = 200         # 200
COST_QUAKE = 2_500        # 2 500
COST_SWAMP = 5_000        # 5 000
COST_KNIGHT = 7_500       # 7 500
COST_VOLCANO = 10_000     # 10 000
COST_FLOOD = 40_000       # 40 000
COST_WAR = 80_000         # 80 000

# Les memes, comme indice dans MANA_VALUES (pour la jauge).
LEVEL_RAISE, LEVEL_MAGNET, LEVEL_QUAKE, LEVEL_SWAMP = 1, 2, 3, 4
LEVEL_KNIGHT, LEVEL_VOLCANO, LEVEL_FLOOD, LEVEL_WAR = 5, 6, 7, 8

# ------------------------------------------------------------- codes _map_blk
BLK_WATER = 0x00        # mer : valid_move renvoie 3
BLK_FLAT = 0x0F         # case à plat, constructible
BLK_TRIBE0 = 0x1F       # $1F + tribu : bâtiment / ville
BLK_TRIBE1 = 0x20
BLK_ROCK = 0x2F         # rocher : valid_move renvoie 2
BLK_ROCK2 = 0x30
BLK_ROCK3 = 0x31
BLK_SWAMP = 0x35
BLK_RUINS = 0x42        # après bataille

# ------------------------------------------------------------- codes _map_bk2
BK2_NONE = 0x00
BK2_CITY = (0x21, 0x2C)          # ville normale
BK2_BIGCITY = 0x2A               # centre d'une grande ville
BK2_TREE = (0x32, 0x34)          # arbres (rotation)

# ------------------------------------------------------------------ états peep
ST_VILLAGER = 0x01
ST_EXPLORER = 0x02
ST_ANIM = 0x04
ST_BATTLE = 0x08
ST_DROWNING = 0x10
ST_DEATHCOUNT = 0x80

FRAME_TOWN = 0x2A                # 42 = « grande ville »
FRAME_AGE = 0x20                 # frame = 0x20 + âge (0..10)

# ------------------------------------------------------- codes d'action (_stats)
ACT_NONE = 0
ACT_RAISE = 1
ACT_LOWER = 2
ACT_QUAKE = 3
ACT_SWAMP = 4
ACT_MAGNET = 5
ACT_VOLCANO = 6
ACT_PLACE0 = 7
ACT_PLACE1 = 8
ACT_PLACE0_M = 9
ACT_PLACE1_M = 10
ACT_TREE = 11
ACT_ROCK = 12
ACT_REMOVE = 13
ACT_ACTION = 14
ACT_NOP = 15

# sous-commandes de _do_action (code 14)
SUB_NONE = 0
SUB_TEND = 1
SUB_SERIAL = 2
SUB_WAR = 3
SUB_FLOOD = 4
SUB_KNIGHT = 5
SUB_PAUSE = 6
SUB_CROSS = 7
SUB_UNK8 = 8
SUB_HALVE0 = 9
SUB_DOUBLE0 = 10
SUB_ROTATE = 11
SUB_CLEAR = 12
SUB_GROUND = 13
SUB_NOP = 14
SUB_CHEAT = 15


def offset_to_dx(offset: int) -> int:
    """dx signé contenu dans un décalage d'index (logique valid_move, asm 4dd08)."""
    dx = offset & 0x3F
    if dx > 3:
        dx -= 64
    return dx


def offset_to_dy(offset: int) -> int:
    return (offset - offset_to_dx(offset)) // 64
