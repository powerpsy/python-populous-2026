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
#: Images par seconde **affichees**.
#:
#: .. note::
#:    L'asm ne fixe **aucun** rythme : la boucle de tour reboucle sur
#:    `LAB_3E7E8` (L1013) et n'attend rien. Le seul `Delay()` du jeu est dans
#:    `_free_inter` (L245, chemin de sortie) et `_waitfor()` n'est appele que
#:    par le code serie (L11653). La frequence reelle est donc celle de la
#:    machine — sur un Amiga 7 MHz en rendu logiciel, de l'ordre de 10 a 15
#:    tours/s. Elle n'est **pas mesurable** depuis le listing.
#:
#: 30 tours/s : rapide mais tres pratique pour la mise au point et les tests.
FPS = 30

#: Nombre d'images affichees entre deux tours de simulation.
#:
#: 1.0 = un tour par image (ce que nous faisons : `FPS` tours par seconde).
#: 3.0 = 10 tours par seconde a 30 img/s, cadence plausible pour un Amiga.
#: **Parametre** : c'est le levier a toucher en premier si la partie parait
#: trop rapide ou trop lente.
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