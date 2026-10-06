"""Carte 64 x 64 de Populous : les 5 plans mémoire et ``_valid_move``.

Plans (tailles données par l'empilement BSS du désassemblage, §1.1 de
``docs/game_logic.md``) :

==============  ==========  ================================================
plan            taille      rôle
==============  ==========  ==================================================
``map_blk``     4096 B      type de la case (mer, plat, bâtiment, marais…)
``map_alt``     4096 B      altitude : **0 = eau**, **< 7 = constructible**
``map_bk2``     4096 B      plan « arrière » : sprite de ville / arbre / rocher
``map_steps``   4096 w      étapes du chemin (champ de vision + case survolée)
``map_who``     4096 B      **index + 1** du peep présent (0 = personne)
==============  ==========  ==================================================

Index : ``i = y * 64 + x`` ; décalage : ``offset = dy * 64 + dx``.
"""
from __future__ import annotations

from .constants import (
    BLK_FLAT, BLK_ROCK, BLK_WATER, MAP_CELLS, OFFSET_VECTOR, offset_to_dx,
)


class GameMap:
    """Les 5 plans de cases.

    Les tableaux peuvent être fournis par l'appelant (``Terrain``) afin que la
    simulation et le rendu partagent **les mêmes objets** : les mutations sont
    donc visibles des deux côtés sans copie.
    """

    __slots__ = ("blk", "alt", "bk2", "steps", "who")

    def __init__(self, blk=None, bk2=None, who=None, alt=None, steps=None):
        self.blk = blk if blk is not None else bytearray(MAP_CELLS)
        self.alt = alt if alt is not None else bytearray(MAP_CELLS)
        self.bk2 = bk2 if bk2 is not None else bytearray(MAP_CELLS)
        self.steps = steps if steps is not None else [0] * MAP_CELLS
        self.who = who if who is not None else bytearray(MAP_CELLS)

    # ----------------------------------------------------------------- accès
    @staticmethod
    def index(x: int, y: int) -> int:
        return y * 64 + x

    @staticmethod
    def xy(block: int) -> tuple[int, int]:
        return block & 63, block >> 6

    def clear(self) -> None:
        for arr in (self.blk, self.alt, self.bk2, self.who):
            for i in range(len(arr)):
                arr[i] = 0
        for i in range(len(self.steps)):
            self.steps[i] = 0

    # ------------------------------------------------------- voisinage (§1.4)
    def neighbours(self, block: int, n: int = 17) -> list[int]:
        """Index des cases voisines (17 = ville, 25 = grande ville).

        Les cases hors carte (hors de [0, 4095]) sont omises, exactement comme
        les appels à ``_valid_move`` le font dans ``_set_town``.
        """
        out = []
        for k in range(n):
            nb = block + OFFSET_VECTOR[k]
            if 0 <= nb < MAP_CELLS and self.valid_move(block, OFFSET_VECTOR[k]) != 1:
                out.append(nb)
        return out

    # ------------------------------------------------------ _valid_move (§1.7)
    def valid_move(self, block: int, offset: int) -> int:
        """Reconstitution exacte de ``_valid_move`` (asm $4DCE8).

        =========  ==================================================
        retour     signification
        =========  ==================================================
        0          case en carte, contenu « normal » (plat, bâtiment…)
        1          hors carte (dépassement de la table)
        2          ``map_blk == $2F`` : rocher
        3          ``map_blk == 0`` : eau
        =========  ==================================================

        ``offset == 0`` (case elle-même) renvoie 0.
        """
        if offset == 0:
            return 0
        idx = block + offset
        if idx < 0 or idx >= 0x1000:            # 4096 : borne de la table
            return 1
        # dx signé contenu dans l'offset (ANDI #$3F / ORI #$FFC0)
        dx = offset & 0x3F
        if dx > 3:
            dx -= 64
        x = (block & 0x3F) + dx
        if x < 0 or x > 0x3F:
            return 1
        v = self.blk[idx]
        if v == BLK_WATER:
            return 3
        if v == BLK_ROCK:
            return 2
        return 0

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < 64 and 0 <= y < 64

    # -------------------------------------------------------- cases utilitaires
    def is_walkable(self, block: int) -> bool:
        """``_map_blk`` non nul et non rocher : un peep peut s'y trouver."""
        v = self.blk[block]
        return v != BLK_WATER and v != BLK_ROCK and v != 0x30 and v != 0x31

    def is_flat(self, block: int) -> bool:
        return self.blk[block] == BLK_FLAT

    def buildable(self, block: int) -> bool:
        """``_map_alt`` <= 7 (contrôle de ``_check_life``/``_set_town``)."""
        return self.alt[block] <= 7

    def step(self, block: int) -> int:
        """Mot ``_map_steps`` non signé."""
        return self.steps[block]

    def set_step(self, block: int, value: int) -> None:
        self.steps[block] = value & 0xFFFF
