"""Phase 84 - l'ecran titre et le demo d'attirance.

Transcription de ``reference/tetracorp/populous_main.asm``, le programme
amovible de l'introduction (hunk S_0 : 0x0000..0x6D27, hunk S_1 : 0x6D28..).
Les adresses citees ci-dessous sont celles du listing ; la base A4 vaut
``SECSTRT_1+$7FFE`` = 0xED26 (``SUB_65F0`` ;65f0), d'ou les offsets negatifs
du type ``(-32074,A4)`` = 0x6F52.

Ce que l'intro fait, dans l'ordre (``SUB_4`` ;0004 -> ``SUB_41C`` ;041c) :

1. ``SUB_384`` ouvre graphics.library et intuition.library ;
2. ``SUB_15FA`` ;15fa decoupe le tampon de 0x1F400 octets en **quatre**
   bitmaps de 320x200x4 plans (32000 o) et quatre structures ecran de 0x12C ;
3. ``SUB_16E4`` ;16e4 charge ``land0`` (0x72+0x8340 o), ``sprites0.dat``
   (0x5BE0 o) et ``font.dat`` (0x1130 o) ;
4. ``SUB_1696`` ;1696 charge ``demo.pic`` (32000 o) ;
5. ``SUB_1BE8`` ;1be8 met a l'echelle le tableau de hauteur des 100 cases ;
6. ``SUB_41C`` ;041c est la boucle principale :
   - ``SUB_456`` ;0456 affiche ``load.pic`` (40000+64 o, 5 plans, 32 couleurs)
     et attend la souris dans l'une des trois zones de la barre du bas ;
     retour 1, 2 ou 3 -> on sort de l'intro ; retour 0 (delai depasse,
     350000 tours) -> demo d'attirance ;
   - ``SUB_1186`` ;1186 fait tomber et rebondir 100 tuiles de ``land0``
     (``SUB_10A2``/``SUB_110A``/``SUB_1C12``), puis appelle ``SUB_714``
     qui fait defiler les credits.

Le ``SUB_714`` du demo (l'interpreteur de script a 16 lignes, ``SUB_50B2`` /
``SUB_50E6`` / ``SUB_1910``) est analyse ci-dessus mais **non transcrit** :
voir ``docs/PROGRESSION.md`` (Phase 85). Le defilement des credits, lui,
est transcrit a l'identique.

Quatre arbitrages assumes, tous marques ECART plus bas :
* l'ecran titre du port fait 320x200 ; la souris est ramenee a l'espace
  0..319 du listing sur les deux axes (voir ``souris_amiga``) ;
* la musique de l'intro vient d'un **fichier** fourni par l'utilisateur
  (``reference/Main Theme.mp3``), pas du lecteur ``popsam`` -- Phase 86,
  voir ``populous.musique`` ;
* la sortie de l'intro (``SUB_16E`` execute ``populous.prg``) devient, dans
  le port, le retour de ``demarrer`` vers le lanceur.

Deux points qui etaient marques ECART en Phase 84 et qui sont desormais
**transcrits**, corrige en cours de route :

* ``LAB_6F82`` est un pointeur bien ecrit : ``SUB_4`` ;0046-0056 y range
  l'adresse du tampon de ``$8340`` octets fourni par ``SUB_6C4A``, et
  ``SUB_16E4`` y lit ``land0`` puis appelle ``SUB_1B8A`` ( ;172e). Le port
  n'alloue rien, mais recolle les memes octets **et** applique la meme
  permutation des 1680 blocs de 20 octets ;
* ``LAB_7226`` (facteur d'echelle isometrique) est ecrit ``$0080`` par
  ``SUB_1186`` ;11ce : ``ECHELLE_ISO`` est donc lu dans le listing, pas
  choisi.
"""

from __future__ import annotations

import pygame

from . import assets
from . import musique                       # ECART Phase 86 : ``reference/*.mp3``

# ------------------------------------------------------------------- ecran
#: Octets par ligne d'un plan : 320 pixels / 8. ``SUB_19EE`` ;1a0c (``$28``).
PAS_LIGNE = 40
#: Hauteur de l'ecran, en lignes. ``SUB_19EE`` ;1a00 (``$C7`` = 199).
HAUTEUR = 200
#: Plans de l'ecran d'attirance : ``SUB_19EE`` emploie ``0``, ``$1F40``,
#: ``$3E80`` et ``$5DC0`` (L2049-2066) : quatre plans.
PLANS = 4
#: Taille d'un plan. ``SUB_4`` ;005a alloue ``$7D00`` = 32000 octets pour un
#: bitmap entier, soit 8000 octets par plan.
TAILLE_PLAN = 8000
#: Longueur d'un bitmap (``SUB_15FA`` ;162e : ``MULS #$7d00``).
TAILLE_BITMAP = TAILLE_PLAN * PLANS

#: Sprite de l'introduction : 32x24 pixels, masque + 4 plans, soit 20 octets
#: par ligne et ``$1E0`` = 480 octets par sprite (``SUB_19EE`` ;1a20).
SPRITE_L = 32
SPRITE_OCTETS = 0x1E0
#: Hauteur de base : ``SUB_19EE`` ;19f4 (``$17`` = 23, soit 24 lignes).
HAUTEUR_SPRITE = 0x17
#: Limite basse de l'ecran : ``SUB_19EE`` ;19f8 (``$B0`` = 176).
LIMITE_BASSE = 0xB0

#: Largeur d'une ligne de credits, en pixels (``SUB_1D1A`` ;1d54 : ``$28``
#: caracteres de 8 pixels sur 320). Le tampon d'une ligne fait 1600 octets,
#: soit 5 plans de 8 lignes (``DS.L $190`` ;1fa2).
CREDITS_H = 8
CREDITS_OCTETS = PAS_LIGNE * CREDITS_H * 5

# -------------------------------------------------------------- variables
# Offsets depuis A4 = 0xED26, donnes par le listing.
OFF_ECRAN_AFFICHE = -32074      # 0x6F52 : bitmap courant (SUB_15FA ;1680)
OFF_ECRAN_CACHE = -32078        # 0x6F4E : bitmap cache
OFF_ECRAN_C = -31900            # 0x6F62
OFF_ECRAN_D = -31904            # 0x6F5E
OFF_CAPTION0 = -31992           # 0x6F66 : tampon du slot 0 (SUB_536 ;0544)
OFF_CAPTION1 = -31988           # 0x6F6A : tampon du slot 1 (SUB_536 ;054c)
OFF_COMPTEUR0 = -31998          # 0x6F60 : compteur du slot 0 (0x4B, ;0550)
OFF_COMPTEUR1 = -31996          # 0x6F64 : compteur du slot 1 (0x32, ;0556)
OFF_IMAGES = -31994             # 0x6F68 : compteur d'images (SUB_536 ;055c)
OFF_BASCULE = -31896            # 0x6F72 : bascule 0/1 (SUB_714 ;0730)
OFF_SOURIS_X = -32002           # 0x7024 = ``LAB_7024`` : X de la souris
OFF_SOURIS_Y = -32000           # 0x7026 = ``LAB_7026`` : Y de la souris
OFF_COLONNES = -31894           # 0x7090 = ``LAB_7090`` : 100 mots de colonne
OFF_VITESSES = -31692           # 0x715A : 100 mots de vitesse

#: Facteur d'echelle isometrique, **transcrit**. ``SUB_1C12`` ;1c5c fait
#: ``MULU LAB_7226,D0 / LSR.W #7`` et ``LAB_7226`` est un ``DS.W 1`` ( ;7226),
#: c'est-a-dire un mot de BSS a zero : rien n'aurait ete dessine. Il est
#: ecrit par ``SUB_1186`` ;11ce, ``MOVE.W #$0080,(-31488,A4)``. Comme
#: ``A4 = $ED26`` ( ``SUB_65F0`` ;65f0), ``(-31488)`` = ``$ED26-$7B00`` =
#: ``$7226`` = exactement ``LAB_7226``, celui que lit ``MULU``. 0x80 / 2^7
#: = 1 : echelle 1.
ECHELLE_ISO = 0x80

#: Le compteur d'une ligne de credits repasse a 0x32 une fois fini
#: (``SUB_714`` ;0818) et le slot 1 demarre a 0x32 (``SUB_536`` ;0556).
COMPTEUR_FIN = 0x32
#: Palier au-dela duquel le masque de fondu est symetrise (``SUB_714`` ;07a0).
PALIER_FADE = 0x19


# --------------------------------------------------------------- donnees
#: ``LAB_1F62`` ;1f62 : 9 longs big-endian = 18 mots de masque de fondu.
#: Le mot 0 est ``$FFFF`` (ligne invisible) et le mot 17 ``$0010`` ; au-dela,
#: la zone ``DS.L 6`` ;1f86 est nulle dans l'image du hunk, donc la ligne est
#: totalement visible (``blitter`` lit jusqu'a ``fade+2``).
FADE = [
    0xFFFF, 0xFFFF, 0xFFFF, 0xFFFD, 0xEFBF, 0xBDEF, 0xEF76, 0x6EB7, 0xB56D,
    0xD5AA, 0x5555, 0x4AA9, 0x2552, 0x4924, 0x2212, 0x8410, 0x2080, 0x0010,
]
#: Prolongation de la ``DS.L 6`` ;1f86 (octets nuls de l'image du hunk).
FADE += [0x0000] * 12

#: ``LAB_1DCE`` ;1dce : les credits, chaine terminees par 0 puis 0xFF.
#: ``reinitialiser`` reproduit ``SUB_1D0E`` ;1d0e, ``ligne_suivante``
#: ``SUB_1D1A`` ;1d44-1d4e et ;1db6-1dbc. Lignes L2372-2394 du listing.
CREDITS = [
    "POPULOUS",
    "(C) 1989 BULLFROG PRODUCTIONS",
    "PUBLISHED BY ELECTRONIC ARTS",
    "PROGRAMMING AND DESIGN BY",
    "PETER MOLYNEUX",
    "AND GLENN CORPES",
    "TECHNICAL HELP FROM",
    "KEVIN DONKIN",
    "GRAPHICS BY",
    "GLENN CORPES",
    "DAN WHEELER",
    "SEAN COOPER",
    "ANDY JONES",
    "& PETER MOLYNEUX",
    "GAME SOUND & MUSIC BY",
    "DAVE HANLON",
    "MUSIC IDEA BY LES EDGAR",
    "TITLE MUSIC BY ROB HUBBARD",
    "SPECIAL THANKS TO",
    "HISOFT FOR DEVPAC 2",
    "ADRIAN MOORE",
    "EVERYONE AT ULTIMA",
    "EXCEPT ROB",
]

#: ``LAB_640C`` ;640c : 300 octets pour 100 cases, en trois plans de tableaux.
#: - ``+0x00`` (100 o) : le numero de sprite (``MOVE.B (A2),D2`` ;1c4e) ;
#: - ``+0x64`` (100 o) : un drapeau, sprite de dessus (``($64,A2)`` ;1c74) ;
#: - ``+0xC8`` (100 o) : la hauteur, en octets (``($C8,A2)`` ;1c3a).
TYPE = bytes([
    0x00, 0x16, 0x06, 0x0F, 0x0F, 0x0F, 0x0F, 0x0F, 0x09, 0x19, 0x00, 0x16,
    0x06, 0x0F, 0x0F, 0x0F, 0x0F, 0x0F, 0x09, 0x19, 0x1C, 0x1E, 0x06, 0x0F,
    0x0F, 0x0F, 0x0F, 0x0F, 0x09, 0x19, 0x0C, 0x0C, 0x0E, 0x0F, 0x0F, 0x0F,
    0x0F, 0x0F, 0x09, 0x19, 0x0C, 0x08, 0x0F, 0x0B, 0x03, 0x03, 0x03, 0x03,
    0x01, 0x19, 0x0F, 0x09, 0x0F, 0x09, 0x0F, 0x0F, 0x0F, 0x1B, 0x13, 0x11,
    0x0F, 0x09, 0x0F, 0x09, 0x0F, 0x0F, 0x0F, 0x1D, 0x18, 0x00, 0x03, 0x01,
    0x0F, 0x09, 0x0F, 0x0F, 0x0F, 0x0F, 0x19, 0x00, 0x03, 0x03, 0x03, 0x01,
    0x1B, 0x13, 0x13, 0x13, 0x15, 0x18, 0x13, 0x13, 0x13, 0x13, 0x11, 0x00,
    0x00, 0x00, 0x12, 0x11,
])
#: ``DS.L $19`` ;6470 : cent octets a zero, le tableau des drapeaux.
DRAPEAU = bytes(100)
#: Onze morceaux, car le bloc melange ``DC.L`` et ``DS.L`` : les trois
#: ``DS.L 1`` de ;650c/;6514/;6520 et le ``DS.L 4`` de ;6528 sont reserves
#: vides, donc a zero dans l'image du hunk.
HAUTEUR_CASE = bytes([
    0x00, 0x00, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00,
    0x00, 0x01, 0x01, 0x01, 0x01,                              # ;64d4
    0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x01, 0x01,
    0x01, 0x01, 0x00, 0x01, 0x01,                              # ;64e4
    0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x02, 0x02, 0x01,
    0x01, 0x01, 0x01, 0x01, 0x01,                              # ;64f4
    0x01, 0x00, 0x02, 0x02, 0x01, 0x01, 0x00, 0x00,            # ;6504
    0x00, 0x00, 0x00, 0x00,                                    # ;650c DS.L 1
    0x02, 0x02, 0x01, 0x01,                                    # ;6510
    0x00, 0x00, 0x00, 0x00,                                    # ;6514 DS.L 1
    0x00, 0x00, 0x02, 0x02, 0x01, 0x01, 0x00, 0x00,            # ;6518
    0x00, 0x00, 0x00, 0x00,                                    # ;6520 DS.L 1
    0x01, 0x01, 0x01, 0x01,                                    # ;6524
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00,                              # ;6528 DS.L 4
])

#: ``SUB_456`` ;04b6-0512 : les trois zones de la barre du bas. ``$9C``/``$AA``
#: sont les bornes de X, ``$E7``/``$F1`` celles de Y, dans l'espace 0..319 du
#: compteur de souris (``LAB_52A6`` ;52a6 plafonne a ``$27F`` puis divise par
#: deux ;52ac). Le retour est le numero du choix : 3, 2, 1.
ZONES = [
    (0x9C, 0xAA, 0xE7),      # zone 3 : 156 <= x < 170 et y >= 231
    (0xAA, 0xB8, 0xE7),      # zone 2 : 170 <= x < 184 et y >= 231
    (0xB8, 0x200, 0xF1),     # zone 1 : x >= 184 et y >= 241
]
#: Duree maximale de l'ecran titre, en tours de boucle (``SUB_456`` ;04a8).
DELAI_TITRE = 0x55730

#: Nombre de plans de l'ecran titre : ``SUB_456`` ;046c pousse ``5``.
#: ``load.pic`` = 320*200//8*5 = 40000 octets suivis de 64 octets de palette
#: (32 mots), lus a part par ``SUB_17B2`` ;17e0 (``PEA $40``).
PLANS_TITRE = 5
PALETTE_TITRE = 64

#: Nombre de cases de la grille (``SUB_1C12`` ;1ca0 et ;1cac).
GRILLE = 10


# ---------------------------------------------------------------- aleatoire
class Alea:
    """Le generateur pseudo-aleatoire de l'intro.

    ``SUB_6538`` ;6538 : ``graine = (graine * $41C64E6D + $3039) mod 2^32``
    puis retourne ``(graine >> 16) & $7FFF`` (L4693-4701). ``SUB_2E2`` ;02e2
    regraine avec ``random() & n``.
    """

    MULT = 0x41C64E6D
    PLUS = 0x3039

    def __init__(self, graine: int = 0) -> None:
        self.graine = graine & 0xFFFFFFFF

    def suivant(self) -> int:
        """Renvoie le mot suivant, sur 15 bits (``SUB_6538`` ;6554-4701)."""
        self.graine = (self.graine * self.MULT + self.PLUS) & 0xFFFFFFFF
        return (self.graine >> 16) & 0x7FFF

    def regrainer(self, masque: int) -> int:
        """``SUB_2E2(n)`` ;02e2 : ``graine = random() & n``."""
        self.graine = self.suivant() & masque
        return self.graine


def rot_word(valeur: int, dec: int, mot: int, haut: int = 0) -> int:
    """Extrait un mot de 16 bits apres ``ROR.L #dec`` (``SUB_19EE`` ;1a44).

    Le registre est charge sur 32 bits : ``MOVE.L #$ffffffff,D1`` puis
    ``MOVE.W (A1)+,D1`` ( ;1a2c-1a3a) pour le masque : d'ou ``haut = $FFFF``,
    seul cas ou le mot superieur compte, et ``CLR.L D2/D4/D5/D6`` puis
    ``MOVE.W`` pour les quatre plans, soit ``haut = 0``. C'est le mot
    superieur qui fournit les bits de **conservation** : apres rotation, les
    ``dec`` bits de poids faible du premier mot sont a un, c'est-a-dire les
    pixels de destination 0..dec-1 que la sprite n'occupe pas ( ;1a6e-1a78 :
    ``SWAP`` puis ``ADDA.W #2`` rejoue le debordement sur le mot suivant).
    """
    plein = ((haut & 0xFFFF) << 16) | (valeur & 0xFFFF)
    r = (16 * mot + dec) % 32
    if not r:
        return plein & 0xFFFF
    return ((plein >> r) | (plein << (32 - r))) & 0xFFFF


# ------------------------------------------------------------------ bitmap
class Ecran:
    """Un bitmap 320x200 en quatre plans, comme l'ecran de l'intro."""

    def __init__(self, donnees: bytearray | None = None) -> None:
        self.donnees = donnees if donnees is not None else bytearray(TAILLE_BITMAP)

    # -- acces -------------------------------------------------------------
    def lire(self, offset: int) -> int:
        """Lit un mot big-endian (l'octet impair est ignore, comme en 68000)."""
        off = offset & ~1
        if not 0 <= off + 1 < TAILLE_BITMAP:
            return 0
        return int.from_bytes(self.donnees[off:off + 2], "big")

    def ecrire(self, offset: int, valeur: int) -> None:
        off = offset & ~1
        if not 0 <= off + 1 < TAILLE_BITMAP:
            return
        self.donnees[off:off + 2] = (valeur & 0xFFFF).to_bytes(2, "big")

    def vider(self, valeur: int = 0) -> None:
        """Efface le bitmap (``SUB_358``; pas de CLR dans l'intro, mais le
        double buffering de ;1216-1224 recopie un tampon net)."""
        for i in range(TAILLE_BITMAP):
            self.donnees[i] = valeur

    # -- sortie ------------------------------------------------------------
    def surface(self, palette: list[tuple[int, int, int]] | None = None
                ) -> pygame.Surface:
        """Renvoie le bitmap comme une image pygame indexe sur la palette.

        Les quatre plans sont lus a ``0``, ``0x1F40``, ``0x3E80`` et ``0x5DC0``
        (``SUB_19EE`` ;2049-2066), poids 1, 2, 4, 8.
        """
        pal = palette if palette is not None else assets.palette_rgb()
        px = pygame.Surface((320, HAUTEUR))
        px.fill(pal[0])
        d = self.donnees
        for y in range(HAUTEUR):
            base = y * PAS_LIGNE
            row = bytearray(320)
            for p in range(PLANS):
                off = base + p * TAILLE_PLAN
                poids = 1 << p
                for x in range(PAS_LIGNE):
                    v = d[off + x]
                    if v:
                        for b in range(8):
                            if v & (0x80 >> b):
                                row[x * 8 + b] |= poids
            for x in range(320):
                px.set_at((x, y), pal[row[x]])
        return px

    # -- dessin ------------------------------------------------------------
    def blitter(self, source: "Ecran", x: int, y: int, masque: int) -> None:
        """``SUB_5026`` ;5026 : recopie une bande de 320x8 en fondu.

        ``dest = (dest & conserv) | (source_{p+1} & ~conserv)`` pour les plans
        p = 0..3, avec ``conserv = (plan0_source | m)`` : le plan 0 de la
        source est le masque de conservation (``OR.W (A0)+,D3`` ;5062). Le
        masque ``m`` alterne entre ``FADE[fade]``, ``FADE[fade+1]`` et
        ``FADE[fade+2]`` (``D2`` reboucle sur 0/2/4, ;5052-505c).
        ``x`` est l'abscisse de depart en pixels ; l'original la fixe a zero.
        """
        # ``A0`` pointe le plan 0 source (le masque de conservation), ``A3``
        # le plan 1 ; chaque plan suit le precedent a ``$140`` = 320 octets
        # ( ;5052 ``A3`` deja avance, puis ``$140``/``$280``/``$3C0``).
        pas = PAS_LIGNE * CREDITS_H                    # 320 octets par plan
        src = source.donnees
        for ligne in range(CREDITS_H):
            dy = y + ligne
            if not 0 <= dy < HAUTEUR:
                continue
            # ``A0`` parcourt le tampon du haut vers le bas (320x8), la
            # destination part de ``y`` : les deux marches sont distinctes.
            src_l = ligne * PAS_LIGNE
            b = dy * PAS_LIGNE
            for k in range(PAS_LIGNE // 2):
                m = FADE[masque + k % 3] & 0xFFFF
                o = b + k * 2
                s0 = src_l + k * 2
                conserv = ((src[s0] << 8) | src[s0 + 1] | m) & 0xFFFF
                for p in range(PLANS):
                    so = (p + 1) * pas + s0
                    s = (src[so] << 8) | src[so + 1]
                    d = self.lire(p * TAILLE_PLAN + o)
                    self.ecrire(p * TAILLE_PLAN + o,
                                (d & conserv) | (s & ~conserv & 0xFFFF))

    def sprite(self, x: int, y: int, numero: int, tuiles: bytes,
               lignes: int = HAUTEUR_SPRITE, limite: int = LIMITE_BASSE,
               dernier: int = 0xC7, octets: int = SPRITE_OCTETS,
               paquets: int = SPRITE_L // 16) -> None:
        """Pose un sprite masque, decale de ``x & 15`` bits par ``ROR.L``.

        Les trois dessinateurs de l'intro partagent la meme trame -- paquets
        de ``[masque][p0][p1][p2][p3]`` = dix octets, deux mots par plan et
        par paquet, une ligne de ``40`` octets dans le bitmap ( ``ADDA.L #2``
        puis ``#$26`` ;1998-19be) -- et different seulement par les bornes :

        =============== ======== ========= =========== ==========
        routine         lignes   limite    dernier     paquets
        =============== ======== ========= =========== ==========
        ``SUB_19EE``      24      ``$B0``   ``$C7``       2
        ``SUB_1910``      16      ``$B8``   ``$C8``       1
        ``SUB_1802``      32      ``$A8``   ``$C8``       1
        =============== ======== ========= =========== ==========

        ``x`` est en pixels (on decale l'adresse de ``x>>4`` mots, puis les
        donnees de ``x&15`` bits par ``ROR.L`` ;1a12-1a18), ``y`` en lignes.
        Le dessin refuse tout ``y < 0`` ( ;19ee/;181a/;1910) et se tronque a
        ``dernier - y`` lignes quand ``y`` depasse ``limite``.
        """
        hauteur = lignes
        if y < 0:
            return
        if y >= limite:
            hauteur = dernier - y
            if hauteur <= 0:
                return
        dec = x & 0x0F
        base = numero * octets
        colonne = (x >> 3) & ~1
        for ligne in range(hauteur + 1):
            dy = y + ligne
            if not 0 <= dy < HAUTEUR:
                continue
            haut = dy * PAS_LIGNE + colonne
            s = base + ligne * (paquets * 5 * 2)
            for bloc in range(paquets):
                mots = [int.from_bytes(tuiles[s + bloc * 10 + 2 * q:
                                              s + bloc * 10 + 2 * q + 2], "big")
                        for q in range(5)]
                # un paquet de 16 pixels = 1 mot = 2 octets de pas
                self._poser(haut + bloc * 2, mots, dec)

    def _poser(self, offset: int, mots: list[int], dec: int) -> None:
        """``SUB_19EE`` ;1a2c-1b08 : AND du masque puis OR des quatre plans.

        Un paquet de 16 pixels tient sur **un** mot (16 bits) par couche :
        cinq mots, soit 10 octets, et deux paquets pour la largeur de 32
        ( ;1a3a-1a42 puis ;1aaa-1ab2). Le debordement de ``dec`` pixels part
        dans le mot suivant : ``SWAP`` puis ``ADDA.W #2`` ( ;1a6e-1a78). Le
        paquet suivant repart exactement a ce meme endroit : d'ou le pas de
        **2 octets** entre paquets, et non de 4.
        """
        masque = mots[0]
        for p, valeur in enumerate(mots[1:]):
            o = offset + p * TAILLE_PLAN
            if not 0 <= o + 3 < TAILLE_BITMAP:
                continue
            for k in range(2):
                m = rot_word(masque, dec, k, haut=0xFFFF)
                b = rot_word(valeur, dec, k)
                self.ecrire(o + k * 2, (self.lire(o + k * 2) & m) | b)


def echelle_pos(v: int) -> int:
    """``MULU LAB_7226,Dx`` puis ``LSR.W #7`` (``SUB_1C12`` ;1c5c-1c6a).

    ``MULU`` est une multiplication **non signee** : seuls les 16 bits de poids
    faible entrent en jeu, puis le ``LSR.W`` ne decale que ce mot-la. Le
    resultat tient donc sur neuf bits, 0..511 : une ordonnee negative revient
    en ``+512`` au lieu de rester negative. Sur les portees reelles de
    ``SUB_1C12`` (x dans 0..288, y dans -236..176) cela se voit peu : les y
    negatifs deviennent 276..511, donc superieurs a 199, et ``SUB_19EE``
    refuse toujours d'y dessiner. Le portage garde la formule du listing.
    """
    produit = (v & 0xFFFF) * ECHELLE_ISO
    return (produit & 0xFFFF) >> 7


# ------------------------------------------------------------------ credits
class Credits:
    """Les deux lignes de credits qui remontent l'ecran (``SUB_714``)."""

    def __init__(self, fonte: bytes) -> None:
        self.fonte = fonte
        self.curseur = 0                 # ``LAB_1F9E`` ;1f9e
        # ``SUB_536`` ;0540-0556 : deux tampons, deux compteurs 0x4B et 0x32.
        self.tampons = [bytearray(CREDITS_OCTETS) for _ in range(2)]
        self.compteurs = [0x4B, COMPTEUR_FIN]
        self.images = 0                  # ``(-31994)`` ;055c

    # -- ``SUB_1D0E`` ;1d0e ------------------------------------------------
    def reinitialiser(self) -> None:
        self.curseur = 0

    def ligne_suivante(self) -> str:
        """Avance d'une chaine nulle, reboucle sur ``0xFF`` ( ;1d44-1dbc)."""
        texte = CREDITS[self.curseur]
        self.curseur = (self.curseur + 1) % len(CREDITS)
        return texte

    # -- ``SUB_1D1A`` ;1d1a ------------------------------------------------
    def dessiner_ligne(self, tampon: bytearray, texte: str) -> None:
        """Remplit ``tampon`` (1600 o, 5 plans de 320x8) avec ``texte``.

        Fond ``$FF`` sur le plan 0 (donc transparent), les quatre autres plans
        a zero ( ;1d28-1d43), le texte centre sur 40 caracteres ( ;1d54-1d5a),
        une glyph de 40 octets par ``(c - 0x20)`` ( ;1d70-1d76) recopiee sur
        cinq plans a pas ``$140`` ( ;1d7e-1d9c).
        """
        tampon[:PAS_LIGNE * CREDITS_H] = b"\xFF" * (PAS_LIGNE * CREDITS_H)
        tampon[PAS_LIGNE * CREDITS_H:] = bytes(CREDITS_OCTETS
                                               - PAS_LIGNE * CREDITS_H)
        x0 = (0x28 - len(texte)) // 2
        for i, c in enumerate(texte):
            g = (ord(c) - 0x20) * 40
            dst = x0 + i
            for r in range(CREDITS_H):
                for p in range(5):
                    tampon[p * PAS_LIGNE * CREDITS_H + r * PAS_LIGNE + dst] = \
                        self.fonte[g + r * 5 + p]

    # -- le corps du slot (``SUB_714`` ;076a-0826) -------------------------
    def pas(self, ecran: Ecran) -> None:
        """Fait avancer les deux slots d'une image, puis pose le fondu."""
        for slot in range(2):
            compteur = self.compteurs[slot]
            if compteur == COMPTEUR_FIN:
                self.dessiner_ligne(self.tampons[slot], self.ligne_suivante())
            p = compteur
            if p > PALIER_FADE:
                p = COMPTEUR_FIN - p
            if p < 0:
                p = 0
            ecran.blitter(Ecran(self.tampons[slot]), 0, compteur, p)
            self.compteurs[slot] = compteur - 1
            if self.compteurs[slot] < 0:
                self.compteurs[slot] = COMPTEUR_FIN


# ------------------------------------------------------------ grille 10 x 10
class Grille:
    """Les cent cases qui tombent et rebondissent (``SUB_1186``/``SUB_1C12``)."""

    def __init__(self, alea: Alea, tuiles: bytes) -> None:
        self.alea = alea
        self.tuiles = tuiles
        self.hauteur = bytearray(HAUTEUR_CASE)  # ``LAB_640C+$C8`` ;64d4
        self.colonnes = [0] * 100               # ``LAB_7090``
        self.vitesses = [0] * 100               # ``0x715A``

    # -- ``SUB_1BE8`` ;1be8 ------------------------------------------------
    def echeller(self) -> None:
        """Multiplie les hauteurs par 8, sur un octet (``LSL.B #3``)."""
        for i in range(100):
            self.hauteur[i] = (self.hauteur[i] << 3) & 0xFF

    # -- ``SUB_10A2`` ;10a2 ------------------------------------------------
    def initialiser(self, n: int) -> None:
        """``(LAB_7090)[i] = random()%13 + $E8``, ``(0x715A)[i] = random()%9``."""
        for i in range(n):
            self.colonnes[i] = self.alea.suivant() % 13 + 0xE8
            self.vitesses[i] = self.alea.suivant() % 9

    # -- ``SUB_110A`` ;110a ------------------------------------------------
    def avancer(self, n: int) -> int:
        """Un tour de chute rebondie ; renvoie le ``D5`` retenu par l'original.

        ``D5 = v+1 ; D6 = c-D5`` ; si ``D6 < 0`` alors ``D5 = -(D5/2)`` et
        ``D6 = 0`` ( ;1136-114a). Le ``DIVS #2`` tronque vers zero : d'ou
        ``-(abs(v)//2)`` et non ``-v//2``.

        **Bug d'origine reproduit** : le resultat n'est pas ``D5`` de la case 0
        mais la premiere vitesse **non nulle** rencontree. ``(-2,A5)`` demarre
        a zero et l'ecriture n'est gatee que par ``TST.W (-2,A5)`` ( ;114c-1152) :
        si la case 0 est deja a l'arret, la suivante ecrase le resultat, et
        ainsi de suite. ``SUB_1186`` ;11e2 n'emploie ce retour que comme un
        booleen (quelque chose bouge encore), donc le portage le voit tel
        quel.
        """
        premier = 0
        for i in range(n):
            v = self.vitesses[i] + 1
            c = self.colonnes[i] - v
            if c < 0:
                v = -(abs(v) // 2)
                c = 0
            if premier == 0:
                premier = v
            self.colonnes[i] = c
            self.vitesses[i] = v
        return premier

    # -- ``SUB_1C12`` ;1c12 ------------------------------------------------
    def dessiner(self, ecran: Ecran) -> None:
        """Pose les 100 cases en projection isometrique 16x8.

        ``x = (col-rang)*16 + $90`` ; ``y = (col+rang)*8 + $20 - colonne[i]
        - hauteur[i]`` ( ;1c32-1c4c), puis mise a l'echelle par ``LAB_7226``
        avec le ``MULU``/``LSR.W`` de ;1c5c-1c6a. Un second sprite recouvre la
        case si son drapeau est non nul, de 8 lignes plus haut, mais le
        ``SUBQ.W #8`` porte sur l'ordonnee **brute**, avant la mise a l'echelle
        ( ;1c70 recharge D0/D1 sauves en ;1c52, puis ;1c7c) : d'ou
        ``echelle_pos(d1 - 8)`` et non ``y - 8``.
        """
        for rang in range(GRILLE):
            for col in range(GRILLE):
                i = rang * GRILLE + col
                d0 = (col - rang) * 16 + 0x90
                d1 = (col + rang) * 8 + 0x20 - self.colonnes[i]
                d1 -= self.hauteur[i]
                x = echelle_pos(d0)
                y = echelle_pos(d1)
                ecran.sprite(x, y, TYPE[i], self.tuiles)
                if DRAPEAU[i]:
                    ecran.sprite(x, echelle_pos(d1 - 8), DRAPEAU[i],
                                 self.tuiles)


# ------------------------------------------------------------------- assets
def _rebatre(brut: bytes) -> bytes:
    """``SUB_1B8A`` ;1b8a-1be6 : rebat les 1680 blocs de 20 octets.

    D6 = ``$068F`` = 1679, donc 1680 iterations de 20 octets : ``0x8340``,
    exactement la taille lue par ``SUB_16E4``. Pour chaque bloc, ``w0..w9``
    sont ses dix mots. Les lectures ( ;1b9c-1bac) se font **toutes** avant les
    ecritures ( ;1bb0-1bd2), la boucle n'est donc qu'une permutation :

    * ``D4`` = w1  -> w5,  ``D0`` bas = w3 -> w6,  ``D1`` bas = w5 -> w7,
      ``D2`` bas = w7 -> w8 ;
    * ``D0`` haut = w2 -> w1, ``D1`` haut = w4 -> w2, ``D2`` haut = w6 -> w3,
      ``D3`` = w8 -> w4 ;
    * ``w0`` et ``w9`` ne sont ni lus ni ecrits.

    Destination de chaque mot source : ``w0 -> w0, w2 -> w1, w4 -> w2,
    w6 -> w3, w8 -> w4, w1 -> w5, w3 -> w6, w5 -> w7, w7 -> w8, w9 -> w9`` ;
    ecrite dans l'ordre des destinations, c'est la permutation
    ``(0, 2, 4, 6, 8, 1, 3, 5, 7, 9)``.

    **Ce que cela veut dire** : le fichier range une ligne **par couche de
    32 bits** -- masque, plan0, plan1, plan2, plan3, quatre octets chacun
    (c'est aussi l'ordre que lit ``_decode_strip``/``load_land``, qui avance
    de ``pb`` = 4 octets). L'intro, elle, consomme la meme ligne **par paquet
    de 16 pixels** : les cinq mots de poids fort (pixels 0..15) puis les cinq
    mots de poids faible (pixels 16..31) -- exactement ce que ``SUB_19EE``
    lit dans ``sprite()``. Sans cette permutation, le masque est pris pour un
    plan : les formes partent et les couleurs avec.
    """
    ordre = (0, 2, 4, 6, 8, 1, 3, 5, 7, 9)
    out = bytearray(len(brut))
    for b in range(0, len(brut) - 19, 20):
        mots = [int.from_bytes(brut[b + 2 * q: b + 2 * q + 2], "big")
                for q in range(10)]
        for q, s in enumerate(ordre):
            out[b + 2 * q:b + 2 * q + 2] = (mots[s] & 0xFFFF).to_bytes(2, "big")
    return bytes(out)


def charger_tuiles() -> bytes:
    """``land0`` sans son en-tete, **apres** ``SUB_1B8A`` : 70 sprites 32x24.

    ``SUB_16E4`` ;16f8-1720 lit d'abord ``$72`` octets puis ``$8340`` octets
    dans le **meme** tampon ``(-32164)`` = ``LAB_6F82`` : le second recouvre
    l'en-tete de 114 octets, le tampon final pese donc ``0x8340`` = 1680 blocs
    de 20 octets = 70 sprites de 24 lignes. ``SUB_1B8A`` tourne juste apres
    ( ;172e), puis viennent ``sprites0.dat`` ( ;1732) et ``font.dat``
    ( ;1762). C'est donc bien ``land0`` -- les memes tuiles que le jeu -- qui
    fournit les sprites de l'introduction, avec en plus cette permutation.
    """
    brut = (assets.GAME / "land0").read_bytes()[0x72:0x72 + 0x8340]
    return _rebatre(brut)


def charger_fonte() -> bytes:
    """``font.dat`` : 110 glyphs de 40 octets, chargee a ``LAB_CE0C`` ;1774."""
    return (assets.GAME / "font.dat").read_bytes()


def charger_sprites() -> bytes:
    """``sprites0.dat`` brut : 147 sprites de 16x16, ``$5BE0`` octets.

    ``SUB_16E4`` ;1744 le lit dans ``(-31482)`` = ``LAB_722C``, d'ou
    ``SUB_1910`` ;1944 le prend par ``MULU #$00A0,D2``. Contrairement a
    ``land0``, ce fichier n'est **pas** rebattu par ``SUB_1B8A`` : chaque
    paquet de 16 pixels y tient deja en ``[masque][p0][p1][p2][p3]`` =
    dix octets, et une ligne en deux paquets = vingt octets.
    """
    return (assets.GAME / "sprites0.dat").read_bytes()


# -------------------------------------------------------- donnees de la scene
#: Decalages fichier -> adresse du binaire ``populous`` (l'executable de
#: l'intro, 29116 octets). Deux hunks y sont : le premier, code **et** tables
#: statiques, couvre ``$0000``-``$6D27`` et commence au fichier ``$28`` ; le
#: second, donnees plus BSS, couvre ``$6D28``-``$6F37`` et commence au fichier
#: ``$6F94``. Les trois calibres sont ``SUB_4`` (``4e55fffe`` en ``$0004``),
#: ``LAB_FA`` (``"demo.pic"`` en ``$00FA``) et la palette ``$6EF0`` retrouvee
#: mot a mot en fichier ``$715C``.
HUNK0 = 0x28
HUNK1 = 0x26C

#: Adresse du binaire de l'intro dans les extraits du disque.
INTRO_BINAIRE = "populous"

#: ``LAB_5A0C`` ;5a0c-640b : ``$A00`` octets, huit sprites d'objets de
#: ``$140`` octets chacun -- soit 32 lignes de 16 pixels, deux paquets de dix
#: octets par ligne. C'est la banque que consomme ``SUB_1802`` ;1862
#: (``MULU #$0140,D2``) ; le numero 0 est un sprite vide (``FF FF`` puis zero).
BANQUE_OBJETS_ADRESSE = 0x5A0C
BANQUE_OBJETS_TAILLE = 0xA00
OBJET_LIGNES = 32            # ``MOVE.W #$001F,D3`` ;1820
OBJET_LIMITE = 0xA8          # ``CMP.W #$00A8,D1`` ;1824
BANQUE_PERSONNAGES_TAILLE = 0x5BE0    # ``SUB_16E4`` ;1744
PERSONNAGE_LIGNES = 16       # ``MOVE.W #$000F,D3`` ;1916
PERSONNAGE_LIMITE = 0xB8     # ``CMP.W #$00B8,D1`` ;191a

#: ``LAB_1272``-``LAB_15B4`` : les seize flux d'octets du script, dans l'ordre
#: de ``LAB_15B6`` ;15b6. ``SUB_714`` ;08be lit ``flux[ligne][pos]``.
#: Les seize flux d'octets du script, dans l'ordre de ``LAB_15B6`` ;15b6.
#: ``SUB_714`` ;08be lit ``flux[ligne][pos]`` ; la signification de chaque
#: octet est detaillee dans ``Scene`` (Phase 85), et les donnees ci-dessous
#: sont lues telles quelles dans ``LAB_1272``-``LAB_15B4``.
#:
FLUX_TABLE = (
    bytes([  # 0  $1272..$1312  160 octets
        0x26, 0x1A, 0x70, 0x9D, 0x9E, 0x64, 0x9D, 0x9E, 0x9D, 0x9E, 0x9D, 0x9E,
        0x04, 0x70, 0x9D, 0x9E, 0x64, 0x9D, 0x9E, 0x9D, 0x9E, 0x9D, 0x9E, 0x70,
        0x71, 0x9D, 0x9E, 0x65, 0x1A, 0x70, 0x71, 0x9D, 0x9E, 0x65, 0x04, 0x71,
        0x72, 0x9D, 0x9E, 0x66, 0x1A, 0x71, 0x72, 0x9D, 0x9E, 0x66, 0x1A, 0x72,
        0x73, 0x9D, 0x9E, 0x67, 0x41, 0x32, 0x9D, 0x9E, 0x9D, 0x9E, 0x9D, 0x9E,
        0x9D, 0x9E, 0x9D, 0x9E, 0x04, 0x72, 0x73, 0x9D, 0x9E, 0x67, 0x9D, 0x9E,
        0x9D, 0x9E, 0x1E, 0x9D, 0x9E, 0x9D, 0x9E, 0x9D, 0x04, 0x73, 0x75, 0x9D,
        0x9E, 0x69, 0x1A, 0x72, 0x75, 0x9D, 0x9E, 0x69, 0x04, 0x75, 0x77, 0x9D,
        0x9E, 0x9D, 0x9E, 0x6B, 0x1A, 0x75, 0x77, 0x70, 0x71, 0x6B, 0x04, 0x77,
        0x78, 0x9D, 0x9E, 0x6C, 0x1A, 0x77, 0x78, 0x9D, 0x9E, 0x6C, 0x56, 0x9D,
        0x9E, 0x9D, 0x9E, 0x9D, 0x9E, 0x9D, 0x9E, 0x9D, 0x0E, 0x7A, 0x9D, 0x9E,
        0x6E, 0x10, 0x7A, 0x9D, 0x9E, 0x6E, 0x0F, 0x9D, 0x9E, 0x9D, 0x9E, 0x9D,
        0xFD, 0xFC, 0x2C, 0xFB, 0x32, 0x78, 0xA1, 0xA2, 0xA3, 0xA4, 0xA1, 0xA2,
        0xA3, 0xA4, 0x0F, 0xFF,
    ]),
    bytes([  # 1  $1312..$13B4  162 octets
        0x2C, 0x18, 0x70, 0x9D, 0x9E, 0x64, 0x1A, 0x06, 0x70, 0x9D, 0x9E, 0x64,
        0x18, 0x70, 0x71, 0x9D, 0x9E, 0x65, 0x06, 0x71, 0x72, 0x9D, 0x9E, 0x66,
        0x18, 0x71, 0x72, 0x9D, 0x9E, 0x66, 0x06, 0x72, 0x73, 0x9D, 0x9E, 0x67,
        0x18, 0x72, 0x73, 0x9D, 0x9E, 0x67, 0x06, 0x73, 0x74, 0x9D, 0x9E, 0x68,
        0x18, 0x73, 0x74, 0x9D, 0x9E, 0x68, 0x06, 0x74, 0x75, 0x9D, 0x9E, 0x69,
        0x18, 0x74, 0x75, 0x9D, 0x9E, 0x69, 0x06, 0x75, 0x76, 0x9D, 0x9E, 0x6A,
        0x18, 0x75, 0x76, 0x9D, 0x9E, 0x6A, 0x06, 0x76, 0x78, 0x9D, 0x9E, 0x6C,
        0x18, 0x76, 0x78, 0x9D, 0x9E, 0x6C, 0x35, 0x44, 0x55, 0x57, 0x56, 0x60,
        0x95, 0x96, 0x97, 0x98, 0x95, 0x96, 0x97, 0x98, 0x95, 0x96, 0x97, 0x98,
        0x95, 0x96, 0x97, 0x98, 0x95, 0x96, 0x97, 0x98, 0x95, 0x96, 0x97, 0x98,
        0x95, 0x96, 0x97, 0x98, 0x95, 0x96, 0x97, 0x98, 0x95, 0x96, 0x97, 0x98,
        0x95, 0x96, 0x05, 0x7B, 0x9D, 0x9E, 0x6F, 0x19, 0x7B, 0x9D, 0x9E, 0x6F,
        0x0F, 0x79, 0x6D, 0xFC, 0x2D, 0xFB, 0x48, 0x78, 0xA1, 0xA2, 0xA3, 0xA4,
        0xA1, 0xA2, 0xA3, 0xA4, 0x0F, 0xFF,
    ]),
    bytes([  # 2  $13B4..$13C3  15 octets
        0xFC, 0x2E, 0xFB, 0x3E, 0x7A, 0xA1, 0xA2, 0xA3, 0xA4, 0xA1, 0xA2, 0xA3,
        0xA4, 0x0F, 0xFF,
    ]),
    bytes([  # 3  $13C3..$13D2  15 octets
        0xFC, 0x2F, 0xFB, 0x34, 0x7A, 0xA1, 0xA2, 0xA3, 0xA4, 0xA1, 0xA2, 0xA3,
        0xA4, 0x0F, 0xFF,
    ]),
    bytes([  # 4  $13D2..$13E1  15 octets
        0xFC, 0x30, 0xFB, 0x2A, 0x78, 0xA1, 0xA2, 0xA3, 0xA4, 0xA1, 0xA2, 0xA3,
        0xA4, 0x0F, 0xFF,
    ]),
    bytes([  # 5  $13E1..$13E7  6 octets
        0xFC, 0x3B, 0xFB, 0x2A, 0x0F, 0xFF,
    ]),
    bytes([  # 6  $13E7..$144B  100 octets
        0xFC, 0x38, 0x41, 0xF9, 0xC5, 0xC5, 0xC6, 0xC6, 0xC7, 0xC7, 0xC7, 0xC7,
        0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7,
        0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7,
        0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7,
        0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7,
        0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7,
        0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7,
        0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7, 0xC7,
        0xC7, 0xC7, 0xC7, 0xFF,
    ]),
    bytes([  # 7  $144B..$14D3  136 octets
        0x53, 0x48, 0x70, 0x9F, 0xA0, 0x64, 0x2A, 0x70, 0x9F, 0xA0, 0x64, 0x48,
        0x70, 0x71, 0x9F, 0xA0, 0x65, 0x2A, 0x70, 0x71, 0x9F, 0xA0, 0x65, 0x48,
        0x71, 0x72, 0x9F, 0xA0, 0x66, 0x2A, 0x71, 0x72, 0x9F, 0xA0, 0x66, 0x48,
        0x72, 0x73, 0x9F, 0xA0, 0x67, 0x2A, 0x72, 0x73, 0x9F, 0xA0, 0x67, 0x48,
        0x73, 0x74, 0x9F, 0xA0, 0x68, 0x2A, 0x73, 0x74, 0x9F, 0xA0, 0x68, 0x48,
        0x74, 0x75, 0x9F, 0xA0, 0x69, 0x2A, 0x74, 0x75, 0x9F, 0xA0, 0x69, 0x48,
        0x75, 0x76, 0x9F, 0xA0, 0x6A, 0x2A, 0x75, 0x76, 0x9F, 0xA0, 0x6A, 0x48,
        0x76, 0x77, 0x9F, 0xA0, 0x6B, 0x2A, 0x76, 0x77, 0x9F, 0xA0, 0x6B, 0x48,
        0x77, 0x78, 0x9F, 0xA0, 0x6C, 0x2A, 0x77, 0x78, 0x9F, 0xA0, 0x6C, 0x34,
        0x7A, 0x9F, 0xA0, 0x6E, 0x9F, 0xA0, 0x9F, 0xA0, 0x9F, 0xA0, 0x9F, 0x32,
        0xFE, 0xFC, 0x5E, 0xFB, 0x18, 0x78, 0xA1, 0xA2, 0xA3, 0xA4, 0xA1, 0xA2,
        0xA3, 0xA4, 0x32, 0xFF,
    ]),
    bytes([  # 8  $14D3..$154C  121 octets
        0x50, 0x32, 0x1F, 0x9F, 0xA0, 0x9F, 0xA0, 0x9F, 0xA0, 0x32, 0x70, 0x9F,
        0xA0, 0x9F, 0xA0, 0x64, 0x46, 0x32, 0x70, 0x71, 0x9F, 0xA0, 0x9F, 0xA0,
        0x65, 0x47, 0x32, 0x71, 0x72, 0x9F, 0xA0, 0x9F, 0xA0, 0x66, 0x3D, 0x32,
        0x72, 0x73, 0x9F, 0xA0, 0x9F, 0xA0, 0x67, 0x33, 0x32, 0x73, 0x74, 0x9F,
        0xA0, 0x9F, 0xA0, 0x68, 0x29, 0x32, 0x74, 0x75, 0x9F, 0xA0, 0x9F, 0xA0,
        0x69, 0x1F, 0x32, 0x75, 0x76, 0x9F, 0xA0, 0x9F, 0xA0, 0x6A, 0x47, 0x32,
        0x76, 0x77, 0x9F, 0xA0, 0x9F, 0xA0, 0x6B, 0x14, 0x32, 0x77, 0x78, 0x9F,
        0xA0, 0x9F, 0xA0, 0x6C, 0x42, 0x12, 0x9F, 0xA0, 0x9F, 0xA0, 0x9F, 0xA0,
        0x9F, 0xA0, 0x9F, 0xA0, 0x3E, 0x7A, 0x9F, 0xA0, 0x6E, 0x32, 0xFC, 0x53,
        0xFB, 0x04, 0x78, 0xA1, 0xA2, 0xA3, 0xA4, 0xA1, 0xA2, 0xA3, 0xA4, 0x32,
        0xFF,
    ]),
    bytes([  # 9  $154C..$155B  15 octets
        0xFC, 0x49, 0xFB, 0x1A, 0x78, 0xA1, 0xA2, 0xA3, 0xA4, 0xA1, 0xA2, 0xA3,
        0xA4, 0x32, 0xFF,
    ]),
    bytes([  # 10  $155B..$156A  15 octets
        0xFC, 0x3F, 0xFB, 0x06, 0x78, 0xA1, 0xA2, 0xA3, 0xA4, 0xA1, 0xA2, 0xA3,
        0xA4, 0x32, 0xFF,
    ]),
    bytes([  # 11  $156A..$1579  15 octets
        0xFC, 0x35, 0xFB, 0x0E, 0x7A, 0xA1, 0xA2, 0xA3, 0xA4, 0xA1, 0xA2, 0xA3,
        0xA4, 0x32, 0xFF,
    ]),
    bytes([  # 12  $1579..$1588  15 octets
        0xFC, 0x2B, 0xFB, 0x05, 0x7B, 0xA1, 0xA2, 0xA3, 0xA4, 0xA1, 0xA2, 0xA3,
        0xA4, 0x32, 0xFF,
    ]),
    bytes([  # 13  $1588..$15A2  26 octets
        0xFC, 0x4A, 0x41, 0xF9, 0xB1, 0xB2, 0xB3, 0xB4, 0xB4, 0xB3, 0xB2, 0xB1,
        0xB2, 0xB3, 0xB4, 0x19, 0x7B, 0x10, 0x7A, 0x32, 0x4A, 0xF7, 0x0F, 0x41,
        0xF6, 0xFF,
    ]),
    bytes([  # 14  $15A2..$15A7  5 octets
        0xFC, 0x38, 0xFA, 0xFA, 0xFF,
    ]),
    bytes([  # 15  $15A7..$15B6  15 octets
        0xFC, 0x4A, 0xFA, 0xFA, 0x0F, 0xFA, 0xA1, 0xA2, 0xA3, 0xA4, 0xA1, 0xA2,
        0xA3, 0xA4, 0xFF,
    ]),
)

#: ``LAB_6D28`` (hunk 1) : seize structures de sept mots, l'etat initial de
#: chaque ligne -- ``id``, ``pos``, ``phase``, ``pas``, ``compteur``, ``anim``,
#: ``hauteur``. ``pas`` vaut 8 partout, qui est la direction neutre du
#: tableau de ;51f0 (``D4 = 0, D7 = 0, D6 = 8``).
LIGNES_ETAT = (
    (0, 0, 0, 8, 38, 0, 0), (0, 0, 0, 8, 44, 0, 0),
    (0, 0, 0, 8, 15, 0, 0), (0, 0, 0, 8, 15, 0, 0),
    (0, 0, 0, 8, 15, 0, 0), (0, 0, 0, 8, 15, 0, 0),
    (32, 0, 0, 8, 15, 1, 0), (16, 0, 0, 8, 83, 0, 0),
    (16, 0, 0, 8, 80, 0, 0), (16, 0, 0, 8, 50, 0, 0),
    (16, 0, 0, 8, 50, 0, 0), (16, 0, 0, 8, 50, 0, 0),
    (16, 0, 0, 8, 50, 0, 0), (48, 0, 0, 8, 50, 0, 0),
    (64, 0, 0, 8, 15, -1, 1), (66, 0, 0, 8, 50, -1, 1),
)

#: ``(-32510,A4)`` = ``$6E28`` : ``$49`` octets, le sprite tire de l'opcode
#: ``$82`` + i ( ``SUB_714`` ;0b5c ).
TABLE_SPRITES = bytes([
    0x40, 0x41, 0x42, 0x43, 0x44, 0x46, 0x47, 0x48, 0x49, 0x4B, 0x4C, 0x55,
    0x56, 0x57, 0x58, 0x59, 0x5A, 0x5B, 0x5C, 0x5D, 0x5E, 0x5F, 0x60, 0x61,
    0x62, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x6B, 0x6C, 0x6D,
    0x6E, 0x6F, 0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79,
    0x7A, 0x7B, 0x7C, 0x7D, 0x7E, 0x7F, 0x80, 0x82, 0x83, 0x84, 0x85, 0x86,
    0x87, 0x88, 0x89, 0x8A, 0x8B, 0x8C, 0x8D, 0x8E, 0x8F, 0x90, 0x90, 0x91,
    0x92,
])

#: ``(-32437,A4)`` = ``$6E71`` : trente octets, le marqueur tire de l'opcode
#: ``$64`` + i ( ;0a1c ).
MARQUEURS_TABLE = bytes([
    0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B, 0x2C,
    0x36, 0x37, 0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F, 0x40, 0x41,
    0x00, 0x00, 0x00, 0x0A, 0x16, 0x00,
])

#: ``(-32398,A4)`` = ``$6E98`` : huit mots, les sprites de la rangee interieure
#: du temple de ``SUB_E40`` ;0ef8.
OBJETS_MARQUEURS = (0, 1, 0, 2, 3, 1, 2, 4)

#: ``LAB_1F62`` ;1f62 : les masques de dither de ``SUB_3F92``. ``$FF`` couvre
#: tout, ``$00`` rien ; entre les deux, les damiers de ``$FD`` a ``$10``.
MASQUES_REVELATION = bytes([
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFD, 0xEF, 0xBF, 0xBD, 0xEF,
    0xEF, 0x76, 0x6E, 0xB7, 0xB5, 0x6D, 0xD5, 0xAA, 0x55, 0x55, 0x4A, 0xA9,
    0x25, 0x52, 0x49, 0x24, 0x22, 0x12, 0x84, 0x10, 0x20, 0x80, 0x00, 0x10,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00,
])

#: ``LAB_4026`` ;4026 : deux images de ``$800`` octets (64 lignes de 32 bytes),
#: revelees l'une a l'offset ``$000`` par l'opcode ``$FE``, l'autre a l'offset
#: ``$800`` par les opcodes ``$DC`` et ``$FD``.
REVELATION_ADRESSE = 0x4026
REVELATION_TAILLE = 0x1000

#: ``LAB_1268`` ;1268 : le fond de la scene, rechargee a chaque ``SUB_1186``.
FOND_NOM = "demo.pic"
FOND_TAILLE = 0x7D00            # 320x200 en quatre plans

#: ``SUB_2C36`` ;2c36 : ``$1C020`` octets alloues puis ``$1C01E`` lus -- la
#: taille exacte de ``popsam``. ``SUB_2DD8`` ;2dd8 le place ensuite en memoire
#: absolue et installe les vecteurs audio.
SON_NOM = "popsam"
SON_TAILLE = 0x1C01E


def charger_fond() -> Ecran:
    """``demo.pic`` lu dans ``(-31900)`` puis recopie dans ``(-31904)``.

    ``SUB_1696`` ;1696-16e4 ouvre le fichier, en ``Read`` ``$7D00`` octets
    dans ``(-31900)`` (bm2) et appelle ``SUB_58CA`` pour les recopier dans
    ``(-31904)`` (bm3). C'est ``bm3`` qui sert de fond : ``SUB_1186`` ;11e6
    et ``SUB_714`` ;075a recopient ``bm3`` dans le tampon de dessin avant
    chaque image. L'intro se joue donc **par dessus une image du jeu**.
    """
    brut = (assets.GAME / FOND_NOM).read_bytes()[:FOND_TAILLE]
    donnees = bytearray(TAILLE_BITMAP)
    donnees[:len(brut)] = brut
    return Ecran(donnees)


# -------------------------------------------------------------- ecran titre
def souris_amiga(x: int, y: int) -> tuple[int, int]:
    """Ramene la position souris a l'espace 0..319 du listing.

    ``LAB_529A`` ;529a plafonne l'accumulateur a ``$27F`` (639) puis range le
    resultat divise deux ( ;52ac) : les deux axes vivent donc dans 0..319.
    L'ecran Amiga faisant 200 lignes, le port etire ces 200 lignes sur les 320
    unites verticales, de sorte que ``y >= $E7`` retombe sur le quart bas de
    la fenetre. **ECART** : la hauteur exacte de l'ecran titre (200 ou 256)
    n'est pas etablie par le listing.
    """
    ax = 0 if x < 0 else min(x * 2, 0x27F)
    ay = 0 if y < 0 else min(y * 0x27F // (HAUTEUR - 1), 0x27F)
    return ax >> 1, ay >> 1


def zone_titre(x: int, y: int) -> int:
    """``SUB_456`` ;04b6-0512 : renvoie 1, 2, 3, ou 0 si la souris est ailleurs."""
    for numero, (gauche, droite, bas) in enumerate(ZONES):
        if gauche <= x < droite and y >= bas:
            return 3 - numero
    return 0


# ------------------------------------------------------------- le pilote
def _fenetre(surface: pygame.Surface, fenetre: pygame.Surface | None
             ) -> tuple[int, int]:
    """Taille de la fenetre reelle, ou celle du cadre pour les tests."""
    if fenetre is not None:
        return fenetre.get_size()
    return surface.get_size()


def _poser(surface: pygame.Surface, image: pygame.Surface,
           fenetre: pygame.Surface | None = None) -> None:
    """Pose ``image`` (320x200) dans le cadre puis l'affiche.

    Le jeu fait de meme a ``game.py`` : ``self.screen.blit(transform.scale(
    self.frame, ...))`` puis ``display.flip()``. Le cadre est en 32 bits, la
    fenetre est agrandie par ``config.ZOOM``.
    """
    surface.blit(image, (0, 0))
    if fenetre is not None and fenetre is not surface:
        fenetre.blit(pygame.transform.scale(surface, fenetre.get_size()),
                     (0, 0))
    pygame.display.flip()


def _repere(surface: pygame.Surface, fenetre: pygame.Surface | None
            ) -> tuple[int, int]:
    """Position de la souris, en lignes de la figure 320x200.

    ``pygame.mouse.get_pos()`` rend les coordonnees de la **fenetre**, qui est
    agrandie par ``ZOOM`` ; on les ramene au cadre (320x256) puis on plafonne
    a ``HAUTEUR-1``, la figure ne faisant que 200 lignes. ``souris_amiga``
    fait le reste ( ``LAB_529A`` ;52a6-52ac).
    """
    mx, my = pygame.mouse.get_pos()
    lx, ly = _fenetre(surface, fenetre)
    bx = mx * surface.get_size()[0] // max(1, lx)
    by = my * surface.get_size()[1] // max(1, ly)
    return bx, min(by, HAUTEUR - 1)



def charger_titre() -> pygame.Surface:
    """``load.pic`` : 40064 octets = 320x200 x 5 plans + 64 o de palette.

    ``SUB_456`` ;046c-0480 transmet ``$0005`` a ``SUB_549A`` : l'ecran titre
    se joue sur **cinq** plans (32 couleurs), alors que ``SUB_15FA`` ;15fa
    n'alloue que des bitmaps a quatre plans. Le port rend donc le fichier tel
    quel, comme le fait ``tools/check_intro.py``.
    """
    return assets.load_pic("load.pic", planes=5)


def renoncer() -> int:
    """Un ``pygame.event.get()`` : -1 pour fermer, 1 pour passer, 0 sinon.

    **[APPROX]** : le listing n'a pas d'abandon en cours de demo. ``SUB_5792``
    ;5792 ne fait que lire ``CIAA_SDR``, et la sortie reelle est ``SUB_16E``,
    qui execute ``populous.prg``. Le port ajoute donc ces touches, faute de
    pouvoir relancer le jeu original. Fermer la fenetre seules arrete le jeu
    ( -1) ; toute autre touche ou le bouton droit fait passer l'intro
    ( 1) et la partie demarre.
    """
    evenements = pygame.event.get()
    if any(e.type == pygame.QUIT for e in evenements):
        return -1
    if any(e.type == pygame.KEYDOWN
           or (e.type == pygame.MOUSEBUTTONDOWN and e.button == 3)
           for e in evenements):
        return 1
    return 0

# ------------------------------------------------------------------ la scene
#: ``SPRITES_PAS`` : ``MULU #$00A0,D2`` ;1940, l'empreinte d'un sprite de
#: ``sprites0.dat`` (16 lignes de dix octets). ``OBJETS_PAS`` :
#: ``MULU #$0140,D2`` ;185e, celle d'un sprite de ``LAB_5A0C`` (32 lignes).
SPRITES_PAS = 0xA0
OBJETS_PAS = 0x140

#: ``CMP.W #$0010,D4`` ;0e2c : seize lignes de script. ``ASL.L #2,D0`` ;0a56 :
#: quatre octets par emplacement de marqueur.
NB_LIGNES = 16

#: Emplacements **reels** du tableau ``cles``/``ids``.
#:
#: Le compteur ``D6`` de ``SUB_714`` cherche le premier emplacement vide par
#: ``TST.W (0,A0,D0.L) ; BNE`` avec ``D0 = D6*4`` ( ;09ea-09fa ) -- **sans
#: aucune borne**. ``SUB_536`` vide le tableau par la meme boucle sans borne
#: ( ;0566-058a ), et le dessin s'arrete au premier emplacement nul ( ;
#: 0880-088e ) : le tableau est termine par un zero, pas par une longueur.
#:
#: Les emplacements sont a ``A4+(-31984)`` (``ids``) et ``A4+(-31982)``
#: (``cles``), A4 valant ``SECSTRT_1+$7FFE`` = 0xED26, donc 0x7036 et 0x7038.
#: L'emplacement ``k`` occupe ``0x7038+4k`` ; ``(-31904)`` = 0x7086, le pointeur
#: ``bm3`` -- le premier mot modifie apres le tableau -- n'est atteint qu'a
#: ``k = 20``. Le bloc ``0x7058..0x7085`` est du BSS que rien n'ecrit (aucune
#: reference ``(-319xx,A4)`` entre 0x7038 et 0x7086) : douze emplacements
#: **supplementaires**, soit 20 au total.
#:
#: S'arreter a 8 -- le port le faisait -- faisait perdre tout placement passe
#: table pleine, mises a jour comprises : les maisons se figaient a un stade
#: de construction deja passe. **[APPROV]** sur ``20`` seul : le debordement
#: au-dela (où ``D6`` tomberait sur ``bm3``) n'est pas reproduit.
NB_EMPLACEMENTS = 20

#: ``SUB_50E6`` ;5130-51f8 : le ``pas`` est un vecteur a deux chiffres signes
#: -- dizaines et unites -- et chaque cas fournit ``(D4', D7, sprite)``, les
#: deux premiers appliques a la position par ``MULS phase`` ( ;51fc-5202), le
#: troisieme ajoute a l'identifiant ( ;5214). Le cas par defaut ( ;51f0) est
#: ``(0, 0, 8)``, la direction **neutre** -- la valeur 8 qu'a ``pas`` a l'etat
#: initial de chaque ligne.
DIRECTIONS = {
    -11: (0, -2, 0), -10: (2, -1, 2), -9: (4, 0, 4), -1: (-2, -1, 14),
    +1: (2, 1, 6), +9: (-4, 0, 12), +10: (-2, 1, 10), +11: (0, 2, 8),
}

#: ``SUB_19EE`` ;1a20 ``MULU #$01E0,D2`` : l'empreinte d'un sprite de
#: ``land0`` **rebattu** -- 24 lignes de 20 octets. ``SUB_1CBC`` rend a la fin
#: par ``BSR.W SUB_19EE`` ( ;1d02) et non par ``SUB_1910`` : les marqueurs de
#: la scene sont donc faits de tuiles de terrain, pas de ``sprites0.dat``.
#:
#: ``TERRAIN_LIGNES`` porte le **``D3`` du listing** ( ``MOVE.W #$0017,D3``
#: ;19f4 ), non un compteur : ``DBF D3`` ( ;1b12) tourne donc ``D3+1 = 24``
#: fois. ``Ecran.sprite`` compte pareil ( ``range(lignes+1)`` ), d'ou
#: ``lignes=TERRAIN_LIGNES`` sans le ``-1`` que portent
#: ``PERSONNAGE_LIGNES``/``OBJET_LIGNES`` -- eux des **compteurs** (16 et 32,
#: soit ``#$000F`` ;1916 et ``#$001F`` ;1820).
TERRAIN_PAS = 0x1E0
TERRAIN_LIGNES = 0x17
TERRAIN_LIMITE = 0xB0

#: ``TABLE_SPRITES`` et ``MARQUEURS_TABLE`` ne sont que les deux moities d'un
#: meme bloc brut de ``$67`` octets a ``$6E28`` : l'opcode ``$82`` + i lit
#: ``(0,A0,D0.W)`` sans borne ( ;0b5c), donc les indices ``73`` et plus
#: retombent dans ``MARQUEURS_TABLE`` -- le 68000 ne peut pas s'en empecher.
DONNEES_6E28 = TABLE_SPRITES + MARQUEURS_TABLE

#: ``SUB_2FC`` ;02fc appelle ``SUB_6538``, c'est-a-dire ``exec/Random()`` ;
#: ``SUB_384`` ;03a0, ``SUB_1186`` ;1198 et ;1258 font passer la graine par
#: ``SUB_2E2`` (``exec/Seed()``). La scene se regraine donc a ``$7F`` avant la
#: chute, et la meme ``Alea`` sert au temple ( ``LAB_F6E`` ``& 7``) et a
#: l'opcode ``$FB`` ( ;0c30). **[APPROV]** : la suite de ``Random()`` n'est
#: pas celle du port, seule la qualite aleatoire est retenu.


#: ``LAB_640C+$C8`` = ``$64D4`` : cent octets de hauteurs de case.
#: ``SUB_1C12`` y accede par ``i>>4`` ( ;1cde) -- c'est une hauteur, la table
#: ``HAUTEUR_CASE`` est donc **egalement** celle que ``SUB_1CBC`` et
#: ``SUB_50E6`` lisent par indice direct ( ;511a, ;5124), pour leurs
#: ``dec2[compteur]`` verticaux. Les douze derniers octets, reserves a zero
#: par les ``DS.L`` de ;650c-;6528, font partie du tableau.
TABLE_COLONNE2 = HAUTEUR_CASE


def _signe(v: int) -> int:
    """Le triplet ``TST``/``BGT``/``BGE`` de ;0924-0976 : 1 si strictement
    positif, -1 si strictement negatif, 0 sinon.

    L'original le construit en deux ``BGT``/``BGE`` soustraits : ``a - b``
    avec ``a = (d > 0)`` et ``b = (d >= 0)`` inverse -- ce qui donne -1,
    0 ou 1, jamais autre chose.
    """
    return (v > 0) - (v < 0)


def _pas_script(compteur: int, cible: int) -> int:
    """Le ``pas`` d'une marche, d'apres ``SUB_714`` ;08f8-098a.

    ``(-4,A5)`` recoit le reste de ``DIVU #10`` apres ``SWAP``, donc les
    **unites** du compteur, et ``(-6,A5)`` le quotient sans ``SWAP``, donc ses
    **dizaines** ( ;0904 et ;0912). La destination passe par le meme couple
    ``DIVU``/``SWAP`` ( ;091e et ;0950). Les deux ecarts sont ensuite reduits
    a -1, 0 ou 1 par le duo ``BLE``/``BGE`` : ``(-8)`` retient l'ecart
    d'unites ( ;0920-0948), ``(-10)`` l'ecart de dizaines ( ;0954-097a).
    Enfin ;097e-098a assemble ``(-10)*10 + (-8)`` : **c'est le dizaine du pas
    qui vient des dizaines**, son unite qui vient des unites, et le resultat
    est toujours l'un des neuf vecteurs du tableau de ;5130.

    Le compteur est positif -- un octet de flux est un entier signe mais les
    cibles sont ``0..99`` et la marche convergente ne le depasse jamais --
    d'ou ``divmod`` sans restriction ; l'octet recharge sans re-test apres
    ``compteur == octet`` ( ;08d6) peut valoir ``$64..$FF``, qui devient
    alors une destination a deux chiffres comme une autre (112, 157...).
    """
    tens, units = divmod(compteur, 10)
    return _signe(cible // 10 - tens) * 10 + _signe(cible % 10 - units)


#: ``LAB_640C+$C8`` = ``$64D4`` : 100 octets, soit ``HAUTEUR_CASE``. Le
#: compteur d'une ligne peut pourtant sortir de ``0..99`` : apres
#: ``compteur == octet``, ;08d6 recharge l'octet suivant **sans retester**
#: ``CMP.W #$0064`` et se sert de la valeur comme d'une destination de marche
#: -- ``$70`` vaut 112. ``SUB_50E6`` lit alors ``(A2,A3.L)`` en aveugle ( ;
#: 511a, ;5124), c'est-a-dire les octets de ``SUB_6538`` qui suit le tableau.
#: Le port lit le meme bloc plutot qu'une valeur imposee. **[APPROV]**
_DEC2_ETENDU: bytes | None = None


def _dec2(i: int) -> int:
    """``LAB_640C+$C8`` lu par **indice** ( ;1cde, ;511a, ;5124).

    ``SUB_1C12`` lit le meme tableau par ``i>>4`` -- c'est une hauteur de
    case. ``SUB_1CBC`` et ``SUB_50E6``, eux, y voient un decalage vertical
    direct, indexe par le compteur de la ligne, et ce compteur peut etre
    superieur a 99 (voir ``_DEC2_ETENDU`` ci-dessus).
    """
    global _DEC2_ETENDU
    if 0 <= i < len(TABLE_COLONNE2):
        return TABLE_COLONNE2[i]
    if _DEC2_ETENDU is None:
        brut = (assets.GAME / INTRO_BINAIRE).read_bytes()
        o = HUNK0 + 0x64D4
        _DEC2_ETENDU = brut[o:o + 0x200]
    if 0 <= i < len(_DEC2_ETENDU):
        return _DEC2_ETENDU[i]
    return 0


def _octet(v: int) -> int:
    """``EXT.W`` d'un octet lu par ``MOVE.B`` : -128..127.

    ``SUB_50E6`` ( ;511a puis ;511e) et ``SUB_1CBC`` ( ;1cde puis ;1cf4)
    chargent le decalage en **octet** puis l'etendent en signe : la valeur
    au-dela de 127 devient negative, et les calculs de plus bas niveau
    ( ``SUB.B`` de ;5124 ) operent egalement sur un octet, c'est-a-dire
    modulo 256.
    """
    v &= 0xFF
    return v - 256 if v >= 128 else v


def acteur_dessiner(ecran: Ecran, sprites: bytes, compteur: int, pas: int,
                    ident: int, phase: int, colonne: int, hauteur: int,
                    bascule: int) -> None:
    """``SUB_50B2`` ;50b2-50e4, qui charge D3/D4/D2/D5/D6 puis ``SUB_50E6``.

    ``SUB_50E6`` pose un personnage de ``sprites0.dat`` a la position
    isometrique donnee par le compteur ``c = diz*10 + uni`` :

    * ``x = (uni - diz)*16 + $98`` ( ;50f6-50fe) ;
    * ``y = (uni + diz)*8 + $1C - colonne - dec2[c]`` ( ;50f8-5120) ;
    * ``y += octet(dec2[c] - dec2[c+pas]) * phase >> 3`` ( ;5124-512e) : les
      huit images d'une phase interpolent le decalage entre la case actuelle
      et la suivante, d'ou la marche continue. L'ecart est pris sur un
      **octet** ( ``SUB.B`` ) puis signe ( ``EXT.W`` ) ; ``MULU`` rend 32
      bits mais ``ASR.W`` ne decale que le mot faible -- le port le
      reproduit mot par mot ;
    * ``x += D4'*phase`` et ``y += D7*phase`` ( ;51fc-5202), le glissement
      propre a chaque direction.

    L'identifiant final est ``ident + sprite_direction + bascule`` quand
    ``hauteur == 0`` et ``ident < $40`` ; ``ident + bascule`` si ``hauteur``
    est non nul ; et **rien** quand ``hauteur == 0`` mais ``ident >= $40`` :
    les marqueurs fixes ne changent ni d'orientation ni d'image ( ;5204-521a).
    """
    tens, units = divmod(compteur, 10)      # ``DIVU #$000A`` ;50ea
    x = (units - tens) * 16 + 0x98
    y = (units + tens) * 8 + 0x1C - colonne - _octet(_dec2(compteur))
    # ``SUB.B (0,A2,A3.L),D6`` ;5124 puis ``EXT.W D6`` ;5128 : l'ecart est
    # un **octet**, donc modulo 256 avant d'etre signe. Pour les hauteurs
    # (0..2) c'est sans effet ; au-dela de ``$64D4+100``, ou le compteur
    # sort de ``0..99``, le port lise le code suivant -- meme ecart que le
    # 68000, et non une difference etendue.
    delta = _octet((_dec2(compteur) - _dec2(compteur + pas)) & 0xFF)
    mot = ((delta * phase) & 0xFFFF)        # ``MULU D5,D6`` ;512a
    if mot >= 0x8000:                       # ``ASR.W #3`` est signe ;512c
        mot -= 0x10000
    y += mot >> 3
    d4, d7, d6 = DIRECTIONS.get(pas, (0, 0, 8))   # ;5130-51f8
    x += d4 * phase
    y += d7 * phase
    if hauteur != 0:
        ident += bascule
    elif ident < 0x40:
        ident += d6 + bascule
    ecran.sprite(x, y, ident, sprites, lignes=PERSONNAGE_LIGNES - 1,
                 limite=PERSONNAGE_LIMITE, dernier=0xC8, octets=SPRITES_PAS,
                 paquets=1)


def marqueur_dessiner(ecran: Ecran, tuiles: bytes, cle: int,
                      ident: int) -> None:
    """``SUB_1CBC`` ;1cbc-1d0c : un marqueur, dessine **avec ``land0``**.

    Meme projection qu'``acteur_dessiner``, mais sans ``phase`` ni ``bascule``
    et avec les constantes propres a cette routine : ``x = (uni - diz)*16 +
    $90`` et ``y = (uni + diz)*8 + $18 - dec2[cle]`` ( ;1ce2-1cfe).

    La fin est ``BSR.W SUB_19EE`` ( ;1d02), la routine du terrain : 24 lignes,
    deux paquets, limite ``$B0``, et surtout ``MOVEA.L LAB_6F82,A1`` ( ;1a24),
    le pointeur du tampon ``land0`` rebattu que ``SUB_1B8A`` a prepare.
    ``sprites0.dat`` n'a aucun role ici.
    """
    tens, units = divmod(cle, 10)           # ``DIVU #$000A`` ;1ce2
    ecran.sprite((units - tens) * 16 + 0x90,
                 (units + tens) * 8 + 0x18 - _octet(_dec2(cle)),
                 ident, tuiles, lignes=TERRAIN_LIGNES,
                 limite=TERRAIN_LIMITE, dernier=0xC7, octets=TERRAIN_PAS,
                 paquets=2)


def reveler(ecran: Ecran, base: int, ecart: int, masque: int,
            donnees: bytes) -> None:
    """``SUB_3F92`` ;3f92-4024 : revele une image de 64x64 en dither.

    ``A0`` part de ``arg1`` -- ``bm1``, ``bm1 + $20``, ``bm3`` ou ``bm3 + $20``
    selon l'appelant, d'ou le parametre ``base`` -- et avance de deux octets
    par paquet puis de ``$20`` par ligne ( ;4008-4010), soit les ``$28`` du
    bitmap ; les quatre plans suivent a ``0``, ``$1F40``, ``$3E80`` et
    ``$5DC0``. ``A1`` part de ``LAB_4026 + ecart`` et consigne quatre mots par
    paquet ( ;3fa0-3fa6), donc 32 octets par ligne.

    Le masque ne vient pas de l'image mais de ``LAB_1F62`` : ``$FFFF`` laisse
    passer le fond, ``$0000`` le recouvre, et les vingt-six damiers
    intermediaires font le fondu. ``D0`` n'est **pas** remis a zero a chaque
    ligne : il tourne sur ``2, 4, 0`` d'un paquet a l'autre, a travers tout
    l'image ( ;3fb6 ``CLR.W D0`` une seule fois, puis ;3fc0-3fc8).
    """
    for ligne in range(0x40):
        for bloc in range(4):
            # ``ADDQ #2`` puis ``CMPI #6``/``CLR`` : 2, 4, 0, 2, 4, 0...
            d0 = 2 * ((ligne * 4 + bloc + 1) % 3)
            mot = int.from_bytes(
                MASQUES_REVELATION[masque * 2 + d0:masque * 2 + d0 + 2], "big")
            invers = (~mot) & 0xFFFF
            source = ecart + ligne * 32 + bloc * 8
            for p in range(PLANS):
                o = base + ligne * PAS_LIGNE + bloc * 2 + p * TAILLE_PLAN
                val = int.from_bytes(donnees[source + p * 2:
                                             source + p * 2 + 2], "big")
                ecran.ecrire(o, (ecran.lire(o) & mot) | (val & invers))


def charger_revelation() -> bytes:
    """``LAB_4026`` ;4026 : les deux images de revelation, ``$1000`` octets.

    Elles ne sont pas un fichier de disque mais un bloc du binaire de
    l'intro : l'offset ``$4026`` est calibre par la zone de code precedant la
    premiere image, et pese ``2 * $800`` octets, soit deux fenetres de 64
    lignes de 32 octets.
    """
    brut = (assets.GAME / INTRO_BINAIRE).read_bytes()
    o = HUNK0 + REVELATION_ADRESSE
    return brut[o:o + REVELATION_TAILLE]


def charger_son() -> bytes:
    """``popsam`` : ``SUB_2C36`` ;2c36-2dbe alloue ``$1C020`` octets puis en
    lit ``$1C01E`` -- la taille exacte du fichier.

    **Format connu (Phase 86), verifie a l'execution** : le fichier n'a
    **pas** d'en-tete plat. C'est un flux de huit blocs, chacun
    ``LONG longueur + WORD periode`` suivi immediatement de ``longueur``
    octets d'echantillon 8 bits signes. Offsets, longueurs et periodes :

    =========  ==========  =========
    offset     longueur    periode
    =========  ==========  =========
    0          21004       10000
    21010      6032        10000
    27048      8244        8000
    35298      35662       8000
    70966      15340       4000
    86312      8008        8000
    94326      1754        5300
    96086      18626       8000
    =========  ==========  =========

    Les longueurs totalisent 114670, plus 8x6 = 48 octets de descripteurs,
    soit **114718 = $1C01E** -- la longueur lue en ;2cc0 -- et le parcours
    retombe exactement sur la fin du fichier. La periode du bloc 0 vaut
    ``$2710`` = 10000 : c'est bien ``$0000 $520C $2710...`` qui ouvre le
    fichier, et ``tools/check_mod.py`` confirme qu'aucune signature
    Protracker (``M.K.``, ``4CHN``) n'y figure.

    **[APPROV]** : le lecteur -- ``SUB_2F9C``, ``SUB_3046``, ``LAB_3060`` --
    n'est pas transcrit ; les tables de sequences resident dans l'executable
    (``$3532..$3F91``) et non dans le fichier, donc aucun lecteur externe ne
    pourrait les lire. Le port lit la banque, verifie sa taille, et laisse la
    musique a ``populous.musique`` (ECART Phase 86) ; ``populous.sound``
    porte les codes de son. Le demarrage lui-meme est ``SUB_2DD8`` ;
    2dd8, appele en ;1260 **apres** ``SUB_2E2(0)``.
    """
    return (assets.GAME / SON_NOM).read_bytes()[:SON_TAILLE]


def charger_objets() -> bytes:
    """``LAB_5A0C`` ;5a0c : les huit sprites d'objets, lus dans le binaire.

    Contrairement a ``sprites0.dat`` et ``font.dat``, cette banque n'est pas
    un fichier de disque : elle est inline dans le code, entre ``LAB_5A0C``
    et ``LAB_640C``.
    """
    brut = (assets.GAME / INTRO_BINAIRE).read_bytes()
    o = HUNK0 + BANQUE_OBJETS_ADRESSE
    return brut[o:o + BANQUE_OBJETS_TAILLE]


class Objets:
    """``SUB_E40`` ;0e40-109e : le temple, en deux cascades de dix-huit pieces.

    ``SUB_10A2($12)`` ;0e44 remplit ``colonne[0..17]`` avec ``random()%13 +
    $E8`` et ``vitesse[i] = random()%9`` ( ;10ac-10f8) -- le **meme** tableau
    que la chute des cent cases et que les seize lignes de script, qui
    partagent donc ``Grille.colonnes``.

    La premiere cascade dessine la piece ``5`` a ``x=$50`` sur ``colonne[0]``
    ( ;0e6c-0e86), puis les pieces ``6`` a ``x=$50 + i*16`` pour ``i = 1..8``
    ( ``BLE`` ;0ecc : la borne est comprise, la rangee compte donc neuf
    pieces), puis la piece ``7`` a ``x=$E0`` sur ``colonne[9]`` ( ;
    0ece-0ee8), puis les huit pieces de ``OBJETS_MARQUEURS`` a ``x=$60 + i*16``
    ( ;0ef0-0f38). Toutes les ordonnees valent ``$A8 - colonne[rang]`` : les
    pieces tombent de ``y = $A8 - 232`` (hors ecran) a ``y = $A8``.

    Quand ``SUB_110A($12)`` rend 0, ``LAB_F58`` ;0f58-0f98 remet les dix-huit
    colonnes a ``$A0`` avec une vitesse aleatoire ``& 7`` et la seconde
    cascade rejoue le **meme** dessin -- mais avec ``y = colonne[rang] + 8``
    ( ;0fbc, ;0fee, ;101a, ;1052) : les pieces remontent cette fois, de la
    position d'atterrissage vers le haut de l'ecran.

    Les deux cascades recopient pourtant bien ``bm3`` dans ``bm1`` ( ;0e5e et
    ;0faa), et les deux finissent par ``SUB_5792`` : ``1`` sur touche ou
    bouton, ``0`` quand la seconde cascade est epuisee ( ``LAB_109C`` ;109c).
    """

    #: ``(x, sprite, rang)`` : ``rang`` choisit la colonne dont depend ``y``.
    PIECES_HAUTE = ((0x50, 5, 0),
                    *((0x50 + i * 16, 6, i) for i in range(1, 9)),
                    (0xE0, 7, 9))
    PIECES_BASSE = tuple((0x60 + i * 16, OBJETS_MARQUEURS[i], i)
                         for i in range(8))
    NB_PIECES = 0x12

    def __init__(self, alea: Alea, grille: Grille, fond: Ecran,
                 objets: bytes) -> None:
        self.alea = alea
        self.grille = grille
        self.fond = fond
        self.objets = objets
        self.repli = False
        grille.initialiser(self.NB_PIECES)      # ``SUB_10A2($12)`` ;0e44

    def _dessiner(self, ecran: Ecran, y) -> None:
        colonnes = self.grille.colonnes
        for x, sprite, rang in self.PIECES_HAUTE + self.PIECES_BASSE:
            ecran.sprite(x, y(colonnes[rang]), sprite, self.objets,
                         lignes=OBJET_LIGNES - 1, limite=OBJET_LIMITE,
                         dernier=0xC8, octets=OBJETS_PAS, paquets=1)

    def pas(self, ecran: Ecran) -> int:
        """Un tour ; renvoie ``2`` quand la seconde cascade est epuisee.

        ``1`` est reserve a la touche ou au bouton, que le pilote lit
        lui-meme -- ``SUB_5792`` vient ici apres ``SUB_358`` ( ;0f3a-0f4c).
        """
        if self.grille.avancer(self.NB_PIECES) == 0:     # ;0e4e
            if self.repli:
                return 2                          # ``LAB_109C`` ;109c
            for i in range(self.NB_PIECES):        # ``LAB_F58`` ;0f58-0f98
                self.grille.colonnes[i] = 0xA0
                self.grille.vitesses[i] = self.alea.suivant() & 7
            self.repli = True
            # ``LAB_F58`` **retombe** sur ``LAB_F9A`` ;0f9a, qui rappelle
            # ``SUB_110A`` avant de dessiner. ``vitesse`` vient d'etre mise a
            # ``random()&7`` (donc 0..7) et ``colonne`` a ``$A0``, si bien que
            # ``D5 = vitesse + 1`` vaut 1..8 et que ``$A0 - D5`` reste positif :
            # l'appel ne peut pas rendre zero, il ne sert qu'a faire avancer
            # les dix-huit colonnes d'un cran de plus. Le passer, c'etait une
            # cascade qui demarrait une image trop tot.
            self.grille.avancer(self.NB_PIECES)    # ;0f9a
        ecran.donnees[:] = self.fond.donnees      # ``SUB_58CA`` ;0e5e et ;0faa
        if self.repli:
            # ``MOVE.W (0,A0,D0.L),D0 ; ADDQ.W #8,D0`` ;0fbc-0fc0
            self._dessiner(ecran, lambda c: c + 8)
        else:
            # ``MOVE.W #$00A8,D0 ; SUB.W (0,A0,D0.L),D0`` ;0e70-0e74
            self._dessiner(ecran, lambda c: 0xA8 - c)
        return 0


class Scene:
    """Le script des seize lignes (``SUB_714`` ;0714-0e3c).

    Une boucle de ``LAB_730`` fait une image : bascule, ``SUB_5792``, sortie
    sur touche ou bouton, ``bm1 <- bm3``, credits, marqueurs, seize lignes de
    script, ``SUB_55E0`` (attente de la ligne de retour), puis ``SUB_358`` (
    ;0e34) qui inverse ``bm0`` et ``bm1``.

    Chaque ligne possede sept mots -- ``id``, ``pos``, ``phase``, ``pas``,
    ``compteur``, ``anim``, ``hauteur`` -- et son propre flux d'octets, dont
    la lecture ne s'arrete que sur une barriere. ``pos`` ne franchit ``$FF``
    ni ``$F8``-``$FD`` qu'a l'aide d'une autre ligne portant ``$F7``, ou d'une
    revelation assez avancee.
    """

    #: ``SUB_714`` ;08c6-0e24 : signification d'un octet de flux.
    #:
    #: * ``< $64`` : marcher vers la coordonnee isometrique deux chiffres
    #:   ``b``. ``pas = sign(diz(b) - diz(c))*10 + sign(uni(b) - uni(c))`` (
    #:   ;0916-098a) -- ``(-10)`` porte 10 et ``(-8)`` porte 1 : c'est le
    #:   dixieme qui vient des **dizaines** et l'unite qui vient des unites,
    #:   de facon que ``pas`` ne soit jamais qu'un des neuf vecteurs du
    #:   tableau de ;5130. ``compteur += pas`` a chaque rebouclage de ``phase``
    #:   sur huit ( ;09ba-09ce) ;
    #: * ``$64``-``$81`` : poser le marqueur ``MARQUEURS_TABLE[b-$64]`` a la
    #:   cle ``compteur``, puis dessiner (hauteur ``0``) et avancer ( ;
    #:   09e6-0b36) ;
    #: * ``$82``-``$DC`` : dessiner avec le sprite ``DONNEES_6E28[b-$82]`` et
    #:   avancer ( ;0b34-0b82) ;
    #: * ``$FD`` : reveler l'image ``$800`` sur le canal ``(-14,A5)`` -- dans
    #:   ``bm3`` seulement a partir de ``19`` ( ;0b8a-0ba8), dans ``bm1 + $20``
    #:   chaque tour, puis ``(-14)++`` ( ;0bac-0bc2). **Aucun avancement** :
    #:   c'est une barriere tant que le compteur n'a pas 19 ;
    #: * ``$FE`` : meme revelation a l'offset ``0`` sur ``(-16,A5)`` ( ;
    #:   0bca-0bc6) ;
    #: * ``$FC`` : avancer seulement si ``(-14,A5) >= 20`` ( ;0c04-0c16) ;
    #: * ``$FB`` : dessiner avec ``DONNEES_6E28[bascule + $1B (+2 si ligne
    #:   >= 7)]``, ou ``DONNEES_6E28[((ligne>=7)<<2) + $E]`` si ``Random() >
    #:   30000`` ( ;0c1a-0c80). **Aucun avancement** : barriere ;
    #: * ``$FA`` : dessiner avec ``id + anim``, ``anim`` parcourant ``0..3`` ;
    #:   ``anim == -1`` dessine ``id`` tel quel ( ;0c84-0cbe). Aucun
    #:   avancement ;
    #: * ``$F9`` : reserve a la ligne ``id == $20`` -- les autres dorment ( ;
    #:   0d04-0d10). ``(-31994)++``, et a ``240`` **toutes** les lignes
    #:   avancent d'un octet ( ;0d20-0d36). Puis ``phase += anim`` avec
    #:   rebond a ``-1``/``8`` et dessin de ``((-31994)&3)+$8A`` ( ;
    #:   0d38-0d8c). Aucun avancement ;
    #: * ``$F7`` : avancer d'un octet **toutes** les lignes dont l'octet
    #:   courant n'est pas ``$FF``, la sienne comprise ( ;0d98-0de0) ;
    #: * ``$F6`` : ``(-31994)++`` puis dessiner ``((-31994)&3)+$79`` ( ;
    #:   0de4-0e20). Aucun avancement ;
    #: * tout le reste (``$DD``-``$F5``, ``$F8``, ``$FF``) : **rien**, pas
    #:   meme ``hauteur`` -- LAB_E24 est le seul saut ( ;0de4-0e24). C'est
    #:   une barriere, et c'est aussi la fin veritable d'une ligne.

    def __init__(self, alea: Alea, grille: Grille, fond: Ecran,
                 fond_repli: Ecran, sprites: bytes, tuiles: bytes,
                 revelation: bytes, credits: "Credits") -> None:
        self.alea = alea
        self.grille = grille
        self.fond = fond                    # ``(-31904)`` = bm3
        self.fond_repli = fond_repli        # ``(-31900)`` = bm2
        self.sprites = sprites              # ``LAB_722C`` ;1744
        self.tuiles = tuiles                # ``LAB_6F82`` ;16fa
        self.revelation_donnees = revelation
        self.credits = credits
        self.lignes = [list(e) for e in LIGNES_ETAT]
        self.cles = [0] * NB_EMPLACEMENTS     # ``(-31982)`` ;09ec
        self.ids = [0] * NB_EMPLACEMENTS      # ``(-31984)`` ;0a30
        self.a_marquer = False              # ``(-12,A5)``
        self.revelation = 0                 # ``(-16,A5)``
        self.revelation2 = 0                # ``(-14,A5)``
        self.images = 0                     # ``(-31994)`` ;055c
        self.bascule = 0                    # ``(-31896)`` = ``LAB_708E`` ;0730

    # -- ``SUB_714`` ;0730-0758 ----------------------------------------------
    def _entete(self) -> bool:
        """Bascule, ``SUB_5792``, puis test de sortie ; ``True`` = continuer.

        ``TST.B (-31694)`` ( ;0746) est le drapeau de touche pose par
        ``SUB_5792`` ; ``TST.W (-32004)`` ( ;074c) vaut 0 quand le bouton
        gauche est enfonce. L'un ou l'autre rend la scene finie.
        """
        self.bascule ^= 1                   # ``LAB_730`` ;0730-0740
        return renoncer() == 0              # ``SUB_5792`` ;0742-0758

    # -- ``SUB_714`` ;0828-0890 ----------------------------------------------
    def _marques(self, ecran: Ecran) -> None:
        """``(-12,A5)`` non nul : la revelation va dans le **fond**.

        ``SUB_58CA`` recopie ``bm2`` dans ``bm3`` ( ;082e-083a) -- donc le
        fond est **remis a zero** a chaque marqueur, et les marqueurs
        s'accumulent dans ``cles``/``ids`` plutot que dans les pixels. Puis
        l'image ``0`` est revelee dans ``bm3`` si ``(-16) >= 20`` ( ;083c),
        et les marqueurs y sont redessines un a un jusqu'au premier emplacement
        vide ( ;0854-088e).
        """
        self.fond.donnees[:] = self.fond_repli.donnees
        if self.revelation >= 0x14:          # ``CMPI.W #$0014`` ;083c
            reveler(self.fond, 0, 0, self.revelation, self.revelation_donnees)
        for i in range(NB_EMPLACEMENTS):
            if self.cles[i] == 0:            # ``LAB_880`` ;0880-088e
                break
            marqueur_dessiner(self.fond, self.tuiles, self.cles[i],
                              self.ids[i])
        self.a_marquer = False               # ``CLR.W (-12,A5)`` ;0890

    # -- ``SUB_714`` ;09e6-0b36 ----------------------------------------------
    def _marqueur_poser(self, ligne: int, octet: int) -> None:
        """Opcode ``$64``-``$81`` : insertion **triee** dans les emplacements.

        ``D6`` est le premier emplacement vide ( ;09e6-09fa) : le 68000
        balaie ``cles``, stride 4, **jusqu'au premier zero** et sans borne.
        Le port balaie donc les ``NB_EMPLACEMENTS`` emplacements du BSS et
        non plus huit -- ``SUB_536`` vide le tableau par la meme boucle sans
        borne ( ;0566-058a ), le dessin s'arrete au premier zero ( ;
        0880-088e ), et rien n'introduit de longueur : ``8`` etait une
        supposition, et elle perdait tout placement passe table pleine --
        mises a jour comprises -- figeant les maisons a un stade de
        construction deja passe.

        ``D7`` parcourt ensuite ``0..D6`` ; a chaque pas, la cle egale met a
        jour l'emplacement ( ;0a14-0a34), une cle inferieure provoque
        l'insertion -- la queue est remontee d'un cran, ce qui fait
        disparaitre le vide ( ;0a38-0a8a) -- et une cle superieure fait
        avancer ``D7`` ( ;0a4a-0ac2). Sinon l'emplacement ``D6`` est rempli
        en bout ( ;0aca-0af8).
        """
        valeur = MARQUEURS_TABLE[octet - 0x64]   # ;0a1c
        cle = self.lignes[ligne][4]
        d6 = 0
        while d6 < NB_EMPLACEMENTS and self.cles[d6] != 0:
            d6 += 1
        if d6 >= NB_EMPLACEMENTS:
            # Le 68000 continuerait jusqu'a ``0x7086`` (``bm3``), le premier
            # mot voisin non nul, puis au-dela en ecrasant les variables
            # suivantes. ``NB_EMPLACEMENTS`` s'arrete **avant** : la scene
            # ne remplit jamais les vingt emplacements. **[APPROV]**
            return
        d7 = 0
        fait = False
        while d7 < d6:
            if self.cles[d7] == cle:
                self.ids[d7] = valeur
                fait = True
                break
            if cle < self.cles[d7]:
                for i in range(d6, d7, -1):
                    self.cles[i] = self.cles[i - 1]     # ;0a50-0a88
                    self.ids[i] = self.ids[i - 1]
                self.cles[d7] = cle
                self.ids[d7] = valeur
                fait = True
                break
            d7 += 1
        if not fait:
            self.cles[d6] = cle
            self.ids[d6] = valeur

    def _dessiner_ligne(self, ecran: Ecran, ligne: int, ident: int,
                        hauteur: int) -> None:
        """L'appel ``SUB_50B2`` commun a tous les dessins de script."""
        etat = self.lignes[ligne]
        acteur_dessiner(ecran, self.sprites, etat[4], etat[3], ident,
                        etat[2], self.grille.colonnes[ligne], hauteur,
                        self.bascule)

    # -- ``SUB_714`` ;08a8-0e30 ----------------------------------------------
    def _ligne(self, ecran: Ecran, ligne: int) -> None:
        """Un pas d'une ligne de script ; ``D5`` est l'octet courant."""
        etat = self.lignes[ligne]
        flux = FLUX_TABLE[ligne]
        pos = etat[1]
        if pos >= len(flux):
            return                           # barriere : la ligne dort
        octet = flux[pos]
        ident, phase, pas, compteur, anim, hauteur = (etat[0], etat[2], etat[3],
                                                      etat[4], etat[5], etat[6])
        if octet < 0x64:
            # ``LAB_8A8`` ;08c6-09d2 : marcher vers ``octet``.
            if compteur == octet:            # ;08ce-08f6 : octet atteint
                pos += 1
                etat[1] = pos
                if pos >= len(flux):
                    return
                octet = flux[pos]            # rechargement **sans re-test** < $64
            pas = _pas_script(compteur, octet)   # ;08f8-098a
            etat[3] = pas
            self._dessiner_ligne(ecran, ligne, ident, hauteur)
            phase = (phase + 1) & 7          # ;09ba-09c4
            etat[2] = phase
            if phase == 0:
                etat[4] = compteur + pas     # ;09c8-09ce
            return
        if octet <= 0x81:
            self._marqueur_poser(ligne, octet)   # ;09e6-0af8
            self._dessiner_ligne(ecran, ligne, ident, 0)   # ``CLR.W -(A7)``
            etat[1] = pos + 1
            self.a_marquer = True
            return
        if octet <= 0xDC:
            self._dessiner_ligne(ecran, ligne, DONNEES_6E28[octet - 0x82],
                                 hauteur)
            etat[1] = pos + 1
            return
        if octet == 0xFD:                    # ;0b84-0bc2
            if self.revelation2 >= 0x13:
                reveler(self.fond, 0x20, 0x800, self.revelation2,
                        self.revelation_donnees)
                etat[1] = pos + 1
            reveler(ecran, 0x20, 0x800, self.revelation2,
                    self.revelation_donnees)
            self.revelation2 += 1
            return
        if octet == 0xFE:                    # ;0bca-0bc6
            if self.revelation >= 0x13:
                reveler(self.fond, 0, 0, self.revelation,
                        self.revelation_donnees)
                etat[1] = pos + 1
            reveler(ecran, 0, 0, self.revelation, self.revelation_donnees)
            self.revelation += 1
            return
        if octet == 0xFC:                    # ;0c04-0c16
            if self.revelation2 >= 0x14:
                etat[1] = pos + 1
            return
        if octet == 0xFB:                    # ;0c1a-0c80
            d6 = self.bascule + 0x1B
            if ligne >= 7:
                d6 += 2
            if self.alea.suivant() & 0xFFFF > 30000:   # ``SUB_2FC`` ;0c30
                d6 = (4 if ligne >= 7 else 0) + 0x0E
            # L'appel ne pousse que **six** arguments ( ``LEA ($E,A7),A7``) :
            # ``hauteur`` lirait le haut mot de A3 dans la trame de ``SUB_714``,
            # soit zero pour tout pointeur de hunk 1. **[APPROV]** noté.
            self._dessiner_ligne(ecran, ligne, DONNEES_6E28[d6], 0)
            return
        if octet == 0xFA:                    # ;0c84-0cbe
            if anim == -1:
                self._dessiner_ligne(ecran, ligne, ident, hauteur)
                return
            anim += 1
            if anim == 4:
                anim = 0
            etat[5] = anim
            self._dessiner_ligne(ecran, ligne, anim + ident, 0)
            return
        if octet == 0xF9:                    # ;0d04-0d8c
            if ident != 0x20:
                return                       # les autres lignes dorment
            self.images += 1
            if self.images == 0xF0:          # ;0d20-0d36 : une seule fois
                for autre in self.lignes:
                    autre[1] += 1
            phase += anim                    # ;0d38
            if phase in (-1, 8):             # ;0d40-0d58
                etat[5] = anim = -anim
                phase += anim
            etat[2] = phase
            self._dessiner_ligne(ecran, ligne, (self.images & 3) + 0x8A,
                                 hauteur)
            return
        if octet == 0xF7:                    # ;0d98-0de0
            for autre in range(NB_LIGNES):
                fl = FLUX_TABLE[autre]
                p = self.lignes[autre][1]
                if p < len(fl) and fl[p] != 0xFF:
                    self.lignes[autre][1] = p + 1
            return
        if octet == 0xF6:                    # ;0de4-0e20
            self.images += 1
            self._dessiner_ligne(ecran, ligne, (self.images & 3) + 0x79, 0)
            return
        # ``$DD``-``$F5``, ``$F8``, ``$FF`` : rien, LAB_E24 ( ;0de8-0e24).

    # -- ``SUB_714`` ;0714-0e3c ----------------------------------------------
    def pas(self, ecran: Ecran) -> bool:
        """Une image de la scene ; ``False`` quand il faut rendre la main."""
        if not self._entete():
            return False
        ecran.donnees[:] = self.fond.donnees     # ``SUB_58CA`` ;075a-0766
        self.credits.pas(ecran)                  # ``LAB_76A`` ;076a-0824
        if self.a_marquer:
            self._marques(ecran)                 # ;0828-0890
        for ligne in range(NB_LIGNES):
            self._ligne(ecran, ligne)            # ;08a8-0e30
        return True


# ----------------------------------------------------------------- pilote
def _titre(cadre: pygame.Surface, fenetre: pygame.Surface | None,
           horloge: object, fps: float, attente_titre: float) -> int:
    """``SUB_456`` ;0456-052a : l'ecran titre et ses trois zones.

    La boucle sort sur ``CMP.L #$00055730,D0 ; BGT`` ( ;04a0-04ae), donc avec
    le choix encore a 0, ou sur une zone, mais **uniquement** si
    ``(-32004,A4) == 0`` ( ;04b0-04b4) : ce mot vaut 2 tant que le bouton
    n'est pas enfonce, et 2 de nouveau en sortant ( ;0492 et ;051e). Les
    zones ne sont donc sondees qu'avec le bouton enfonce.

    Renvoie 1, 2 ou 3 pour une zone, 0 pour le delai, -1 si la fenetre a ete
    fermee.
    """
    titre = charger_titre()
    _poser(cadre, titre, fenetre)

    # ``CLR.L (-6,A5)`` ( ;0498) puis ``CMP.L #$00055730,D0 ; BGT LAB_51E``
    # ( ;04a8) : la boucle ne **rend** rien a l'ecran, elle compte et elle
    # sonde le bouton. ``attente_titre < 0`` rejoue donc ce compte brut, sans
    # rafraichissement ; sinon le pilote mesure une duree au chrono et
    # rafraichit, puisque le port n'a pas la tache d'interruption qui
    # retouche l'ecran pendant la boucle. **[APPROV]** sur le rythme seul :
    # le test des zones lui-meme est transcrit.
    compteur = 0
    depart = pygame.time.get_ticks()
    duree_ms = int(attente_titre * 1000) if attente_titre >= 0.0 else -1
    enfonce = False
    while True:
        if duree_ms < 0:
            compteur += 1
            if compteur > DELAI_TITRE:
                break                       # retour 0, ``BGT LAB_51E``
        elif pygame.time.get_ticks() - depart >= duree_ms:
            break                           # retour 0, meme chemin
        fermer = False
        passer = False
        zone = 0
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                fermer = True
            elif ev.type == pygame.KEYDOWN:
                passer = True
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3:
                passer = True
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                enfonce = True
            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                enfonce = False
        if fermer:
            return -1
        if passer:
            return 0                        # ``SUB_16E`` : la partie demarre
        if enfonce:
            zone = zone_titre(*souris_amiga(*_repere(cadre, fenetre)))
            if zone:
                return zone
        _poser(cadre, titre, fenetre)
        if duree_ms >= 0:
            horloge.tick(fps)
    return 0


def _scene(cadre: pygame.Surface, fenetre: pygame.Surface | None,
           horloge: object, fps: float, duree_script: float,
           son: bool = True) -> int:
    """``SUB_1186`` ;1186-1266 : le fond, la chute, le temple, le script.

    L'ordre du listing est exact : ``SUB_1696`` charge ``demo.pic`` dans
    ``bm2`` et le recopie dans ``bm3`` ( ;118a) ; ``SUB_2C36`` charge
    ``popsam`` ( ;1194) ; ``SUB_2E2($7F)`` regraine ( ;1198) ; ``SUB_10A2(100)``
    prepare la chute ( ;11c4) ; ``SUB_1D0E`` les credits ( ;11d4) ; la boucle
    ``LAB_11D8`` fait tomber les cases sur le fond ; ``LAB_120E`` fait du
    **dernier vues** le nouveau fond ( ``bm3 <- bm0`` puis ``bm2 <- bm0``) ;
    ``SUB_E40`` pose le temple ; ``SUB_714`` joue le script. Le retour est
    ``SUB_1236`` et rien d'autre : aucune branche n'en sort.

    Renvoie -1 si la fenetre a ete fermee, 0 sinon -- le pilote d'attract
    reboucle alors sur ``SUB_456``.
    """
    alea = Alea(0)
    alea.regrainer(0x7F)                    # ``SUB_2E2($7F)`` ;1198
    tuiles = charger_tuiles()
    sprites = charger_sprites()
    revelation = charger_revelation()
    fond = charger_fond()                   # ``SUB_1696`` ;118a-1192
    charger_son()                           # ``SUB_2C36`` ;1194  **[APPROV]**
    if son:
        # C'est **ici**, en tete de ``SUB_1186``, que le listing arme le
        # lecteur ( ``JSR (SUB_2C36,PC)`` ;1194 ) : ``SUB_456`` (le titre)
        # n'appelle aucune routine de son -- verifie : les seuls ``JSR`` de
        # ;041c a ;0714 vont a ``SUB_17B2``, ``SUB_549A``, ``SUB_55BA``,
        # ``SUB_29E``, ``SUB_58CA``, ``SUB_10A2``, ``SUB_110A``,
        # ``SUB_50B2`` et ``SUB_358``. La musique n'existe donc que pendant
        # la scene, jamais sur l'ecran titre.
        musique.demarrer(musique.MUSIQUE_INTRO)   # **ECART** : ``popsam``
    repli = Ecran(bytearray(fond.donnees))  # ``bm3 <- bm2``
    grille = Grille(alea, tuiles)
    grille.echeller()
    grille.initialiser(GRILLE * GRILLE)     # ``SUB_10A2($64)`` ;11c4
    ecran = Ecran()
    credits = Credits(charger_fonte())
    credits.reinitialiser()                 # ``SUB_1D0E`` ;11d4

    # -- ``LAB_11D8`` ;11d8-120c : la chute des cent cases -----------------
    while grille.avancer(GRILLE * GRILLE) != 0:
        passe = renoncer()                  # ``SUB_5792`` ;11fc
        if passe != 0:
            return -1 if passe < 0 else 0   # ``LAB_1236`` ;1236
        ecran.donnees[:] = fond.donnees     # ``SUB_58CA`` ;11e6
        grille.dessiner(ecran)              # ``SUB_1C12`` ;11f4
        _poser(cadre, ecran.surface(), fenetre)   # ``SUB_358`` ;11f8
        horloge.tick(fps)
    # ``LAB_120E`` ;120e-1228 : le dernier vues sert de fond aux deux suites.
    fond.donnees[:] = ecran.donnees
    repli.donnees[:] = ecran.donnees

    # -- ``SUB_E40`` ;0e40 : le temple, dix-huit pieces --------------------
    objets = Objets(alea, grille, fond, charger_objets())
    while True:
        epuise = objets.pas(ecran)
        _poser(cadre, ecran.surface(), fenetre)   # ``SUB_358`` ;0f3a
        horloge.tick(fps)
        if renoncer() != 0:                        # ``SUB_5792`` ;0f3e
            return 0                               # ``LAB_1236`` ;1236
        if epuise:
            break

    # -- ``SUB_714`` ;0714 : le script des seize lignes --------------------
    # ``LAB_11D8`` et ``SUB_714`` n'ont **aucune** sortie : la boucle tourne
    # jusqu'a ce que le joueur touche quelque chose, et ``SUB_16E`` relance
    # ``populous.prg`` depuis ``SUB_41C``. ``duree_script`` remplace ce
    # bouton-less infini. **[APPROV]**
    scene = Scene(alea, grille, fond, repli, sprites, tuiles, revelation,
                  credits)
    bord = pygame.time.get_ticks() + int(max(0.0, duree_script) * 1000) \
        if duree_script >= 0.0 else None
    while scene.pas(ecran):
        if bord is not None and pygame.time.get_ticks() - bord >= 0:
            return 0
        _poser(cadre, ecran.surface(), fenetre)
        horloge.tick(fps)
    return 0


def demarrer(cadre: pygame.Surface, horloge: object = None,
             fenetre: pygame.Surface | None = None,
             im_par_seconde: float = 50.0, attente_titre: float = 30.0,
             duree_script: float = 45.0, boucle: bool = True,
             son: bool = True) -> int:
    """Joue l'intro -- titre, scene, et rebouclage -- et renvoie le choix.

    ``SUB_41C`` ;041c-0454 assemble deux bouts seulement : ``SUB_456`` et,
    quand il rend 0, ``SUB_1186`` qui, rendue, reboucle sur ``LAB_452`` puis
    ``LAB_420``. L'attract est donc **infini** : titre, scene, titre, scene...
    jusqu'a ce qu'une zone soit cliquee, et c'est ``SUB_16E`` -- appele par
    ``SUB_4`` -- qui relance ``populous.prg``.

    Graine : ``SUB_384`` ;03a0-03a6 n'appelle ``SUB_2E2`` qu'avec 0, et
    ``SUB_1186`` regraine a ``$7F`` avant la chute : la scene est determinee.

    **[APPROV]** -- cinq ecarts assumes :

    * le rythme vient d'une horloge pygame ; le listing est pilote par le
      copper (``SUB_358`` ;0358 echange ``(-32078)`` et ``(-32074)`` puis
      appelle ``SUB_308(..., $FFFF)``, et ``SUB_55E0`` ;55e0 attend
      ``INTREQR & $20``). Le port pose l'image a l'ecran et rafraichit ;
    * ``attente_titre`` remplace le compte d'iterations de ;04a0-04ae par une
      duree en secondes, mesuree au chrono : la boucle serree de six
      instructions n'est pas datable sans emulateur. ``attente_titre < 0``
      retombe sur le compte brut du listing, ``DELAI_TITRE`` ;
    * ``renoncer()`` remplace ``SUB_5792`` (lecture de ``CIAA_SDR``) et les
      touches ``-1``/``1`` qu'il faut inventer faute de pouvoir relancer
      ``populous.prg``. Une touche ou le bouton droit rend la scene finie et
      reboucle sur le titre, comme dans le listing ;
    * ``duree_script`` borne la phase ``SUB_714``, qui n'a aucune fin propre.
      ``< 0`` la laisse ouverte jusqu'a une touche, ``0`` l'evite ;
    * ``son`` arme la musique de fond. Le **calque** est celui du listing,
      et non plus le calque oppose en Phase 86 : ``SUB_2C36`` est appele en
      ;1194, en tete de ``SUB_1186``, et ``SUB_2DD8`` en ;1260, derniere
      instruction de la scene avant ``RTS``. ``SUB_456`` (le titre) n'appelle
      aucune routine de son -- verifie : les seuls ``JSR`` de ;041c a ;0714
      vont a ``SUB_17B2``, ``SUB_549A``, ``SUB_55BA``, ``SUB_29E``,
      ``SUB_58CA``, ``SUB_10A2``, ``SUB_110A``, ``SUB_50B2`` et ``SUB_358``.
      La musique est donc **pendant la scene** et le titre est silencieux.
      Seul le support reste un **ECART** : le port joue
      ``reference/Main Theme.mp3`` au lieu de ``popsam``, dont le lecteur
      (``SUB_2F9C``/``SUB_3046``/``LAB_3060``) n'est pas transcrit. Les
      effets (codes de son) restent portes par ``populous.sound``.
      ``son=False`` coupe tout -- c'est ce que font les outils qui n'ont
      pas de carte son.

    ``cadre`` est le bitmap de travail, celui que le jeu appelle
    ``self.frame`` (320x200, quatre plans) ; ``fenetre`` est la surface de
    ``display.set_mode``, agrandie par ``config.ZOOM``. ``fenetre=None``
    affiche directement le cadre, ce qui sert aux tests sans fenetre.

    ``boucle=False`` ne fait qu'un tour -- titre, une scene, fin -- et renvoie
    0 : c'est le mode de ``tools/check_intro.py``.

    Renvoie 1, 2 ou 3 selon la zone touchee sur l'ecran titre ; 0 quand
    l'intro est finie sans zone (touche en cours de route, ou un tour sans
    boucle) : la partie demarre alors ; -1 si la fenetre a ete fermee, ce qui
    arrete le jeu.
    """
    fps = max(0.0, float(im_par_seconde))
    if horloge is None:
        horloge = pygame.time.Clock()
    try:
        while True:
            choix = _titre(cadre, fenetre, horloge, fps, attente_titre)
            if choix != 0:
                return choix                    # 1, 2, 3 -- ou -1
            fini = _scene(cadre, fenetre, horloge, fps, duree_script, son)
            # ``SUB_2DD8`` ;1260 est la **derniere** instruction de
            # ``SUB_1186`` avant ``UNLK/RTS`` : couper ici, a l'heure ou la
            # scene rend la main, est le calque exact du listing. La scene
            # est donc musique et le titre est silencieux.
            if son:
                musique.arreter()
            if fini < 0:
                return -1
            if not boucle:
                return 0
    finally:
        # Filet de securite : la fenetre fermee (-1) ou une exception sort
        # du ``while`` sans repasser par ;1260.
        if son:
            musique.arreter()
