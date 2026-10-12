# -*- coding: utf-8 -*-
"""Verifie le routage ``_get_message`` code 14 -> ``_do_action``.

Phase 51 : ``_sub_action`` (version ecrite a la main) a ete supprime au
profit de ``PowerEngine.do_action``, la transcription du listing
(L18376-19004). Ce controle existe pour que ce changement soit **mesure**
et non suppose :

1. ``dispatch(tribe, 14, p1, code)`` doit bien atteindre ``do_action`` ;
2. les codes 3/4/5 doivent appeler ``do_war``/``do_flood``/``do_knight``
   exactement une fois — c'etaient les trois que ``_sub_action`` faisait
   tourner et que la table de Phase 46 donnait pour "non lus" ;
3. le calcul du mana (codes 9/10) doit egaler le listing, reference
   reecrite ici de maniere independante (flottant, pas ``divs_long``) ;
4. les codes ``2, 7, 8`` : le 7 est **transcrit** depuis la Phase 68 et
   doit appeler ``_options`` une fois par tribu ; les codes ``2`` et ``8``
   doivent **lever** ``NotImplementedError`` sur leurs branches serie et
   surtout pas retomber silencieusement en no-op - c'est la regle de
   Phase 22, et c'est exactement ce que ``_sub_action`` faisait ;
5. le code 12 doit **bien vider la carte** (Phase 52) — 4225 sommets,
   4096 cases ``who``, puis ``_no_peeps`` a 0 — et appeler
   ``_make_map(0,0,$3F,$3F)`` et ``_draw_map(0,0,$3F,$3F)`` dans cet ordre.
   Le ``blk``/``bk2`` n'est pas verifie en sortie de ``clear_all_map`` :
   c'est ``_make_map`` qui les remplit apres le nettoyage. On les verifie
   donc au moment precis ou ``_make_map`` est sur le point d'etre appele,
   en l'interceptant.
6. le code 13 doit **changer d'habillage sans toucher au relief** (Phase 53) :
   ``map_colour`` duplique en 16..31 (la boucle L4A348 que le port avait
   manquee), ``weapons_order`` re-copie et trie, ``_draw_map(0,0,63,63)``
   appele une fois — et ``_alt``/``_map_blk`` **inchangees**, puisque
   ``_load_ground`` ne s'occupe ni du relief ni de la carte.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from populous.constants import ACT_ACTION  # noqa: E402

CIBLES = ("do_war", "do_flood", "do_knight")
CODES_APPELES = (3, 4, 5)
CODES_SANS_CIBLEE = (1, 6, 11, 15)
ESSAIS_MANA = (399, -250, 0, 1, 32767, 32768, 65535, 65536,
               99_999, 100_000, 100_001, 200_000, 300_000, 2_000_063)


def ref_mana(mana: int, p1: int) -> int:
    """L18943-18959, reecrite sans passer par m68k."""
    if p1:                                     # TST.W ($A,A5) / BEQ
        return int(mana / 2)                   # ___divs : tronque vers zero
    if mana >= 100_000:                        # CMPI.L #$186A0 / BGE
        return mana
    return mana * 2 + 500                      # ASL.L #1 + ADD.L #$1F4


def main() -> int:
    from populous.game import Game

    g = Game(59, 0, 3)
    sim = g.sim
    pe = g.powers
    echecs = []

    # --- 1. codes 3/4/5 doivent atteindre la bonne cible, une fois -------
    sauves = {n: getattr(pe, n) for n in CIBLES}
    appels = {}

    def fabrique(nom):
        def compteur(*a, **k):
            appels[nom] = appels.get(nom, 0) + 1
            return sauves[nom](*a, **k)
        return compteur

    for nom in CIBLES:
        setattr(pe, nom, fabrique(nom))
    try:
        for code, attendu in zip(CODES_APPELES, CIBLES):
            appels.clear()
            pe.dispatch(0, ACT_ACTION, 0, code)
            pris = appels.get(attendu, 0)
            parasites = {k: v for k, v in appels.items() if k != attendu}
            if pris != 1:
                echecs.append("code %d : %s appele %d fois (attendu 1)"
                              % (code, attendu, pris))
            if parasites:
                echecs.append("code %d : appels parasite(s) %s"
                              % (code, parasites))
    finally:
        for nom, fn in sauves.items():
            setattr(pe, nom, fn)
    print("routage 3/4/5 -> do_war/do_flood/do_knight : %d ecart(s)"
          % len(echecs))

    # --- 2. codes sans cotee : doivent passer sans lever ----------------
    n_lev = 0
    for code in CODES_SANS_CIBLEE:
        try:
            pe.dispatch(0, ACT_ACTION, 0, code)
        except NotImplementedError:
            n_lev += 1
            echecs.append("code %d leve NotImplementedError a tort" % code)
    print("routage 1/6/11/15 sans le lever           : %d levage(s)" % n_lev)

    # --- 3. codes non transcrits : doivent LEVER ------------------------
    # Les deux boites ouvertes par le code 8 - `_game_setup` (L18735) et
    # `_two_players` (L18936) - sont elles-memes des boucles modales : on
    # les epingle pour isoler le routage, sinon la boucle attend un clic
    # qui n'arrivera jamais.
    vrai_setup, vrai_two = g.game_setup, g.two_players
    appel_setup, appel_two = [], []
    pose_new_map = [0]

    def setup_epion():
        appel_setup.append(1)
        sim.new_map = pose_new_map[0]               # L13239 / L13279

    g.game_setup, g.two_players = setup_epion, \
        lambda: appel_two.append(1)
    garde_si = (sim.serial_off, sim.new_map, sim.bring_up_two, sim.player)
    n_ok = 0

    def lancer(libelle, attendu, action):
        """`attendu` = sous-chaine attendue dans la levee, ou `None`."""
        nonlocal n_ok
        try:
            action()
        except NotImplementedError as exc:
            bon, detail = bool(attendu) and attendu in str(exc), str(exc)
        except Exception as exc:                        # noqa: BLE001
            bon, detail = False, "erreur inattendue %r" % (exc,)
        else:
            bon = attendu is None
            detail = "no-op silencieux" if attendu else "retour sans levee"
        if bon:
            n_ok += 1
        else:
            echecs.append("%s : %s" % (libelle, detail))
        print("  %-50s %s" % (libelle, "OK" if bon else "ECHEC"))

    try:
        # code 2 : `serial_off != 0` rend la main (L18405-18406)
        sim.serial_off, sim.new_map, sim.bring_up_two, sim.player = 1, 0, 0, 0
        pose_new_map[0] = 0
        lancer("code 2, liaison coupee -> retour (L18405-18406)", None,
               lambda: pe.dispatch(0, ACT_ACTION, 0, 2))
        # code 2 : sinon `_get_a_message` puis `_write_serial` (L18430-18468)
        sim.serial_off = 0
        lancer("code 2, liaison active -> _write_serial (L18430-18468)",
               "_write_serial", lambda: pe.dispatch(0, ACT_ACTION, 0, 2))
        # code 8, joueur local, liaison active (L18738-18753)
        lancer("code 8, local + liaison -> _write_serial (L18738-18753)",
               "_write_serial", lambda: pe.dispatch(0, ACT_ACTION, 0, 8))
        # code 8, un seul joueur, mais `_game_setup` a demande un nouveau
        # terrain : `___setup_display` n'est pas transcrit (L18924-18928)
        sim.serial_off, pose_new_map[0] = 1, 1
        lancer("code 8, _new_map -> ___setup_display (L18924-18928)",
               "___setup_display", lambda: pe.dispatch(0, ACT_ACTION, 0, 8))
        # code 8, autre tribu, liaison active (L18757-18762)
        pose_new_map[0] = 0
        sim.serial_off, sim.player = 0, 1
        lancer("code 8, autre tribu + liaison -> _read_serial (L18757)",
               "_read_serial", lambda: pe.dispatch(0, ACT_ACTION, 0, 8))
        # code 8, un seul joueur, rien a demander : retour silencieux
        sim.serial_off, sim.player, sim.bring_up_two = 1, 0, 0
        lancer("code 8, un joueur -> retour (L18917-18942)", None,
               lambda: pe.dispatch(0, ACT_ACTION, 0, 8))
    finally:
        g.game_setup, g.two_players = vrai_setup, vrai_two
        (sim.serial_off, sim.new_map, sim.bring_up_two,
         sim.player) = garde_si
    if len(appel_setup) != 3:
        echecs.append("_game_setup appele %d fois (attendu 3 : les codes 8 "
                      "locaux)" % len(appel_setup))
    if appel_two:
        echecs.append("_two_players appele a tort %d fois" % len(appel_two))
    print("codes 2/8, branche par branche : %d/6 conformes, "
          "_game_setup %d appel(s)" % (n_ok, len(appel_setup)))

    # --- 3bis. code 7 : `_options` (L18634-18645) ------------------------
    # Transcrit en Phase 68 : le code 7 ne leve plus, il ouvre la boite.
    # On l'epingle pour prouver le routage sans laisser la boucle modale
    # attendre un clic qui n'arrivera pas.
    appels7 = []
    vrai_options = g.options

    def options_epion(tribu):
        appels7.append(tribu)
        return None

    g.options = options_epion
    try:
        pe.dispatch(0, ACT_ACTION, 1, 7)            # arg2 != 0 -> joueur
        pe.dispatch(0, ACT_ACTION, 0, 7)            # arg2 == 0 -> autre
    finally:
        g.options = vrai_options
    if appels7 != [sim.player, sim.not_player]:
        echecs.append("code 7 : options(%s) au lieu de (%s, %s)"
                      % (appels7, sim.player, sim.not_player))
    print("code 7 -> _options(joueur) puis _options(autre) : %s"
          % ("OK" if appels7 == [sim.player, sim.not_player]
             else "ECHEC %s" % appels7))

    # --- 4. codes 9/10 : le calcul doit egaler le listing ---------------
    ecart_mana = []
    n = 0
    for code in (9, 10):
        cible = 0 if code == 9 else 1
        for mana0 in ESSAIS_MANA:
            for p1 in (0, 1):
                n += 1
                sim.players[cible].mana = mana0
                pe.dispatch(0, ACT_ACTION, p1, code)
                obtenu = sim.players[cible].mana
                attendu = ref_mana(mana0, p1)
                if obtenu != attendu:
                    ecart_mana.append((code, mana0, p1, obtenu, attendu))
    print("codes 9/10 via dispatch : %d essais, %d ecart(s)"
          % (n, len(ecart_mana)))
    for e in ecart_mana[:8]:
        print("   code=%d mana=%-9d p1=%d obtenu=%s attendu=%s" % e)
    echecs.extend("mana code=%d mana=%d p1=%d" % e[:3] for e in ecart_mana)

    # --- 5. code 1 : ecriture de `command` (L18402) ---------------------
    sim.players[1].command = 0
    pe.dispatch(1, ACT_ACTION, 5, 1)
    if sim.players[1].command != 5:
        echecs.append("code 1 : command=%s (attendu 5)"
                      % sim.players[1].command)
    print("code 1 ecrit players[].command             : %s"
          % ("OK" if sim.players[1].command == 5 else "ECHEC"))

    # --- 6. code 12 : _clear_all_map (L6926-6963) -----------------------
    terr = g.terrain
    n_sommets, n_cases = len(terr.alt), len(terr.who)
    e12 = []
    for i in range(n_sommets):
        terr.alt[i] = (i % 60) + 1                  # 4225 sommets non nuls
    for i in range(n_cases):
        terr.who[i] = (i % 250) + 1                 # 4096 cases non nules
        terr.bk2[i] = (i % 250) + 1
        terr.blk[i] = (i % 60) + 1
    n_peeps = max(sim.no_peeps, 1)
    sim.no_peeps = n_peeps
    for i in range(n_peeps):
        sim.peeps[i].life = 1
        sim.peeps[i].state = 0
    survivant = n_peeps                             # hors boucle : ne doit pas mourir
    sim.peeps[survivant].life = 77

    # on intercepte `_make_map` pour voir l'etat AU MOMENT ou il est appele,
    # lui-meme remplit ensuite `blk`/`bk2` : c'est le seul instant ou le
    # nettoyage des cases est observable. `Terrain` a des `__slots__`, on
    # patauge donc la **classe**, pas l'instance.
    captures = {}
    TERRAIN, REN = type(terr), type(g.ren)
    make_reel, dessin_reel = TERRAIN.make_map, REN.draw_minimap

    def make_epion(self_, x0, y0, x1, y1):
        captures["args"] = (x0, y0, x1, y1)
        captures["no_peeps"] = sim.no_peeps
        captures["who"] = bytes(self_.who)
        captures["bk2"] = bytes(self_.bk2)
        captures["blk"] = bytes(self_.blk)
        return make_reel(self_, x0, y0, x1, y1)

    def dessin_epion(self_, *a, **k):
        captures["draw"] = captures.get("draw", 0) + 1
        return dessin_reel(self_, *a, **k)

    TERRAIN.make_map, REN.draw_minimap = make_epion, dessin_epion
    try:
        pe.dispatch(0, ACT_ACTION, 0, 12)
    except NotImplementedError:
        e12.append("encore NotImplementedError")
    except Exception as exc:                        # noqa: BLE001
        e12.append("erreur inattendue %r" % (exc,))
    finally:
        TERRAIN.make_map, REN.draw_minimap = make_reel, dessin_reel

    restants = sum(1 for v in terr.alt if v)
    if restants:
        e12.append("_alt : %d/%d sommets non nuls" % (restants, n_sommets))
    restants = sum(1 for v in terr.who if v)
    if restants:
        e12.append("_map_who : %d/%d cases non nules" % (restants, n_cases))
    if captures.get("args") != (0, 0, 0x3F, 0x3F):
        e12.append("_make_map appele avec %s (attendu (0, 0, 63, 63))"
                   % (captures.get("args"),))
    if captures.get("no_peeps") != 0:
        e12.append("_no_peeps = %s au moment de _make_map (attendu 0)"
                   % captures.get("no_peeps"))
    for cle in ("who", "bk2", "blk"):
        octets = captures.get(cle)
        if octets is None:
            e12.append("_make_map pas intercepte")
            break
        if any(octets):
            e12.append("_map_%s : %d octets non nuls avant _make_map"
                       % (cle, sum(1 for v in octets if v)))
    if captures.get("draw") != 1:
        e12.append("_draw_map appele %s fois (attendu 1)"
                   % captures.get("draw"))
    if sim.no_peeps != 0:
        e12.append("_no_peeps = %s apres (attendu 0)" % sim.no_peeps)
    vivants = [i for i in range(n_peeps) if sim.peeps[i].life != 0]
    if vivants:
        e12.append("peeps 0..%d non tues : %s" % (n_peeps - 1, vivants[:6]))
    if sim.peeps[survivant].life != 77:
        e12.append("peep %d (hors no_peeps) touche : life=%s"
                   % (survivant, sim.peeps[survivant].life))
    echecs.extend("code 12 : %s" % e for e in e12)
    print("code 12 _clear_all_map : %d sommets, %d cases, "
          "no_peeps %d->0, _draw_map x%s  %s"
          % (n_sommets, n_cases, n_peeps, captures.get("draw"),
             "OK" if not e12 else "%d ecart(s)" % len(e12)))
    for e in e12:
        print("   %s" % e)

    # --- 7. code 13 : _load_ground (L16468-4A444) -----------------------
    from populous.assets import load_sprites as _sprites
    from populous.land import load_land as _tables

    e13 = []
    rom = bytes.fromhex("0e0c0b0b0c0c0b0b0d0d0c0c0d0d0c0c")
    alt0 = list(g.terrain.alt)
    blk0 = bytes(g.terrain.blk)
    sprites_obj0 = g.ren.sprites
    sprites_in0 = g.ren.header["sprites_no"]
    dessins = {}
    REN = type(g.ren)
    draw_reel = REN.draw_minimap

    def draw_epion(self_, *a, **k):
        dessins["n"] = dessins.get("n", 0) + 1
        dessins["dest"] = a[0] if a else None
        dessins["terr"] = a[1] if len(a) > 1 else None
        dessins["couleurs"] = k.get("colours")
        return draw_reel(self_, *a, **k)

    def verifier(n_sol, attendu_sprites_obj):
        """Les invariants de la routine, pour un sol donne."""
        t = _tables(n_sol)
        if g.ground != n_sol:
            e13.append("sol %d : _ground_in = %s" % (n_sol, g.ground))
        if g.colours[16:32] != g.colours[0:16]:
            e13.append("sol %d : _map_colour[16..31] ne double pas 0..15"
                       % n_sol)
        if list(g.colours[0:16]) != list(t.map_colour):
            e13.append("sol %d : _map_colour[0..15] = %s, fichier = %s"
                       % (n_sol, g.colours[0:16], list(t.map_colour)))
        if bytes(g.colours[0:16]) != rom and bytes(g.colours[16:32]) == rom:
            e13.append("sol %d : 16..31 garde l'image ROM (le bug de la "
                       "Phase 53)" % n_sol)
        if g.colours[32:] != [0x19] * 200:
            e13.append("sol %d : _map_colour[32..] != 0x19" % n_sol)
        if g.ren.header["sprites_no"] != t.sprites_no:
            e13.append("sol %d : sprites_no = %s (fichier = %s)"
                       % (n_sol, g.ren.header["sprites_no"], t.sprites_no))
        if g.sim.weapons_order[:11] != sorted(t.weapons_add):
            e13.append("sol %d : weapons_order = %s (trie = %s)"
                       % (n_sol, g.sim.weapons_order[:11],
                          sorted(t.weapons_add)))
        if g.sim.land.mana_add != t.mana_add:
            e13.append("sol %d : sim.land non recharge" % n_sol)
        if attendu_sprites_obj == "idem":
            if g.ren.sprites is not sprites_obj0:
                e13.append("sol %d : sprites recharges alors que "
                           "sprites_no n'a pas change" % n_sol)
        elif g.ren.sprites is sprites_obj0:
            e13.append("sol %d : sprites NON recharges alors que "
                       "sprites_no a change" % n_sol)

    REN.draw_minimap = draw_epion
    try:
        # a) sprites_no 0 -> 0 : le BEQ de L4A334 doit sauter _read_sprites
        g.powers.dispatch(0, ACT_ACTION, 1, 13)
        verifier(1, "idem")
        # b) sprites_no 0 -> 4 : le chemin complet, et le sol 4 a un
        #    map_colour qui n'a rien a voir avec l'image ROM.
        g.powers.dispatch(0, ACT_ACTION, 4, 13)
        verifier(4, "recharge")
        if len(g.ren.sprites) != len(_sprites("sprites4.dat")):
            e13.append("sprites4 : %d sprites (attendu %d)"
                       % (len(g.ren.sprites), len(_sprites("sprites4.dat"))))
    except NotImplementedError as exc:
        e13.append("encore NotImplementedError : %s" % exc)
    except Exception as exc:                        # noqa: BLE001
        e13.append("erreur inattendue %r" % (exc,))
    finally:
        REN.draw_minimap = draw_reel

    if list(g.terrain.alt) != alt0:
        e13.append("_alt a change : _load_ground ne doit pas y toucher")
    if bytes(g.terrain.blk) != blk0:
        e13.append("_map_blk a change : _load_ground ne doit pas y toucher")
    if dessins.get("n") != 2:
        e13.append("_draw_map appele %s fois (attendu 2, un par sol)"
                   % dessins.get("n"))
    elif dessins.get("couleurs") is not g.colours:
        e13.append("_draw_map ne recoit pas les couleurs fraiches")
    echecs.extend("code 13 : %s" % e for e in e13)
    print("code 13 _load_ground : sols 1 puis 4, map_colour duplique, "
          "weapons_order trie, relief inchange  %s"
          % ("OK" if not e13 else "%d ecart(s)" % len(e13)))
    for e in e13:
        print("   %s" % e)

    print()
    if echecs:
        print("ECHECS : %d" % len(echecs))
        for e in echecs:
            print("   %s" % e)
        return 1
    print("TOUS LES CONTROLES DE ROUTAGE SONT VERTS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
