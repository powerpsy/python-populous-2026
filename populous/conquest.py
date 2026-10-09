"""Conquest : les 495 niveaux de ``level.dat``.

``level.dat`` = **990 octets = 99 entrées de 10 octets** (« the game has
99 * 5 = 495 levels », L12322-12323). Une entrée décrit un *palier* ; le
niveau affiché est ``numero // 5``.

Décodage des 10 colonnes, **celui du listing** - les symboles viennent de
l'en-tête commenté du désassemblage (L24329-24348) et les rôles des
instructions qui les lisent :

======  =======================  =========================  ==============
col     symbole                  rôle                       preuve
======  =======================  =========================  ==============
0       ``_conquest``            seuil de la tribu 1        L407-408
1       ``conq_01_speed``        période des décisions IA   L410-411
2       ``conq_02_enemypow``     pouvoirs ennemis, bitfield  L414-418, L12666
3       ``conq_03_yourpow``      pouvoirs du joueur, bits    L419-423, L12633
4       ``conq_04_mode``         bits de ``_game_mode``     L425-427
5       ``conq_05_terrain``      sol, ``0..3``              L395-399
6       ``conq_06_yourpop``      population de départ        L7660
7       ``conq_07_enemypop``     population ennemie          L7762
8-9     ``conq_08_seed`` (mot)   graine du relief           L388-391
======  =======================  =========================  ==============

**Ce qui a fait changer le décodage.** Une lecture précédente voyait
« couleur » en 2, « graine » en 3, « mana de départ » en 8 et 9. Trois
preuves du listing l'excluent :

* ``conq_08_seed`` est un **mot** (``DS.W 1`` à 518b2, L24347-24348) et
  L390 l'additionne à ``(in_conquest & 7)`` pour former ``_seed`` : la
  graine est donc en 8-9, et non en 3 ;
* ``line_0`` (L12631-12671) fait ``AND`` de ``conq_03_yourpow`` puis de
  ``conq_02_enemypow`` avec ``1 << (index - 10)`` pour choisir entre deux
  images : ce sont deux **bitfields de pouvoirs**, pas des scalaires ;
* la colonne 9 du fichier (``level.dat``) n'accepte, d'après la liste des
  valeurs admises (L24327), **que** les mots de la forme ``0019 001e ...
  6302 ... 7e8e`` : le mot ``6302`` de l'entrée 0 y figure. ``data[3]``
  en 0x3F, lui, est un bitfield a six bits (L24321).

Il n'existe **aucune** mana de départ par niveau : L1070 pose 399 pour
les deux tribus, et ``conq_08`` n'est lu nulle part ailleurs que L390.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # racine du projet
_CANDIDATES = (ROOT / "reference" / "original" / "extracted" / "level.dat",
               ROOT / "extracted" / "level.dat")

LEVEL_ENTRIES = 99
LEVEL_PER_ENTRY = 5           # 99 * 5 = 495
LEVEL_COUNT = LEVEL_ENTRIES * LEVEL_PER_ENTRY

# modes de jeu (§5.2, colonne 4) - bits de `_game_mode`
MODE_GIVE_PEEPS = 0x01
MODE_CASTLES = 0x02
MODE_HIGH_ONLY = 0x04
MODE_SWAMP = 0x08
MODE_WATER = 0x10


class ConquestLevel:
    """Une entrée de 10 octets, prête à être appliquée à la carte."""

    __slots__ = ("index", "number", "threshold", "ai_period", "enemypow",
                 "yourpow", "mode", "terrain", "yourpop", "enemypop",
                 "seed")

    def __init__(self, index: int, data: bytes) -> None:
        self.index = index
        self.number = index + 1                       # numero affiche (1..99)
        self.threshold = data[0]                      # _conquest, L407-408
        self.ai_period = data[1]                      # conq_01_speed, L410-411
        self.enemypow = data[2]                       # conq_02_enemypow, L415
        self.yourpow = data[3]                        # conq_03_yourpow, L420
        self.mode = data[4]                           # conq_04_mode, L425-427
        self.terrain = data[5] & 3                    # conq_05_terrain, L395
        self.yourpop = data[6]                        # conq_06_yourpop, L7660
        self.enemypop = data[7]                       # conq_07_enemypop, L7762
        # conq_08_seed est un MOT (L24347-24348) lu en grand-endian par
        # `ADD.W (conq_08_seed,A4),D0` (L390) : deux octets, 8 puis 9.
        self.seed = (data[8] << 8) | data[9]

    @property
    def playable(self) -> bool:
        """Vrai si la colonne « population ennemie » est remplie (§5.2)."""
        return self.enemypop > 0 and self.mode != 0

    @property
    def powers(self) -> tuple[int, int]:
        """``(ennemi, joueur)`` : les deux bitfields deja composés comme
        L414-418 et L419-423 les composent - ``(col << 3) | 7``."""
        return ((self.enemypow << 3) | 7, (self.yourpow << 3) | 7)

    def setup_kwargs(self) -> dict:
        """Paramètres lus par :meth:`populous.game.Game.load_conquest`.

        Chaque cle correspond a une lecture du listing, et a elle seule :
        aucun de ces champs n'est derive ni converti ici.
        """
        return {
            "seed": (self.number & 7) + self.seed,    # L388-391
            "ground": self.terrain,                   # L395-399
            "mode": self.mode,                        # L425-427
            "yourpop": self.yourpop,                  # L7660
            "enemypop": self.enemypop,                # L7762
            "threshold": self.threshold,              # L407-408
            "ai_period": self.ai_period,              # L410-411
            "enemypow": self.enemypow,                # L414-418
            "yourpow": self.yourpow,                  # L419-423
        }

    def __repr__(self) -> str:                        # pragma: no cover
        return ("ConquestLevel(n=%d graine=%d sol=%d mode=0x%02X "
                "pop=%d/%d pow=%02X/%02X)"
                % (self.number, self.seed, self.terrain, self.mode,
                   self.yourpop, self.enemypop, self.enemypow, self.yourpow))


def _load_raw() -> list[bytes]:
    for p in _CANDIDATES:
        if p.exists():
            b = p.read_bytes()
            return [b[i * 10:(i + 1) * 10] for i in range(len(b) // 10)]
    return []


# cache des 99 entrees
_LEVELS: list[ConquestLevel] = []


def load_levels() -> list[ConquestLevel]:
    """Les 99 entrées de ``level.dat`` (vide si le fichier est absent)."""
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
    """Applique un palier et renvoie les kwargs de la partie (§5.2).

    ``seed = (in_conquest & 7) + conq_08_seed`` avec ``in_conquest =
    level_no`` (L388-391).
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
