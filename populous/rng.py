"""Générateur aléatoire original de Populous (``_newrand``, asm $4C2E6).

::

    D0 = _seed (mot)
    D0 = D0 * $24A1            ; MULU -> 32 bits
    D0.W += $24DF              ; ADDI.W (mot faible seul)
    BCLR #15,D0                ; bit 15 toujours nul
    _seed = D0.W
    retourne D0 (long)

Les appelsants font ``EXT.L D0`` (prend le mot faible, signé) puis ``DIVS #n`` :
le mot faible étant toujours <= $7FFF, ``newrand() % n`` revient à un modulo
non signé sur 15 bits.
"""
from __future__ import annotations


class Rng:
    """Équivalent exact de la boucle de tirage du jeu."""

    __slots__ = ("seed",)

    def __init__(self, seed: int = 0):
        self.seed = seed & 0xFFFF

    def raw(self) -> int:
        """Renvoie D0 (32 bits) comme le fait ``_newrand``."""
        d0 = (self.seed * 0x24A1) & 0xFFFFFFFF
        low = ((d0 & 0xFFFF) + 0x24DF) & 0xFFFF
        d0 = (d0 & 0xFFFF0000) | low
        d0 &= 0xFFFF7FFF                 # BCLR #15
        self.seed = d0 & 0xFFFF          # MOVE.W D0,_seed
        return d0

    def below(self, n: int) -> int:
        """``newrand() % n`` — modulo signé 15 bits, comme dans le jeu."""
        if n <= 0:
            raise ValueError("n > 0 requis")
        return (self.raw() & 0xFFFF) % n

    def rand_range(self) -> int:
        """Mot faible signé (0..32767) : la valeur réellement exploitée."""
        return self.raw() & 0xFFFF

    def copy(self) -> "Rng":
        return Rng(self.seed)
