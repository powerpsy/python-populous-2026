# -*- coding: utf-8 -*-
"""Phase 89 : les quatre pouvoirs, transcrits ligne a ligne du listing.

``_do_magnet`` (L6769-6819), ``_do_lower_point`` (L7091-7176),
``_do_raise_point`` (L7180-7267) et ``_do_swamp`` (L8295-8388).

Le port avait deja les **primitives** de terrain (``Terrain.raise_point`` /
``lower_point``, L1274 / L2571) mais pas les **gabarits de pouvoir**. Ce
controle verifie les faits du listing qui les distinguent d'une
approximation plausible :

1. le depot n'est pas un fixe 10, mais ``10 + 4*_build_count`` — le compteur
   compte **chaque sommet releve**, lui-meme et les voisins lisses ( ;3ef9c );
2. ``_do_raise_point`` et ``_do_lower_point`` n'ont **pas la meme garde** :
   le relever compte ``_war``, l'abaissement non ;
3. l'abaissement pose ses bornes **avant** la garde, le relever **apres** ;
4. le marais vise la case donnee + ``(newrand()%7) - 3``, et non une case
   au hasard ;
5. la mana se lit en **LONG signe** : revenue sous zero sous la forme
   ``$FF......``, une garde non signee la lirait a quatre milliards et
   l'IA declencherait tous ses pouvoirs d'un coup.

Toutes les donnees sont produites par le port lui-meme : aucune lecture de
fichier hors de l'arbre tracke.
"""
from __future__ import annotations

import sys

from populous.constants import BLK_FLAT, BLK_SWAMP
from populous.game import Game

MANA_AIMANT = 0xC8             # LAB_5187C, L24291
MANA_MARAIS = 0x1388           # LAB_51884, L24295
POINTS_MARAIS = 50             # L8331 : +$32 points
CIBLE = (25 << 6) | 40         # `_set_magnet_to(tribu, (y<<6)|x)`


def partie():
    """Une partie neuve, les deux tribus riches et toutes les portes ouvertes."""
    g = Game(59, 0, 3)
    sim = g.sim
    sim.player = 0
    sim.paint_map = 0
    sim.war = 0
    sim.pause = 0
    for t in (0, 1):
        sim.players[t].mana = 100000
        sim.stats[t].power_mask = 0xFFFF
    return g


def main() -> int:
    ko = []
    total = [0]

    def ok(cond, libelle, detail=""):
        total[0] += 1
        if cond:
            print("  [OK] %s" % libelle)
        else:
            ko.append(libelle)
            print("  [KO] %s  ->  %s" % (libelle, detail))

    # ---------------------------------------------------- 1. le depot variable
    print("\n1. Le depot est `10 + 4*_build_count`, pas un fixe 10")
    g = partie()
    pe, terr = g.powers, g.terrain
    relances = []
    for x in range(4, 60, 7):
        for y in range(4, 60, 7):
            m0 = pe.mana(0)
            pe.do_raise_point(0, x, y)
            relances.append((terr.build_count, m0 - pe.mana(0)))
    payes = [p for n, p in relances if n >= 1]
    ok(all(p == 10 + 4 * n for n, p in relances if p),
       "chaque depot vaut `10 + 4 * _build_count` (L7215-7219)",
       "ecarts=%s" % [c for c in relances if c[1] != 10 + 4 * c[0]][:4])
    ok(max(n for n, _ in relances) >= 2,
       "`_build_count` compte bien les voisins lisses, pas le seul sommet",
       "max=%d, payes=%s" % (max(n for n, _ in relances), sorted(set(payes))))

    # ---------------------------------------------------- 2. meme depot en bas
    print("\n2. L'abaissement coute de meme (L7124-7128)")
    g = partie()
    pe, terr = g.powers, g.terrain
    bas = []
    for x in range(4, 60, 7):
        for y in range(4, 60, 7):
            m0 = pe.mana(0)
            pe.do_lower_point(0, x, y)
            bas.append((terr.build_count, m0 - pe.mana(0)))
    ok(all(p == 10 + 4 * n for n, p in bas if p),
       "l'abaissement preleve aussi `10 + 4 * _build_count`",
       "ecarts=%s" % [c for c in bas if c[1] != 10 + 4 * c[0]][:4])

    # ---------------------------------------------------- 3. la guerre
    print("\n3. Asymetrie `_war` : relever compte la guerre, abaisser non")
    g = partie()
    sim, pe = g.sim, g.powers
    sim.war = 1
    sim.players[0].mana = 0
    rel = pe.do_raise_point(0, 32, 32)
    bas = pe.do_lower_point(0, 32, 32)
    ok(rel, "en guerre et sans mana, le relever passe quand meme (L7191-7192)",
       "renvoie %s" % rel)
    ok(not bas,
       "en guerre et sans mana, l'abaissement sort (L7102-7105 ignore `_war`)",
       "renvoie %s" % bas)
    ok(pe.mana(0) == 0,
       "ni l'un ni l'autre ne preleve en guerre (L7206-7209)",
       "mana=%d" % pe.mana(0))

    # ---------------------------------------------------- 4. paint_map
    print("\n4. `_paint_map` : effet gratuit")
    g = partie()
    sim, pe = g.sim, g.powers
    sim.paint_map = 1
    sim.players[0].mana = 0
    a = pe.do_raise_point(0, 32, 32)
    b = pe.do_lower_point(0, 32, 32)
    ok(a and b, "sans mana, `_paint_map` fait passer relever ET abaisser",
       "releve=%s abaisse=%s" % (a, b))
    ok(pe.mana(0) == 0, "`_paint_map` ne preleve rien", "mana=%d" % pe.mana(0))

    # ---------------------------------------------------- 5. les bornes
    print("\n5. Les bornes : posees avant la garde par l'abaissement (L7093-7096)")
    g = partie()
    sim, pe, terr = g.sim, g.powers, g.terrain
    sim.players[0].mana = 0
    terr.xmin = terr.xmax = terr.ymin = terr.ymax = 99
    r = pe.do_lower_point(0, 21, 44)
    ok(not r, "sans mana et sans `_paint_map`, l'abaissement sort", "renvoie %s" % r)
    ok((terr.xmin, terr.xmax, terr.ymin, terr.ymax) == (21, 21, 44, 44),
       "  ... mais il a deja pose ses bornes avant de sortir",
       "boite=%s" % ((terr.xmin, terr.xmax, terr.ymin, terr.ymax),))

    terr.xmin = terr.xmax = terr.ymin = terr.ymax = 99
    r = pe.do_raise_point(0, 21, 44)
    ok(not r, "sans mana, le relever sort lui aussi", "renvoie %s" % r)
    ok((terr.xmin, terr.xmax, terr.ymin, terr.ymax) == (99, 99, 99, 99),
       "  ... mais il n'a pas touche aux bornes (L7197 vient apres la garde)",
       "boite=%s" % ((terr.xmin, terr.xmax, terr.ymin, terr.ymax),))

    # ---------------------------------------------------- 6. le carre 7x7
    print("\n6. Les bornes bornees d'un seul cote puis `_make_map` (L7130-7154)")
    g = partie()
    pe, terr = g.powers, g.terrain
    sim = g.sim
    sim.paint_map = 1
    terr.xmin = terr.xmax = terr.ymin = terr.ymax = 0
    pe.do_raise_point(0, 0, 0)
    ok((terr.xmin, terr.ymin) == (1, 1),
       "`_xmin`/`_ymin` sont retombeees a 1, pour que `_xmin-1` reste valide",
       "boite=%s" % ((terr.xmin, terr.xmax, terr.ymin, terr.ymax),))
    pe.do_raise_point(0, 0x40, 0x40)
    ok((terr.xmax, terr.ymax) == (0x3F, 0x3F),
       "`_xmax`/`_ymax` sont retombees a 0x3F",
       "boite=%s" % ((terr.xmin, terr.xmax, terr.ymin, terr.ymax),))

    # ---------------------------------------------------- 7. les portes du marais
    print("\n7. Les portes du marais (L8297-8317)")

    def marais(mana, war=0, pause=0, mask=0xFFFF, paint=0):
        sim.paint_map = paint
        sim.war = war
        sim.pause = pause
        sim.players[0].mana = mana
        sim.stats[0].power_mask = mask
        avant = pe.mana(0)
        r = pe.do_swamp(0, 32, 32)
        return r, avant - pe.mana(0)

    r, p = marais(MANA_MARAIS - 1)
    ok(not r and p == 0, "mana 4999 < 5000 -> refus, rien de preleve",
       "r=%s paye=%d" % (r, p))
    r, p = marais(MANA_MARAIS, war=1)
    ok(not r and p == 0, "en guerre -> refus (L8306-8307)",
       "r=%s paye=%d" % (r, p))
    r, p = marais(MANA_MARAIS, pause=1)
    ok(not r and p == 0, "en pause -> refus (L8308-8309)",
       "r=%s paye=%d" % (r, p))
    r, p = marais(MANA_MARAIS, mask=0xFFEF)
    ok(not r and p == 0, "`power_mask` sans le bit 4 -> refus (L8310-8313)",
       "r=%s paye=%d" % (r, p))
    r, p = marais(MANA_MARAIS)
    ok(r and p == MANA_MARAIS, "tout est en ordre -> 5000 preleves (L8319-8325)",
       "r=%s paye=%d" % (r, p))
    r, p = marais(0, paint=1)
    ok(r and p == 0,
       "`_paint_map` saute garde ET depot (L8297-8298 -> LAB_4415A)",
       "r=%s paye=%d" % (r, p))

    # ---------------------------------------------------- 8. le score du marais
    print("\n8. Le marais et le score (L8327-8331)")
    sim.paint_map = 1
    sim.war = sim.pause = 0
    g.score = 1000
    pe.do_swamp(0, 32, 32)
    ok(g.score == 1000 + POINTS_MARAIS, "tribu jouee -> +50 points",
       "score=%d" % g.score)
    g.score = 1000
    pe.do_swamp(1, 32, 32)
    ok(g.score == 1000, "autre tribu -> aucun point",
       "score=%d" % g.score)

    # ---------------------------------------------------- 9. la portee
    print("\n9. La portee du marais : la case visee + (newrand()%7) - 3")
    sim.paint_map = 1
    sim.map.blk[:] = [BLK_FLAT] * 4096
    sim.map.who[:] = [0] * 4096
    sim.rng.seed = 1234
    pe.do_swamp(0, 32, 32)
    poses = [i for i, b in enumerate(sim.map.blk) if b == BLK_SWAMP]
    hors = [(i & 0x3F, i >> 6) for i in poses
            if abs((i & 0x3F) - 32) > 3 or abs((i >> 6) - 32) > 3]
    ok(bool(poses) and not hors,
       "toutes les case posent dans le carre 7x7 centre sur (32, 32)",
       "%d pose(s), hors carre : %s" % (len(poses), hors[:5]))
    ok(len(poses) <= 30,
       "30 essais au plus (L8385-8387, borne $1E)",
       "%d pose(s)" % len(poses))

    # ---------------------------------------------------- 10. la mana signee
    print("\n10. La mana se lit en LONG signe")
    g = partie()
    sim, pe = g.sim, g.powers
    sim.players[1].mana = 0xFFFEA84D
    ok(pe.mana(1) == -87987,
       "`mana()` relit `$FFFEA84D` comme -87987, non comme 4294087309",
       "lu=%d" % pe.mana(1))
    sim.players[1].mana = 0x7FFFFFFF
    ok(pe.mana(1) == 0x7FFFFFFF,
       "un grand positif reste tel quel", "lu=%d" % pe.mana(1))
    sim.players[1].mana = 0xFFFEA84D
    r = pe.do_raise_point(1, 32, 32)
    ok(not r, "une mana negative bloque le relever, comme le `BGE` signe",
       "renvoie %s" % r)
    sim.players[1].mana = 0xFFFEA84D
    r = pe.do_swamp(1, 32, 32)
    ok(not r, "et bloque aussi le marais", "renvoie %s" % r)

    # ---------------------------------------------------- 11. l'aimant
    print("\n11. L'aimant (L6769-6819)")
    g = partie()
    sim, pe = g.sim, g.powers

    def aimant(mana, cible=1, war=0):
        sim.war = war
        sim.players[0].mana = mana
        sim.players[0].magnet = cible
        g.effect = 0
        avant = pe.mana(0)
        r = pe.do_magnet(0, 40, 25)
        return r, avant - pe.mana(0), g.effect

    r, p, _ = aimant(MANA_AIMANT - 1)
    ok(not r and p == 0, "mana 199 < 200 -> refus", "r=%s paye=%d" % (r, p))
    r, p, _ = aimant(MANA_AIMANT, cible=0)
    ok(not r and p == 0, "sans cible (`_magnet[tribu] == 0`) -> refus",
       "r=%s paye=%d" % (r, p))
    r, p, _ = aimant(MANA_AIMANT, cible=1, war=1)
    ok(not r and p == 0, "en guerre -> refus (L6784-6785)",
       "r=%s paye=%d" % (r, p))
    r, p, e = aimant(MANA_AIMANT, cible=1)
    ok(r and p == MANA_AIMANT, "tout est en ordre -> 200 preleves (L6792-6793)",
       "r=%s paye=%d" % (r, p))
    ok(e == 0x4D, "`_effect = $4D` (L6786)", "effect=%s" % e)
    ok(sim.players[0].magnet_to == CIBLE,
       "la cible est `(y<<6)|x` bornee a [0, 0x3F] (L6794-6815)",
       "magnet_to=%s (attendu %d)" % (sim.players[0].magnet_to, CIBLE))

    # ---------------------------------------------------- 12. les ecarts levess
    print("\n12. Les `_effect` absents du listing ne sont plus ecrits")
    for libelle, appel in (("relever", lambda p: p.do_raise_point(0, 10, 10)),
                           ("abaisser", lambda p: p.do_lower_point(0, 10, 10)),
                           ("marais", lambda p: p.do_swamp(0, 10, 10))):
        g = partie()
        g.sim.paint_map = 1
        g.effect = 0x1234
        appel(g.powers)
        ok(g.effect == 0x1234,
           "`%s` n'ecrit aucun `_effect` (ni `$40|tribu`, ni `$48`)" % libelle,
           "effect=%s" % g.effect)

    print("\n%d controle(s) en echec sur %d" % (len(ko), total[0]))
    if ko:
        return 1
    print("\n=> OK : tous les controles passent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
