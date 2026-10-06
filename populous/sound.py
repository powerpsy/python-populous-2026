r"""Le son du jeu, tel que l'asm le calcule.

`_load_sound` (asm L20712) attend un module Amiga charge par `Open($3ED)` :
un en-tete `_measln / _seqlen / _sequn / _measure_length`, une zone de mesures
de 0x100 octets (4 sous-pistes a +0x00, +0x40, +0x80, +0xC0 — cf.
`_PlayMeas`, L20433) et des echantillons 8 bits signes.

Aucun de nos fichiers extraits (`popsam`, `gmusic1`, `gwords`) ne porte la
signature d'un module ProTracker (`M.K.`, `4CHN`…) ni l'en-tete que
`_load_sound` lit : le format relait de `Open($3ED)` n'est donc pas
ProTracker, et pymod / pytracker ne peuvent pas le lire. (Verification
reproductible : `tools/check_mod.py`.)

Ce module reproduit en revanche **la logique de jeu** de l'asm, qui ne joue
pas des echantillons mais des **codes de son** : `_PlaySound(son, voie)` joue
le son numero `son` sur la voie `voie`, et la simulation calcule ces codes.

=====================================  =====================  ==============
code                                   produit par            sens
=====================================  =====================  ==============
0x40 \| tribu                          powers.py L64/L74      un pieu
0x42                                   sim.py L623            un habitant meurt
0x47                                   LAB_4C9DE              tic du tempo
0x48                                   LAB_4CA0E              temps du tempo
0x49                                   do_quake               seisme
0x4A                                   do_swamp               marais
0x4B                                   do_volcano             volcan
0x4C                                   do_flood               deluge
0x4D                                   do_magnet              aimant
0x50 \| (code & 0x0F)                  sim.py L738            evenement
=====================================  =====================  ==============

Comme le fichier de samples n'est pas decodable, chaque code est realise par
un timbre genere a la volee (ondes glissades, carres, triangles, bruit a
graine fixe). Ce ne sont pas les echantillons d'origine, mais la **cadence**
et la **densite d'evenements** sont exactement celles que pilote l'asm.
"""
from __future__ import annotations

import math
from array import array

import pygame

TAILLE = 44100                     # Hz, frequence de generation


# --------------------------------------------------------------- utilitaires
def _enveloppe(n: int, attaque: float, decay: float) -> array:
    """Enveloppe lineaire attaque / decroissance, en flottants 0..1."""
    env = array("f", [0.0]) * n
    na = max(1, int(n * attaque))
    nd = max(1, n - na)
    for i in range(na):
        env[i] = i / na
    for i in range(nd):
        env[na + i] = max(0.0, 1.0 - (i / nd) ** decay)
    return env


def _bruit(n: int, graine: int) -> array:
    """Bruit blanc, graine fixe pour etre reproductible."""
    out = array("f", [0.0]) * n
    s = (graine & 0x7FFFFFFF) or 1
    for i in range(n):
        s = (1103515245 * s + 12345) & 0x7FFFFFFF
        out[i] = (s / 0x3FFFFFFF) - 1.0
    return out


def _ton(n: int, f0: float, f1: float, forme: int = 0) -> array:
    """Un ton glisse de ``f0`` vers ``f1`` Hz.

    ``forme`` : 0 = sinus, 1 = carre, 2 = triangle.
    """
    out = array("f", [0.0]) * n
    ph = 0.0
    for i in range(n):
        t = i / n
        f = f0 + (f1 - f0) * t
        ph += 2.0 * math.pi * f / TAILLE
        if forme == 0:
            out[i] = math.sin(ph)
        elif forme == 1:
            out[i] = 1.0 if math.sin(ph) > 0 else -1.0
        else:                       # tri
            x = (ph / math.pi) % 2.0
            out[i] = 4.0 * abs(x - 1.0) - 2.0
    return out


def _vers_son(buf: array, gain: float = 0.45,
              attaque: float = 0.01, decay: float = 1.6) -> pygame.Sound:
    """Applique l'enveloppe puis convertit en 16 bits signes pour le mixer."""
    env = _enveloppe(len(buf), attaque, decay)
    out = array("h", [0]) * len(buf)
    for i in range(len(buf)):
        v = int(max(-1.0, min(1.0, buf[i] * env[i] * gain)) * 32767)
        out[i] = v
    return pygame.mixer.Sound(buffer=out.tobytes())


# ------------------------------------------------------------ les 33 timbres
def _construire() -> dict[int, tuple[str, array]]:
    """Les timbres, un par code d'effet de l'asm.

    Les durees sont choisies pour que la densite d'evenements soit celle du
    jeu original : les pieux ($40/$41) sont courts et frequents, les powers
    ($49..$4C) longs et rares.
    """
    sons: dict[int, tuple[str, array]] = {}

    def put(code: int, nom: str, buf: array) -> None:
        sons[code] = (nom, buf)

    n = int(TAILLE * 0.10)
    put(0x40, "pieu_tribu0", _ton(n, 320, 180, 0))
    put(0x41, "pieu_tribu1", _ton(n, 280, 150, 0))

    n = int(TAILLE * 0.16)
    put(0x42, "mort", _bruit(n, 0x1234))
    put(0x43, "batiment", _ton(n, 140, 90, 2))

    n = int(TAILLE * 0.12)
    put(0x44, "relever", _ton(n, 260, 520, 0))
    put(0x45, "abaisser", _ton(n, 520, 260, 0))
    put(0x46, "arbre", _bruit(n, 0x5A5A))

    n = int(TAILLE * 0.05)
    put(0x47, "tic", _ton(n, 1400, 1400, 0))
    put(0x48, "temps", _ton(n, 900, 900, 0))

    n = int(TAILLE * 0.18)
    put(0x4E, "guerre", _ton(n, 120, 60, 1))
    put(0x4F, "victoire", _ton(n, 400, 800, 0))

    # les 4 pouvoirs — longs, donc nettement audibles
    n = int(TAILLE * 0.55)
    put(0x49, "seisme", _bruit(n, 0x1111))
    put(0x4A, "marais", _bruit(n, 0x2222))
    put(0x4B, "volcan", _bruit(n, 0x3333))
    put(0x4C, "deluge", _bruit(n, 0x4444))

    n = int(TAILLE * 0.25)
    put(0x4D, "aimant", _ton(n, 200, 900, 0))

    # les 16 sous-types d'evenement ($50 | n)
    n = int(TAILLE * 0.35)
    put(0x50, "evenement0", _ton(n, 500, 250, 1))
    put(0x51, "evenement1", _ton(n, 400, 200, 1))
    put(0x52, "evenement2", _bruit(n, 0x2468))
    put(0x53, "evenement3", _ton(n, 600, 300, 0))
    put(0x54, "evenement4", _ton(n, 350, 700, 2))
    put(0x55, "evenement5", _bruit(n, 0x1357))
    put(0x56, "evenement6", _ton(n, 800, 200, 0))
    put(0x57, "evenement7", _ton(n, 250, 450, 2))
    put(0x58, "evenement8", _ton(n, 700, 350, 1))
    put(0x59, "evenement9", _ton(n, 450, 900, 0))
    put(0x5A, "evenementA", _bruit(n, 0x8642))
    put(0x5B, "evenementB", _ton(n, 600, 600, 2))
    put(0x5C, "evenementC", _ton(n, 1000, 500, 0))
    put(0x5D, "evenementD", _ton(n, 180, 360, 1))
    put(0x5E, "evenementE", _ton(n, 520, 260, 2))
    put(0x5F, "evenementF", _bruit(n, 0xACE0))
    return sons


# --------------------------------------------------------------- la mesure
# `_PlayMeas` (L20433) lit 4 sous-pistes de 64 notes dans la mesure courante,
# a `curbeat + 0x00`, `+0x40`, `+0x80`, `+0xC0`, et joue chacune sur les
# voices 0..3.  Une note vaut 0 = silence (l'asm retranche 0x41 puis teste
# `son < _no_sounds` : une valeur trop grande ne fait rien).
#
# Le fichier n'etant pas lisible, ces 4 sous-pistes sont generees, mais leur
# structure (4 x 64, une note par voix et par temps) est celle de l'asm.
_LG = 64                                     # 0x40 notes par sous-piste


def _mesure() -> list[list[int]]:
    """Les 4 sous-pistes d'une mesure, en indices de note (0 = silence).

    Gamme pentatonique mineure, comme le caractere « archaique » du jeu.
    """
    gamme = (0, 3, 5, 7, 10, 12, 10, 7, 5, 3)
    motif = (
        # voix 0 : basse, une note par temps
        (0, 0, 7, 0, 5, 0, 7, 0, 3, 0, 7, 0, 5, 0, 3, 0),
        # voix 1 : melodie
        (0, 4, 0, 5, 0, 7, 0, 5, 0, 4, 0, 2, 0, 4, 0, 7),
        # voix 2 : contre-chant
        (0, 0, 9, 0, 0, 5, 0, 0, 9, 0, 0, 5, 0, 7, 0, 5),
        # voix 3 : ponctuation
        (0, 0, 0, 12, 0, 0, 10, 0, 0, 0, 0, 12, 0, 0, 10, 0),
    )
    pistes = []
    for v, pat in enumerate(motif):
        piste = []
        for t in range(_LG):
            degre = pat[t % len(pat)]
            piste.append(0 if degre == 0 else degre + 1 + v)
        pistes.append(piste)
    return pistes


def _note(degre: int) -> float:
    """La frequence d'un degre de la gamme (les silences ne l'appellent pas)."""
    return 220.0 * (2.0 ** ((degre - 1) / 12.0))


# ------------------------------------------------------------------ le son
class SoundEngine:
    """``_PlaySound`` (L20307) et ``_kill_effect`` (L20876).

    L'asm impose deux conditions avant de jouer (L20311-20314) :

    * ``son < _no_sounds`` — sinon ``D0 = 0`` et rien ne joue ;
    * ``voie <= 3`` — il n'y a que **4** voies, en indices 0..3.

    C'est exactement ce que fait ``play`` : un code inconnu, ou une voie
    hors 0..3, ne produit aucun son.
    """

    VOIES = 4                      # `CMPI #$0003,($A,A5) / BLS`

    def __init__(self, frequence: int = 22050) -> None:
        self.sons = _construire()
        self.frequence = frequence
        self.no_sounds = max(self.sons) + 1     # `_no_sounds`
        self._tampon: dict[int, pygame.Sound] = {}
        self.voies: list[pygame.mixer.Channel] = []
        try:
            pygame.mixer.init(frequency=frequence, size=-16, channels=1)
            pygame.mixer.set_num_channels(self.VOIES)
            self.voies = [pygame.mixer.Channel(i) for i in range(self.VOIES)]
        except pygame.error:                    # pas de carte son
            self.voies = []

    # ------------------------------------------------------------- chemins
    def pret(self) -> bool:
        """Vrai si le mixer est disponible (carte son presente)."""
        return bool(self.voies)

    def _son(self, code: int) -> pygame.Sound | None:
        """Le `pygame.Sound` du code, converti une seule fois."""
        if code in self._tampon:
            return self._tampon[code]
        item = self.sons.get(code)
        if item is None:
            return None
        try:
            snd = _vers_son(item[1])
        except pygame.error:
            snd = None
        self._tampon[code] = snd
        return snd

    def _son_note(self, degre: int) -> pygame.Sound | None:
        """Le timbre d'une note de la mesure, mis en cache par degre."""
        cle = -degre                       # negatif : pas de collision $40..$5F
        if cle in self._tampon:
            return self._tampon[cle]
        n = int(TAILLE * 0.13)
        buf = _ton(n, _note(degre), _note(degre), 0)
        try:
            snd = _vers_son(buf, gain=0.22, attaque=0.02, decay=1.2)
        except pygame.error:
            snd = None
        self._tampon[cle] = snd
        return snd

    # --------------------------------------------------------------- jeu
    def play(self, son: int, voie: int = 0) -> None:
        """``_PlaySound(son, voie)`` — joue l'effet ``son`` sur la voie."""
        if not self.pret():
            return
        if voie < 0 or voie >= self.VOIES:       # `CMPI #$0003 / BLS`
            return
        if son >= self.no_sounds or son < 0:    # `CMP _no_sounds / BCC`
            return
        snd = self._son(son)
        if snd is not None:
            self.voies[voie].play(snd)

    def note(self, degre: int, voie: int) -> None:
        """Une note de la couche melodique (`_PlayMeas`, L20433)."""
        if not self.pret() or voie >= self.VOIES:
            return
        snd = self._son_note(degre)
        if snd is not None:
            self.voies[voie].play(snd)

    def mesure(self, pistes: list[list[int]], curbeat: int) -> None:
        """``_PlayMeas`` : les 4 sous-pistes au temps ``curbeat``."""
        for voie in range(self.VOIES):
            degre = pistes[voie][curbeat % _LG]
            if degre:
                self.note(degre, voie)

    def kill_effect(self, debut: int, fin: int) -> None:
        """``_kill_effect(debut, fin)`` (L20876) : coupe les voies [debut, fin).

        L'asm fait `for i in range(debut, fin): AbortIO(_ioas[i])`.
        """
        for i in range(max(0, debut), min(self.VOIES, fin)):
            try:
                self.voies[i].stop()
            except pygame.error:
                pass

    def check_effect(self, voie: int) -> bool:
        """``_check_effect(voie)`` (L20898) : la voie sonne-t-elle encore ?"""
        if voie < 0 or voie >= self.VOIES:
            return False
        return self.voies[voie].get_busy()

    def sound_in(self) -> int:
        """``_sound_in`` : combien de voies sonnent encore."""
        return sum(1 for v in self.voies if v.get_busy())


# --------------------------------------------------------- l'horloge (asm)
class MusicEngine:
    """La partie audio de la boucle d'image (asm L19620-19673).

    Ce handler est appele **une fois par image** (c'est la partie sonore de la
    VBI). Il fait, dans cet ordre exact :

    1. si ``_music_off`` est **non nul**, on avance le compteur de mesure :
       ``_music_now += 1`` ; s'il atteint ``_music``, on remet ``_music`` a 10,
       on joue une mesure et on reboucle le compteur a zero (L19623-19631) ;
    2. si ``_effect_off`` est non nul (L19633) :
       * si ``_effect != 0`` : on met ``_music`` a **0x28** (40) — c'est ce
         delai qui repousse la prochaine mesure — on joue l'effet sur les
         **voies 2 et 3**, on remet ``_effect`` a zero, et on **saute**
         le bloc du tempo (L19637-19647) ;
       * sinon, si aucune voie ne sonne (``_sound_in == 0``) et
         ``_tempo != 0`` : le tic du tempo. ``_tempo_now += 1`` ; s'il
         atteint ``_tempo``, son ``$47`` et remise a zero ; sinon, si
         ``_tempo - _beat_two == _tempo_now``, son ``$48`` (L19651-19672).

    **Sur la polarite des drapeaux.** Les etiquettes de l'asm disent
    ``_music_off`` / ``_effect_off``, mais le code montre l'inverse du nom :
    ``TST.W _music_off / BEQ.S`` **saute** le bloc musique quand le mot est
    **zero**. Le son joue donc quand le drapeau est **non nul**. On
    reproduit le comportement observe, pas le nom du symbole.

    Le tempo, lui, est derive de la population (L557-603) :
    ``_tempo = 0x32 - (pop_adv / pop_joueur) * 2``, borne a un minimum de 7,
    et ``_beat_two = _tempo / 3``. Plus l'adversaire est peuple, plus le
    tempo est **court**, donc plus les tics sont rapproches.

    .. note::
       Cette horloge lit et ecrit des attributs du jeu (par matage) : c'est
       la traduction directe des variables globales de l'asm.
    """

    def __init__(self, sound: SoundEngine) -> None:
        self.sound = sound
        self.music = 10            # `_music`  : l'asm le met a 10 (L19627)
        self.music_now = 0         # `_music_now`
        self.tempo = 0             # `_tempo`  : 0 = pas de tic
        self.tempo_now = 0         # `_tempo_now`
        self.beat_two = 1          # `_beat_two`
        self.pistes = _mesure()    # la mesure courante (`_measures`)
        self.curbeat = 0           # `_curbeat`
        self.curseq = 0            # `_curseq`

    # ------------------------------------------------------ le tempo (L557)
    def suivre(self, pop_joueur: int, pop_adv: int) -> None:
        """Recalcule `_tempo` et `_beat_two` d'apres les deux populations.

        Transcription de L557-603 : si la population du joueur est nulle, le
        tempo est mis a zero (plus de tic) et `_beat_two` a 1 ; sinon
        ``_tempo = 0x32 - (pop_adv / pop_joueur) * 2``, borne a 7, puis
        ``_beat_two = _tempo / 3``, et `_tempo_now` est recale s'il depasse.
        """
        if pop_joueur <= 0:
            self.tempo = 0                     # LAB_3E852
            self.beat_two = 1
        else:
            ratio = pop_adv // pop_joueur       # `___divs`
            tempo = 0x32 - ratio * 2            # `ASL.L #1` puis `SUB #$32`
            if tempo < 7:                       # `CMPI #$0007 / BGE`
                tempo = 7
            self.tempo = tempo
            self.beat_two = tempo // 3          # `DIVS #$0003`
        if self.tempo_now > self.tempo:         # LAB_3E85C
            self.tempo_now = self.tempo

    # ------------------------------------------------- une image (L19620)
    def image(self, jeu) -> None:
        """Un appel par image — le bloc L19620-19673 de l'asm."""
        # (1) l'avance de la mesure — L19621-19631
        if jeu.music_on:
            d0 = self.music_now + 1
            if d0 == self.music:
                self.music = 10
                self.sound.mesure(self.pistes, self.curbeat)
                self.curbeat = (self.curbeat + 1) % _LG
                d0 = 0
            self.music_now = d0

        # (2) les effets et le tempo — L19633-19672
        if not jeu.effect_on:
            return
        if jeu.effect:
            # `MOVE.W #$0028,_music` : l'effet repousse la mesure
            self.music = 0x28
            self.sound.play(jeu.effect, 2)
            self.sound.play(jeu.effect, 3)
            jeu.effect = 0
            return                                # `BRA.W LAB_4CA1A`
        if self.sound.sound_in():
            return                                # `TST.W _sound_in / BNE`
        if not self.tempo:
            return                                # `TST.W _tempo / BEQ`
        d0 = self.tempo_now + 1
        self.tempo_now = d0
        if d0 >= self.tempo:
            self.sound.play(0x47, 0)               # le tic
            self.tempo_now = 0
        elif self.tempo - self.beat_two == self.tempo_now:
            self.sound.play(0x48, 0)               # le contretemps