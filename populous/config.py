"""Les reglages du jeu — tout ce que l'original ne fixe pas.

L'asm est la reference pour **tout ce qu'il fixe**. Mais l'original laisse
certains choix a la machine, et ces la ne sont pas transcrits : ils
appartiennent a ce module. On les met ici, avec la raison de leur valeur,
pour pouvoir les ajuster apres coup sans toucher au code du jeu.

Criteres de separation :

* **transcrit** — la valeur vient d'une instruction du listing, avec son
  numero de ligne. On ne la touche pas.
* **parametre** — la valeur est un choix. L'asm ne la fixe pas, ou la fixe
  d'une facon non mesurable. Elle est ici.

.. warning::
   Le portage se fait **fidele d'abord**. Ces reglages restent donc au plus
   proche de l'original tant qu'on n'a pas de mesure de l'emulateur ;
   c'est une fois le port complet qu'on les ajuste sur le ressenti.
"""
from __future__ import annotations

# ------------------------------------------------------------------ affichage
#: Cadran de la fenetre de jeu, en pixels : la largeur *hauteur du visible*
#: dans le listing. `SCREEN_W` vaut 320 sur Amiga PAL.
SCREEN_W = 320
SCREEN_H = 256

#: Facteur d'aggrandissement de la fenetre. L'original upscale en hardware ;
#: ici on rend en 320x256 puis on met a l'echelle, ce qui donne le meme
#: resultat pour un facteur entier. **Parametre** : purement visuel.
ZOOM = 3

# ------------------------------------------------------------------- cadence
#: Nombre de tours de simulation par seconde. **Parametre.**
#:
#: .. note::
#:    La boucle de tour ne contient aucun ``Delay`` ni ``WaitTOF`` : elle
#:    reboucle sur `LAB_3E7E8` (L1013). Mais elle **est** rythmee par le
#:    basculement d'ecran, la derniere chose faite avant les entrees
#:    (L761-762) : ``___swap_screens`` -> ``_swap_screens`` (L16743-16754)
#:    -> ``_Setscreen`` (L16695-16739) -> ``_show_screen`` (L19782-19790)::
#:
#:        COP1LCH = copper_list + 4
#:    LAB_4CB92:  D0 = INTREQR ; D0 &= $0020 ; BEQ LAB_4CB92   ; RTS
#:
#:    ``$0020`` dans ``INTREQR`` est le drapeau d'interruption **vertical
#:    blank** : la routine ecrit la nouvelle liste de cuivre, puis tourne
#:    jusqu'au prochain vblank. C'est le seul tempo de la boucle - le
#:    listing fixe donc **un tour par image**, soit un plafond de **50
#:    tours/s** en PAL (``SCREEN_W = 320``). ``_waittof`` (L19791-19797),
#:    qui *efface* ce drapeau avant d'attendre, n'est utilise que par le
#:    code serie (L11635/11645) et pour les quatre attentes de L14717-14720.
#:
#:    Le rendu original (320x256 en 8 passes, logiciel, sur un Amiga 7 MHz)
#:    ne tenait pas forcement ces 50 Hz : c'est alors la **machine** qui
#:    faisait retomber le rythme, jamais le listing. D'ou ce parametre et
#:    non une constante :
#:
#:    * ``0.0``  - sans plafond, le plus rapide que la machine accepte ;
#:    * ``50.0`` - le plafond VBlank de la boucle d'origine ;
#:    * ``30.0`` - la valeur par defaut, celle du port depuis sa creation,
#:      retenue pour rester confortable a la mise au point.
TURNS_PER_SECOND = 30.0

#: Nombre d'images affichees entre deux tours de simulation.
#:
#: ``1.0`` = un tour par image, la regle du listing : ``_animate`` appelle
#: ``_move_peeps`` une seule fois par tour (L681). ``3.0`` = un tour toutes
#: les trois images, si le rendu ne suit pas le plafond de tours/s.
#: **Parametre.**
TURNS_PER_FRAME = 1.0

#: Mode Conquest au demarrage. L'asm demarre sur l'ecran titre ; on commence
#: directement en partie, comme dans notre port. **Parametre.**
START_IN_CONQUEST = False

# ------------------------------------------------------------------- depart
#: Graine et terrain par defaut, quand on lance sans argument. **Parametre.**
DEFAULT_SEED = 1
DEFAULT_GROUND = 0

# ---------------------------------------------------------------------- son
#: Activer le son au demarrage. L'asm demarre avec le son actif ; nos
#: drapeaux `music_on` / `effect_on` sont a 1 par defaut (L1744-1780).
SOUND_ENABLED = True

#: Volumes multiplicateurs appliques au rendu des timbres synthetises. Les
#: echantillons d'origine ne sont pas lisibles (voir `populous/sound.py`), donc
#: ces deux valeurs sont **des nôtres** et n'ont aucun equivalent dans l'asm.
#: **Parametre.**
VOLUME_EFFECT = 1.0
VOLUME_MUSIC = 0.45

# ----------------------------------------------------------------- fenetre
#: Elargir la fenetre pour la lisibilite sur un ecran moderne. L'amiga
#: affichait en 320x256 ; on peut vouloir plus grand. **Parametre.**
WINDOW_BORDERLESS = False