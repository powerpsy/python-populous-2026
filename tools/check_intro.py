"""Controle d'execution de l'intro (Phase 84) : ``populous/intro.py``.

Ce que l'original fait, et que l'on verifie ici
-----------------------------------------------

* Les **constantes sont lues dans le listing**, pas relues a la main :
  ``check_intro`` reconstruit ``LAB_640C`` (300 octets), ``LAB_1F62`` (les
  18 mots de fondu) et ``LAB_1DCE`` (les 23 chaines de credits) depuis
  ``populous_main.asm`` et les confronte a ``intro.TYPE`` / ``HAUTEUR_CASE`` /
  ``FADE`` / ``CREDITS``. Le bloc de credits est double : le desassembleur a
  laisse les octets bruts en commentaires (L2346-2371) **avant** la
  transcription en chaines (L2372-2394) ; les deux doivent designer la meme
  suite d'octets.
* ``SUB_6538`` : les constantes ``$41C64E6D`` et ``$3039`` sont relues dans
  le listing ( ;653c et ;654a) et confrontees a ``Alea.MULT`` / ``PLUS``, et
  le masque de retour ``$7FFF`` ( ;4701) a ``suivant``.
* ``SUB_110A`` (``avancer``) est confronte a une reecriture independante des
  semantiques 68000, y compris la **division tronquant vers zero** du
  ``DIVS #$2`` ( ;1142) et le **bug** du resultat retenu (voir ci-dessous).
* ``SUB_1D1A`` (``dessiner_ligne``) est confrontee a un decodage independant
  de ``font.dat`` : plan 0 en ``$FF`` partout, les quatre autres a zero, les
  cinq plans de la glyph ecrits au pas de ``40`` octets.
* ``SUB_5026`` (``blitter``) est confrontee a la formule bit a bit
  ``dest = (dest & (p0|m)) | (source & ~(p0|m))`` : le plan 0 de la source est
  bien un **masque de conservation**, donc la ligne de credits est
  transparente la ou le fond est deja pose.
* ``SUB_19EE`` (``sprite``) est confrontee au decodage bit a bit de ``land0``,
  masque + quatre plans compris, y compris le decalage de 1 a 15 pixels
  (``ROR.L``) et les trois coupures de hauteur (``y < 0``, ``y >= $B0``,
  ``y >= 200``).
* ``SUB_456`` (``zone_titre``) est confrontee a une reecriture directe de la
  chaine ``CMP``/``BLT``/``BGE`` de ;04b6-0512, sur une grille de 40000
  positions de souris.
* Enfin, le demo complet tourne : la grille rebondit jusqu'a l'arret, les
  23 lignes de credits defilent **toutes**, et rien ne sort du bitmap.

Le bug de ``SUB_110A`` reproduit
--------------------------------

``(-2,A5)`` est initialise a zero ( ;1112) et l'ecriture n'est gatee que par
``TST.W (-2,A5)`` ( ;114c-1152), et non par un indice de case egal a zero.
Tant que la vitesse retenue vaut zero, la boucle continue d'ecraser le
resultat : le retour est donc la **premiere vitesse non nulle**, pas celle de
la case 0. ``intro.Grille.avancer`` le reproduit, et le controle verifie que
les deux comportements different sur au moins un cas tire au sort.

::

    python tools\\check_intro.py
"""
import io
import os
import random
import re
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame                                     # noqa: E402

pygame.init()
pygame.display.set_mode((8, 8))

from populous import assets, intro                # noqa: E402

TOTAL = [0]
ECHECS: list[str] = []


def chk(cond: bool, message: str) -> None:
    TOTAL[0] += 1
    print(("  OK    " if cond else "  ECHEC ") + message)
    if not cond:
        ECHECS.append(message)


# ------------------------------------------------------------------ listing
CHEMIN = Path(__file__).resolve().parent.parent / "reference" / "tetracorp" \
    / "populous_main.asm"
LIGNES = CHEMIN.read_text(encoding="utf-8", errors="replace").split("\n")


def _sans_commentaire(s: str) -> str:
    """Retire le suffixe ``;aaaa`` qu'ajoute le desassembleur en fin de ligne."""
    return re.sub(r"\s*;[0-9a-f]{4}\s*$", "", s.strip())


def _bloc(debut: int, fin: int) -> bytes:
    """Reconstruit les octets du bloc de lignes ``[debut, fin]`` (1-based).

    ``DS.L``/``DS.W``/``DS.B`` sont reserves vides : ils comptent pour des
    octets nuls, ce qui est exactement ce que DevPac emit dans un hunk DATA.
    """
    octets = bytearray()
    for s in LIGNES[debut - 1:fin]:
        t = _sans_commentaire(s)
        m = re.match(r"^DC\.([LWB])\s+(.+)$", t)
        if m:
            for it in m.group(2).split(","):
                v = int(it.strip().lstrip("$"), 16)
                octets += v.to_bytes({"L": 4, "W": 2, "B": 1}[m.group(1)], "big")
            continue
        m = re.match(r"^DS\.([LWB])\s+(\$[0-9a-fA-F]+|\d+)", t)
        if m:
            n = int(m.group(2).lstrip("$"), 16) \
                if m.group(2).startswith("$") else int(m.group(2))
            octets += bytes(n * {"L": 4, "W": 2, "B": 1}[m.group(1)])
    return bytes(octets)


def _numero_adresse(numero: int) -> int:
    """Adresse de la ligne ``numero`` (1-based), quel que soit son gabarit.

    Le listing melange trois formes : ``6538: LINK.W A5,#0`` (adresse en tete),
    ``;6538: 4e550000`` (adresse seule en commentaire) et
    ``DC.L $... ;640c`` (adresse en fin de ligne).
    """
    s = LIGNES[numero - 1]
    m = re.match(r"^([0-9a-f]{4}):", s)
    if m:
        return int(m.group(1), 16)
    m = re.search(r";([0-9a-f]{4}):\s*[0-9a-f]*\s*$", s)
    if m:
        return int(m.group(1), 16)
    m = re.search(r";([0-9a-f]{4})\s*$", s)
    return int(m.group(1), 16) if m else -1


print("check_intro : lecture du listing et confrontation au portage")
print()

# ------------------------------------------------- LAB_640C : 300 octets
# L4664..L4682 ; l'adresse de depart est ;640c et celle de fin ;6538 (SUB_6538).
debut = _numero_adresse(4664)
fin = _numero_adresse(4684)                     # ;6538, la ligne de SUB_6538
bloc = _bloc(4664, 4682)
chk(debut == 0x640C, "le bloc LAB_640C debute en ;640c (lu : %04x)" % debut)
chk(fin == 0x6538, "il se termine juste avant SUB_6538 en ;6538 (lu : %04x)"
    % fin)
chk(len(bloc) == fin - debut == 300,
    "LAB_640C pese exactement 300 octets : %d, soit %d - %d"
    % (len(bloc), fin, debut))

attendu = intro.TYPE + intro.DRAPEAU + intro.HAUTEUR_CASE
chk(bloc == attendu,
    "LAB_640C = TYPE (100) + DRAPEAU (100, DS.L $19) + HAUTEUR_CASE (100, "
    "avec ses quatre DS reserves) : %s"
    % ("" if bloc == attendu else "ecart a l'octet %d" % next(
        (i for i in range(min(len(bloc), len(attendu)))
         if bloc[i] != attendu[i]), -1)))
chk(intro.TYPE[:4] == bytes([0x00, 0x16, 0x06, 0x0F]),
    "les quatre premiers types valent 00 16 06 0f ( ;640c)")
chk(intro.DRAPEAU == bytes(100),
    "le tableau des drapeaux est entierement nul : DS.L $19 a ;6470")
chk(intro.HAUTEUR_CASE[-16:] == bytes(16),
    "les quatre derniers octets sont nuls : DS.L 4 a ;6528")
chk(sorted(set(intro.TYPE)) == sorted(set(bloc[:100])),
    "TYPE ne contient que des octets pris dans le bloc")

# ------------------------------------------------- LAB_1F62 : le fondu
d2 = _numero_adresse(2397)
chk(d2 == 0x1F62, "le tableau de fondu debute en ;1f62 (lu : %04x)" % d2)
fade = _bloc(2397, 2400)                       # neuf DC.L puis DS.L 6
mots = [int.from_bytes(fade[i:i + 2], "big") for i in range(0, 36, 2)]
chk(len(fade) == 36 + 24, "neuf longs (36 o) suivis de DS.L 6 (24 o) : %d"
    % len(fade))
chk(mots == intro.FADE[:18],
    "les 18 mots de LAB_1F62 sont recopies a l'identique : %s" % (mots,))
chk(intro.FADE[0] == 0xFFFF,
    "le masque 0 est $FFFF : au debut, la ligne est invisible ( ;1f62)")
chk(all(v == 0 for v in intro.FADE[18:]),
    "au-dela de la table, la DS.L 6 rend un masque nul : la ligne est "
    "entierement visible")
# Les mots sont un tramage, pas une rampe : la densite de bits a un doit
# diminuer en moyenne, meme si les mots se croisent d'un rang a l'autre.
densites = [bin(v).count("1") for v in intro.FADE[:18]]
chk(densites[0] == 16 and densites[-1] <= 5,
    "le tramage passe de 16 bits a 1 (complet) a %d bits a 1 en fin de "
    "table" % densites[-1])
chk(intro.FADE[17] == 0x0010,
    "le dernier mot de LAB_1F62 est $0010, soit 1/8e de bit fonde")

# ------------------------------------------------- LAB_1DCE : les credits
commentes = bytearray()
for s in LIGNES[2345:2371]:                    # L2346..L2371 (dump d'octets)
    m = re.search(r";DC\.B\s+((?:\$[0-9a-fA-F]{2},?)+)", s)
    if m:
        for h in m.group(1).split(","):
            commentes.append(int(h.strip().lstrip("$"), 16))
commentes = bytes(commentes)
chains = []
for s in LIGNES[2371:2394]:                     # L2372..L2394 uniquement
    m = re.match(r'^\s*DC\.B\s+"(.*)",0\s*$', s)
    if m:
        chains.append(m.group(1))
suite = b"\x00".join(c.encode("ascii") for c in chains) + b"\x00"
if commentes != suite:
    print("    [diag] commentaires=%d chaines=%d" % (len(commentes), len(suite)))
    for i in range(min(len(commentes), len(suite))):
        if commentes[i] != suite[i]:
            print("    [diag] premier octet different a %d : %02x vs %02x"
                  % (i, commentes[i], suite[i]))
            print("    [diag] versant : %r" % suite[max(0, i - 12):i + 12])
            print("    [diag] en comm : %r"
                  % bytes(commentes[max(0, i - 12):i + 12]))
            break
    else:
        print("    [diag] l'un est un prefixe de l'autre")
chk(len(chains) == 23,
    "il y a bien 23 chaines de credits dans LAB_1DCE (L2372-2394) : %d"
    % len(chains))
chk(commentes == suite,
    "le dump d'octets en commentaires (L2346-2371) et les chaines "
    "transcrites (L2372-2394) donnent la meme suite de %d octets" % len(suite))
chk(chains == intro.CREDITS,
    "intro.CREDITS est exactement la suite du listing")
chk(_numero_adresse(2395) == 0x1F60,
    "le marqueur de fin de suite est en ;1f60")
fin_suite = re.sub(r"\s+", " ", _sans_commentaire(LIGNES[2394])).strip().upper()
chk(fin_suite == "DC.W $FF00",
    "la fin de suite est bien le mot $FF00, soit l'octet $FF de rebouclage "
    "(lu : %r)" % fin_suite)

# ------------------------------------------------- SUB_6538 : l'aleatoire
src6538 = "\n".join(LIGNES[4682:4704])
chk("41c64e6d" in src6538, "SUB_6538 emploie la constante #$41c64e6d ( ;653c)")
chk("3039" in src6538, "SUB_6538 emploie la constante #$00003039 ( ;654a)")
chk("7fff" in src6538, "SUB_6538 masque le retour par #$00007fff ( ;4701)")
chk(intro.Alea.MULT == 0x41C64E6D and intro.Alea.PLUS == 0x3039,
    "Alea.MULT/PLUS correspondent aux constantes du listing")
a = intro.Alea(1234)
g = 1234
suite = []
for _ in range(50):
    g = (g * 0x41C64E6D + 0x3039) & 0xFFFFFFFF
    suite.append((g >> 16) & 0x7FFF)
chk([a.suivant() for _ in range(50)] == suite,
    "Alea.suivant() suit exactement la recurrence du listing sur 50 tirages")
chk(all(0 <= v < 0x8000 for v in suite), "tous les tirages tiennent sur 15 bits")
chk(intro.Alea(0).regrainer(0x7F) == 0, "SUB_2E2(0) laisse la graine a 0")
b = intro.Alea(999)
chk(b.regrainer(0x7F) == (intro.Alea(999).suivant() & 0x7F),
    "SUB_2E2(n) ramene bien graine = random() & n")

# ------------------------------------------------- SUB_110A : la chute
def _ref_110a(colonnes, vitesses, n):
    """Reecriture independante des semantiques 68000 de SUB_110A.

    ``DIVS #$2`` divise en entier en **tronquant vers zero** : -3 divise par 2
    vaut -1 et non -2. ``NEG.W`` inverse ensuite le signe.
    """
    c = list(colonnes)
    v = list(vitesses)
    retenu = 0
    for i in range(n):
        d5 = (v[i] + 1) & 0xFFFF
        d5s = d5 - 0x10000 if d5 & 0x8000 else d5
        d6 = (c[i] - d5s)
        d6 = d6 & 0xFFFF
        d6s = d6 - 0x10000 if d6 & 0x8000 else d6
        if d6s < 0:
            q = int(d5s / 2)                 # DIVS : troncature vers zero
            d5s = (-q) & 0xFFFF
            d5s = d5s - 0x10000 if d5s & 0x8000 else d5s
            d6s = 0
        if retenu == 0:
            retenu = d5s
        c[i] = d6s
        v[i] = d5s
    return c, v, retenu


diffs = 0
for graine in range(40):
    g_alea = intro.Alea(graine * 7919)
    gr = intro.Grille(g_alea, intro.charger_tuiles())
    gr.initialiser(100)
    rc, rv = list(gr.colonnes), list(gr.vitesses)      # etat de depart
    rr = 0
    for _ in range(30):
        obtenu = gr.avancer(100)
        rc, rv, rr = _ref_110a(rc, rv, 100)
        if (gr.colonnes, gr.vitesses, obtenu) != (rc, rv, rr):
            diffs += 1
chk(diffs == 0,
    "avancer(100) suit la reecriture 68000 independante sur 40x30 tours : "
    "%d divergences" % diffs)

# la premiere vitesse non nulle, et non celle de la case 0
trouve = False
for graine in range(2000):
    ga = intro.Alea(graine)
    gr = intro.Grille(ga, intro.charger_tuiles())
    gr.colonnes[0] = 0
    gr.vitesses[0] = 0
    gr.colonnes[1] = 3
    gr.vitesses[1] = 5
    if gr.avancer(2) != 0:
        trouve = True
        break
chk(trouve,
    "bug reproduit : la case 0 est a l'arret, c'est la case 1 qui fournit le "
    "retour (gatee par TST.W (-2,A5) en ;114c et non par un indice)")

# le modele : colonnes dans [232, 244], vitesses dans [0, 8]
g0 = intro.Grille(intro.Alea(42), intro.charger_tuiles())
g0.initialiser(100)
chk(all(0xE8 <= c < 0xE8 + 13 for c in g0.colonnes),
    "SUB_10A2 range les colonnes dans [232, 244] : %d..%d"
    % (min(g0.colonnes), max(g0.colonnes)))
chk(all(0 <= v < 9 for v in g0.vitesses),
    "SUB_10A2 range les vitesses dans [0, 9[ : %d..%d"
    % (min(g0.vitesses), max(g0.vitesses)))

# la chute finit toujours par s'arreter
g1 = intro.Grille(intro.Alea(7), intro.charger_tuiles())
g1.initialiser(100)
tours = 0
while g1.avancer(100) != 0 and tours < 5000:
    tours += 1
arrets = sum(1 for i in range(100) if g1.colonnes[i] == 0 and g1.vitesses[i] == 0)
chk(tours < 5000 and arrets == 100,
    "les 100 cases finissent toutes a l'arret, colonne 0 et vitesse 0, "
    "en %d tours" % tours)

# SUB_1BE8 : multiplication par 8 sur un octet
g2 = intro.Grille(intro.Alea(0), intro.charger_tuiles())
g2.echeller()
chk(g2.hauteur == bytearray((b << 3) & 0xFF for b in intro.HAUTEUR_CASE),
    "SUB_1BE8 multiplie chaque hauteur par 8, sur un octet")

# ------------------------------------------------- SUB_1D1A : une ligne
def _ref_ligne(fonte, texte):
    """Reecriture independante de SUB_1D1A : 5 plans de 320x8."""
    tampon = bytearray(40 * 8 * 5)
    tampon[:320] = b"\xFF" * 320
    x0 = (0x28 - len(texte)) // 2
    for i, c in enumerate(texte):
        g = (ord(c) - 0x20) * 40
        for r in range(8):
            for p in range(5):
                tampon[p * 320 + r * 40 + x0 + i] = fonte[g + r * 5 + p]
    return tampon


fonte = intro.charger_fonte()
chk(len(fonte) == 0x1130,
    "font.dat pese 0x1130 = 4400 octets, soit 110 glyphs de 40 : %d"
    % len(fonte))
cr = intro.Credits(fonte)
for texte in ("POPULOUS", "EXCEPT ROB", "PUBLISHED BY ELECTRONIC ARTS"):
    tampon = bytearray(intro.CREDITS_OCTETS)
    cr.dessiner_ligne(tampon, texte)
    chk(bytes(tampon) == _ref_ligne(fonte, texte),
        "dessiner_ligne(%r) recopie bien les 5 plans de la glyph, centree "
        "sur 40 caracteres" % texte)

cr.reinitialiser()
chk(cr.curseur == 0, "SUB_1D0E remet le curseur de credits a zero")
vus = [cr.ligne_suivante() for _ in range(23)]
chk(vus == intro.CREDITS, "les 23 lignes sortent dans l'ordre du listing")
chk(cr.ligne_suivante() == "POPULOUS",
    "la 24e boucle sur la premiere : le marqueur $FF reboucle ( ;1db6)")

# le fond du tampon est transparent sur le plan 0, opaque ailleurs
tampon = bytearray(intro.CREDITS_OCTETS)
cr.dessiner_ligne(tampon, "")                   # aucun caractere dessine
chk(all(tampon[i] == 0xFF for i in range(40 * 8)),
    "le plan 0 du tampon est en $FF : c'est le masque de conservation "
    "(SUB_1D1A ;1d28-1d34)")
chk(all(tampon[i] == 0 for i in range(40 * 8, 1600)),
    "les plans 1 a 4 sont nuls hors glyph ( ;1d36-1d43)")
chk(all(tampon[i] == 0xFF for i in range(intro.PAS_LIGNE * intro.CREDITS_H))
    and all(tampon[i] == 0
            for i in range(intro.PAS_LIGNE * intro.CREDITS_H,
                           intro.CREDITS_OCTETS)),
    "un tampon vierge : plan 0 entier en $FF, plans 1 a 4 nuls "
    "(320 + 1600 octets)")

# ------------------------------------------------- SUB_5026 : le fondu
ec = intro.Ecran()
for i in range(intro.TAILLE_BITMAP):
    ec.donnees[i] = 0x55 if (i % 2) else 0xAA
src = bytearray(intro.CREDITS_OCTETS)
for i in range(intro.CREDITS_OCTETS):
    src[i] = (i * 7) & 0xFF
avant = bytes(ec.donnees)
ec.blitter(intro.Ecran(src), 0, 0, 0)
apres = ec.donnees
diverge = []
s0base = 0
for k in range(20):
    m = intro.FADE[0 + k % 3] & 0xFFFF
    n = ~m & 0xFFFF
    conserv = ((src[k * 2] << 8) | src[k * 2 + 1] | m) & 0xFFFF
    for p in range(4):
        so = (p + 1) * intro.PAS_LIGNE * intro.CREDITS_H + k * 2
        s = (src[so] << 8) | src[so + 1]
        o = p * intro.TAILLE_PLAN + k * 2
        d = int.from_bytes(avant[o:o + 2], "big")
        v = (d & conserv) | (s & n)
        if int.from_bytes(apres[o:o + 2], "big") != v:
            diverge.append((p, k))
chk(not diverge,
    "blitter applique bien dest = (dest & (plan0_source|masque)) | "
    "(source & ~(plan0_source|masque)), plan par plan : %d mots differs"
    % len(diverge))

# ou la source vaut $FF sur le plan 0, rien ne bouge
ec2 = intro.Ecran()
for i in range(intro.TAILLE_BITMAP):
    ec2.donnees[i] = 0x37
avant2 = bytes(ec2.donnees)
plein = bytearray(intro.CREDITS_OCTETS)
plein[:320] = b"\xFF" * 320                # plan 0 tout a un
ec2.blitter(intro.Ecran(plein), 0, 0, 0)
chk(bytes(ec2.donnees) == avant2,
    "la ou le plan 0 source vaut $FF, l'ecran est intact : la ligne de "
    "credits est bien transparente sur son fond")

# ------------------------------------------------- SUB_19EE : les sprites
def _ref_depose(tuiles, numero, x, y, colonne, dec, hauteur):
    """Modele independant de ``SUB_19EE`` : pixels modifies par la sprite.

    Renvoie ``{(px, py): (masque, donnees)}`` : un bit de masque commun aux
    quatre plans, puis un bit de donnees par plan. La regle de compositing du
    listing est ``dest = (dest & masque) | donnees`` ( ;1a4e-1a6a), donc :
    masque a 0 et donnees a 0 **effacent** le pixel, masque a 1 le conserve.
    Le pixel de source ``j`` part a ``colonne*8 + bloc*16 + j + dec``, le
    debordement ``j + dec >= 16`` allant dans le mot suivant ( ``SWAP``
    ;1a6e-1a78). L'ecriture est lineaire dans le bitmap, **sans retour a la
    ligne** : quand ``colonne + 4 >= 40`` (donc ``x >= 288``), le troisieme
    mot part sur la premiere octet de la ligne suivante.
    """
    out = {}
    base = numero * intro.SPRITE_OCTETS
    for r in range(hauteur + 1):
        s = base + r * 20
        for bloc in range(2):
            mots = [int.from_bytes(tuiles[s + bloc * 10 + 2 * q:
                                           s + bloc * 10 + 2 * q + 2], "big")
                    for q in range(5)]
            m, p0, p1, p2, p3 = mots
            for j in range(16):
                lin = (y + r) * 320 + colonne * 8 + bloc * 16 + j + dec
                if not 0 <= lin < 200 * 320:
                    continue
                py, px = divmod(lin, 320)
                donnees = ((((p0 >> (15 - j)) & 1) << 0)
                           | (((p1 >> (15 - j)) & 1) << 1)
                           | (((p2 >> (15 - j)) & 1) << 2)
                           | (((p3 >> (15 - j)) & 1) << 3))
                out[(px, py)] = (1 if m & (0x8000 >> j) else 0, donnees)
    return out


def _attendu(masque, donnees, ancien):
    """``dest = (dest & masque) | donnees``, plan par plan."""
    res = 0
    for p in range(4):
        res |= (((((ancien >> p) & 1) & masque) | ((donnees >> p) & 1)) << p)
    return res


def _indices(ec):
    out = [[0] * 320 for _ in range(200)]
    for y in range(200):
        base = y * 40
        for x in range(320):
            o = base + (x >> 3)
            bit = 0x80 >> (x & 7)
            c = 0
            for p in range(4):
                if ec.donnees[o + p * intro.TAILLE_PLAN] & bit:
                    c |= 1 << p
            out[y][x] = c
    return out


tuiles = intro.charger_tuiles()


def _masque(i):
    """Les 48 mots de masque d'une tuile de ``land0`` (2 par ligne)."""
    base = i * intro.SPRITE_OCTETS
    return [int.from_bytes(tuiles[base + r * 20 + b * 10:
                                   base + r * 20 + b * 10 + 2], "big")
            for r in range(24) for b in range(2)]


def _donnees(i):
    """Les 192 mots de plans d'une tuile de ``land0`` (4 par ligne et paquet)."""
    out = []
    base = i * intro.SPRITE_OCTETS
    for r in range(24):
        s = base + r * 20
        for b in range(2):
            for q in range(1, 5):
                out.append(int.from_bytes(tuiles[s + b * 10 + 2 * q:
                                                 s + b * 10 + 2 * q + 2],
                                          "big"))
    return out


nuls = [i for i in range(70) if sum(_masque(i)) == 0]
chk(nuls == [69],
    "des 70 tuiles de land0, seule la 69 a un masque entierement nul "
    "(le temoin 'rien') : %s" % (nuls,))
chk(sum(_donnees(69)) == 0,
    "et ses quatre plans sont nuls eux aussi : la tuile 69 ecrase donc la "
    "boite de 32x24 par du noir, au lieu d'y poser un relief")
chk(all(intro.TYPE[i] not in nuls for i in range(100)),
    "aucune des 100 cases de la grille ne pointe sur la tuile d'effacement")
chk(all(sum(_masque(i)) for i in range(69)),
    "les 69 autres tuiles conservent au moins un pixel de fond")

# ---------------------------------------------------- SUB_1B8A : la permutation
# ``SUB_16E4`` ;172e appelle ``SUB_1B8A`` juste apres avoir lu ``$8340``
# octets : le tampon passe de ``[masque 4o][p0 4o][p1 4o][p2 4o][p3 4o]``
# par ligne a ``[5 mots de poids fort][5 mots de poids faible]``, c'est-a-dire
# paquet 0 (pixels 0..15) puis paquet 1 (pixels 16..31).
_brut = (intro.assets.GAME / "land0").read_bytes()[0x72:0x72 + 0x8340]
_mauvais = 0
_premier = None
for _b in range(0, len(_brut), 20):
    _couches = [_brut[_b + 4 * k: _b + 4 * k + 4] for k in range(5)]
    _voulus = [c[0:2] for c in _couches] + [c[2:4] for c in _couches]
    _got = [tuiles[_b + 2 * q: _b + 2 * q + 2] for q in range(10)]
    if _got != _voulus:
        _mauvais += 1
        if _premier is None:
            _premier = (_b // 20, _voulus, _got)
chk(_mauvais == 0,
    "SUB_1B8A rebat les 1680 blocs de 20 octets : 5 couches de 32 bits -> "
    "paquet de mots hauts puis paquet de mots bas, %d bloc faux" % _mauvais)
if _premier:
    chk(False, "  premier bloc faux (ligne %s) attendu=%s obtenu=%s"
        % _premier)

# ---------------------------------------------------- meme rendu que le jeu
# Ce controle est celui qui aurait vu le bug : sans ``SUB_1B8A`` le masque
# est pris pour un plan, et les formes et les couleurs partent.
try:
    _pal = intro.assets.palette_rgb()
    _indice = {}
    for _i, _rgb in enumerate(_pal):
        _indice.setdefault(_rgb, _i)
    _jeu = intro.assets.load_land(0)[1]
    _ecart = 0
    for _n in range(70):
        _ref = _jeu[_n]
        _base = _n * intro.SPRITE_OCTETS
        for _y in range(24):
            _r = _base + _y * 20
            for _x in range(32):
                _bloc, _bit = divmod(_x, 16)
                _v = 0
                for _p in range(1, 5):
                    _w = int.from_bytes(
                        tuiles[_r + _bloc * 10 + _p * 2:
                               _r + _bloc * 10 + _p * 2 + 2], "big")
                    if _w & (0x8000 >> _bit):
                        _v |= 1 << (_p - 1)
                if _v != _indice.get(_ref.get_at((_x, _y))[:3], -1):
                    _ecart += 1
    chk(_ecart == 0,
        "les 70 sprites de l'intro sont pixels a pixels ceux de load_land : "
        "%d ecart(s) sur %d" % (_ecart, 70 * 24 * 32))
except Exception as _exc:                              # pragma: no cover
    chk(False, "comparaison a load_land impossible : %r" % (_exc,))

for (x, y, no) in [(0, 0, 46), (7, 3, 12), (31, 17, 2), (300, 150, 3),
                   (10, 195, 46), (16, 0, 5)]:
    fond = intro.Ecran()
    for i in range(intro.TAILLE_BITMAP):
        fond.donnees[i] = 0x5A                     # un motif quelconque
    avant = _indices(fond)
    dec = x & 0x0F
    colonne = (x >> 4) * 2
    hauteur = 0x17 if y < 0xB0 else 0xC7 - y
    ref = _ref_depose(tuiles, no, x, y, colonne, dec, hauteur) \
        if hauteur > 0 else {}
    fond.sprite(x, y, no, tuiles)
    got = _indices(fond)
    mauvais = []
    for (px, py), (m, d) in ref.items():
        attendu = _attendu(m, d, avant[py][px])
        if got[py][px] != attendu:
            mauvais.append((px, py, got[py][px], attendu))
    fuite = [(px, py) for py in range(200) for px in range(320)
             if got[py][px] != avant[py][px] and (px, py) not in ref]
    chk(not mauvais and not fuite,
        "sprite(x=%d,y=%d,%d) [dec=%d, colonne=%d, hauteur=%d] : %d pixels "
        "traites, %d errones, %d pixels de fond modifies"
        % (x, y, no, dec, colonne, hauteur, len(ref), len(mauvais),
           len(fuite)))

# les trois coupures de hauteur
hors_haut = intro.Ecran()
hors_haut.sprite(10, -1, 46, tuiles)
chk(all(v == 0 for v in hors_haut.donnees),
    "y < 0 : SUB_19EE ne pose rien ( ;19ee)")
hors_bas = intro.Ecran()
hors_bas.sprite(10, 200, 46, tuiles)
chk(all(v == 0 for v in hors_bas.donnees),
    "y >= 200 : D3 = $C7 - y est negatif, rien n'est pose ( ;1a00-1a06)")
coupe = intro.Ecran()
coupe.sprite(10, 190, 46, tuiles)
got = _indices(coupe)
ligne = [x for x in range(320) if got[199][x] != 0]
chk(got[199] != [0] * 320, "y = 190 : la ligne 199 est bien dessinee")

# ------------------------------------------------- SUB_456 : les zones
def _ref_zone(x, y):
    """Reecriture directe de la chaine CMP/BLT/BGE de ;04b6-0512."""
    if 0x9C <= x < 0xAA and y >= 0xE7:
        return 3
    if 0xAA <= x < 0xB8 and y >= 0xE7:
        return 2
    if x >= 0xB8 and y >= 0xF1:
        return 1
    return 0


mauvais = []
for x in range(0, 320, 2):
    for y in range(0, 320, 4):
        if intro.zone_titre(x, y) != _ref_zone(x, y):
            mauvais.append((x, y))
chk(not mauvais,
    "zone_titre suit exactement la chaine de ;04b6-0512 sur 40000 "
    "positions : %d divergences" % len(mauvais))
chk(intro.zone_titre(0x9C, 0xE7) == 3, "x=$9C, y=$E7 -> choix 3")
chk(intro.zone_titre(0xA9, 0xE7) == 3, "x=$A9 (borne haute exclue) -> choix 3")
chk(intro.zone_titre(0xAA, 0xE7) == 2, "x=$AA -> choix 2")
chk(intro.zone_titre(0xB7, 0x200) == 2, "x=$B7 -> toujours choix 2")
chk(intro.zone_titre(0xB8, 0xF1) == 1, "x=$B8, y=$F1 -> choix 1")
chk(intro.zone_titre(0xB8, 0xF0) == 0, "y=$F0 < $F1 : hors zone")
chk(intro.zone_titre(0x9B, 0xE7) == 0, "x=$9B < $9C : hors zone")
chk(intro.zone_titre(0x50, 0x50) == 0, "au milieu de l'ecran : 0 (delai)")

# la conversion de la souris reste dans 0..319
mauvais = [p for p in ((x, y) for x in range(-5, 400, 7)
                       for y in range(-5, 400, 7))
           if not (0 <= intro.souris_amiga(*p)[0] <= 319
                   and 0 <= intro.souris_amiga(*p)[1] <= 319)]
chk(not mauvais,
    "souris_amiga ramene toujours les deux axes dans 0..319, comme le "
    "plafond $27F de ;529a suivi du LSR de ;52ac")
chk(intro.souris_amiga(0, 0) == (0, 0), "haut gauche -> (0, 0)")
chk(intro.souris_amiga(319, 199) == (319, 319),
    "bas droite -> (319, 319) : les 200 lignes sont etirees sur 320 unites")

# ------------------------------------------------- SUB_1186 : la chute
print()
print("  -- simulation de SUB_1186 puis du rouleau de credits --")
tuiles = intro.charger_tuiles()
g_alea = intro.Alea(1234)
g_alea.regrainer(0x7F)
grille = intro.Grille(g_alea, tuiles)
grille.echeller()
grille.initialiser(100)
credits = intro.Credits(fonte)
credits.reinitialiser()                   # ``SUB_1D0E`` appele en ;11d4
ecran = intro.Ecran()

chk(credits.compteurs == [0x4B, 0x32],
    "SUB_536 arme les deux compteurs a $4b et $32 ( ;0550 et ;0556)")
chk(intro.PALIER_FADE == 0x19 and intro.COMPTEUR_FIN == 0x32,
    "le palier de fondu est $19 et la borne du compteur $32 ( ;07a0 et ;0818)")

# Corps de LAB_11D8 : avancer, effacer, dessiner, retournement de tampon,
# puis SUB_5792, qui n'est que la lecture du clavier.
visibles = 0
tours = 0
while tours < 2000:
    if grille.avancer(100) == 0:
        break
    ecran.vider()
    grille.dessiner(ecran)
    visibles += 1 if any(ecran.donnees) else 0
    tours += 1
chk(tours < 2000,
    "la grille s'arrete en %d tours, comme l'attend SUB_1186 ;11e2" % tours)
chk(visibles > 0,
    "sur les %d tours de chute, %d rendent deja une grille non vide"
    % (tours, visibles))
chk(credits.curseur == 0,
    "SUB_1186 n'avance pas les credits : SUB_5792 n'est que la lecture du "
    "clavier CIAA_SDR ( ;5792-57fc), et le curseur remis a zero en ;11d4 "
    "vaut toujours %d" % credits.curseur)

# Au repos : les 100 cases doivent tenir dans le losange isometrique
attendus_x = []
attendus_y = []
for rang in range(intro.GRILLE):
    for col in range(intro.GRILLE):
        i = rang * intro.GRILLE + col
        d0 = (col - rang) * 16 + 0x90
        d1 = (col + rang) * 8 + 0x20 - grille.colonnes[i] - grille.hauteur[i]
        attendus_x.append(intro.echelle_pos(d0))
        attendus_y.append(intro.echelle_pos(d1))
chk(all(0 <= v <= 288 for v in attendus_x)
    and all(8 <= v <= 176 for v in attendus_y),
    "au repos les 100 cases rentrent dans le losange x=0..288, y=8..176 "
    "(x %d..%d, y %d..%d)" % (min(attendus_x), max(attendus_x),
                              min(attendus_y), max(attendus_y)))
chk(all(grille.colonnes[i] == 0 for i in range(100)),
    "toutes les colonnes sont retombees a zero")

ecran.vider()
grille.dessiner(ecran)
nb = sum(1 for v in ecran.donnees if v)
chk(nb > 0, "la grille au repos remplit %d octets du bitmap" % nb)
got = _indices(ecran)
vus = {(x, y) for y in range(200) for x in range(320) if got[y][x]}
chk(len(vus) > 400,
    "les 100 tuiles se voient : %d pixels non nuls" % len(vus))
chk(all(0 <= y < 200 for (_, y) in vus), "rien ne sort de la hauteur de l'ecran")
chk(not [(x, y) for y in range(200) for x in range(320)
         if got[y][x] and x >= 320],
    "rien ne sort de la largeur de l'ecran")

# ------------------------------------------------- SUB_536 / SUB_714 : credits
# Le rouleau ne vit pas pendant la chute : il est pilote par SUB_714, apres
# LAB_120E, qui appelle SUB_536 ( ;072c) pour armer les tampons puis boucle
# sur LAB_76A ( ;076a-0824).
ec2 = intro.Ecran()
credits2 = intro.Credits(fonte)
credits2.reinitialiser()
seen = set()
lignes_nouvelles = 0
precedent = list(credits2.compteurs)
for tour in range(2000):
    credits2.pas(ec2)
    seen.add(credits2.curseur)
    for slot in range(2):
        if credits2.compteurs[slot] == intro.COMPTEUR_FIN \
                and precedent[slot] == 0:
            lignes_nouvelles += 1
    precedent = list(credits2.compteurs)
chk(len(seen) == 23,
    "2000 tours de credits font defiler les 23 lignes : %d" % len(seen))
chk(all(0 <= c <= intro.COMPTEUR_FIN for c in credits2.compteurs),
    "les compteurs ne sortent jamais de 0..$32 : %s" % credits2.compteurs)
chk(lignes_nouvelles >= 23,
    "une nouvelle ligne est posee a chaque compteur retombe a $32 : %d "
    "appels de SUB_1D1A ( ;0774-078a)" % lignes_nouvelles)

# la cadence : un compteur reboucle toutes les $32+1 tours, sauf le tout
# premier ($4b - $32 = 25 tours de depart ; ;0550 puis ;0818)
cadence = intro.Credits(fonte)
cadence.reinitialiser()
cad = intro.Ecran()
retours = []
dernier = None
prec = list(cadence.compteurs)
for tour in range(400):
    cadence.pas(cad)
    reboucle = (cadence.compteurs[0] == intro.COMPTEUR_FIN and prec[0] == 0)
    if reboucle:
        if dernier is not None:
            retours.append(tour - dernier)
        dernier = tour
    prec = list(cadence.compteurs)
chk(retours and all(r == intro.COMPTEUR_FIN + 1 for r in retours[:5]),
    "le compteur 0 reboucle toutes les %d tours, une fois passe le depart de "
    "%d tours : %s" % (intro.COMPTEUR_FIN + 1, 0x4B - 0x32, retours[:5]))

# un tampon deja trace (plan 0 en $FF partout) laisse l'ecran intact
ec4 = intro.Ecran()
for i in range(intro.TAILLE_BITMAP):
    ec4.donnees[i] = 0x24
avant4 = bytes(ec4.donnees)
c4 = intro.Credits(fonte)
c4.reinitialiser()
for slot in range(2):
    c4.dessiner_ligne(c4.tampons[slot], "")     # plan 0 en $FF, plans 1-4 nuls
c4.compteurs = [0x10, 0x10]                     # ni rebouclage, ni nouvelle ligne
for _ in range(4):
    c4.pas(ec4)
chk(bytes(ec4.donnees) == avant4,
    "un tampon au fond $FF laisse l'ecran intact : le plan 0 source sert "
    "bien de masque de conservation ( ;07e8 -> ;5062)")

# ------------------------------------------------- l'ecran titre
try:
    img = assets.load_pic("load.pic", planes=intro.PLANS_TITRE)
    chk(img.get_size() == (320, 200),
        "load.pic se decode bien en 320x200 sur %d plans : %s"
        % (intro.PLANS_TITRE, img.get_size()))
    teintes = {img.get_at((x, y))[:3]
               for x in range(0, 320, 7) for y in range(0, 200, 5)}
    chk(len(teintes) <= 32,
        "l'ecran titre tient dans 32 couleurs : %d teintes echantillonnees"
        % len(teintes))
    charge = True
except Exception as exc:                             # pragma: no cover
    charge = False
    chk(False, "load.pic ne se charge pas : %r" % (exc,))

# un rendu complet, pour s'assurer que rien n'explose
surface = ecran.surface()
chk(surface.get_size() == (320, 200),
    "le rendu d'un bitmap d'attirance fait bien 320x200")

# ------------------------------------- ECHELLE_ISO et la palette de la chute
# ``(-31488,A4)`` avec ``A4 = $ED26`` donne $7226, c'est-a-dire ``LAB_7226``,
# le mot que multiplie ``MULU LAB_7226,D0`` en ;1c5c. ``SUB_1186`` ;11ce y
# ecrit $0080 : l'echelle n'est pas un choix du portage.
_m = [s for s in LIGNES if ';11ce:' in s]
chk(bool(_m) and '#$0080' in _m[0] and '(-31488,A4)' in _m[0],
    "SUB_1186 ;11ce ecrit $0080 en (-31488,A4)")
chk((0xED26 - 31488) & 0xFFFF == 0x7226,
    "(-31488) avec A4 = $ED26 vaut bien $7226 = LAB_7226, lu par ;1c5c")
chk(intro.ECHELLE_ISO == 0x80,
    "ECHELLE_ISO = $80, donc echelle 1 dans le LSR.W #7 : valeur lue, "
    "pas inventee")

# La palette de la chute est dans le fichier, en ;6ef0 : c'est elle que
# ``SUB_1186`` ;11b0-11bc recopie dans le cuivre par ``SUB_55F8(..., $10)``
# (16 couleurs).
def _pal_listing():
    """Les mots de ``;6ef0`` : la palette recopiee dans le cuivre en ;11b0."""
    debut = None
    for i, s in enumerate(LIGNES):
        if s.rstrip().endswith(";6ef0") and "DC.L" in s:
            debut = i
            break
    if debut is None:
        return None
    mots = []
    for s in LIGNES[debut:debut + 8]:
        if "DC.L" not in s:
            break
        hexes = s.split("DC.L", 1)[1].split(";")[0]
        for v in hexes.replace("$", " ").replace(",", " ").split():
            n = int(v, 16)
            mots.extend([(n >> 16) & 0xFFFF, n & 0xFFFF])
        if ";6f10" in s:
            break
    return mots

_p = _pal_listing()
chk(_p is not None and len(_p) >= 16,
    "la palette de la chute existe bien en ;6ef0 du listing")
if _p:
    _jeu = intro.assets.palette_rgb()
    _voulu = [(((v >> 8) & 0xF) * 17, ((v >> 4) & 0xF) * 17, (v & 0xF) * 17)
              for v in _p[:16]]
    chk(_voulu == list(_jeu[:16]),
        "les 16 couleurs de ;6ef0 sont celles que charge assets.palette_rgb() "
        "-- le port n'invente pas de palette")
    chk(len(intro.assets.PALETTE) == 16,
        "PALETTE pese 16 mots : une plane a 4 bits, comme le tampon de "
        "l'intro")

# ------------------------- le rouleau de credits ne doit jamais etre sans fin
# ``LAB_11D8`` n'a aucune sortie propre : le rouleau boucle sur ``0xFF`` et
# c'est ``SUB_714`` (Phase 85) qui, dans l'original, appelle ``SUB_16E``.
# Sans le script ni une borne, ``demarrer`` se fige -- vu a l'execution.
import inspect as _inspect
_sig = _inspect.signature(intro.demarrer)
chk("duree_credits" in _sig.parameters,
    "demarrer sait borner le rouleau : parametre duree_credits")
chk(_sig.parameters["duree_credits"].default > 0,
    "duree_credits est borne par defaut (%s s), l'intro finit seule"
    % (_sig.parameters["duree_credits"].default,))

import os as _os, time as _time
import importlib as _importlib
_ancien = _os.environ.get("SDL_VIDEODRIVER")
_os.environ["SDL_VIDEODRIVER"] = "dummy"
try:
    pygame.display.quit()
    pygame.display.init()
    _scr = pygame.display.set_mode((960, 768))
    _cadre = pygame.Surface((320, 256)).convert()
    _cadre.fill((0, 0, 0))
    _clk = pygame.time.Clock()
    pygame.event.clear()
    _t0 = _time.time()
    _r = intro.demarrer(_cadre, _clk, fenetre=_scr, im_par_seconde=5000.0,
                        attente_titre=0.02, duree_credits=0.02)
    _dt = _time.time() - _t0
    chk(_r == 0,
        "le pilote traverse titre -> chute -> credits et rend 0 : %s "
        "(%.2f s)" % (_r, _dt))
    chk(_dt < 60.0,
        "il y arrive sans se figer (%.2f s)" % _dt)
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    _r2 = intro.demarrer(_cadre, _clk, fenetre=_scr, im_par_seconde=5000.0,
                         attente_titre=0.02, duree_credits=-1)
    chk(_r2 == -1, "fermeture de fenetre pendant les credits : -1 ( %s )" % (_r2,))
    pygame.display.quit()
finally:
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    if _ancien is None:
        _os.environ.pop("SDL_VIDEODRIVER", None)
    else:
        _os.environ["SDL_VIDEODRIVER"] = _ancien

# ------------------------------------------------- SUB_456 : la boucle d'attente
m = [s for s in LIGNES if ';04a8:' in s]
chk(bool(m) and '#$00055730' in m[0] and intro.DELAI_TITRE == 0x55730,
    "SUB_456 sort sur CMP.L #$00055730,D0 ; BGT ( ;04a8) : DELAI_TITRE = "
    "$%X" % intro.DELAI_TITRE)
m = [s for s in LIGNES if ';046c:' in s]
chk(bool(m) and '#$0005' in m[0] and intro.PLANS_TITRE == 5,
    "SUB_456 pousse $0005 a SUB_549A : l'ecran titre se joue sur cinq plans "
    "( ;046c)")
m = [s for s in LIGNES if ';0492:' in s]
chk(bool(m) and '#$0002' in m[0],
    "(-32004) est arme a 2 avant la boucle : le test des zones n'a lieu "
    "qu'a 0, donc le bouton enfonce ( ;0492 puis ;04b0)")
bornes = [(0x04b6, 0x9c), (0x04be, 0xaa), (0x04c6, 0x0e7),
          (0x04d8, 0xaa), (0x04e0, 0x0b8), (0x04e8, 0x0e7),
          (0x04fa, 0x0b8), (0x0502, 0x0f1)]
ok_bornes = []
for adresse, valeur in bornes:
    s = [x for x in LIGNES if ';%04x:' % adresse in x]
    ok_bornes.append(bool(s) and ('#$%04x' % valeur) in s[0])
chk(all(ok_bornes),
    "les huit bornes comparees en ;04b6-0502 sont bien celles de ZONES")
chk(intro.ZONES == [(0x9C, 0xAA, 0xE7), (0xAA, 0xB8, 0xE7), (0xB8, 0x200, 0xF1)],
    "ZONES recopie les trois couples de bornes du listing")
chk(callable(intro.demarrer) and callable(intro.charger_titre)
    and callable(intro.renoncer),
    "le pilote de la phase 84 existe : demarrer / charger_titre / renoncer")

# le lanceur ne bouge pas tant que SHOW_INTRO est ferme
from populous import config as _config
chk(getattr(_config, "SHOW_INTRO", None) is False,
    "config.SHOW_INTRO est ferme par defaut : la phase 84 ne modifie pas le "
    "comportement du lanceur")

print()
if ECHECS:
    print("%d/%d controle(s) en echec :" % (len(ECHECS), TOTAL[0]))
    for m in ECHECS:
        print("  -", m)
    sys.exit(1)
print("check_intro : %d/%d OK" % (TOTAL[0], TOTAL[0]))
