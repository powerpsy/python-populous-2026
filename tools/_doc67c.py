# -*- coding: utf-8 -*-
"""Phase 67 (suite) : corriger la doc de `_requester` + journal."""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
ENC = "utf-8"


def load(p):
    with io.open(p, "r", encoding=ENC) as f:
        return f.read()


def save(p, t):
    with io.open(p, "w", encoding=ENC, newline="") as f:
        f.write(t)


# --- 1. la vraie signature de `_requester` -----------------------------------
p = "populous/game.py"
t = load(p)
bad = """            Les 6 pushes avant le JSR donnent :

                _requester(ecran, x, y, largeur, hauteur, titre, message)
"""
good = """            Les **sept** pushes avant le JSR donnent :
``_requester(ecran, x, y, largeur, hauteur, end_ok, end_cancel)``. Les
            deux derniers arguments ne sont pas des chaines mais des
            **structures de trois mots** ``(x0, y0, x1)`` que la routine
            remplit elle-meme (L10081-10085 pour CANCEL) et dont le texte
            est a ``+6`` (L10046-10052 : ``ADDQ.L #6,A0`` puis ``___strlen``) -
            d'ou ``DC.B "OK",0`` a ``_end_ok+6`` (L24354) et
            ``DC.B "CANCEL",0`` a ``_end_cancel+6`` (L24361). Les appels du
            listing passent donc ``PEA (_end_cancel,A4)`` puis
            ``PEA (_end_ok,A4)`` (L13634-13635 pour ``_options``).

            Ce port n'a garde que les deux chaines : le cadre et le texte
            sont fideles, les **boutons OK/CANCEL ne sont pas poses** et
            leurs cadres sont calcules par l'appelant (voir
            ``Game.check_cancel``). ECART assume, Phase 67.

            Releve dans le tas d'appels :
``_requester(d_screen, $10, $10, $120, $A6, ...)`` pour ``_options``
            (L13636-13640), ``(d_screen, $30, $46, $E4, $40, ...)`` pour la
            saisie du niveau (L11927).
"""
assert bad in t, "ancre requester"
t = t.replace(bad, good, 1)
save(p, t)
print("OK docstring requester")

# --- 2. journal --------------------------------------------------------------
SECTION = '''### Phase 67 (suite) - `_check_cancel` transcrit, et la signature de `_requester` corrigee

En branchant `_options`, une chose est tombee : **la signature du port pour
`_requester` est fausse**.

Les sept pushes avant le JSR (L13634-13640 pour `_options`) donnent
``_requester(ecran, x, y, largeur, hauteur, end_ok, end_cancel)``. Les deux
derniers arguments ne sont pas des chaines mais des **structures de trois
mots** `(x0, y0, x1)` que la routine remplit elle-meme (L10081-10085) et dont
le texte est a `+6` - d'ou `DC.B "OK",0` a `_end_ok+6` (L24354). Les appels
du listing passent donc `PEA (_end_cancel,A4)` puis `PEA (_end_ok,A4)`.

Le port n'avait garde que les deux chaines : le cadre et le texte sont
fideles, mais **les boutons OK/CANCEL ne sont pas poses**. Ecart assume et
documente dans la docstring de `requester` ; les cadres sont desormais
calcules par l'appelant.

**`_check_cancel` (L12106-12159) est transcrit** : ``Game.check_cancel(ok,
cancel)`` recoit les deux structures `(x0, y0, x1)` et renvoie 0 / 1 (OK) /
2 (CANCEL). Le test de chaque cadre est

    x0 <= _mousex <= x1   et   y0 <= _mousey <= y0 + $10

- une bande haute de 16 px, et dans cet ordre : OK d'abord (L12110), CANCEL
ensuite (L12135), un cadre nul etant saute. `_left_button != 0` coupe court
et rend 0 (L12108).

#### Verification

`tools/check_checkcancel.py` (nouveau) : **198 cas** de souris systematiques
(3 etats de bouton x 11 positions x 6 positions) confrontes a une reecriture
independante du listing, plus 9 cas particuliers (bornes inclusives, bande
des 16 px, cadre nul, entre les deux cadres) : **11 controles, 0 echec**.

Suite complete toujours au vert : `check_options` 17/17 ; `autopilot` 84/84 ;
`check_icons` 51/51 ; `check_level` 41/41.
'''
P = "docs/PROGRESSION.md"
t = load(P)
anc = "### Reste a faire"
assert t.count(anc) == 1
t = t.replace(anc, SECTION + anc, 1)

bad = ("  ouverts : `_options` (L13617) et `_game_options`")
if bad in t:
    t = t.replace(bad, "  ouverts : `_game_options`", 1)
save(P, t)
print("ecrit : docs/PROGRESSION.md (%d lignes)" % t.count("\n"))

G = "docs/game_logic.md"
t = load(G)
bad = "**`_check_cancel`** renvoie `0` tant qu'aucun des deux cadres n'est\n touche, `1` pour OK et `2` pour CANCEL - chacun teste une boite de 16 px de\n haut (L12125-12129)."
good = ("**`_check_cancel`** (L12106-12159) recoit les deux **structures**\n"
        "`(x0, y0, x1)` que `_requester` vient de remplir et renvoie `0`\n"
        "tant qu'aucun des deux cadres n'est touche, `1` pour OK et `2` pour\n"
        "CANCEL - chacun teste `x0 <= _mousex <= x1` et\n"
        "`y0 <= _mousey <= y0 + $10`, une bande de 16 px. L'ordre des deux\n"
        "tests est OK puis CANCEL ; `_left_button != 0` rend 0 immediatement.")
assert bad in t, "ancre check_cancel doc"
t = t.replace(bad, good, 1)

bad2 = ("| boite | 13634-13642 | `_requester(d_screen, $10, $10, $120, $A6, ...)` |")
good2 = ("| boite | 13634-13642 | `_requester(d_screen, $10, $10, $120, $A6, _end_ok,\n"
         "      _end_cancel)` - sept arguments, les deux derniers etant des structures\n"
         "      `(x0, y0, x1)` remplies par la routine (texte a `+6`) |")
assert bad2 in t, "ancre requester doc"
t = t.replace(bad2, good2, 1)
save(G, t)
print("ecrit : docs/game_logic.md (%d lignes)" % t.count("\n"))
