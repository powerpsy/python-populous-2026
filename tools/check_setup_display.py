# -*- coding: utf-8 -*-
"""Verifie ``_setup_display`` (L380-498) — la Phase 77.

Depuis la Phase 77, ``Game.setup_display(a, ground)`` est la transcription
de L380-498 et ``_new_map`` (L18733, L13239, L13279, L13284, L18918) est
**consomme** : c'est ce qui supprime les deux derniers ``raise`` de
``_exec_game_setup`` (ligne 15) et de ``_do_action`` code 8.

Ce controle mesure le changement sur :

1. l'ecart ``a != 0`` (L460-461), jamais pris par les cinq appels ;
2. la branche **partie libre** (L429-458) : ``_start_seed = _seed`` (L430),
   le tirage ``_newrand`` **inconditionne** (L433-435), le test
   ``ground == -1`` (L436-437), le cyclage de ``_ground_in`` avec son
   plafond a 3 (L438-441), et le ``_seed += 1`` final (L496) ;
3. la branche **conquête** (L382-427) : le tampon ``_conquest`` relu tel
   quel, ``_seed = _start_seed = (in_conquest & 7) + conq_08`` (L388-392),
   ``_ground_in = conq_05_terrain`` (L399) et les quatre ecritures de
   L407-427 ;
4. ``set_ground(..., conserver_etat=True)`` : le listing ne re-instantie
   rien — les globaux (``_in_conquest``, ``_player``, ``_serial_off``,
   ``_stats``, ``_game_mode``, ``_setup_ticks``) doivent survivre a la
   regeneneration que le port est oblige de faire ;
5. la ligne 15 de *GAME SETUP* (L13282-13284) et sa consommation par
   ``_do_action`` code 8 (L18917-18931), y compris le retour de
   ``_seed = _start_seed`` (L18922).

Attention : ``set_ground`` **re-instantie** ``Sim`` (ECART de port), donc
toute reference a ``g.sim`` prise avant un ``setup_display`` pointe une
fiche jetee — les sections ci-dessous la reprennent apres chaque appel.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from populous.constants import ACT_ACTION  # noqa: E402
from populous.rng import Rng  # noqa: E402

# (seuil, conq_01, conq_02, conq_03, conq_04, conq_05, yourpop, enemypop,
#  conq_08h, conq_08l) : la colonne 6 (votre population) n'est pas lue par
# L380-498.
PALIER = bytes((50, 10, 1, 2, 0x03, 2, 3, 3, 0x42, 0x62))
GRANDE = 0x4262                                # (data[8] << 8) | data[9]


def main() -> int:
    from populous.game import Game

    echecs = []
    n_ok = [0]

    def check(libelle, condition, detail=""):
        if condition:
            n_ok[0] += 1
            print("[OK] %s  %s" % (libelle, detail))
        else:
            echecs.append("%s  %s" % (libelle, detail))
            print("[ECHEC] %s  %s" % (libelle, detail))

    # deux graines de depart dont on connait d'avance le bit0 (L434)
    bit = next(s for s in range(1, 2000) if Rng(s).raw() & 1)
    nobit = next(s for s in range(1, 2000) if not Rng(s).raw() & 1)

    def SD(g, a, ground):
        """``setup_display`` puis la fiche **neuve**."""
        g.setup_display(a, ground)
        return g.sim

    # --- 1. `a != 0` : jamais pris, donc non modele (L460-461) ------------
    g = Game(59, 0, 3)
    try:
        g.setup_display(1, 0)
        check("L460-461 : `a != 0` leve en nommant `_setup_display`", False,
              "aucune leve")
    except NotImplementedError as exc:
        check("L460-461 : `a != 0` leve en nommant `_setup_display`",
              "_setup_display" in str(exc), "leve")
    except Exception as exc:                        # noqa: BLE001
        check("L460-461 : `a != 0` leve en nommant `_setup_display`", False,
              "erreur inattendue %r" % (exc,))

    # --- 2. branche partie libre : le tirage, puis le cyclage -------------
    g = Game(59, 0, 3)
    g.sim.in_conquest = -1
    g.sim.rng.seed = bit                           # _seed, dont bit0 = 1
    sim = SD(g, 0, -1)
    check("L436-438 : `ground == -1` et bit0 a 1 -> `_ground_in + 1`",
          g.ground == 1 and sim.ground_in == 1,
          "ground=%d ground_in=%d" % (g.ground, sim.ground_in))

    g = Game(59, 0, 3)
    g.sim.in_conquest = -1
    g.sim.rng.seed = nobit                         # L435 : BEQ -> LAB_3E68C
    sim = SD(g, 0, -1)
    check("L434-435 : bit0 a 0 -> `_ground_in` inchange malgre `-1`",
          g.ground == 0 and sim.ground_in == 0,
          "ground=%d ground_in=%d" % (g.ground, sim.ground_in))

    g = Game(59, 0, 3)
    g.sim.in_conquest = -1
    g.sim.rng.seed = 0                             # L431-432 : pas de tirage
    sim = SD(g, 0, -1)
    check("L431-432 : `_seed == 0` -> aucun tirage, aucun cyclage",
          g.ground == 0 and sim.rng.seed == 1,
          "ground=%d rng=%d" % (g.ground, sim.rng.seed))

    g = Game(59, 0, 3)
    g.ground = 3
    g.set_ground(3)
    g.sim.in_conquest = -1
    g.sim.rng.seed = bit
    sim = SD(g, 0, -1)
    check("L439-441 : `BLE` -> au dela de 3, `_ground_in` revient a 0",
          g.ground == 0 and sim.ground_in == 0,
          "ground=%d ground_in=%d" % (g.ground, sim.ground_in))

    # L451-456 : le `-2` de `_two_players` recharge le sol courant.
    g = Game(59, 0, 3)
    g.sim.in_conquest = -1
    sim = SD(g, 0, -2)
    check("L451-456 : `ground == -2` recharge le sol courant",
          g.ground == 0 and sim.ground_in == 0,
          "ground=%d ground_in=%d" % (g.ground, sim.ground_in))

    # L430 puis L496 : `_start_seed = _seed` **avant** le tirage, `_seed += 1`
    # **apres** - et L433 a deja avance `_seed` d'un `_newrand`.
    g = Game(59, 0, 3)
    g.sim.in_conquest = -1
    g.sim.rng.seed = bit
    sim = SD(g, 0, 0)
    r = Rng(bit)
    r.raw()                                        # L433 `___newrand`
    check("L430/L496 : `_start_seed` = `_seed` d'entree, `_seed` = +1",
          g.start_seed == bit and sim.rng.seed == (r.seed + 1) & 0xFFFF,
          "start=%d rng=%d attendu=%d" % (g.start_seed, sim.rng.seed,
                                          (r.seed + 1) & 0xFFFF))

    # --- 3. `conserver_etat` : les globaux survivent ----------------------
    g = Game(59, 0, 3)
    g.sim.in_conquest, g.sim.player, g.sim.serial_off = 7, 1, 0
    g.sim.setup_ticks[3] = "\x81"
    stats_avant = g.sim.stats
    sim = SD(g, 0, -2)
    check("L380-498 : `_in_conquest` survit a la regeneneration",
          sim.in_conquest == 7, "in_conquest=%d" % sim.in_conquest)
    check("L380-498 : `_player` / `_serial_off` survivent",
          sim.player == 1 and sim.serial_off == 0,
          "player=%d serial_off=%d" % (sim.player, sim.serial_off))
    check("L380-498 : `_stats` est la **meme** fiche, pas une recreee",
          sim.stats is stats_avant, "id conserve")
    check("L380-498 : les coches de GAME SETUP survivent",
          sim.setup_ticks[3] == "\x81", "ticks[3]=%r" % sim.setup_ticks[3])

    # --- 4. branche conquete ---------------------------------------------
    g = Game(59, 0, 3)
    g._conquest[:] = PALIER
    g.sim.in_conquest = 7                          # L388 `& 7`
    sim = SD(g, 0, -1)
    check("L388-392 : `_seed = _start_seed = (in_conquest & 7) + conq_08`",
          g.seed == ((7 & 7) + GRANDE) and g.start_seed == g.seed,
          "seed=%d start=%d" % (g.seed, g.start_seed))
    check("L399 : `_ground_in = conq_05_terrain` (octet 5, masque a 2 bits)",
          g.ground == 2 and sim.ground_in == 2,
          "ground=%d ground_in=%d" % (g.ground, sim.ground_in))
    check("L407-408 : stats[1].threshold = _conquest[0]",
          sim.stats[1].threshold == 50, "thr=%d" % sim.stats[1].threshold)
    check("L410-411 : stats[1].period = conq_01_speed",
          sim.stats[1].period == 10, "per=%d" % sim.stats[1].period)
    check("L414-418 : stats[1].power_mask = (enemypow << 3) | 7",
          sim.stats[1].power_mask == (1 << 3) | 7,
          "pm=0x%04X" % sim.stats[1].power_mask)
    check("L419-423 : stats[0].power_mask = (yourpow << 3) | 7",
          sim.stats[0].power_mask == (2 << 3) | 7,
          "pm=0x%04X" % sim.stats[0].power_mask)
    check("L425-427 : `_game_mode = conq_04_mode`",
          sim.game_mode == 0x03, "gm=0x%02X" % sim.game_mode)
    check("L382-427 : `_in_conquest` survit egalement en conquete",
          sim.in_conquest == 7, "in_conquest=%d" % sim.in_conquest)
    check("L391/L496 : `_seed` du simulateur = graine + 1",
          sim.rng.seed == (g.seed + 1) & 0xFFFF, "rng=%d" % sim.rng.seed)

    # `_palier()` : les dix octets du tampon, relus comme `ConquestLevel`.
    g = Game(59, 0, 3)
    g._conquest[:] = PALIER
    lv = g._palier()
    check("L12340-12368 : `_palier()` relit le tampon `_conquest`",
          (lv.threshold, lv.ai_period, lv.enemypow, lv.yourpow, lv.mode,
           lv.terrain, lv.seed) == (50, 10, 1, 2, 0x03, 2, GRANDE),
          "lv=%r" % ((lv.threshold, lv.mode, lv.terrain, lv.seed),))

    # --- 5. ligne 15 + consommation code 8 --------------------------------
    g = Game(59, 0, 3)
    sim = g.sim
    sim.serial_off, sim.new_map = 1, 0
    sortie = g._exec_game_setup(15)
    check("L13282-13284 : la ligne 15 pose `_new_map = _ground_in + 2`",
          sortie is True and sim.new_map == g.ground + 2,
          "new_map=%d sortie=%r" % (sim.new_map, sortie))

    # On epingle `game_setup` (boite modale, qui pose `_new_map` comme la
    # ligne 15) et `setup_display` (qui regenere `Sim`, et donc jetterait
    # les aliases `sim` du test).
    appel_disp = []
    vrai_setup, vrai_disp = g.game_setup, g.setup_display

    def epingle(nouveau):
        def setup_epion():
            g.sim.new_map = nouveau
        g.game_setup = setup_epion
        g.setup_display = lambda a, ground: appel_disp.append(
            (a, ground, g.sim.rng.seed))

    def libere():
        g.game_setup, g.setup_display = vrai_setup, vrai_disp

    epingle(g.ground + 2)
    try:
        g.powers.dispatch(0, ACT_ACTION, 0, 8)
    finally:
        libere()
    check("L18924-18928 : code 8 consomme `_new_map` par `setup_display`",
          [a[:2] for a in appel_disp] == [(0, g.ground)],
          "appels=%s" % appel_disp)
    check("L18917 : `_new_map` n'est **pas** efface apres consommation",
          g.sim.new_map == g.ground + 2, "new_map=%d" % g.sim.new_map)

    # L18920-18922 : `_new_map != 1` restaure `_seed = _start_seed` avant
    # de regenerer.
    appel_disp.clear()
    g.start_seed, g.sim.rng.seed = 4321, 999
    epingle(g.ground + 2)
    try:
        g.powers.dispatch(0, ACT_ACTION, 0, 8)
    finally:
        libere()
    check("L18922 : `_seed = _start_seed` juste avant `_setup_display`",
          bool(appel_disp) and appel_disp[-1][2] == 4321,
          "appels=%s" % appel_disp)

    # `_new_map == 1` (lignes 9 et 14) laisse `_seed` tel quel.
    appel_disp.clear()
    g.start_seed, g.sim.rng.seed = 4321, 999
    epingle(1)
    try:
        g.powers.dispatch(0, ACT_ACTION, 0, 8)
    finally:
        libere()
    check("L18920-18921 : `_new_map == 1` ne restaure rien",
          bool(appel_disp) and appel_disp[-1][2] == 999,
          "appels=%s" % appel_disp)

    # --- 6. `load_conquest` remplit le tampon -----------------------------
    g = Game(59, 0, 3)
    g.load_conquest(2)
    lv = g._palier()
    check("Phase 77 : `load_conquest` remplit aussi `_conquest`",
          g.conquest is not None and
          (lv.threshold, lv.ai_period, lv.mode, lv.terrain, lv.seed) ==
          (g.conquest.threshold, g.conquest.ai_period, g.conquest.mode,
           g.conquest.terrain, g.conquest.seed),
          "lv=%r vs %r" % ((lv.threshold, lv.mode, lv.seed),
                           (g.conquest.threshold, g.conquest.mode,
                            g.conquest.seed)))

    print()
    print("%d controles, %d echec(s)" % (n_ok[0] + len(echecs), len(echecs)))
    for e in echecs:
        print("   ECHEC : %s" % e)
    return 1 if echecs else 0


if __name__ == "__main__":
    raise SystemExit(main())
