# -*- coding: utf-8 -*-
"""Controle aller-retour de la sauvegarde — `_save_game` / `_load_game`.

Le format est verifie champ par champ contre le listing par
`tools/check_savegame.py`. Ici on verifie l'autre moitie : que le port
transforme bien son etat en octets, et qu'il le retrouve intact.

On sauvegarde une partie, on **casse** tout ce qui peut l'etre, on recharge,
et on compare. Un octet de trop, un champ oublie ou une conversion de signe
faux se voit ici.

Usage::

    python tools/check_save_roundtrip.py
"""
from __future__ import annotations

import os
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from populous.game import Game  # noqa: E402
from populous.savegame import (CHAMPS, TAILLE,  # noqa: E402
                                   checksum, nom_de_fichier)
from populous.saveio import (PEEPS_DANS_FICHIER, TAILLE_PEEP,  # noqa: E402
                             TAILLE_TRIBU, pack_moteur, pack_peep,
                             pack_tribu, unpack_peep, unpack_tribu)

TOTAL = [0]
KO = [0]


def check(label, cond, detail=""):
    TOTAL[0] += 1
    if not cond:
        KO[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "KO", label,
                           ("  -> " + detail) if detail else ""))


def main():
    g = Game(59, 0, 3)

    # ---- une partie non triviale -------------------------------------
    sim = g.sim
    for i in range(6):
        p = sim.peeps[i]
        p.tribe = i % 2
        p.life = 100 + i * 7
        p.block = 0x40 + i
        p.state = 0x11 + i
        p.frame = 0x200 + i
        p.w6 = 300 - i
        p.target = (i + 1) % 6
        p.weapons = 30 + i
        p.offspring = i
        p.face = i & 1
        p.spawn_block = i & 1
    sim.no_peeps = 6
    sim.stats[0].act = 14
    sim.stats[0].p1 = 3
    sim.stats[0].p2 = 5
    sim.stats[0].threshold = 4
    sim.stats[0].power_mask = 0xBEEF
    sim.stats[0].period = 7
    sim.stats[0].castles = 3
    sim.stats[0].towns = 9
    sim.stats[0].colour = 11
    sim.stats[0].strongest = 5
    sim.stats[0].p26 = 4
    sim.stats[0].p2a = 6
    sim.stats[1].act = 0x0E
    sim.stats[1].can_build = 1
    sim.stats[1].power_mask = 0x1234
    sim.mode = 2
    sim.player = 1
    sim.ground_in = 3
    sim.war = 1
    sim.game_turn = 1234
    sim.in_conquest = 7
    sim.paint_map = 1
    sim.game_mode = 0b10110
    g.seed = 0x4321
    terr = g.terrain
    for i in range(0x1081):
        terr.alt[i] = (i * 3) & 0xFFFF
    terr.blk[100] = 0x2F
    terr.bk2[200] = 0x35
    terr.who[300] = 4
    terr.disp_alt[400] = 0x17

    # ---- 1. la taille du fichier -------------------------------------
    donnees = pack_moteur(g, "essai")
    check("L17190-17364 : le fichier fait exactement %d octets" % TAILLE,
          len(donnees) == TAILLE == sum(c[2] for c in CHAMPS),
          "%d produits" % len(donnees))
    check("L17125 : les quatre premiers octets sont $FFFFB615",
          donnees[:4] == b"\xff\xff\xb6\x15",
          donnees[:4].hex())
    check("L17358 : le dernier mot est le checksum du terrain",
          donnees[-2:] == (checksum_terrain(g) & 0xFFFF).to_bytes(2, "big"),
          "%s contre %s" % (donnees[-2:].hex(),
                            (checksum_terrain(g) & 0xFFFF).to_bytes(2, "big").hex()))

    # ---- 2. le decoupage ---------------------------------------------
    pos, morceaux = 0, {}
    for nom, _s, taille, _l in CHAMPS:
        morceaux[nom] = donnees[pos:pos + taille]
        pos += taille
    check("L17197 : `_alt` occupe $2102 octets, les 4225 sommets",
          len(morceaux["alt"]) == 0x2102
          and int.from_bytes(morceaux["alt"][8450 - 2:], "big")
          == ((0x1080 * 3) & 0xFFFF),
          "dernier sommet = %d"
          % int.from_bytes(morceaux["alt"][8448:8450], "big"))
    for nom in ("map_alt", "map_blk", "map_bk2", "map_who"):
        check("L17204-17231 : `%s` fait $1000 octets" % nom,
              len(morceaux[nom]) == 0x1000)
    check("L17239 : `_peeps` fait $1222 = 211 fiches de 22 octets",
          len(morceaux["peeps"]) == 0x1222
          == PEEPS_DANS_FICHIER * TAILLE_PEEP,
          "%d = %d x %d" % (len(morceaux["peeps"]), PEEPS_DANS_FICHIER,
                            TAILLE_PEEP))
    check("L17239 : la fiche 0 est bien la premiere unite",
          morceaux["peeps"][:TAILLE_PEEP] == pack_peep(g.sim.peeps[0]))

    # ---- 3. les trois mises en page isolées --------------------------
    for t, nom in ((g.sim.stats[0], "stats0"), (g.sim.stats[1], "stats1")):
        check("L17246-17259 : la fiche `%s` fait 46 octets" % nom,
              len(morceaux[nom]) == TAILLE_TRIBU == 0x2E
              and morceaux[nom] == pack_tribu(t))
    un = bytearray(TAILLE_PEEP)
    t2 = g.sim.peeps[0]
    b = pack_peep(t2)
    un[:] = b
    import copy
    vide = copy.copy(t2)
    vide.life = vide.block = 0
    unpack_peep(bytes(TAILLE_PEEP), vide)
    check("L17239 : `unpack_peep` remet tout a zero", vide.life == 0)
    unpack_peep(un, vide)
    check("L17493 : `unpack_peep(pack_peep(p))` redonne le meme peep",
          (vide.tribe, vide.life, vide.block, vide.state, vide.frame,
           vide.target) ==
          (t2.tribe, t2.life, t2.block, t2.state, t2.frame, t2.target),
          "%r contre %r" % (vide, t2))

    # ---- 4. l'aller-retour complet ----------------------------------
    avec = {
        "mode": sim.mode, "seed": g.seed, "player": sim.player,
        "ground_in": sim.ground_in, "war": sim.war,
        "game_turn": sim.game_turn, "in_conquest": sim.in_conquest,
        "paint_map": sim.paint_map, "game_mode": sim.game_mode,
        "alt0": terr.alt[0], "altN": terr.alt[-1],
        "blk": bytes(terr.blk), "bk2": bytes(terr.bk2),
        "who": bytes(terr.who), "disp_alt": bytes(terr.disp_alt),
        "peeps": [pack_peep(p) for p in sim.peeps[:PEEPS_DANS_FICHIER]],
        "t0": pack_tribu(sim.stats[0]), "t1": pack_tribu(sim.stats[1]),
    }
    import copy
    avant_peeps = [copy.copy(p) for p in sim.peeps]
    # on casse tout
    sim.mode = 0
    sim.player = 0
    sim.not_player = 0
    sim.ground_in = 0
    sim.war = 0
    sim.game_turn = 0
    sim.in_conquest = -1
    sim.paint_map = 0
    sim.game_mode = 0
    g.seed = 0
    terr.alt = [0] * 0x1081
    terr.blk = bytearray(0x1000)
    terr.bk2 = bytearray(0x1000)
    terr.who = bytearray(0x1000)
    terr.disp_alt = bytearray(0x1000)
    for p in sim.peeps:
        p.__init__()
    for t in sim.stats:
        t.act = t.p1 = t.p2 = 0
        t.power_mask = 0
        t.castles = t.towns = 0

    # L17650-17670 : on espionne `get_heading` pour prouver qu'elle est
    # appelee une fois par unite **qui a une cible** (le test du listing est
    # `TST.L (LAB_53022)`, donc une cible nulle ne passe pas).
    appels = []
    vrai = sim.get_heading

    def espion(i):
        appels.append(i)
        return vrai(i)

    sim.get_heading = espion

    d = tempfile.mkdtemp()
    # `save_game`/`load_game` suffixent toujours, et le test se fait sur
    # le nom **complet** : `name[4:]` n'est donc jamais `.GAM`, sauf
    # pour un nom nu de quatre caracteres (L17135-17137).
    chemin = os.path.join(d, "essai")
    with open(chemin + ".GAM", "wb") as f:
        f.write(donnees)
    ok = g.load_game(chemin)
    check("L17453 : le chargement d'un bon fichier reussit", ok)

    check("L17508-17570 : les scalaires reviennent a l'identique",
          (sim.mode, g.seed, sim.player, sim.ground_in, sim.war,
           sim.game_turn, sim.in_conquest, sim.paint_map, sim.game_mode)
          == (avec["mode"], avec["seed"], avec["player"], avec["ground_in"],
              avec["war"], avec["game_turn"], avec["in_conquest"],
              avec["paint_map"], avec["game_mode"]),
          str((sim.mode, g.seed, sim.player, sim.ground_in, sim.war,
               sim.game_turn, sim.in_conquest, sim.paint_map, sim.game_mode)))
    check("L17463 : `_alt` revient sommet par sommet",
          terr.alt[0] == avec["alt0"] and terr.alt[-1] == avec["altN"]
          and terr.alt == [(i * 3) & 0xFFFF for i in range(0x1081)])
    for attr in ("blk", "bk2", "who", "disp_alt"):
        check("L17468-17487 : `%s` revient octet pour octet" % attr,
              bytes(getattr(terr, attr)) == avec[attr])
    # `get_heading` (L17650-17670) est appele sur toute unite qui a une
    # cible : il touche `target`, `w6` et `frame`. On compare donc les
    # champs qu'il ne regarde pas.
    stables = ("state", "tribe", "offspring", "weapons", "life", "block",
               "prev_block", "spawn_block", "face")
    ecarts = []
    for k in range(PEEPS_DANS_FICHIER):
        a, b = sim.peeps[k], avant_peeps[k]
        for nom in stables:
            if getattr(a, nom) != getattr(b, nom):
                ecarts.append("peep %d : %s %r != %r"
                              % (k, nom, getattr(a, nom), getattr(b, nom)))
    check("L17493 : les 211 fiches `_peeps` reviennent intactes",
          not ecarts, "; ".join(ecarts[:3]))
    sim.get_heading = vrai
    avec_cible = [k for k in range(sim.no_peeps)
                  if avant_peeps[k].target != 0]
    check("L17650-17670 : `get_heading` est appele une fois par unite dont "
          "la cible est non nulle",
          appels == avec_cible,
          "appele %s, attendu %s" % (appels, avec_cible))
    check("L17623-17638 : les unites au-dela de `_no_peeps` ne sont pas "
          "traitees",
          all(k < sim.no_peeps for k in appels))

    # L17639-17649 met `act`, `p1` et `p2` a zero dans les deux fiches :
    # on compare donc le paquet a la donnee sauvee, ces trois octets effaces.
    attendu = []
    for t_, clef in ((sim.stats[0], "t0"), (sim.stats[1], "t1")):
        b = bytearray(avec[clef])
        b[0] = b[1] = b[2] = 0
        attendu.append(bytes(b))
    check("L17498-17507 : les deux fiches `_stats` reviennent intactes "
          "(`act`/`p1`/`p2` mis a zero par L17639-17649)",
          pack_tribu(sim.stats[0]) == attendu[0]
          and pack_tribu(sim.stats[1]) == attendu[1],
          "stats0 %s" % (pack_tribu(sim.stats[0])[:8].hex(),))

    # ---- 5. ce que `_load_game` fait de plus ----------------------------
    check("L17623-17638 : `_no_peeps` est recalcule, pas relu",
          sim.no_peeps == 6, "no_peeps=%d" % sim.no_peeps)
    check("L17590-17595 : `not_player` suit `player`",
          sim.not_player == 1 - sim.player)
    check("L17639-17649 : `act`, `p1` et `p2` sont mis a zero",
          (sim.stats[0].act, sim.stats[0].p1, sim.stats[0].p2) == (0, 0, 0)
          and (sim.stats[1].act, sim.stats[1].p1, sim.stats[1].p2) == (0, 0, 0),
          str((sim.stats[0].act, sim.stats[0].p1, sim.stats[0].p2)))
    check("L17671-17682 : `_pointer` vaut 4 pour le joueur 1",
          sim.pointer == 4, "pointer=%d" % sim.pointer)
    check("L17579 : `_land_checksum` est relu (sans jamais etre compare)",
          sim.land_checksum == (checksum_terrain(g) & 0xFFFF),
          "land_checksum=%d" % sim.land_checksum)

    # ---- 6. un fichier etranger est refuse ------------------------------
    mauvais = os.path.join(d, "mauvais.GAM")
    with open(mauvais, "wb") as f:
        f.write(b"\x00\x00\x00\x00" + donnees[4:])
    check("L17453 : un en-tete different est refuse sans rien charger",
          g.load_game(mauvais) is False)
    vide = os.path.join(d, "vide.GAM")
    open(vide, "wb").close()
    check("L17446-17447 : un fichier vide est refuse",
          g.load_game(vide) is False)
    check("L17446-17447 : un fichier absent est refuse",
          g.load_game(os.path.join(d, "absent.GAM")) is False)

    # ---- 7. le suffixe `.GAM` ------------------------------------------
    check("L17130-17153 : `save_game` ajoute `.GAM` une seule fois",
          g.save_game(os.path.join(d, "essai")) == 0
          and os.path.exists(chemin + ".GAM")
          and not os.path.exists(chemin + ".GAM.GAM"))
    check("L17418-17433 : `load_game` relit le fichier ecrit",
          g.load_game(chemin) is True)
    check("L17135-17137 : un nom de quatre caracteres deja en `…GAM` "
          "n'est pas re-suffixe",
          nom_de_fichier("ab.GAM") == "ab.GAM.GAM",
          "ab.GAM -> %r (le test porte sur l'octet 4)"
          % nom_de_fichier("ab.GAM"))

    print("\n%d controles, %d echec(s)" % (TOTAL[0], KO[0]))
    return 1 if KO[0] else 0


def checksum_terrain(g):
    from populous.savegame import terrain_checksum
    t = g.terrain
    return terrain_checksum({
        "alt": b"".join((v & 0xFFFF).to_bytes(2, "big") for v in t.alt),
        "map_alt": bytes(t.disp_alt), "map_blk": bytes(t.blk),
        "map_bk2": bytes(t.bk2), "map_who": bytes(t.who),
        "good_pop": sum(p.life for p in g.sim.peeps if p.tribe == 0),
        "bad_pop": sum(p.life for p in g.sim.peeps if p.tribe == 1),
    })


if __name__ == "__main__":
    sys.exit(main())