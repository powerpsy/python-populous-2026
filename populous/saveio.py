# -*- coding: utf-8 -*-
"""Paquetage et depaquetage du fichier de sauvegarde.

`_save_game` (L17123) ecrit 25 blocs d'affilee ; `_load_game` (L17412) les
relit dans le meme ordre. Ce module fait le pont entre ces blocs et les
objets Python du port.

Le format lui-meme est dans `populous/savegame.py`, verifie champ par champ
contre le listing par `tools/check_savegame.py`. Ici on ne fait que ranger les
valeurs dans les octets.

**Trois mises en page** sont necessaires, toutes deja documentees dans
`populous/sim.py` :

* la fiche de tribu, **46 octets** (`Tribe`) ;
* la fiche d'unite, **22 octets** (`Peep`) ;
* `_magnet`, **16 mots** (`$20`), dont le port ne garde que les six premiers
  sous forme nommee.

Les champs dont l'ecriture ou la lecture n'a jamais ete tracee sont mis a
zero et **comptes** ici, pour qu'un fichier reste bit-compatible avec la
taille annoncee par le listing.
"""
from __future__ import annotations

from populous.savegame import BLOCS_CHECKSUM, CHAMPS, MAGIE

# --------------------------------------------------------------------------
# la fiche de tribu, 46 octets. Les decalages sont ceux de `Tribe`
# (sim.py) : `+0` act, `+1` p1, `+2` p2, `+6` can_build, `+8` queued,
# `+0x0C` threshold, `+0x0E` power_mask, `+0x10` period, `+0x12` t12,
# `+0x14` castles, `+0x16` towns, `+0x18`/`+0x1A`/`+0x1C`/`+0x1E`, `+0x20`
# colour, `+0x22` strongest, `+0x26` p26, `+0x2A` p2a.
TAILLE_TRIBU = 0x2E

TRIBU = [
    ("act",        0x00, "b"),
    ("p1",         0x01, "b"),
    ("p2",         0x02, "b"),
    ("can_build",  0x06, "h"),
    ("queued",     0x08, "h"),
    ("threshold",  0x0C, "h"),
    ("power_mask", 0x0E, "h"),
    ("period",     0x10, "h"),
    ("t12",        0x12, "h"),
    ("castles",    0x14, "h"),
    ("towns",      0x16, "h"),
    ("t18",        0x18, "h"),
    ("t1a",        0x1A, "h"),
    ("t1c",        0x1C, "h"),
    ("t1e",        0x1E, "h"),
    ("colour",     0x20, "h"),
    ("strongest",  0x22, "h"),
    ("p26",        0x26, "l"),
    ("p2a",        0x2A, "l"),
]

# --------------------------------------------------------------------------
# la fiche d'unite, 22 octets. `face` occupe l'octet **haut** du mot `+0x14`
# (commentaire de `Peep.face` dans sim.py) : le mot assemble les deux.
TAILLE_PEEP = 0x16

# `state` est un **octet** : les bits 3 et 7 de `peep+0x00` sont la bataille
# et le compte a rebours (game_logic 9.3), et `tribe` occupe deja l'octet +1.
PEEP = [
    ("state",        0x00, "b"),
    ("tribe",        0x01, "b"),
    ("offspring",    0x02, "b"),
    ("weapons",      0x03, "b"),
    ("life",         0x04, "h"),
    ("w6",           0x06, "h"),
    ("block",        0x08, "h"),
    ("prev_block",   0x0A, "h"),
    ("frame",        0x0C, "h"),
    ("target",       0x0E, "l"),
    ("spawn_block",  0x12, "h"),
    ("make_level_res", 0x14, "h"),
    ("face",         0x15, "b"),
]

# `_peeps` vaut $1222 octets, soit 211 fiches de 22 octets (L17239) - et non
# les 212 du port (`PEEP_SLOTS`). Le listing n'en ecrit donc que 211 ; la
# derniere fiche reste a zero cote saving. ECART declare.
PEEPS_DANS_FICHIER = 0x1222 // TAILLE_PEEP        # 211

# `_magnet`, $20 = 16 mots (L17232)
MOTS_MAGNET = 0x20 // 2                           # 16


def _h(v: int) -> bytes:
    return (v & 0xFFFF).to_bytes(2, "big")


def _l(v: int) -> bytes:
    return (v & 0xFFFFFFFF).to_bytes(4, "big")


def _hlu(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 2], "big", signed=False)


def _llu(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 4], "big", signed=False)


def _signe(v: int) -> int:
    """Ramène un mot ou un long non signé dans l'intervalle signe du port."""
    return v - 0x10000 if v >= 0x8000 else v


def _signe32(v: int) -> int:
    return v - 0x100000000 if v >= 0x80000000 else v


# ---------------------------------------------------------------------- tribus
def pack_tribu(t) -> bytes:
    """Les 46 octets de la fiche `_stats` (ou `strABC`)."""
    b = bytearray(TAILLE_TRIBU)
    for nom, off, genre in TRIBU:
        v = getattr(t, nom)
        if genre == "b":
            b[off] = v & 0xFF
        elif genre == "h":
            b[off:off + 2] = _h(v)
        else:
            b[off:off + 4] = _l(v)
    return bytes(b)


def unpack_tribu(b: bytes, t) -> None:
    for nom, off, genre in TRIBU:
        if genre == "b":
            setattr(t, nom, b[off])
        elif genre == "h":
            setattr(t, nom, _signe(_hlu(b, off)))
        else:
            setattr(t, nom, _signe32(_llu(b, off)))


# ---------------------------------------------------------------------- peeps
def pack_peep(p) -> bytes:
    """Les 22 octets de la fiche `_peeps`."""
    b = bytearray(TAILLE_PEEP)
    for nom, off, genre in PEEP:
        if nom == "make_level_res":
            # l'octet haut du mot porte `face` (sim.py) : on les assemble
            v = (p.face << 8) | (p.make_level_res & 0xFF)
            b[off:off + 2] = _h(v)
            continue
        v = getattr(p, nom)
        if genre == "b":
            b[off] = v & 0xFF
        elif genre == "h":
            b[off:off + 2] = _h(v)
        else:
            b[off:off + 4] = _l(v)
    return bytes(b)


def unpack_peep(b: bytes, p) -> None:
    for nom, off, genre in PEEP:
        if nom == "make_level_res":
            p.make_level_res = b[off] & 0xFF
            continue
        if genre == "b":
            setattr(p, nom, b[off])
        elif genre == "h":
            setattr(p, nom, _signe(_hlu(b, off)))
        else:
            setattr(p, nom, _signe32(_llu(b, off)))


# --------------------------------------------------------------- terrain
def pack_alt(alt) -> bytes:
    """`_alt`, `$2102` = 4225 sommets en 16 bits (65 x 65), grand-boutiste."""
    return b"".join(_h(v) for v in alt)


def unpack_alt(b: bytes, terrain) -> None:
    terrain.alt = [_hlu(b, i * 2) for i in range(0x1081)]


# --------------------------------------------------------------- assemblage
def pack_moteur(g, chemin: str) -> bytes:
    """Le fichier complet de `g`, dans l'ordre exact des 25 `Write`."""
    sim, terr = g.sim, g.terrain
    blocs = {
        "alt": pack_alt(terr.alt),
        "map_alt": bytes(terr.disp_alt),
        "map_blk": bytes(terr.blk),
        "map_bk2": bytes(terr.bk2),
        "map_who": bytes(terr.who),
    }
    blocs["good_pop"] = sum(p.life for p in sim.peeps if p.tribe == 0)
    blocs["bad_pop"] = sum(p.life for p in sim.peeps if p.tribe == 1)

    from populous.savegame import terrain_checksum
    somme = terrain_checksum(blocs)

    # `_magnet` : 16 mots. Le port garde six champs nommes par joueur
    # (`Player`), pour deux joueurs ; le listing en a seize, un par joueur
    # plus les sixteen emplacements. ECART : les dix derniers mots sont a
    # zero.
    aimant = bytearray(0x20)

    scalaires = {
        "magic": _l(MAGIE),
        "magnet": bytes(aimant),
        "peeps": b"".join(pack_peep(p)
                          for p in sim.peeps[:PEEPS_DANS_FICHIER]),
        "stats0": pack_tribu(sim.stats[0]),
        "stats1": pack_tribu(sim.stats[1]),
        "mode": _h(sim.mode),
        "seed": _h(g.seed),
        "start_seed": _h(g.seed),          # ECART, cf. savegame.py
        "player": _h(sim.player),
        "ground_in": _h(sim.ground_in),
        "war": _h(sim.war),
        "game_turn": _h(sim.game_turn),
        "conquest": bytes(0x0A),            # ECART, non suivi par le port
        "in_conquest": _h(sim.in_conquest),
        "paint_map": _h(sim.paint_map),
        "battle_won": _l(0),                # ECART, non suivi par le port
        "game_mode": _h(sim.game_mode),
        "level_number": _h(0),              # ECART, non suivi par le port
        "score": _l(0),                     # ECART, non suivi par le port
        "checksum": _h(somme),
    }

    sortie = bytearray()
    for nom, _src, taille, _ligne in CHAMPS:
        if nom in blocs:              # `alt` et les quatre cartes
            bloc = blocs[nom]
        else:
            bloc = scalaires[nom]
        if len(bloc) != taille:
            raise ValueError("champ %s : %d octets produits pour %d attendus"
                             % (nom, len(bloc), taille))
        sortie += bloc
    assert len(sortie) == sum(c[2] for c in CHAMPS)
    return bytes(sortie)


def unpack_moteur(g, data: bytes) -> bool:
    """Le chemin inverse de `pack_moteur`. Rend faux si l'en-tete cloche.

    `_load_game` verifie les **quatre** premiers octets contre `$FFFFB615`
    (L17453) et, si le test manque, ferme le fichier et rend la main sans rien
    charger de plus (LAB_4B21C). Aucune taille n'est verifiee cote lecture -
    contrairement a l'ecriture. Reproduit tel quel.
    """
    if len(data) < 4 or int.from_bytes(data[:4], "big") != MAGIE:
        return False
    sim, terr = g.sim, g.terrain
    pos = 0
    champs = {}
    for nom, _src, taille, _ligne in CHAMPS:
        champs[nom] = data[pos:pos + taille]
        pos += taille
    assert pos == len(data) == sum(c[2] for c in CHAMPS)

    unpack_alt(champs["alt"], terr)
    terr.disp_alt = bytearray(champs["map_alt"])
    terr.blk = bytearray(champs["map_blk"])
    terr.bk2 = bytearray(champs["map_bk2"])
    terr.who = bytearray(champs["map_who"])

    for i, p in enumerate(sim.peeps):
        if i < PEEPS_DANS_FICHIER:
            unpack_peep(champs["peeps"][i * TAILLE_PEEP:(i + 1) * TAILLE_PEEP], p)
        else:
            p.__init__()                      # type: ignore[misc]
    unpack_tribu(champs["stats0"], sim.stats[0])
    unpack_tribu(champs["stats1"], sim.stats[1])

    sim.mode = _signe(_hlu(champs["mode"], 0))
    g.seed = _signe(_hlu(champs["seed"], 0))
    sim.player = _signe(_hlu(champs["player"], 0))
    sim.not_player = 1 - sim.player                # L17590-17595
    sim.ground_in = _signe(_hlu(champs["ground_in"], 0))
    sim.war = _signe(_hlu(champs["war"], 0))
    sim.game_turn = _signe(_hlu(champs["game_turn"], 0))
    sim.in_conquest = _signe(_hlu(champs["in_conquest"], 0))
    sim.paint_map = _signe(_hlu(champs["paint_map"], 0))
    sim.game_mode = _signe(_hlu(champs["game_mode"], 0))
    sim.land_checksum = _signe(_hlu(champs["checksum"], 0))
    return True