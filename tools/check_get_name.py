# -*- coding: utf-8 -*-
"""Controle de `_get_name` (asm L10307-10489) - l'editeur de nom au clavier.

La routine est **executee**, pas relue : `Game.get_name` tourne avec une
file de touches et un scenario de clics, et l'on regarde ce qu'elle rend
ainsi que ce qu'elle dessine. Quatre reperes du listing sont en plus
relus mot a mot, pour que le comportement observe ne puisse pas venir
d'ailleurs :

=========================================  ==============================
Ce que l'on releve                          Pourquoi
=========================================  ==============================
sept arguments, `LEA ($16,A7)` a 6 endroits l'empilement des 6 appels
`LINK.W A5,#-46` puis `LEA (-40,A5)`         le tampon `scratch` = 40 octets
aucun `_mouse` dans la routine               la souris vient de la VERTB
`_setup_interrupt` + `___AddIntServer(5)`    la preuve, en L10202-10204
=========================================  ==============================

Usage::

    python tools/check_get_name.py
"""
from __future__ import annotations

import io
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

ASM = os.path.join(ROOT, "reference", "tetracorp", "populous_prg.asm")

from populous.game import Game  # noqa: E402

TOTAL = [0]
KO = [0]

# Les deux cadres que `_check_cancel` lit (L12110 et L12135).
OK_BOX = (0x20, 0x90, 0x70)
CANCEL_BOX = (0xA0, 0x90, 0xF0)


def check(label, cond, detail=""):
    TOTAL[0] += 1
    if not cond:
        KO[0] += 1
    print("  [%s] %s%s" % ("OK" if cond else "KO", label,
                           ("  -> " + detail) if detail else ""))


def editer(g, texte, touches, clics=(), n=16, x=0x20, y=0x2C,
           ok=OK_BOX, cancel=CANCEL_BOX):
    """Fait tourner `Game.get_name`.

    Une touche est poussee par image, **uniquement** pendant que
    `_saisie` est vrai - exactement ce que `handle` fait avec les KEYDOWN
    d'un vrai evenement. Les clics sont consommes pareil, un par image,
    comme les etapes d'un `scenario` d'autre part.
    """
    traces = []
    vrai = g.ren.draw_text
    k = [0]
    c = [0]
    g._touches = []

    def draw(dest, dx, dy, t):
        traces.append((dx, dy, t))
        return vrai(dest, dx, dy, t)

    def pompe():
        if g._saisie and k[0] < len(touches):
            g._touches.append(touches[k[0]])
            k[0] += 1
        if c[0] < len(clics):
            mx, my, presse = clics[c[0]]
            c[0] += 1
            g.mouse = (mx, my)
            g._raw_left = presse
            g._read_buttons()

    g.ren.draw_text = draw
    g._pompe = pompe
    try:
        res = g.get_name(texte, x, y, n, ok, cancel)
    finally:
        del g._pompe
        g.ren.draw_text = vrai
        g._touches = []
    return res, traces, k[0]


def main():
    g = Game(59, 0, 3)

    # ---- 1. la signature, relevee sur les six appels ---------------------
    ls = io.open(ASM, "r", encoding="utf-8", newline="").read().splitlines()
    d = next(i for i, l in enumerate(ls) if l.startswith("_get_name:"))
    f = next(i for i, l in enumerate(ls) if l.startswith("_save_load:"))
    corps = ls[d:f]

    appelants = [i + 1 for i, l in enumerate(ls)
                 if "JSR\t(_get_name,PC)" in l]
    details = []
    bon = True
    for n in appelants:
        # les six octets `LEA ($16,A7),A7` suivent le JSR a +-2 lignes
        apres = ls[n:n + 4]
        ok_ligne = [i + n + 1 for i, l in enumerate(apres)
                    if "LEA\t($16,A7),A7" in l]
        details.append("%d->%s" % (n, ok_ligne))
        bon = bon and bool(ok_ligne)
    check("L10798, L10814, L11177, L11628, L11675, L12249 : les six appels "
          "depilent 22 octets = 4+4+2+2+2+4+4, soit **sept arguments**",
          len(appelants) == 6 and bon, " ".join(details))

    check("L10308 : le cadre fait 46 octets, dont 40 pour `scratch` a "
          "`(-40,A5)` - deux octets de trop et le tampon deborde",
          "LINK.W\tA5,#-46" in corps[1]
          and "LEA\t(-40,A5),A0" in "\n".join(corps), corps[1].strip())
    check("L10310-10312 : `-46` est initialise par `___strlen`, c'est la "
          "position du curseur",
          "JSR\t(___strlen,A4)" in "\n".join(corps[:6]), "")

    texte_corps = "\n".join(corps)
    check("La routine n'appelle **aucune** lecture de souris : `_mousex`, "
          "_mousey et `___mouse` sont absents des 183 lignes",
          "_mousex" not in texte_corps and "_mousey" not in texte_corps
          and "___mouse" not in texte_corps, "")
    check("L10388 et L10441 : en revanche `_keyboard` et `_check_cancel` "
          "y sont appeles",
          "JSR\t(___keyboard,A4)" in texte_corps
          and "JSR\t(_check_cancel,PC)" in texte_corps, "")
    inter = [i + 1 for i, l in enumerate(ls)
             if "___AddIntServer,A4" in l]
    vbl = [i + 1 for i, l in enumerate(ls)
            if i + 1 in range(inter[0] - 4, inter[0] + 1) and "5.W" in l]
    check("L10202-10204 : `_setup_interrupt` pose `___mouse` comme serveur "
          "d'interruption **5** (VERTB) - c'est de la que vient la souris "
          "pendant `_get_name`, et non d'un appel de la routine",
          bool(inter) and bool(vbl), "AddIntServer=%s 5.W=%s"
          % (inter, vbl))
    ecrits = [i + d + 1 for i, l in enumerate(corps)
              if "MOVE.W\t#$0002,(_left_button,A4)" in l]
    check("L10348 et L10457 : `_left_button` n'est ecrit qu'a l'entree et "
          "dans la branche `check_cancel == 0`",
          ecrits == [10348, 10457], "ecrits=%s" % ecrits)

    # ---- 2. le remplissage : le champ fait toujours `maxlen` glyphes ----
    res, traces, _ = editer(g, "AB CD", ["\r"], n=8)
    champs = [t for _, _, t in traces]
    check("L10313-10347 : l'espace interne devient `$82` et la chaine est "
          "completee jusqu'a `maxlen` avant le zero de L10344",
          res == "AB\x82CD", "res=%r len=%d" % (res, len(res)))
    check("L10349 puis L10382 : chaque champ dessine fait exactement "
          "`maxlen = 8` glyphes, jamais un de plus",
          champs and all(len(t) == 8 for t in champs),
          "longueurs=%s" % sorted({len(t) for t in champs}))
    check("L10349 : le premier dessin est le tampon `scratch`, tout en "
          "`$82`", champs and champs[0] == "\x82" * 8, "champs[0]=%r"
          % (champs[0],))
    check("L10350-10351 : il est trace en (x>>3, y) = (4, 44)",
          bool(traces) and traces[0][:2] == (0x20 >> 3, 0x2C),
          "premier=%s" % (traces[0][:2],))

    # ---- 3. les majuscules et la borne `maxlen - 1` (L10410-10400) -------
    res, _, _ = editer(g, "", ["a", "b", "z", "\r"], n=8)
    check("L10410-10414 : les lettres minuscules sont stockees en "
          "majuscules", res == "ABZ", "res=%r" % res)

    res, _, _ = editer(g, "", list("abcdefghij") + ["\r"], n=8)
    check("L10396-10400 : on n'ecrit plus des que `curseur >= maxlen - 1`, "
          "donc sept caracteres pour `maxlen = 8`",
          res == "ABCDEFG" and len(res) == 7, "res=%r" % res)

    res, _, _ = editer(g, "", list("abc") + ["\x7f", "\r"], n=8)
    check("L10424 : `$7f` efface comme `$08`", res == "AB", "res=%r" % res)

    res, _, _ = editer(g, "", ["A", "B", "\x08", "\x08", "\x08", "\r"], n=8)
    check("L10427-10432 : la retour arriere recule en posant `$82` a "
          "l'ancienne position, et un troisieme appui sur un champ vide "
          "ne fait rien", res == "", "res=%r" % res)

    res, _, _ = editer(g, "", ["\x1b", "\r"], n=8)
    check("L10392-10395 + L10478 : une touche hors `$20..$7A`, ni `$08`, "
          "ni `$7f`, ni `$0d` est ignoree - le champ reste vide",
          res == "", "res=%r" % res)

    # ---- 4. le clignotement : `maxlen + 20` (L10359-10364) --------------
    # 57 images : t = 0 a 56, et le reste ne s'annule qu'en 0, 28 et 56.
    res, traces, prises = editer(g, "", ["\x1b"] * 56 + ["\r"], n=8)
    # le premier dessin est `scratch` : les champs suivants portent t = 0..
    # 57 images de boucle + le redraw de L10464, soit 58 champs.
    champs = [ord(t[0]) for _, _, t in traces[1:58]]
    changements = [i for i in range(1, len(champs))
                   if champs[i] != champs[i - 1]]
    check("L10359-10364 : le curseur ne bouge qu'aux multiples de "
          "`maxlen + 20 = 28` - soit les images 28 et 56 apres celle 0",
          changements == [28, 56] and len(champs) == 57,
          "changements=%s champs=%d (prises=%d)"
          % (changements, len(champs), prises))
    check("L10366-10380 : le curseur alterne `$83` puis `$82` selon qu'il "
          "etait deja `$82`",
          champs[0] == 0x83 and champs[28] == 0x82 and champs[56] == 0x83,
          "%02x %02x %02x" % (champs[0], champs[28], champs[56]))
    check("Les 57 touches ont ete lues, une par image (L10388)",
          prises == 57, "prises=%d" % prises)
    check("L10475-10487 : la validation ne laisse que les caracteres "
          "anteurs au curseur", res == "", "res=%r" % res)

    # ---- 5. la souris est vivante pendant la boucle ----------------------
    res, traces, prises = editer(
        g, "GENESIS",
        ["\x1b"] * 6,                       # toutes inutiles
        clics=[(0, 0, False), (CANCEL_BOX[0] + 4, CANCEL_BOX[1] + 8, True)],
        n=16)
    check("L10445-10451 : un clic dans CANCEL coupe la boucle avant le "
          "clavier - `texte[0]` est efface et la fonction rend la main",
          res == "" and prises <= 2, "res=%r touches=%d/6" % (res, prises))
    check("L10447 : la rendue est bien la chaine vide, pas `None`",
          res == "", "%r" % res)

    res, traces, prises = editer(
        g, "GENESIS",
        ["\x1b"] * 6,
        clics=[(0, 0, False), (OK_BOX[0] + 4, OK_BOX[1] + 8, True)],
        n=16)
    check("L10452-10453 puis L10460-10489 : un clic dans OK valide sans "
          "attendre RETOUR et ne trime que les `$82` de fin",
          res == "GENESIS" and prises <= 2,
          "res=%r touches=%d/6" % (res, prises))

    # ---- 6. la validation par RETOUR, et le troncature -------------------
    res, traces, _ = editer(g, "un nom beaucoup trop long pour le champ",
                            ["\r"], n=16)
    dessines = [len(t) for _, _, t in traces]
    check("L10316-10344 : les espaces internes passent aussi a `$82`, le "
          "zero est pose a `texte[maxlen]` (et non a `strlen`), et le trim "
          "de L10480-10487 n'enleve que les `$82` de fin",
          res == "un\x82nom\x82beaucoup" and len(res) == 15,
          "res=%r len=%d" % (res, len(res)))
    check("Chaque dessin (scratch, boucle, validation) porte 16 glyphes : "
          "une chaine plus longue que le champ ne deborde jamais",
          bool(dessines) and set(dessines) == {16},
          "dessins=%s" % dessines)

    res, _, _ = editer(g, "", list("ok") + ["\r"], n=6)
    check("L11675 : le plus petit des six `maxlen` (6, le champ de baud) "
          "borne le champ a `maxlen - 1 = 5` caracteres",
          res == "OK" and len(res) == 2, "res=%r" % res)

    res, _, _ = editer(g, "", ["a", "b", "c", "d", "e", "f", "\r"], n=6)
    check("Idem, a la borne : cinq caracteres ecrits sur sept tries",
          res == "ABCDE", "res=%r" % res)

    # ---- 7. la sortie laisse le clavier a personne d'autre ---------------
    check("L10307-10489 : `_saisie` est reposse a faux, y compris par "
          "`finally`", g._saisie is False and g._touches == [],
          "_saisie=%s touches=%s" % (g._saisie, g._touches))

    print("\n%d controles, %d echec(s)" % (TOTAL[0], KO[0]))
    return 1 if KO[0] else 0


if __name__ == "__main__":
    sys.exit(main())
