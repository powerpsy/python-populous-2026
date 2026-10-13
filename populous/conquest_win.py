r"""L'ecran de victoire de conquete — `_won_conquest` (asm L14460-14494).

 Transcription de la sequence complete, dans l'ordre du listing.

## La condition de fin (asm L4323-4352)

Appelee depuis la simulation, chaque tour :

* si ``good_pop[joueur] == 0`` **ou** ``_surender == joueur``
  -> ``_end_game(1)`` : le joueur a **perdu** ;
* sinon, si ``good_pop[adv] == 0`` **ou** ``_surender == adv``
  -> ``_end_game(0)`` : le joueur a **gagne**.

**Attention au sens de l'argument.** L'asm ne passe pas un booleen
« gagne » : a L14027 il fait ``CMPI.W #$0001,(8,A5)`` et, si l'argument vaut
1, il ecrit `"LOST"` (strLost, L14029). L'argument 1 designe donc la
**defaite du joueur** — et c'est bien cohent : si la population du joueur est
nulle, c'est lui qui a disparu. Notre `Game._end_game(perdu)` prend donc la
meme convention que l'asm.

## Le calcul du nouveau niveau (L14462-14495)

.. code-block:: none

    ancien = _level_number
    _level_number += _score / 5000 + 1        # `ADDQ.L #1` puis `ADD.W`
    # puis un palier de 5 niveaux tous les 5 niveaux :
    reste = _level_number % 5
    if reste != 0:
        _level_number += 5 - reste
    # et le plafond :
    if _level_number > 0x9A6:                  # 2470
        if ancien == 0x9A6:
            _level_number = 0                  # tour complet -> on repart
        else:
            _level_number = 0x9A6              # « WEAVUSPERT », le maximum

Puis `_seed = _level_number` et le relief est regenere : le niveau suivant est
une **nouvelle carte**.

## L'ecran (L14520-14589)

Trois lignes, composees par `strcpy`/`strcat` :

* si le joueur a **termine le mode** (`-122(A5) != 0`) : le grand texte de
  fin, `LAB_52230`, ecrit en `(8, 0xB2)` ;
* sinon : ``_con_text[level/250 + 0x18]`` — le nom du monde — suivi de
  `LAB_52228`, puis le numero du monde, puis `LAB_5222C` ;
* enfin `_message` (L14580) est concatene, puis le tout est ecrit en
  `(8, 0xBA)`.

Les **deux** lignes ne sont pas deux appels arbitraires mais deux
``_text(_w_screen, 8, y, s)`` — `x` en **pixels** (le listing fait
``LSR.W #3`` pour en tirer un offset d'octet, L19978) et `y` en lignes de
l'ecran, d'ou `(8, 0xB2)` et `(8, 0xBA)` (L14526, L14559, L14588).

Premiere ligne — ``_text(..., 0xB2, ...)``
------------------------------------------

* ``(-122) != 0`` (le mode est boucle) : la chaine entiere
  `strWellDoneConq` (L14522-14527) ;
* sinon : `strWellDone` (L14534) + `_con_text[level/250 + 0x18]` (L14542-14549)
  + `strYouConquered` (L14551-14554).

**`_con_text[0x18 + monde]` n'est pas un nom de monde.** La table
(L24726-24770) compte d'abord quatorze mots de sol, quatorze messages de
construction, puis, a l'index ``0x18 = 24``, **dix notes** allant de
`strMortal` a `strEternalGod` (L21353-21392). C'est la note du joueur, qui
monte d'un cran tous les 250 niveaux.

Deuxieme ligne — ``_text(..., 0xBA, ...)``
------------------------------------------

Le meme tampon ``(-100,A5)`` est reutilise :

* ``(-122) != 0`` : `strcpy(-100, strBattleOverTry)` (L14528) — le monde
  n'est pas nomme puisque le mode est fini ;
* sinon : ``(-100)`` recoit `GENESIS` si ``_seed == 0`` (L14563), sinon
  `_code(newrand())` (L14569-14572), puis `strNowBattleAt` (L14575) ;
* et dans les deux cas `_message` est concatene (L14580) avant l'ecriture.

``_seed`` est ici la **variable globale**, que L148C6A vient de remettre a
``(-106)`` = l'ancien ``_level_number`` : la condition « GENESIS » se lit
donc sur l'ancien niveau, pas sur la graine de carte.

.. note::
   Le jeu original joue aussi un **discours** : `_read_lord` pose le portrait
   dans `_w_screen`, `_read_mouth` lit les 5040 octets de `mouths.pic` dans
   `_map_steps`, et `_draw_mouth` (L19894) recopie la bouche et les yeux
   pendant que le joueur attend (Phase 81). Les couleurs viennent de
   `_tcmap`, que `_read_lord` remplit avec les 16 mots de `lord.pic`.
"""
from __future__ import annotations

#: `strWellDone` (L21396) : le prefixe de la premiere ligne.
WELL_DONE = "WELL DONE "
#: `strYouConquered` (L21400) : son suffixe.
YOU_CONQUERED = " YOU CONQUERED "
#: `strNowBattleAt` (L21404) : le milieu de la seconde ligne.
NOW_BATTLE_AT = " NOW BATTLE AT "
#: `strWellDoneConq` (L21410) : la premiere ligne quand le mode est boucle.
WELL_DONE_CONQ = "WELL DONE YOU HAVE CONQUERED EVIL"
#: `strBattleOverTry` (L21416) : le debut de la seconde ligne dans le meme cas.
BATTLE_OVER_TRY = "THE BATTLE IS OVER BUT TRY "
#: `strGENESIS` (L14781) : le nom du premier monde.
GENESIS = "GENESIS"

#: `_con_text[0x18 + monde]` — les dix notes, de `strMortal` (L21353) a
#: `strEternalGod` (L21392). `_con_text` commence par quatorze mots de sol
#: puis quatorze messages de construction : la note est bien a l'index 24.
NOTES = ("MORTAL", "IMMORTAL", "ETERNAL", "DEVA", "GREATER BEING",
         "DEITY", "GREATER DEITY", "MORTAL GOD", "GREATER GOD",
         "ETERNAL GOD")

#: Les colonnes des deux appels de `_draw_mouth` (L14652, L14724).
#:
#: **Elles sont en octets, pas en pixels** : `_draw_mouth` ajoute `x`
#: directement au pointeur d'ecran (``ADDA.L D0,A0``, L19900) et ne fait
#: **pas** le ``LSR.W #3`` que `_text` fait (L19978). Comme une ligne fait
#: `$28 = 40` octets pour 320 pixels, il faut multiplier par 8 pour obtenir
#: la colonne a l'ecran.
BLOC_X = 0x12                  # la bouche, L14724 : 18 x 8 = 144 pixels
YEUX_X = 0x10                  # les yeux,  L14655 : 16 x 8 = 128 pixels

#: Les deux ordonnees, elles, sont en lignes d'ecran (`MULU #$0028`).
BLOC_Y = 0x87                  # la bouche : ligne 135
YEUX_Y = 0x4B                  # les yeux :  ligne  75

#: Une bouche fait 35 lignes : `$0023` passe aux deux appels (L14653,
#: L14722), et c'est exactement la hauteur d'une image de `mouths.pic`.
BLOC_H = 0x23                  # 35 lignes

# le niveau maximal : « WEAVUSPERT »
LEVEL_MAX = 0x9A6                      # 2470

# un niveau tous les 5000 points
POINTS_PER_LEVEL = 5000                # `$00001388`

# le monde est regenere tous les 250 niveaux
PALIER_NOMS = 250                      # `DIVS #$00fa`

# ------------------------------------------------------------------ la voix
# Les deux tables d'effets de ``_won_conquest``. Ce sont des indexes de la
# banque ``gwords``, chargee par ``_load_sound(str_gwords)`` au L148C60 —
# la banque qui remplace ``gmusic1`` pendant tout le discours.
#
#: ``_end_words`` (L24783-24785) : cinq mots, indexes par ``compteur - 10``
#: dans la branche « mode termine » (L14633-14641).
END_WORDS = (0x0000, 0x0001, 0x0003, 0x0005, 0x0006)

#: ``_words`` (L24786-24789) : vingt mots, **deux par monde**, le monde
#: etant ``_level_number / 250`` (L148C40). Un mot negatif — la table est
#: pleine de ``$FFFF`` — n'est pas un effet : L148CA8 fait
#: ``TST.W (0,A0,D0.L) / BLT.S`` et saute le ``_PlaySound``.
#:
#: ``0xFFFF`` est stocke comme ``-1`` : c'est la lecture signee du listing,
#: et c'est elle qui fait sauter le mot.
WORDS = (0x0009, -1, 0x0005, -1, 0x0003, -1, 0x0007, -1,
         0x0001, 0x0008, 0x0002, -1, 0x0001, 0x0002, 0x0009, 0x0006,
         0x0001, 0x0006, 0x0003, 0x0006)


def nouveau_niveau(ancien: int, score: int) -> tuple[int, bool]:
    """Transcription de L14462-14495.

    Renvoie ``(nouveau_niveau, mode_termine)``. ``mode_termine`` vaut vrai
    quand le joueur a boucle le mode complet (son niveau precedent etait
    deja le maximum) : c'est le grand texte de fin de l'asm.
    """
    n = ancien + score // POINTS_PER_LEVEL + 1      # `ADDQ.L #1` + `ADD.W`
    reste = n % 5                                  # `DIVS #$0005 / SWAP`
    if reste != 0:
        n += 5 - reste
    fini = False
    if n > LEVEL_MAX:                              # `CMPI.W #$09a6 / BLE`
        if ancien == LEVEL_MAX:
            n = 0                                  # on reboucle le mode
            fini = True
        else:
            n = LEVEL_MAX                          # « WEAVUSPERT »
    return n, fini


def code_monde(graine: int) -> str:
    """``_code`` (L14793-14889) : le nom d'un monde, tire d'un mot de 16 bits.

    Trois boucles identiques empilent trois syllabes dans la chaine de
    destination et, a chaque fois, indexent la table par un champ de cinq
    bits du mot :

    * `_start[graine & 0x1F]` (L148FDA-149000) ;
    * `_mid[(graine >> 5) & 0x1F]` (L149024-14904E, ``ASR.W #5``) ;
    * `_end[(graine >> 10) & 0x1F]` (L149074-1490A0, ``ASR.W #10, D1``).

    Chaque boucle copie **jusqu'au zero inclus** sauf le zero lui-meme
    (``TST.B (0,A0,D1.L)`` en tete), et le routine rend la main apres avoir
    ecrit ce zero (``CLR.B (0,A0,D4.W)``, L148C86). Les trois tables sont
    dans :mod:`populous.decode` — ce sont exactement celles que
    ``decode``(texte) inverse.

    Le bit 15 du mot n'est jamais lu : il y a 32 x 32 x 32 = 32768 noms.
    """
    from populous.decode import END, MID, START
    v = graine & 0xFFFF
    return START[v & 0x1F] + MID[(v >> 5) & 0x1F] + END[(v >> 10) & 0x1F]


def note(level_no: int) -> str:
    """La note du joueur — `_con_text[level/250 + 0x18]` (L14542-14547).

    Dix valeurs, une par tranche de 250 niveaux : `MORTAL` au niveau 0,
    `ETERNAL GOD` au-dela de 2250. Voir :data:`NOTES`.
    """
    return NOTES[min(len(NOTES) - 1, max(0, level_no // PALIER_NOMS))]


def texte_fin(level_no: int, fini: bool, message: str = "",
              graine: int = 0) -> tuple[str, str]:
    """Les **deux** lignes du portrait (L14520-14589).

    ``level_no`` est l'ancien ``_level_number`` — celui que L148C6A remet
    dans ``_seed`` avant de tester la condition « GENESIS ». ``graine`` est
    le mot passe a `_newrand`'s apparence, i.e. le tirage dont `_code` tire
    le nom du monde ; il n'est lu que si ``level_no != 0``.

    Renvoie ``(ligne_0xB2, ligne_0xBA)``, dans l'ordre ou le listing les
    ecrit.
    """
    if fini:
        # L14522-14527 : `_text` recoit directement la chaine, sans tampon ;
        # le tampon (-100) ne sert qu'a LAB_52234 (L14528).
        return WELL_DONE_CONQ, BATTLE_OVER_TRY + message
    ligne1 = WELL_DONE + note(level_no) + YOU_CONQUERED
    monde = GENESIS if level_no == 0 else code_monde(graine)
    return ligne1, monde + NOW_BATTLE_AT + message