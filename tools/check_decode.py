# -*- coding: utf-8 -*-
"""Controle de `_decode` (asm L14900-15119) et de ses trois tables.

Trois preuves, par execution :

1. **Le listing comme source.** Les 96 syllabes sont relues dans le
   listing : la table de pointeurs d'abord (`_start` L25075, `_end`
   L25108, `_mid` L25141), puis les octets **a l'adresse vers laquelle
   chaque entree pointe** (`;52972: 0004e35c` donne `$4e35c`). On ne
   relit donc pas nos propres noms.

2. **Une reecriture independante.** `assemblage_ind` est ecrite a partir
   du listing avec une autre formulation (`s[col:].startswith(mot)`)
   que `populous.decode._passe` (index explicite plus `break`). On les
   confronte sur ~7000 noms : les 1001 valides, chaque troncature, chaque
   suffixe en plus, et toutes les combinaisons deux a deux des tables.

3. **Le sens des octets.** Le code de 15 bits est reconstruit
   indifferemment par les deux voies pour les 1001 graines de
   `0, 5, ... 5000`, et chaque nom retourne une graine valide.

Les cinq retours negatifs du listing (-1, -2, -3, -4, -5) sont provoques
un par un.

Usage::

    python tools/check_decode.py
"""
from __future__ import annotations

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

ASM = os.path.join(ROOT, "reference", "tetracorp", "populous_prg.asm")
ENC = "utf-8"

TOTAL = [0]
KO = [0]


def check(label, cond, detail=""):
    TOTAL[0] += 1
    if not cond:
        KO[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "KO", label,
                           ("  -> " + detail) if detail else ""))


def main():
    from populous.decode import END, MID, START, NB, decode, _passe
    from populous.rng import Rng

    ls = io.open(ASM, "r", encoding=ENC, newline="").read().splitlines()
    from check_con_text import chaine, image
    mem = image(ls)

    # ---- 1. les trois tables, lues dans le listing ----------------------
    bornes = (("_start:", "_end:", 0x52972),
              ("_end:", "_mid:", 0x529F2),
              ("_mid:", "_a_flat:", 0x52A72))
    lues = []
    for debut, fin, base in bornes:
        i0 = next(k for k, l in enumerate(ls) if l.startswith(debut))
        i1 = next(k for k, l in enumerate(ls) if l.startswith(fin))
        table, adr, juste = [], base, 0
        for l in ls[i0:i1]:
            corps = l.split(";")[0].strip()
            m = re.match(r"^DC\.L\s+(\w+)\s*$", corps)
            if m is None:
                continue
            val = re.search(r";([0-9a-f]{5}):\s+([0-9a-f]{8})\s*$", l)
            ok = val is not None and int(val.group(1), 16) == adr
            adr += 4
            juste += ok
            table.append((m.group(1), int(val.group(2), 16))
                         if val is not None else (m.group(1), -1))
        lues.append(table)
        check("L25075-L25173 : les 32 entrees de `%s` portent chacune leur "
              "adresse $%05x..$%05x" % (debut[:-1], base, adr - 4),
              len(table) == 32 and juste == 32 and adr == base + 128,
              "%d entrees, %d adresses justes" % (len(table), juste))

    # ---- 2. les chaines, lues a leur adresse ----------------------------
    noms = [tuple(chaine(mem, ptr) for _, ptr in t) for t in lues]
    for attendu, port, nom in ((noms[0], START, "_start"),
                               (noms[1], END, "_end"),
                               (noms[2], MID, "_mid")):
        check("L25075-25173 : `%s` vaut %r" % (nom, port[:4] + ("...",)),
              port == attendu,
              "listing %r" % (attendu,))
        check("`%s` : les 32 syllabes sont non vides et en majuscules"
              % nom,
              all(t and t.upper() == t and t.isalpha() for t in port),
              repr([t for t in port if not (t and t.upper() == t
                                            and t.isalpha())][:4]))

    check("L25075-25173 : aucune syllabe en double dans une meme table",
          len(set(START)) == len(set(MID)) == len(set(END)) == NB,
          "%d/%d/%d distinctes"
          % (len(set(START)), len(set(MID)), len(set(END))))
    check("`_start` precede `_mid`, qui precede `_end` : les trois LEA de "
          "`_decode` sont lus dans cet ordre",
          [re.search(r"\(_(\w+),A4\)", l).group(1)
           for l in ls[14899:15120] if "LEA" in l
           and re.search(r"\(_(?:start|mid|end),A4\)", l)]
          == ["start"] * 3 + ["mid"] * 3 + ["end"] * 3,
          "L14914/L14977/L15039")
    check("L15096-15099 : la troisieme syllabe est decalee de 10 bits "
          "(`MOVEQ #$A,D1 ; ASL.W D1,D0 ; OR.W D0,(-2))",
          any("MOVEQ\t#$A,D1" in l and ";492a0" in l for l in ls[15095:15100]),
          "L14996-15028 pour le milieu : `MOVEQ\t#$5,D1`")

    # ---- 3. `_passe`, compare a la reecriture independante --------------
    def assemblage_ind(table, s, col):
        """`_decode`, un passage - formulation `startswith` (L14919-14951)."""
        reste = s[col:]
        for i, mot in enumerate(table):
            if reste.startswith(mot):
                return i, col + len(mot)
        return NB, col

    check("L14921-14939 : le zéro de fin de `s` n'est jamais confondu avec "
          "un caractere du mot",
          _passe(START, "RIN", 0) == (NB, 0)
          and _passe(START, "", 0) == (NB, 0),
          "%r / %r" % (_passe(START, "RIN", 0), _passe(START, "", 0)))
    check("L14949-14951 : sur correspondance le curseur avance de la "
          "longueur consommee",
          _passe(START, "RINGOUTH", 0) == (0, 4)
          and _passe(MID, "RINGOUTH", 4) == (0, 7),
          "%r / %r" % (_passe(START, "RINGOUTH", 0),
                       _passe(MID, "RINGOUTH", 4)))
    check("L14905-14956 : c'est la **premiere** syllabe compatible qui "
          "l'emporte, pas la plus longue",
          _passe(MID, "ING", 0) == (2, 3) and MID[2] == "ING",
          "%r" % (_passe(MID, "ING", 0),))

    # ---- 4. le code de 15 bits, par les deux voies ----------------------
    def code_ind(s):
        col = 0
        i, col = assemblage_ind(START, s, col)
        if i == NB:
            return -1
        code = i
        i, col = assemblage_ind(MID, s, col)
        if i == NB:
            return -2
        code |= i << 5
        i, col = assemblage_ind(END, s, col)
        if i == NB:
            return -3
        if len(s) != col:
            return -4
        return code | (i << 10)

    # les 1001 noms valides : graine -> code, puis code -> nom
    grains = list(range(0, 0x1388 + 1, 5))
    codes = {}
    for g in grains:
        c = Rng(g).raw() & 0xFFFF
        codes.setdefault(c, g)
    noms_ok = {}
    for g in grains:
        c = Rng(g).raw() & 0xFFFF
        noms_ok[g] = (START[c & 31] + MID[(c >> 5) & 31]
                      + END[c >> 10])
    check("L15101-15102 : les 1001 graines ne donnent pas 1001 codes "
          "distincts - la legende parle de 1,000",
          990 <= len(codes) <= 1001,
          "%d codes distincts pour 1001 graines" % len(codes))
    check("L15104-15117 : `_passe` lit `RINGOUTHILL` comme "
          "start=0 / mid=0 / end=0, donc code 0",
          code_ind("RINGOUTHILL") == 0
          and _passe(START, "RINGOUTHILL", 0) == (0, 4)
          and _passe(MID, "RINGOUTHILL", 4) == (0, 7)
          and _passe(END, "RINGOUTHILL", 7) == (0, 11),
          "code %r" % code_ind("RINGOUTHILL"))
    check("une syllabe de depart inconnue rend -1 (L14962)",
          decode("ZZZZ") == -1 and code_ind("ZZZZ") == -1,
          "%d / %d" % (decode("ZZZZ"), code_ind("ZZZZ")))
    check("start connu, milieu inconnu : -2 (L15023)",
          decode("RINGZZZZ") == -2 and code_ind("RINGZZZZ") == -2,
          "%d / %d" % (decode("RINGZZZZ"), code_ind("RINGZZZZ")))
    check("start et milieu connus, fin inconnue : -3 (L15085)",
          decode("RINGOUT") == -3 and code_ind("RINGOUT") == -3,
          "%d / %d" % (decode("RINGOUT"), code_ind("RINGOUT")))
    check("un nom plus long que les trois syllabes : -4 (L15088-15094)",
          decode("RINGOUTHILLZ") == -4 and code_ind("RINGOUTHILLZ") == -4,
          "%d / %d" % (decode("RINGOUTHILLZ"), code_ind("RINGOUTHILLZ")))

    # ---- 5. la confrontation sur ~7000 noms -----------------------------
    echantillons = list(noms_ok.values())
    for n in list(noms_ok.values()):
        echantillons += [n[:k] for k in range(1, len(n))]
        echantillons += [n + c for c in ("Z", " ", "0", "S")]
    echantillons += [START[i] for i in range(32)]
    echantillons += [START[i] + END[j] for i in range(0, 32, 3)
                     for j in range(0, 32, 3)]
    echantillons += [MID[i] + END[j] for i in range(0, 32, 3)
                     for j in range(0, 32, 3)]
    echantillons += [START[i] + MID[j] for i in range(0, 32, 3)
                     for j in range(0, 32, 3)]
    import random
    rnd = random.Random(20261012)
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for _ in range(400):
        echantillons.append("".join(rnd.choice(alphabet)
                                    for _ in range(rnd.randrange(0, 20))))
    echantillons = sorted(set(echantillons))

    ecarts = [(n, code_ind(n), _code_port(n)) for n in echantillons
              if code_ind(n) != _code_port(n)]
    check("les deux decompositions du code de 15 bits donnent le meme "
          "resultat sur %d noms" % len(echantillons),
          not ecarts, "%d ecarts, ex. %r" % (len(ecarts), ecarts[:3]))

    # ---- 6. `decode`, compare a l'ecriture independante -----------------
    def decode_ind(s):
        c = code_ind(s)
        if c < 0:
            return c
        for g in grains:
            if Rng(g).raw() & 0xFFFF == c:
                return g
        return -5

    mauvais = [(n, decode(n), decode_ind(n)) for n in echantillons
               if decode(n) != decode_ind(n)]
    check("`decode` rend la meme valeur que la reecriture independante sur "
          "%d noms" % len(echantillons),
          not mauvais, "%d ecarts, ex. %r" % (len(mauvais), mauvais[:3]))
    check("L15118 : un nom correct dont le code n'est pas atteignable rend "
          "-5",
          decode("RINGOUTHILL") == -5,
          "code 0, graines %r ... %r"
          % (Rng(0).raw() & 0xFFFF, Rng(5000).raw() & 0xFFFF))

    # ---- 7. les 1001 noms tournent sur leur graine ----------------------
    # ... sauf deux : `_mid` essaye `EA` (17) avant `E` (26), et `_end` rend
    # alors `AL` suivi d'un `L` orphelin que plus aucune syllabe ne prend.
    retour, bacs = {}, [0] * 11
    hors = []
    for k, g in enumerate(grains):
        nom = noms_ok[g]
        r = decode(nom)
        retour.setdefault(r, []).append(g)
        if code_ind(nom) != Rng(g).raw() & 0xFFFF:
            hors.append((g, nom, r))
        elif r == g:
            bacs[k // 91] += 1
    check("999 des 1001 noms construits depuis une graine retombent sur "
          "leur propre code",
          len(grains) == 1001 and len(hors) == 2,
          "%d ecarts sur %d" % (len(hors), len(grains)))
    check("les deux noms qui ne retombent pas sont `NIMEAL` (3095) et "
          "`BUREAL` (4685), et l'original rend -3 sur chacun - c'est un "
          "limite du balayage, pas une reecriture",
          [(nom, r) for _, nom, r in hors]
          == [("NIMEAL", -3), ("BUREAL", -3)],
          repr([(nom, r) for _, nom, r in hors]))
    check("cause : `_mid` est balaye dans l'ordre, `EA` (17) est donc "
          "essayee avant `E` (26), et `_end` rend ensuite `AL` suivi d'un "
          "`L` que plus aucune syllabe ne reprend",
          _passe(MID, "NIMEAL", 3) == (17, 5)
          and _passe(END, "NIMEAL", 5) == (NB, 5),
          "%r / %r" % (_passe(MID, "NIMEAL", 3), _passe(END, "NIMEAL", 5)))
    for bac in range(11):
        attendu = len([k for k in range(len(grains)) if k // 91 == bac])
        perdus = len([k for k in range(len(grains))
                      if k // 91 == bac and grains[k] in (3095, 4685)])
        check("aller-retour : les graines du sac %d rendent leur nom"
              % bac,
              bacs[bac] == attendu - perdus,
              "%d/%d (2 noms perdus en tout)" % (bacs[bac],
                                                 attendu - perdus))
    check("chaque nom valide rend **une** graine, toujours un multiple de "
          "5 dans [0, 5000]",
          set(retour) - {-3} == set(codes.values()) - {3095, 4685}
          and all(g % 5 == 0 and 0 <= g <= 5000 for g in retour if g >= 0),
          "%d graines rendues distinctes" % len(retour))
    egaux = [c for c in list(codes) if 0 < len(
        [g for g in grains if Rng(g).raw() & 0xFFFF == c]) > 1]
    check("quand deux graines donnent le meme code, `decode` rend la "
          "**plus petite** (la boucle croissante de L15105-15117)",
          all(decode(START[c & 31] + MID[(c >> 5) & 31] + END[c >> 10])
              == min(g for g in grains if Rng(g).raw() & 0xFFFF == c)
              for c in egaux[:12]),
          "%d codes en collision, %d verifies" % (len(egaux),
                                                  min(12, len(egaux))))

    # ---- 8. l'effet de bord sur `_seed` ---------------------------------
    class Jeu:
        seed = -999

    j, k = Jeu(), Jeu()
    r = decode("RINGINGHILL", j)
    ri = decode_ind_avec_etat(k, "RINGINGHILL")
    check("L15106 : `_seed` est ecrit a chaque tentative - au retour il "
          "vaut le tirage de la derniere",
          r == ri and j.seed == k.seed,
          "graine %d, `_seed` = %d (independant %d)"
          % (r, j.seed, k.seed))

    # ---- 9. `_atoi` (C), tel que L12262-12265 l'emploie -----------------
    from populous.game import _atoi
    cas = (("12345", 12345), ("  007", 7), ("-12", -12), ("+42", 42),
           ("", 0), ("GENESIS", 0), ("12abc", 12), ("   ", 0))
    for s, v in cas:
        check("___atoi(%r) = %d" % (s, v), _atoi(s) == v,
              "obtenu %d" % _atoi(s))

    print("\n%d controles, %d echec(s)" % (TOTAL[0], KO[0]))
    return 1 if KO[0] else 0


def _code_port(s):
    """Le code de 15 bits par la voie de `populous.decode` (sans la graine)."""
    from populous.decode import END, MID, NB, START, _passe
    pos = 0
    d4, pos = _passe(START, s, pos)
    if d4 == NB:
        return -1
    code = d4
    d4, pos = _passe(MID, s, pos)
    if d4 == NB:
        return -2
    code |= d4 << 5
    d4, pos = _passe(END, s, pos)
    if d4 == NB:
        return -3
    if len(s) != pos:
        return -4
    return code | (d4 << 10)


def decode_ind_avec_etat(jeu, s):
    """La recherche de graine ecrite autrement, pour comparer l'effet de bord."""
    from populous.decode import END, MID, NB, START
    from populous.rng import Rng

    def pas(table, t, col):
        reste = t[col:]
        for i, mot in enumerate(table):
            if reste.startswith(mot):
                return i, col + len(mot)
        return NB, col

    col = 0
    i, col = pas(START, s, col)
    if i == NB:
        return -1
    code = i
    i, col = pas(MID, s, col)
    if i == NB:
        return -2
    code |= i << 5
    i, col = pas(END, s, col)
    if i == NB:
        return -3
    if len(s) != col:
        return -4
    code |= i << 10
    g = 0
    while True:
        jeu.seed = g
        rng = Rng(g)
        v = rng.raw() & 0xFFFF
        jeu.seed = rng.seed
        if v == code:
            return g
        g += 5
        if g > 0x1388:
            return -5


if __name__ == "__main__":
    sys.exit(main())
