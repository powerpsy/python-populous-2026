r"""La musique de fond par fichier -- **ECART assumé au listing**.

Le listing ne connaît pas de fichier de musique : ``SUB_2C36`` ;2c36 lit
``popsam`` (huit échantillons, 114718 octets exactement) et le lecteur
``SUB_2F9C`` / ``LAB_3060`` fait tourner un séquenceur dont les tables
vivent dans l'exécutable, de ``$3532`` à ``$3F91``. Ce séquenceur n'est
pas transcrit : voir ``docs/game_logic.md``.

La musique est donc fournie par deux fichiers posés dans ``reference/`` :

===========================  ==========================  ==============
fichier                      durée                       emploi
===========================  ==========================  ==============
``Main Theme.mp3``           ~240 s                      l'intro (Phase 86)
``BGM.mp3``                  ~128 s                      la partie
===========================  ==========================  ==============

**Décision d'architecture** : on lit le MP3 tel quel avec
``pygame.mixer.music``, qui *mélange* son flux avec les canaux du
``SoundEngine`` -- les codes de son (``_PlaySound``) passent donc par
dessus la musique, comme sur l'Amiga où ils occupaient les voies libres.
En revanche la mesure synthétisée de ``MusicEngine`` (``_mesure()``, une
gamme pentatonique **inventée** faute d'avoir décodé ``_load_sound``) est
muée pendant que la piste joue : deux musiques de fond en même temps
n'ont aucun sens.

Le mixer est ouvert à ``44100 / -16 / 2`` s'il ne l'est pas encore. C'est
exactement la fréquence de génération de ``sound.TAILLE`` : les effets
synthétisés gardent leur hauteur. Si un mixer est déjà ouvert (c'est le
cas après ``pygame.init()``), on n'y touche pas.
"""

from __future__ import annotations

from pathlib import Path

import pygame

from .assets import ROOT

#: Les deux pistes, fournies par l'utilisateur.
DOSSIER = ROOT / "reference"
MUSIQUE_INTRO = DOSSIER / "Main Theme.mp3"
MUSIQUE_JEU = DOSSIER / "BGM.mp3"

#: Même valeur que ``sound.TAILLE`` : la génération des effets.
DEBIT = 44100
BITS = -16
CANAUX = 2

#: Volume de la musique -- les effets restent prioritaires à l'oreille.
VOLUME = 0.75

#: Chemin en cours de lecture, ``None`` si rien ne joue.
_charge: Path | None = None

#: Dernier fichier lance, **y compris apres** ``arreter()`` : c'est ce
#: qui permet de verifier qu'un parcours a bien demarre la musique.
_dernier: Path | None = None


def _ouvrir() -> bool:
    """Ouvre le mixer au format de ``sound.TAILLE`` s'il ne l'est pas."""
    if pygame.mixer.get_init():
        return True
    try:
        pygame.mixer.init(frequency=DEBIT, size=BITS, channels=CANAUX)
    except pygame.error:                    # pas de carte son
        return False
    return bool(pygame.mixer.get_init())


def demarrer(chemin: Path, boucle: bool = True) -> bool:
    """Charge et lance ``chemin``.

    Renvoie ``False`` sans effet si le fichier manque ou si le mixer
    refuse : les outils en ligne de commande n'ont pas de carte son, et
    l'absence de musique ne doit jamais faire échouer une vérification.
    """
    global _charge, _dernier
    if not chemin.is_file():
        return False
    if not _ouvrir():
        return False
    musique = pygame.mixer.music
    try:
        if _charge == chemin and musique.get_busy():
            return True                     # déjà en train de tourner
        musique.load(str(chemin))
        musique.set_volume(VOLUME)
        musique.play(-1 if boucle else 0)
    except (pygame.error, OSError):
        _charge = None
        return False
    _charge = chemin
    _dernier = chemin
    return True


def arreter() -> None:
    """Coupe la piste -- appelée quand l'intro rend la main et à la fin."""
    global _charge
    _charge = None
    if pygame.mixer.get_init():
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass


def actif() -> bool:
    """Vrai si une piste est chargée **et** réellement en train de jouer."""
    if _charge is None or not pygame.mixer.get_init():
        return False
    try:
        return bool(pygame.mixer.music.get_busy())
    except pygame.error:
        return False


def courant() -> Path | None:
    """Le fichier chargé, ``None`` si rien ne joue."""
    return _charge


def dernier() -> Path | None:
    """Le dernier fichier lancé, même après ``arreter()``.

    Uniquement pour la vérification : dire « l'intro a démarré sa
    musique » revient à comparer ce chemin à
    :data:`MUSIQUE_INTRO`.
    """
    return _dernier
