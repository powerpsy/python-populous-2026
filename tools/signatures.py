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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--details", action="store_true",
                    help="montrer les routines non trouvees et les ambiguites")
    ap.add_argument("--mots", type=int, default=3,
                    help="combien d'instructions pour la signature")
    ap.add_argument("--sans-adresses", action="store_true",
                    help="retirer les long absolus (degrade : 98 -> 55)")
    args = ap.parse_args()

    lignes = io.open(ASM, encoding="utf-8", errors="replace").read().split("\n")
    data = io.open(DAD, "rb").read()

    departs = []
    for i, l in enumerate(lignes):
        m = RE_FONCTION.match(l)
        if m:
            departs.append((m.group(1), i))

    uniques: dict[str, int] = {}
    ambigues: list[tuple[str, int]] = []
    absents: list[tuple[str, int]] = []
    sans_sig: list[str] = []
    signature_courte: list[str] = []

    for n, (nom, i) in enumerate(departs):
        fin = departs[n + 1][1] if n + 1 < len(departs) else len(lignes)
        sig, vus = octets_de_la_routine(lignes, i, fin, args.mots,
                                      args.sans_adresses)
        if not sig:
            sans_sig.append(nom)
            continue
        if len(sig) < 4:
            signature_courte.append(nom)
        coups = trouver(data, sig)
        if len(coups) == 1:
            uniques[nom] = coups[0]
        elif len(coups) > 1:
            ambigues.append((nom, len(coups)))
        else:
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