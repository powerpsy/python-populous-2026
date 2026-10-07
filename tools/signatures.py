r"""Tableau de correspondance : routine du listing -> offset dans le DAD.

Pourquoi
--------
Le listing tetracorp et notre build DAD n'ont **pas la meme disposition** du
code (Phase 31). Les adresses du listing ne servent donc a rien pour
retrouver une routine dans le binaire. Mais on peut la retrouver par ses
**octets** : le listing donne l'encodage de chaque instruction dans le
commentaire ``;XXXX:``.

.. code-block:: none

    _newrand:
        MOVE.W _seed,D0   ;4c2e6: 303900052dd0

Le premier mot du commentaire est literally l'instruction. Les premiers
octets d'une routine forment donc une signature qu'on cherche dans le
fichier.

Ce que l'outil ne fait **pas**
-----------------------------
Il n'invente pas. Une signature trouvee **plusieurs fois** est signalee
ambigue et exclue du tableau : pretendre savoir ou est une routine alors
qu'on ne sait pas, c'est exactement l'erreur qu'un oracle doit interdire.

::

    python tools\signatures.py            # resume
    python tools\signatures.py --details  # ecarts et ambiguites
"""
from __future__ import annotations

import argparse
import io
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
ASM = RACINE / "reference" / "tetracorp" / "populous_prg.asm"
DAD = RACINE / "reference" / "original" / "extracted" / "DAD"

RE_FONCTION = re.compile(r"^(_[A-Za-z0-9_]+):\s*$")
#: le commentaire du listing est ``;<adresse>: <encodage>``.
#:
#:   MOVE.W _seed,D0        ;4c2e6: 303900052dd0
#:                      adresse  encodage
#:
#: Prendre l'adresse au lieu de l'encodage donne 0 % de correspondance a
#: toute largeur — un resultat si improbable qu'il a denonce le bug.
RE_ENC = re.compile(r";([0-9a-f]{3,8}):\s*([0-9a-f]{2,16})\b")


RE_ABSOLU = re.compile(r"^00[0-9a-f]{2}$")


def octets_de_la_routine(lignes: list[str], debut: int, fin: int,
                         nombre: int, sans_adresses: bool) -> tuple[bytes, int]:
    """Signature de la routine.

    Par défaut on concatène les encodages **complets** des instructions. Mesure
    faite, c'est ce qui donne le plus de correspondances uniques (98 pour
    349 routines a 3 instructions).

    ``sans_adresses`` retire les paires de mots ``00xx`` d'un long absolu —
    les deux builds n'ayant pas les memes adresses. C'etait l'intuition
    evidente, et elle est **fausse** : elle fait tomber les uniques de 98 a
    55 et multiplie les ambiguites par trois, parce qu'elle retire justement
    ce qui rend la signature specifique. Le mode est garde pour le
    documenter, pas par defaut.
    """
    bruts: list[str] = []
    vus = 0
    i = debut
    while i < fin and len(bruts) < 40:
        m = RE_ENC.search(lignes[i])
        i += 1
        if not m:
            continue
        h = m.group(2)
        if len(h) % 2:
            h = "0" + h
        bruts.append(h)
        vus += 1

    if not sans_adresses:
        return bytes.fromhex("".join(bruts[:nombre])), vus

    mots: list[str] = []
    for h in bruts:
        o = bytes.fromhex(h)
        mots.extend(o[k:k + 2].hex() for k in range(0, len(o), 2))
    gardee: list[str] = []
    k = 0
    while k < len(mots):
        if RE_ABSOLU.match(mots[k]) and k + 1 < len(mots):
            k += 2
            continue
        gardee.append(mots[k])
        k += 1
        if len(gardee) >= nombre:
            break
    return bytes.fromhex("".join(gardee[:nombre])), vus


def trouver(data: bytes, sig: bytes) -> list[int]:
    out, i = [], data.find(sig)
    while i >= 0:
        out.append(i)
        i = data.find(sig, i + 1)
    return out


def decalage_donnees(lignes: list[str], data: bytes) -> int | None:
    """Le decalage constant entre adresses du listing et offsets du DAD.

    Mesure sur des symboles **dont on a deja verifie le contenu** :

    .. code-block:: none

        _opposite  A4+$83BA = $517A8  ->  fichier $14754
        _to_delta  A4+$840A = $517F8  ->  fichier $147A4
        _to_offset A4+$841C = $5180A  ->  fichier $147B6

    Les trois donnent -249940. Les **donnees** sont donc a la meme place dans
    les deux builds.

    Le **code**, non : on mesure -249918 pour `_newrand`, -249860 pour
    `_divs`, -249902 pour `_mulu`. L'ecart est faible mais reel — c'est ce
    qui rend l agencement different (Phase 31).

    Consequence exploitable : la position d une routine est **predite a
    +/-200 octets**, ce qui suffit a lever les ambiguites.
    """
    A4_LISTING = 0x493EE            # LEA (_peeps,A4) -> A4 + $9C26 = $53014
    reperes = [("_opposite", 0x83BA), ("_to_delta", 0x840A),
               ("_to_offset", 0x841C)]
    # offsets fichier, mesures sur les octets (voir docs Phase 35)
    fiches = [0x14754, 0x147A4, 0x147B6]
    valeurs = set()
    for (nom, off_asm), off_fichier in zip(reperes, fiches):
        adresse = A4_LISTING + off_asm
        valeurs.add(off_fichier - adresse)
    if len(valeurs) == 1:
        return valeurs.pop()
    # si l outil ne les retrouve pas lui-meme, on garde la valeur mesuree
    return -249940


def fenetre(sig: bytes, data: bytes, debut: int, demi: int) -> list[int]:
    """Occurrences de `sig` dans [debut - demi, debut + demi]."""
    if demi <= 0:
        i = data.find(sig, debut)
        return [i] if i >= 0 else []
    bas = max(0, debut - demi)
    haut = min(len(data) - len(sig), debut + demi)
    out = []
    i = data.find(sig, bas)
    while 0 <= i <= haut:
        out.append(i)
        i = data.find(sig, i + 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--details", action="store_true",
                    help="montrer les routines non trouvees et les ambiguites")
    ap.add_argument("--mots", type=int, default=3,
                    help="combien d'instructions pour la signature")
    ap.add_argument("--sans-adresses", action="store_true",
                    help="retirer les long absolus (degrade : 98 -> 55)")
    ap.add_argument("--fenetre", type=int, default=400,
                    help="demi-largeur de la fenetre predicted, 0 = desactive")
    args = ap.parse_args()

    lignes = io.open(ASM, encoding="utf-8", errors="replace").read().split("\n")
    data = io.open(DAD, "rb").read()

    departs = []
    for i, l in enumerate(lignes):
        m = RE_FONCTION.match(l)
        if m:
            departs.append((m.group(1), i))

    # adresse DAD de la premiere instruction de chaque routine
    ADRESSE_L = [{}]
    for nom, i in departs:
        m = RE_ENC.search(lignes[i + 1]) if i + 1 < len(lignes) else None
        if m:
            try:
                ADRESSE_L[0][nom] = int(m.group(1), 16)
            except ValueError:
                pass

    uniques: dict[str, int] = {}
    ambigues: list[tuple[str, int]] = []
    absents: list[tuple[str, int]] = []
    sans_sig: list[str] = []
    signature_courte: list[str] = []
    resolus: list[str] = []

    dec = decalage_donnees(lignes, data)
    print("decalage des DONNEES       : %d" % dec)
    print("  => position predicted a +/- %d octets pour le code" % args.fenetre)
    print()

    for n, (nom, i) in enumerate(departs):
        fin = departs[n + 1][1] if n + 1 < len(departs) else len(lignes)
        sig, vus = octets_de_la_routine(lignes, i, fin, args.mots,
                                      args.sans_adresses)
        if not sig:
            sans_sig.append(nom)
            continue
        if len(sig) < 4:
            signature_courte.append(nom)

        # 1. recherche globale
        coups = trouver(data, sig)
        # 2. si elle est ambigue, on restreint a la fenetre predicted
        if len(coups) > 1 and args.fenetre > 0:
            adresse = ADRESSE_L[0].get(nom)
            if adresse is None:
                ambigues.append((nom, len(coups)))
                continue
            pred = adresse + dec
            dans = fenetre(sig, data, pred, args.fenetre)
            if len(dans) == 1:
                uniques[nom] = dans[0]
                resolus.append(nom)
                continue
            if dans:
                coups = dans
        if len(coups) == 1:
            uniques[nom] = coups[0]
        elif len(coups) > 1:
            ambigues.append((nom, len(coups)))
        else:
            # 3. absente globalement : on tente la fenetre predicted
            if args.fenetre > 0:
                adresse = ADRESSE_L[0].get(nom)
                if adresse is not None:
                    pred = adresse + dec
                    dans = fenetre(sig, data, pred, args.fenetre)
                    if len(dans) == 1:
                        uniques[nom] = dans[0]
                        resolus.append(nom)
                        continue
            absents.append((nom, vus))

    n = len(departs)
    print("DAD                   : %d octets" % len(data))
    print("routines du listing   : %d" % n)
    print()
    print("SIGNATURES UNIQUES    : %d  (%.1f%%)"
          % (len(uniques), 100.0 * len(uniques) / n))
    print("  -> exploitables pour un interpreteur")
    print("ambiguës (multiples)  : %d" % len(ambigues))
    print("absentes (0 hit)      : %d" % len(absents))
    print("sans aucun encodage   : %d" % len(sans_sig))
    if signature_courte:
        print("signature trop courte : %d  (a elargir avec --mots)"
              % len(signature_courte))

    if args.details:
        print()
        print("=== les 40 plusgrosses absentes ===")
        poids = {nom: i for nom, i in departs}
        for nom, lmots in sorted(absents, key=lambda x: -poids[x[0]])[:40]:
            print("  %-28s signature de %d mots" % (nom, lmots))
        print()
        print("=== ambiguës (30 premieres) ===")
        for nom, k in ambigues[:30]:
            print("  %-28s %d occurrences" % (nom, k))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())