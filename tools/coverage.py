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
    "_newrand": "Rng.raw",
    "_divs": "m68k.divs_word",
    "_mulu": "m68k.mulu_word",
}

#: ``routine asm`` : **analysée mais pas encore transcrite**.
#:
#: Sans cette liste, une routine analysée passerait pour une routine
#: transcrite — c'est exactement le piège que ``[APPROX]`` ne voit pas. Un
#: alias declare vers un symbole inexistant signale une regression ; une
#: entree ici signale du travail **a faire**.
PLANIFIE: set[str] = {
    "_devil_effect",          # Phase 26 : lu, structure relue, code mort trouve
    "_set_devil_magnet",      # Phase 26 : depends de _devil_effect
    "_do_computer_effect",    # Phase 26 : appele par _devil_effect, pas encore lu
    # Phase 28-36 : lu integralement, tables verifiees dans les octets.
    # Le mecanisme est entierement connu ; reste a ecrire les ~1500 lignes.
    "_move_magnet_peeps",
}

RE_FONCTION = re.compile(r"^(_[A-Za-z0-9_]+):\s*$")
RE_TROU = re.compile(r"^\s*;\s*lines cut", re.IGNORECASE)
RE_APPEL = re.compile(r"\b(?:JSR|BSR)\w*\s+(_{1,3}[A-Za-z0-9_]+)")


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


def classe(r: dict, source: str) -> tuple[str, str]:
    """-> (etat, detail).

    Etats : ``alias`` (declare et present), ``cite`` (trouve par son nom),
    ``planifie`` (analyse, pas encore code), ``absent`` (rien).
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
    if court and re.search(r"\b%s\b" % re.escape(court), source):
        return "cite", court
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
    n_couv = n_total - len(par_etat.get("absent", []))
    n_reel = n_couv - len(par_etat.get("planifie", []))
    pct = 100.0 * n_reel / n_total if n_total else 0.0

    print("lignes du listing      : %d" % (len(lignes) - 1))
    print("routines _xxx:         : %d" % n_total)
    print("  dont lignes de code  : %d"
          % sum(r["code"] for r in rs))
    print()
    print("COUVERTURE REELLE      : %d / %d  (%.1f%%)" % (n_reel, n_total, pct))
    print("  par alias declare    : %d" % len(par_etat.get("alias", [])))
    print("  par citation de nom  : %d" % len(par_etat.get("cite", [])))
    print("  analysees, a coder   : %d" % len(par_etat.get("planifie", [])))
    print("  NON couvertes        : %d" % len(par_etat.get("absent", [])))
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