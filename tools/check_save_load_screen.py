# -*- coding: utf-8 -*-
"""Controle de l'ecran SAVE/LOAD — `_save_load` (asm L10493-10972).

Le tiroir et le tri sont verifies par `tools/check_saveslots.py`. Ici on verifie
la **navigation** : zone cliquable, lecture de la ligne, defilement, et le
raccord avec `save_game` / `load_game` — y compris l'effet sur `_saved`.

`_pompe` est remplace par un scenario, comme pour les autres boucles modales.

Usage::

    python tools/check_save_load_screen.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from populous.game import Game  # noqa: E402

TOTAL = [0]
KO = [0]


def check(label, cond, detail=""):
    TOTAL[0] += 1
    if not cond:
        KO[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "KO", label,
                           ("  -> " + detail) if detail else ""))


def scenario(g, pas):
    n = [0]

    def pompe():
        if n[0] >= len(pas):
            return
        mx, my, presse = pas[n[0]]
        n[0] += 1
        g.mouse = (mx, my)
        g._raw_left = presse
        g._read_buttons()

    g._pompe = pompe


def main():
    g = Game(59, 0, 3)
    d = tempfile.mkdtemp()
    try:
        for nom in ("un.GAM", "deux.GAM", "trois.GAM", "quatre.GAM",
                    "cinq.GAM", "six.GAM", "sept.GAM"):
            open(os.path.join(d, nom), "wb").close()
        g._saves_drawer = d
        g._saves_liste = []
        from populous.saveslots import get_a_dir, sort
        g._saves_liste = get_a_dir(d)
        sort(g._saves_liste)
        noms = [x.rstrip(b"\x00").decode("latin-1") for x in g._saves_liste]

        check("L10589-10598 : le tiroir est liste une fois, puis trie a "
              "l'envers",
              noms == sorted(noms, reverse=True) and len(noms) == 7,
              str(noms))

        # ---- la zone cliquable (L10759-10784) --------------------------
        g._saves_defil = 0
        g._saves_nom = ""
        g.mouse = (0x60, 0x22)
        check("L10759-10766 : x = $60 et y = $22 touchent la premiere ligne",
              g._survol_save_load() == 0,
              "survol=%s" % g._survol_save_load())
        check("L10779-L10781 : `_filename` prend l'entree cliquee",
              g._saves_nom == noms[0], g._saves_nom)

        g.mouse = (0x60, 0x2A)
        check("L10767-10771 : `(y-$22) >> 3` donne l'index de la ligne",
              g._survol_save_load() == 1, "survol=%s" % g._survol_save_load())

        g.mouse = (0x60, 0x22 + 8 * 9)
        check("L10772-10774 : une ligne au-dela du contenu est refusee",
              g._survol_save_load() is None,
              "survol=%s" % g._survol_save_load())

        g.mouse = (0x57, 0x22)
        check("L10759-10760 : x < $58 est dehors",
              g._survol_save_load() is None)
        g.mouse = (0xD9, 0x22)
        check("L10761-10762 : x > $D8 est dehors",
              g._survol_save_load() is None)
        g.mouse = (0x60, 0x21)
        check("L10763-10764 : y < $22 est dehors",
              g._survol_save_load() is None)
        g.mouse = (0x60, 0x83)
        check("L10765-10766 : y > $82 est dehors",
              g._survol_save_load() is None)

        # ---- le defilement (L10819-10842) ------------------------------
        g._saves_defil = 0
        g._defiler_save_load(-1)
        check("L10827-10828 : la fleche du haut ne descend pas sous zero",
              g._saves_defil == 0)
        g._defiler_save_load(1)
        g._defiler_save_load(1)
        check("L10841-10842 : la fleche du bas avance",
              g._saves_defil == 2, "defil=%d" % g._saves_defil)
        for _ in range(20):
            g._defiler_save_load(1)
        check("L10837-10840 : `defil + 5 < n` borne le defilement",
              g._saves_defil == 2, "defil=%d (n=%d)" % (g._saves_defil, len(noms)))
        for _ in range(20):
            g._defiler_save_load(-1)
        check("L10827 : la fleche du haut revient a zero",
              g._saves_defil == 0)

        # ---- SAVE : la boucle ecrit reellement un fichier ----------------
        g._saved = False
        ok, cancel = g._cadres_boutons(*g._boite_save_load())
        g._saves_liste = get_a_dir(d)
        sort(g._saves_liste)
        pas = [(0, 0, False), (0x60, 0x22, True),          # ligne 0
               (0, 0, False), (ok[0] + 4, ok[1] + 8, True)]  # OK
        scenario(g, pas)
        r = g.save_load(True)
        del g._pompe
        check("L10888-10894 + L10930 : SAVE ecrit le fichier et pose "
              "`_saved`", r == 1 and g._saved is True,
              "r=%d _saved=%s" % (r, g._saved))
        # `_get_a_dir` majusculise (L16870), donc selectionner l'emplacement
        # "UN" ecrit `UN.GAM` : sur un systeme de fichiers insensible a la
        # casse comme Windows, cela **ecrase** `un.GAM`. C'est la machine.
        attendu = noms[0] + ".GAM"
        fichiers = sorted(os.listdir(d))
        check("L10832-10886 + L17130 : le fichier porte le nom de "
              "l'emplacement, majusculise par `_get_a_dir`",
              attendu.lower() in [f.lower() for f in fichiers]
              and len([f for f in fichiers if f.upper().endswith(".GAM")]) == 7,
              "%s (attendu %s)" % (fichiers, attendu))

        # ---- CANCEL ne fait rien ----------------------------------------
        avant = sorted(os.listdir(d))
        scenario(g, [(0, 0, False), (cancel[0] + 4, cancel[1] + 8, True)])
        r = g.save_load(True)
        del g._pompe
        check("L10850 : CANCEL rend 0 sans rien ecrire",
              r == 0 and sorted(os.listdir(d)) == avant,
              "r=%d" % r)

        # ---- les deux zones d'edition lèvent ---------------------------
        for y, nom in ((0x90, "tiroir"), (0xA4, "nom de fichier")):
            scenario(g, [(0, 0, False), (0x60, y, True)])
            leve, detail = False, ""
            try:
                g.save_load(True)
            except NotImplementedError as exc:
                leve, detail = True, str(exc)
            del g._pompe
            check("L10787-10815 : la zone d'edition du %s leve en nommant "
                  "`_get_name`" % nom, leve and "_get_name" in detail,
                  detail or "aucune leve")

        # ---- LOAD relit ce que SAVE a ecrit -----------------------------
        import random
        sim = g.sim
        for i in range(5):
            p = sim.peeps[i]
            p.tribe = i % 2
            p.life = 500 + i
            p.block = 0x30 + i
        sim.no_peeps = 5
        sim.player = 1
        sim.game_turn = 4242
        g._saves_liste = get_a_dir(d)
        sort(g._saves_liste)
        nom_cible = noms[0] + "2"
        i_cible = [x.rstrip(b"\x00").decode("latin-1")
                   for x in g._saves_liste].index(noms[0])
        # on ecrit sous un nom qu'on sait retrouver
        from populous.saveslots import chemin_complet
        g.save_game(chemin_complet(d, nom_cible))
        g._saves_liste = get_a_dir(d)
        sort(g._saves_liste)
        lignes = [(k, x.rstrip(b"\x00").decode("latin-1"))
                  for k, x in enumerate(g._saves_liste)]
        cible = next(k for k, n in lignes if n == nom_cible.upper())
        scenario(g, [(0, 0, False), (0x60, 0x22 + 8 * cible, True),
                     (0, 0, False), (ok[0] + 4, ok[1] + 8, True)])
        r = g.save_load(False)
        del g._pompe
        check("L10888/L10952-10954 : LOAD relit et rend 1", r == 1, "r=%d" % r)
        check("L17508-17570 : les valeurs rechargees sont celles ecrites",
              sim.game_turn == 4242 and sim.player == 1
              and sim.peeps[3].life == 503,
              "tour=%d joueur=%d vie[3]=%d"
              % (sim.game_turn, sim.player, sim.peeps[3].life))
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print("\n%d controles, %d echec(s)" % (TOTAL[0], KO[0]))
    return 1 if KO[0] else 0


if __name__ == "__main__":
    sys.exit(main())