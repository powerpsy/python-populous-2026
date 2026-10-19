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

Trois arbitrages assumes, tous marques ECART plus bas :
* l'ecran titre du port fait 320x200 ; la souris est ramenee a l'espace
  0..319 du listing sur les deux axes (voir ``souris_amiga``) ;
* le son de l'intro (``popsam``, ``SUB_2DD8``) n'est pas porte ;
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

    def sprite(self, x: int, y: int, numero: int, tuiles: bytes) -> None:
        """``SUB_19EE`` ;19ee : pose un sprite 32x24 masque de ``land0``.

        ``x`` est en pixels (on decale l'adresse de ``x>>4`` mots, puis les
        donnees de ``x&15`` bits par ``ROR.L`` ;1a12-1a18), ``y`` en lignes.
        Le dessin s'arrete a la ligne 199 (``D3 = $C7 - y``, ;1a00) et refuse
        tout ``y < 0`` ( ;19ee).
        """
        hauteur = HAUTEUR_SPRITE
        if y < 0:
            return
        if y >= LIMITE_BASSE:
            hauteur = 0xC7 - y
            if hauteur <= 0:
                return
        dec = x & 0x0F
        base = numero * SPRITE_OCTETS
        colonne = (x >> 3) & ~1
        for ligne in range(hauteur + 1):
            dy = y + ligne
            if not 0 <= dy < HAUTEUR:
                continue
            haut = dy * PAS_LIGNE + colonne
            s = base + ligne * (SPRITE_L // 8 * 5)
            for bloc in range(SPRITE_L // 16):
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


def demarrer(cadre: pygame.Surface, horloge: object = None,
             fenetre: pygame.Surface | None = None,
             im_par_seconde: float = 50.0, attente_titre: float = 30.0,
             duree_credits: float = 12.0) -> int:
    """Joue l'intro, du titre au rouleau de credits, et renvoie le choix.

    Trois bouts transcrits y sont assembles :

    1. ``SUB_456`` ;0456 : ``load.pic`` et ses trois zones (``zone_titre``).
       La boucle sort sur ``CMP.L #$55730,D0 ; BGT`` ( ;04a0-04ae), donc avec
       le choix encore a 0, ou sur une zone, mais **uniquement** si
       ``(-32004,A4) == 0`` ( ;04b0-04b4) : ce mot vaut 2 tant que le bouton
       n'est pas enfonce, et 2 de nouveau en sortant ( ;0492 et ;051e). Les
       zones ne sont donc sondees qu'avec le bouton enfonce.
    2. ``SUB_1186`` ;1186 : la chute des 100 cases (``Grille``), qui s'arrete
       en 58 tours.
    3. ``SUB_536`` / ``SUB_714`` : le rouleau a deux slots (``Credits``).

    Graine : ``SUB_384`` ;03a0-03a6 n'appelle ``SUB_2E2`` qu'avec 0, et
    ``random() & 0`` vaut 0 - la demo est donc deterministe (``Alea(0)``).

    **[APPROX]** - trois ecarts assumes :

    * le rythme vient d'une horloge pygame ; le listing est pilote par le
      copper (``SUB_358`` ;0358 echange ``(-32078)`` et ``(-32074)`` puis
      appelle ``SUB_308(..., $FFFF)``, et ``SUB_58CA`` ;58ca recopie $1F40
      mots entre deux tampons). Le port efface le tampon avant chaque image,
      qui est le rendu visible que la chaine du listing produit ;
    * ``attente_titre`` remplace le compte d'iterations de ;04a0-04ae par une
      duree en secondes, mesuree au chrono : la boucle serree de six
      instructions n'est pas datable sans emulateur. ``attente_titre < 0``
      retombe sur le compte brut du listing, ``DELAI_TITRE`` ;
    * la phase de script de ``SUB_714`` (Phase 85) n'est pas jouee : c'est
      elle qui, dans l'original, decide de la fin. ``LAB_11D8`` n'a en effet
      **aucune** sortie propre : le rouleau des credits reboucle indefiniment
      sur ``0xFF`` ( ``SUB_1D1A`` ;1d44-1dbc) et c'est ``SUB_16E``, appele par
      ``SUB_714`` quand son script est epuise, qui lance ``populous.prg``.
      Sans le script, le port laisserait donc la boucle tourner a jamais.
      ``duree_credits`` la borne : secondes, ``0`` pour l'eviter tout de
      suite, ``< 0`` pour la laisser ouverte jusqu'a une touche.

    ``cadre`` est le bitmap de travail, celui que le jeu appelle
    ``self.frame`` (320x256, 32 bits) ; ``fenetre`` est la surface de
    ``display.set_mode``, agrandie par ``config.ZOOM``. ``fenetre=None``
    affiche directement le cadre, ce qui sert aux tests sans fenetre.

    Renvoie 1, 2 ou 3 selon la zone touchee sur l'ecran titre ; 0 quand
    l'intro est finie (delai depasse puis chute et credits passes, ou touche
    en cours de route) : la partie demarre alors ; -1 si la fenetre a ete
    fermee, ce qui arrete le jeu.
    """
    fps = max(0.0, float(im_par_seconde))
    if horloge is None:
        horloge = pygame.time.Clock()

    # -- 1. SUB_456 ;0456-052a : l'ecran titre -----------------------------
    titre = charger_titre()
    _poser(cadre, titre, fenetre)

    # ``CLR.L (-6,A5)`` ( ;0498) puis ``CMP.L #$00055730,D0 ; BGT LAB_51E``
    # ( ;04a8) : la boucle ne **rend** rien a l'ecran, elle compte et elle
    # sonde le bouton. ``attente_titre < 0`` rejoue donc ce compte brut,
    # sans rafraichissement ; sinon le pilote mesure une duree au chrono et
    # rafraichit, puisque le port n'a pas la tache d'interruption qui
    # retouche l'ecran pendant la boucle. **[APPROX]** sur le rythme seul :
    # le test des zones lui-meme est transcrit.
    compteur = 0
    depart = pygame.time.get_ticks()
    duree_ms = int(attente_titre * 1000) if attente_titre >= 0.0 else -1
    enfonce = False
    choix = 0
    while True:
        if duree_ms < 0:
            compteur += 1
            if compteur > DELAI_TITRE:
                break                       # retour 0, ``BGT LAB_51E``
        elif pygame.time.get_ticks() - depart >= duree_ms:
            break                           # retour 0, meme chemin
        fermer = False
        passer = False
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
            return 0            # ``SUB_16E`` : on rend la main au jeu
        if enfonce:
            zone = zone_titre(*souris_amiga(*_repere(cadre, fenetre)))
            if zone:
                choix = zone
                break
        if duree_ms >= 0:
            _poser(cadre, titre, fenetre)
            horloge.tick(fps)
    if choix:
        return choix

    # -- 2. SUB_1186 ;1186 : la chute des 100 cases -------------------------
    tuiles = charger_tuiles()
    grille = Grille(Alea(0), tuiles)
    grille.echeller()
    grille.initialiser(GRILLE * GRILLE)
    ecran = Ecran()
    while grille.avancer(GRILLE * GRILLE) != 0:
        passe = renoncer()
        if passe < 0:
            return -1
        if passe > 0:
            return 0            # on passe la chute, la partie demarre
        ecran.vider()
        grille.dessiner(ecran)
        _poser(cadre, ecran.surface(), fenetre)
        horloge.tick(fps)

    # -- 3. SUB_536 / SUB_714 : le rouleau de credits -----------------------
    fonte = charger_fonte()
    credits = Credits(fonte)
    credits.reinitialiser()
    ecran = Ecran()
    # ``LAB_11D8`` n'a pas de sortie : dans l'original c'est ``SUB_714`` qui
    # tranche (Phase 85). En attendant, ``duree_credits`` le remplace.
    bord = pygame.time.get_ticks() + int(max(0.0, duree_credits) * 1000) \
        if duree_credits >= 0.0 else None
    while True:
        passe = renoncer()
        if passe != 0:
            return 0 if passe > 0 else -1
        if bord is not None and pygame.time.get_ticks() - bord >= 0:
            return 0                    # fin de l'intro, la partie demarre
        ecran.vider()
        credits.pas(ecran)
        _poser(cadre, ecran.surface(), fenetre)
        horloge.tick(fps)
