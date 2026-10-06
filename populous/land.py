"""Tables de terrain : fichiers ``LAND0``..``LAND9`` (``_load_ground``, asm $4A23E).

Format du fichier (114 octets d'en-tête + 0x8340 octets de graphismes) :

===========  ====  ==================================================
octets      taille  symbole BSS
===========  ====  ==================================================
+0            2    ``walk_death``       vie perdue à chaque déplacement
+2           22    ``population_add``   11 mots, croissance par âge
+24          22    ``mana_add``         11 mots, mana par âge / 8 tours
+46          22    ``weapons_add``      11 octets, arme par âge
+68          22    ``battle_add1``      11 mots, mana après bataille
+90           6    ``battle_add2``      3 mots
+96          16    ``map_colour``       couleurs des 16 cases de la mini-carte
+112          2    ``sprites_no``       numéro de jeu de sprites (0 ou 4)
+114      0x8340   ``blk_data``         70 tuiles 32x24 (voir assets.load_land)
===========  ====  ==================================================

Les lectures du désassemblage (lignes 16483-16530) confirment cet ordre ; le
« trou » signalé à la ligne 16504 est un simple défaut de listing : la somme
des lectures vaut exactement 114 octets, ce que confirment les fichiers du
disque original.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAME = ROOT / "reference" / "original" / "extracted"
DATA = ROOT / "extracted"

HEADER_SIZE = 114
TILES_SIZE = 0x8340          # 70 tuiles x 480 octets
N_TILES = 70
N_AGES = 11                  # âges 0..10 (frame = 0x20 + âge)


@dataclass
class LandTables:
    """Contenu de l'en-tête d'un fichier LANDn."""

    walk_death: int
    population_add: list[int] = field(default_factory=list)
    mana_add: list[int] = field(default_factory=list)
    weapons_add: list[int] = field(default_factory=list)
    battle_add1: list[int] = field(default_factory=list)
    battle_add2: list[int] = field(default_factory=list)
    map_colour: list[int] = field(default_factory=list)
    sprites_no: int = 0
    tiles: bytes = b""

    @property
    def name(self) -> str:
        return "LAND%d" % self.sprites_no


def land_path(n: int) -> Path:
    """Chemin du fichier ``land{n}`` (disque de jeu puis disque de données)."""
    for folder in (GAME, DATA):
        p = folder / ("land%d" % n)
        if p.exists():
            return p
    raise FileNotFoundError("land%d introuvable" % n)


def load_land(n: int) -> LandTables:
    """Charge l'en-tête (et les graphismes) du terrain numéro ``n``."""
    b = land_path(n).read_bytes()
    if len(b) < HEADER_SIZE:
        raise ValueError("land%d trop court" % n)
    walk_death = struct.unpack_from(">H", b, 0)[0]
    return LandTables(
        walk_death=walk_death,
        population_add=list(struct.unpack_from(">11H", b, 2)),
        mana_add=list(struct.unpack_from(">11H", b, 24)),
        weapons_add=list(struct.unpack_from(">11H", b, 46)),
        battle_add1=list(struct.unpack_from(">11H", b, 68)),
        battle_add2=list(struct.unpack_from(">3H", b, 90)),
        map_colour=list(b[96:112]),
        sprites_no=struct.unpack_from(">H", b, 112)[0],
        tiles=b[HEADER_SIZE:HEADER_SIZE + TILES_SIZE],
    )


def load_all_lands() -> dict[int, LandTables]:
    """Charge tous les terrains disponibles (0..4 sur les deux disques)."""
    out = {}
    for n in range(10):
        try:
            out[n] = load_land(n)
        except FileNotFoundError:
            break
    return out


if __name__ == "__main__":
    for i, land in sorted(load_all_lands().items()):
        print("land%d  walk_death=%d  pop=%s  mana=%s"
              % (i, land.walk_death, land.population_add[:5], land.mana_add[:5]))
