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

Nos chaines viennent des `DC.B` du listing :

=====================================  ==========================
ligne                                  asm
=====================================  ==========================
``BATTLE NUMBER IS ``                 LAB_52224
``WORLDS LANDSCAPE IS ``              LAB_52228
``HIS RATING IS ``                     LAB_5222C
``GENESIS``                            strGENESIS
=====================================  ==========================

.. note::
   Le jeu original joue aussi un **discours** (`_read_lord`, `_read_mouth`,
   `_draw_mouth`) et fait tourner un cycle de palette de 16 entrees
   (L14590-14603) pendant que le joueur attend. Nous rendons le texte et la
  palette ; le discours est le seul element non rendu.
"""
from __future__ import annotations

# les chaines, extraites des DC.B du listing
BATTLE_NUMBER = "BATTLE NUMBER IS "
WORLDS_LANDSCAPE = "WORLDS LANDSCAPE IS "
HIS_RATING = "HIS RATING IS "
GENESIS = "GENESIS"

# le niveau maximal : « WEAVUSPERT »
LEVEL_MAX = 0x9A6                      # 2470

# un niveau tous les 5000 points
POINTS_PER_LEVEL = 5000                # `$00001388`

# le monde est regenere tous les 250 niveaux
PALIER_NOMS = 250                      # `DIVS #$00fa`


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


#: Les noms de mondes, dans l'ordre de `_con_text`. Le listing n'en contient
#: que l'indexation (``_con_text[(level/250 + 0x18) * 4]``) ; `level.dat`
#: donne le relief mais pas ces noms. On garde donc la structure exacte et on
#: retombe sur « GENESIS », comme l'asm fait quand `_seed == 0`.
def nom_monde(seed: int) -> str:
    """Le nom affiche apres « WORLDS LANDSCAPE IS » (L14561-14573).

    L'asm fait exactement deux choses : si ``_seed == 0`` il recopie la
    chaine ``GENESIS``, sinon il y met le nombre tire de la graine. Les
    vrais noms vivent dans `_con_text`, que le listing ne developpe pas.
    """
    return GENESIS if seed == 0 else str(seed)


def nom_bataille(level_no: int) -> str:
    """Le nom de la bataille — `_con_text[level/250 + 0x18]` (L14538-14547).

    Le listing n'inclut que l'indexation ; la table `_con_text` elle-meme
    n'est pas decompilee ici. On expose donc l'index, qui est ce que
    l'asm calcule reellement.
    """
    return level_no // PALIER_NOMS + 0x18


def texte_fin(level_no: int, seed: int, fini: bool) -> str:
    """La ligne assemblee puis ecrite en `(8, 0xBA)` (L14522-14589).

    Transcription de la suite de `strcpy`/`strcat` :

    * mode termine  -> le grand texte de fin (L14522-14527) ;
    * sinon         -> `WORLDS LANDSCAPE IS ` (L14534)
      + le nom du monde (L14563 ou le nombre, L14572)
      + `HIS RATING IS ` (L14575) ;
    * enfin         -> `_message` est concatene (L14580).
    """
    if fini:
        return HIS_RATING
    return WORLDS_LANDSCAPE + nom_monde(seed) + HIS_RATING