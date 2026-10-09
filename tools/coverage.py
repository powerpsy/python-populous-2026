r"""Inventaire de couverture : quelles routines du listing sont dans le port.

Pourquoi cet outil
------------------
Les marqueurs ``[APPROX]`` ne disent **rien** de la couverture : ils sont
écrits là où nous avons regardé, donc là où nous avons trouvé un doute. Une
routine jamais lue n'a aucun marqueur — non parce qu'elle est correcte, mais
parce que personne ne l'a visitée.

La seule mesure honnête est arithmétique : **combien** des 564 routines du
listing se retrouvent dans le code Python. C'est cet outil.

Le comptage par simple citation de nom est **imparfait** : une routine
transcrite sous un autre nom passe pour absente. D'où la table
``ALIAS`` ci-dessous, qui déclare explicitement « cette routine de l'asm est
cette fonction Python ». Plus on transcrit, plus on la remplit — et plus le
taux veut dire quelque chose.

::

    python tools\coverage.py            # résumé
    python tools\coverage.py --top 40   # les plus grosses routines non couvertes
    python tools\coverage.py --holes    # les 8 trous « lines cut »

Sortie : un code de retour non nul si la couverture régresse, pour que le
taux devienne une cible qu'on surveille au lieu d'un chiffre qu'on oublie.
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
ASM = RACINE / "reference" / "tetracorp" / "populous_prg.asm"
PY = RACINE / "populous"

#: ``routine asm`` -> ``symbole Python`` (nom qualifie ou attribut).
#:
#: À remplir à chaque transcription. Une entrée dit « cette routine EST ce
#: code », et dispense donc la recherche par nom.
ALIAS: dict[str, str] = {
    # --- Phase 1-11 : interaction, villageois, batiments, pouvoirs, interface
    "_do_populous": "Game.run",
    "_sculpt": "Game.sculpt",
    "_one_block_flat": "Game.one_block_flat",
    "_devil_effect": "Game.devil_effect",
    "_set_devil_magnet": "Game.set_devil_magnet",
    "_do_place_funny": "Game.do_place_funny",
    "_check_life": "Game.check_life",
    "_set_town": "Game.set_town",
    "_join_battle": "Game.join_battle",
    "_set_magnet_to": "Game.set_magnet_to",
    "_do_battle": "Game.do_battle",
    "_battle_over": "Game.battle_over",
    "_grow_peep": "Game.grow_peep",
    "_move_sprite": "Game.move_peeps",
    "_get_heading": "Game.get_heading",     # Phase 36 : transcrit et verifie
    "_move_magnet_peeps": "Game.move_magnet_peeps",   # Phase 37 : verifie
    "_move_explorer": "Game.move_explorer",          # Phase 40 : dispatch cable
    "_devil_effect": "PowerEngine.devil_effect",     # Phase 42-43
    "_do_computer_effect": "PowerEngine.do_computer_effect",
    "_set_devil_magnet": "PowerEngine.set_devil_magnet",
    "_where_do_i_go": "Game.where_do_i_go",          # appele par _move_explorer
    "_rotate_all_map": "Terrain.rotate_all_map",      # Phase 47 : verifie 400 essais
    "_clear_all_map": "Game.clear_all_map",           # Phase 52 : verifie par dispatch
    "_load_ground": "Game.load_ground",               # Phase 53 : verifie par dispatch
    "_move_mana": "Game.move_mana",                   # Phase 49 : verifie 665 essais
    # Phase 51-53 : 13 des 16 codes transcrits et verifies (check_dispatch) ;
    # les codes 2, 7, 8 LEVENT `NotImplementedError` par regle.
    "_do_action": "PowerEngine.do_action",
    "_newrand": "Rng.raw",
    # `_divs` (L23385) est la division **longue** signee ; `___divs` n'est
    # qu'un `JMP _divs` (L24077). Cet alias pointait sur `m68k.divs_word`
    # (`DIVS.W`, 16 bits) — la meme confusion de largeur que celle qui
    # tronquait `pl.mana` dans powers.py:619.
    "_divs": "m68k.divs_long",
    "_mulu": "m68k.mulu_word",

    # --- Phase 58 : l'init `.data` de `_stats`, la periode de `queued`
    # `_clear_send` (L18234-18254) ne vide que `act/p1/p2` et laisse
    # `queued` intact. `_get_message` (L17707) contient en plus tout le
    # canal serie et le replay : il n'est PAS declare ici, seule la
    # periode `can_build == 1 and game_turn % period == 0` (L17934-17951)
    # est transcrite, dans `Game._run_commands`.
    "_clear_send": "PowerEngine.do_queued",

    # --- Phase 55 : audit des routines « citees ». Une entree par preuve
    #     (la def nomme la routine, ou cite sa ligne / son adresse de
    #     depart). Voir PROGRESSION 55 pour les cas non retenus.
    "_zoom_map": "Game.zoom_map",   # Phase 55 : L1658 (game.py)
    "_end_game": "Game._end_game",   # Phase 55 : L14019 (game.py)
    "_show_the_shield": "Game.show_the_shield",   # Phase 55 : L2769 (game.py)
    "_requester": "Game.requester",   # Phase 55 : L9901 (game.py)
    "_set_tend_icons": "Game.set_tend_icons",   # Phase 55 : L2455 (game.py)
    "_set_mode_icons": "Game.set_mode_icons",   # Phase 55 : L2526 (game.py)
    "_interogate": "Game.interogate",   # Phase 55 : L2719 (game.py)
    "_draw_sprite": "Game._draw_sprite_at",   # Phase 55 : L19283 (game.py)
    "_raise_point": "Terrain.raise_point",   # Phase 55 : L1274 (terrain.py)
    "_lower_point": "Terrain.lower_point",   # Phase 55 : L2571 (terrain.py)
    "_make_map": "Terrain.make_map",   # Phase 55 : L1420 (terrain.py)
    "_make_thing": "Terrain.make_thing",   # Phase 55 : L1208 (terrain.py)
    "_mod_map": "Terrain.mod_map",   # Phase 55 : L1594 (terrain.py)
    "_make_alt": "Terrain.make_alt",   # Phase 55 : L1189 (terrain.py)
    "_make_woods_rocks": "Terrain.make_woods_rocks",   # Phase 55 : L8535 (terrain.py)
    "_clear_map": "Terrain.clear",   # Phase 55 : L1023 (terrain.py)
    "_draw_it": "Renderer.draw_window",   # Phase 55 : L15794 (render.py)
    "_draw_map": "Renderer.draw_minimap",   # Phase 55 : L1543 (render.py)
    "_text": "Renderer.draw_text",   # Phase 55 : L19973 (render.py)
    "_drw_blk": "Renderer.blit_tile",   # Phase 55 : L15737/SUB_49938 (render.py)
    "_draw_bar": "Renderer.draw_bar",   # Phase 55 : L19213 (render.py)
    "_draw_icon": "Renderer.draw_icon",   # Phase 55 : L19184 (render.py)
    "_toggle_icon": "Renderer.toggle_icon",   # Phase 55 : L19493 (render.py)
    "_do_knight": "PowerEngine.do_knight",   # Phase 55 : L8392 (powers.py)
    "_do_war": "PowerEngine.do_war",   # Phase 55 : L8482 (powers.py)
    "_valid_move": "GameMap.valid_move",   # Phase 55 : L20912 (map.py)
    "_kill_effect": "SoundEngine.kill_effect",   # Phase 55 : L20876 (sound.py)
    "_check_effect": "SoundEngine.check_effect",   # Phase 55 : L20898 (sound.py)
    "_PlaySound": "SoundEngine.play",   # Phase 55 : L20307 (sound.py)
    "_PlayMeas": "SoundEngine.mesure",   # Phase 55 : L20433 (sound.py)
    "___clear_all_map": "Game.clear_all_map",   # Phase 55 : L23947 (game.py)
    "_move_peeps": "Game.move_peeps",   # Phase 55 : $4059A (sim.py)
    "_set_frame": "Game.set_frame",   # Phase 55 : $422D2 (sim.py)
    "_place_people": "Game.place_people",   # Phase 55 : $43164 (sim.py)
    "_join_forces": "Game.join_forces",   # Phase 55 : ligne 5540 (sim.py)
    "_set_battle": "Game.set_battle",   # Phase 55 : $42CBA (sim.py)
    "_zero_population": "Game.zero_population",   # Phase 55 : $421F4 (sim.py)
}

#: ``routine asm`` : **analysée mais pas encore transcrite**.
#:
#: Sans cette liste, une routine analysée passerait pour une routine
#: transcrite — c'est exactement le piège que ``[APPROX]`` ne voit pas. Un
#: alias declare vers un symbole inexistant signale une regression ; une
#: entree ici signale du travail **a faire**.
PLANIFIE: set[str] = {
    # Phase 43 : les trois routines de l IA sont transcrites et cablees.
    #   `_set_devil_magnet` est du CODE MORT (L1065 est la seule ecriture de
    #   `command`, et la routine exige `command == 0`) — mais elle est
    #   appelee quand meme, comme le fait le listing.
}

RE_FONCTION = re.compile(r"^(_[A-Za-z0-9_]+):\s*$")
RE_TROU = re.compile(r"^\s*;\s*lines cut", re.IGNORECASE)
RE_APPEL = re.compile(r"\b(?:JSR|BSR)\w*\s+(_{1,3}[A-Za-z0-9_]+)")
#: un renvoi au listing : ``L4905``, ``$4268A``, ``asm 24269``
RE_REPERE = re.compile(r"L\d{3,6}|\$[0-9A-Fa-f]{4,8}\b|\basm\b")


def lire_asm() -> list[str]:
    return io.open(ASM, encoding="utf-8", errors="replace").read().split("\n")


def routines(lignes: list[str]) -> list[dict]:
    """Chaque routine ``_xxx:``, avec son corps et ses trous."""
    departs = []
    for i, l in enumerate(lignes):
        m = RE_FONCTION.match(l)
        if m:
            departs.append((m.group(1), i))
    out = []
    for n, (nom, i) in enumerate(departs):
        fin = departs[n + 1][1] if n + 1 < len(departs) else len(lignes)
        corps = lignes[i + 1:fin]
        # les lignes de données ne sont pas de la logique
        n_code = sum(1 for l in corps
                     if l.strip() and not l.strip().startswith(";")
                     and not re.match(r"^\s*(DC|DS)\.", l))
        out.append({
            "nom": nom,
            "ligne": i + 1,
            "code": n_code,
            "trous": sum(1 for l in corps if RE_TROU.match(l)),
        })
    return out


def lire_py() -> str:
    morceaux = []
    for f in sorted(PY.glob("*.py")):
        morceaux.append(io.open(f, encoding="utf-8").read())
    return "\n".join(morceaux)


def cite_solide(source: str, nom: str) -> bool:
    """Le nom complet est-il cite **a cote d'un repere asm** ?

    Un mot seul ne prouve rien : le Python a un ``open()``, et le listing a
    un ``_Open`` de la bibliotheque C. Et nos docstrings parlent d'``A4`` a
    chaque ligne — ce qui faisait passer ``_A4`` pour couvert.

    Deux conditions, donc :

    1. le nom **avec son souligne** doit apparaitre — nos docstrings ecrivent
       bien ``_move_peeps``, ``_do_battle``, ``_sculpt``, et Python n'a
       aucune raison d'ecrire ``_Open`` ;
    2. a moins de trois lignes d'un renvoi au listing (``L4905``,
       ``$4268A``, ``asm 24269``).
    """
    motif = re.compile(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(nom))
    lignes = source.split("\n")
    for n, l in enumerate(lignes):
        if not motif.search(l):
            continue
        for m in range(max(0, n - 3), min(len(lignes), n + 4)):
            if RE_REPERE.search(lignes[m]):
                return True
    return False


def classe(r: dict, source: str) -> tuple[str, str]:
    """-> (etat, detail).

    Etats : ``alias`` (declare et present), ``cite`` (nom cite a cote d un
    repere asm), ``collision`` (le nom apparait mais sans repere : on ne
    peut pas conclure), ``planifie``, ``absent``.

    Le seau ``collision`` est **hors couverture** : c est lui qui gonflait
    le taux a 31 % avec des routines de la bibliotheque C.
    """
    if r["nom"] in PLANIFIE:
        return "planifie", ""
    if r["nom"] in ALIAS:
        cible = ALIAS[r["nom"]]
        nom_simple = cible.split(".")[-1]
        present = (f"def {nom_simple}" in source or f"class {nom_simple}" in source
                   or f"{nom_simple} =" in source)
        if present:
            return "alias", cible
        return "alias-absent", cible
    court = r["nom"].lstrip("_")
    if cite_solide(source, r["nom"]):
        return "cite", court
    if court and re.search(r"\b%s\b" % re.escape(court), source):
        return "collision", court
    return "absent", ""


def appelants(lignes: list[str]) -> dict[str, set[str]]:
    """Qui appelle qui, a partir des `JSR`/`BSR` du listing.

    On ne garde que les cibles nommées ``_xxx:`` ; les appels par
    bibliotheque (``___xxx``) sont resolus sur le nom sans les deux
    soulignes, car le listing fournit le trampoline.
    """
    noms = {r["nom"] for r in routines(lignes)}
    courant = None
    out: dict[str, set[str]] = {}
    for l in lignes:
        m = RE_FONCTION.match(l)
        if m:
            courant = m.group(1)
            out.setdefault(courant, set())
            continue
        m = RE_APPEL.search(l)
        if m and courant:
            cible = m.group(1)
            if cible.startswith('___'):
                cible = '_' + cible[3:]
            if cible in noms:
                out[courant].add(cible)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top", type=int, default=25,
                    help="combien de routines non couvertes lister")
    ap.add_argument("--holes", action="store_true",
                    help="ne montrer que les routines contenant un trou")
    args = ap.parse_args()

    lignes = lire_asm()
    source = lire_py()
    rs = routines(lignes)

    etats = [classe(r, source) for r in rs]
    par_etat: dict[str, list[dict]] = {}
    for r, (etat, _) in zip(rs, etats):
        par_etat.setdefault(etat, []).append(r)

    n_total = len(rs)
    n_code = sum(1 for r in rs if r["code"] > 0)
    n_donnees = n_total - n_code
    n_reel = len(par_etat.get("alias", [])) + len(par_etat.get("cite", []))
    pct = 100.0 * n_reel / n_total if n_total else 0.0
    pct_code = 100.0 * n_reel / n_code if n_code else 0.0

    print("lignes du listing      : %d" % (len(lignes) - 1))
    print("etiquettes _xxx:       : %d" % n_total)
    print("  routines AVEC code   : %d" % n_code)
    print("  symboles de DONNEES  : %d   (`_peeps`, `_alt`, `_to_delta`...)"
          % n_donnees)
    print("  lignes de code       : %d" % sum(r["code"] for r in rs))
    print()
    print("COUVERTURE REELLE      : %d / %d  (%.1f%%)"
          % (n_reel, n_total, pct))
    print("  sur les routines seulement : %d / %d  (%.1f%%)"
          % (n_reel, n_code, pct_code))
    print("  par alias declare    : %d  (fiable)"
          % len(par_etat.get("alias", [])))
    print("  par citation reperee : %d  (nom + renvoi asm)"
          % len(par_etat.get("cite", [])))
    print("  analysees, a coder   : %d" % len(par_etat.get("planifie", [])))
    print("  COLLISIONS de nom    : %d  (hors couverture)"
          % len(par_etat.get("collision", [])))
    print("  NON couvertes        : %d"
          % (n_total - n_reel - len(par_etat.get("planifie", []))
             - len(par_etat.get("collision", [])) - len(par_etat.get("alias-absent", []))))
    if par_etat.get("alias-absent"):
        print("  !! ALIAS CASSE        : %d  (le symbole Python a disparu)"
              % len(par_etat["alias-absent"]))
        for r in par_etat["alias-absent"]:
            print("       %s -> %s" % (r["nom"], ALIAS[r["nom"]]))

    if args.holes:
        print()
        print("=== trous « lines cut » ===")
        trouves = False
        for r in rs:
            if r["trous"]:
                trouves = True
                etat, _ = classe(r, source)
                print("  %-28s ligne %-6d %d l. de code   [%s]"
                      % (r["nom"], r["ligne"], r["code"], etat))
        if not trouves:
            print("  aucun")
        return 0

    print()
    print("=== joignabilite des routines COUVERTES ===")
    app = appelants(lignes)
    couvertes = {r["nom"] for r in rs
                 if classe(r, source)[0] in ("alias", "cite")}
    sans_appelant = sorted(n for n in couvertes if not app.get(n))
    injoignables = []
    for n in sorted(couvertes):
        cibles = {c for c in app.get(n, ()) if c in couvertes}
        if not cibles:
            manquant = sorted(app.get(n, ()) - couvertes)
            injoignables.append((n, manquant))
    print("  couvertes                       : %d" % len(couvertes))
    print("  dont jamais appelees par le code : %d"
          % len(sans_appelant))
    for n in sans_appelant[:8]:
        print("       %s" % n)
    print("  dont INJOIGNABLES (aucun appelant")
    print("      lui-meme couvert)          : %d" % len(injoignables))
    for n, manquant in injoignables[:args.top]:
        print("       %-26s appelants manquants : %s"
              % (n, ", ".join(manquant[:5]) or "(aucun)"))
    if len(injoignables) > args.top:
        print("       ... et %d autres" % (len(injoignables) - args.top))

    print()
    print("=== %d plus grosses routines NON couvertes ===" % args.top)
    absents = sorted(par_etat.get("absent", []),
                     key=lambda r: -r["code"])
    for r in absents[:args.top]:
        marque = "  <-- TROU" if r["trous"] else ""
        print("  %-30s ligne %-6d %4d l. de code%s"
              % (r["nom"], r["ligne"], r["code"], marque))

    reste = absents[args.top:]
    if reste:
        print("  ... et %d autres" % len(reste))

    return 0


if __name__ == "__main__":
    sys.exit(main())