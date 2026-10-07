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
4. les codes ``2, 7, 8, 12, 13`` doivent **lever** ``NotImplementedError``
   et surtout pas retomber silencieusement en no-op : c'est la regle de
   Phase 22, et c'est exactement ce que ``_sub_action`` faisait.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from populous.constants import ACT_ACTION  # noqa: E402

CIBLES = ("do_war", "do_flood", "do_knight")
CODES_APPELES = (3, 4, 5)
CODES_SANS_CIBLEE = (1, 6, 11, 15)
CODES_NON_TRANSCRITS = (2, 7, 8, 12, 13)
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
    n_ok = 0
    for code in CODES_NON_TRANSCRITS:
        try:
            pe.dispatch(0, ACT_ACTION, 0, code)
        except NotImplementedError:
            n_ok += 1
        except Exception as exc:
            echecs.append("code %d : erreur inattendue %r" % (code, exc))
        else:
            echecs.append("code %d : PAS leve — no-op silencieux" % code)
    print("codes 2/7/8/12/13 lèvent                 : %d/%d"
          % (n_ok, len(CODES_NON_TRANSCRITS)))

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
