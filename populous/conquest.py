"""Conquest : les 495 niveaux de ``level.dat``.

``level.dat`` = **990 octets = 99 entrées de 10 octets** (« the game has
99 * 5 = 495 levels », 5 niveaux par entrée). Une entrée décrit un *palier* ;
le niveau affiché est ``numero // 5``.

Décodage vérifié des 10 colonnes (``docs/game_logic.md`` §5.1, colonnes 0-9) :

=====  =========================================  ==========================
col    champ                                      exemple (entrée 0)
=====  =========================================  ==========================
0     difficulties / numéro de niveau             ``0x0A``
1     difficulties                                ``0x0A``
2     couleur / décalage initial                   ``0x00``
3     **graine** (valeurs 0..63)                   ``0x3F``
4     **mode de jeu** (0,1,3,4,8,10,16,17,18)     ``0x03``
5     **terrain** (0..3) → ``land0..land3``        ``0x00``
6     points de départ / décor                     ``0x03``
7    Crystal : nombre d'ennemis                    ``0x03``
8    Crystal :Bonus de départ                      ``0x63``
9     Crystal :Mana / décalage (croissant)         ``0x02``
=====  =========================================  ==========================

La colonne 3 est la graine du relief : ``seed = (in_conquest & 7) + graine``
(§5.2). 495 niveaux = 99 entrées × 5.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # racine du projet
_CANDIDATES = (ROOT / "reference" / "original" / "extracted" / "level.dat",
               ROOT / "extracted" / "level.dat")

LEVEL_ENTRIES = 99
LEVEL_PER_ENTRY = 5           # 99 * 5 = 495
LEVEL_COUNT = LEVEL_ENTRIES * LEVEL_PER_ENTRY

# modes de jeu (§5.2, colonne 4) — bits de `_game_mode`
MODE_GIVE_PEEPS = 0x01
MODE_CASTLES = 0x02
MODE_HIGH_ONLY = 0x04
MODE_SWAMP = 0x08
MODE_WATER = 0x10


class ConquestLevel:
    """Une entrée de 10 colonnes, prête à être appliquée à la carte."""

    __slots__ = ("index", "number", "difficulty1", "difficulty2", "colour",
                 "seed", "mode", "terrain", "n_peeps", "n_enemies",
                 "start_mana", "mana_offset")

    def __init__(self, index: int, data: bytes) -> None:
        self.index = index
        self.number = index + 1                       # numero affiche (1..99)
        self.difficulty1 = data[0]
        self.difficulty2 = data[1]
        self.colour = data[2]
        self.seed = data[3]                           # graine du relief
        self.mode = data[4]
        self.terrain = data[5] & 3                    # 0..3
        self.n_peeps = data[6]
        self.n_enemies = data[7]
        self.start_mana = data[8]
        self.mana_offset = data[9]

    @property
    def playable(self) -> bool:
        """Vrai si la colonne « nombre d'ennemis » estfillable (§5.2)."""
        return self.n_enemies > 0 and self.mode != 0

    def setup_kwargs(self) -> dict:
        """Parametres passes a :meth:`populous.game.Game.set_mode_conquest`."""
        return {
            "seed": (self.number & 7) + self.seed,
            "ground": self.terrain,
            "mode": self.mode,
            "n_peeps": self.n_peeps,
            "n_enemies": self.n_enemies,
            "start_mana": self.start_mana,
            "ai_period": self.difficulty2 or 1,
        }

    def __repr__(self) -> str:                        # pragma: no cover
        return ("ConquestLevel(n=%d graine=%d sol=%d mode=0x%02X "
                "peeps=%d ennemis=%d mana=%d)"
                % (self.number, self.seed, self.terrain, self.mode,
                   self.n_peeps, self.n_enemies, self.start_mana))


def _load_raw() -> list[bytes]:
    for p in _CANDIDATES:
        if p.exists():
            b = p.read_bytes()
            return [b[i * 10:(i + 1) * 10] for i in range(len(b) // 10)]
    return []


# cache des 99 entrees
_LEVELS: list[ConquestLevel] = []


def load_levels() -> list[ConquestLevel]:
    """Les 99 entrees de ``level.dat`` (vide si le fichier est absent)."""
    global _LEVELS
    if not _LEVELS:
        _LEVELS = [ConquestLevel(i, d) for i, d in enumerate(_load_raw())]
    return _LEVELS


def level(n: int) -> ConquestLevel | None:
    """Palier ``n`` (1..99) ; renvoie ``None`` hors limites."""
    levels = load_levels()
    if not levels:
        return None
    return levels[max(0, min(len(levels) - 1, n - 1))]


def apply_display(level_no: int) -> dict | None:
    """Applique un palier et renvoie les kwargs pour :class:`Game` (§5.2).

    ``seed = (in_conquest & 7) + conq_08_seed`` avec ``in_conquest = level_no``.
    """
    lv = level(level_no)
    return lv.setup_kwargs() if lv is not None else None


if __name__ == "__main__":                            # pragma: no cover
    levels = load_levels()
    print("%d entrees, %d niveaux" % (len(levels), LEVEL_COUNT))
    for lv in levels[:6]:
        print(" ", lv)
    print("  ...")
    for lv in levels[-3:]:
        print(" ", lv)