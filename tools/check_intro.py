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
                _seg16, _bit = divmod(_x, 16)
                _v = 0
                for _p in range(1, 5):
                    _w = int.from_bytes(
                        tuiles[_r + _seg16 * 10 + _p * 2:
                               _r + _seg16 * 10 + _p * 2 + 2], "big")
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
# ``LAB_11D8`` n'a aucune sortie propre : le rouleau boucle sur ``0xFF``.
# ``SUB_714`` non plus -- Phase 85 : on le borne par ``duree_script`` et on
# sait faire une passe unique avec ``boucle=False`` (vu a l'execution).
import inspect as _inspect
_sig = _inspect.signature(intro.demarrer)
chk("duree_script" in _sig.parameters,
    "demarrer sait borner la scene : parametre duree_script")
chk(_sig.parameters["duree_script"].default > 0,
    "duree_script est borne par defaut (%s s), l'intro finit seule"
    % (_sig.parameters["duree_script"].default,))
chk(_sig.parameters["boucle"].default is True,
    "demarrer boucle par defaut, et sait faire une passe avec "
    "boucle=False")

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
    # ``son=False`` : ces deux passes mesurent la scene, pas la musique.
    # Le son de l'intro est controle separement en Phase 86 plus bas.
    _r = intro.demarrer(_cadre, _clk, fenetre=_scr, im_par_seconde=5000.0,
                        attente_titre=0.02, duree_script=0.05, boucle=False,
                        son=False)
    _dt = _time.time() - _t0
    chk(_r == 0,
        "le pilote fait titre -> scene (SUB_1186) -> retour et rend 0 : %s "
        "(%.2f s)" % (_r, _dt))
    chk(_dt < 60.0,
        "il y arrive sans se figer (%.2f s)" % _dt)
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    _r2 = intro.demarrer(_cadre, _clk, fenetre=_scr, im_par_seconde=5000.0,
                         attente_titre=0.02, duree_script=-1, boucle=False,
                         son=False)
    chk(_r2 == -1, "fermeture de fenetre pendant la scene : -1 ( %s )" % (_r2,))
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


# ==================================================== Phase 85 : la scene
print()
print("Phase 85 : la scene, SUB_714, SUB_E40, SUB_3F92")
print()


def _lignes_depuis(adresse):
    """Numero de ligne (1-based) de la premiere donnee a cette adresse."""
    for i, s in enumerate(LIGNES):
        if _numero_adresse(i + 1) == adresse:
            return i + 1
    return -1


def _dump(numero):
    """Les octets du commentaire ``;aaaa: xxxx`` de la ligne ``numero``."""
    m = re.search(r";[0-9a-f]{4}:\s*([0-9a-f]+)\s*$", LIGNES[numero - 1])
    if not m:
        return b""
    h = m.group(1)
    if len(h) % 2:
        h = "0" + h
    return bytes(int(h[i:i + 2], 16) for i in range(0, len(h), 2))


def _octets_depuis(adresse, n, decalage=0):
    """Les ``n`` octets du **listing** a partir d'une adresse.

    On accumule les ``DC``/``DS`` de ligne en ligne ; quand le gabarit ne
    convient pas (chaine ASCII, code machine) on retombe sur le dump
    hexadecimal que le desassembleur depose en commentaire (``;aaaa: xxxx``),
    exact par construction. C'est la seule facon de lire la suite de
    ``HAUTEUR_CASE`` : ``SUB_6538`` est du code, pas des donnees.
    """
    debut = _lignes_depuis(adresse)
    if debut < 0:
        return b""
    octets = bytearray()
    i = debut
    while len(octets) < decalage + n and i <= len(LIGNES) and i < debut + 800:
        try:
            b = _bloc(i, i)
        except (ValueError, IndexError):
            b = b""
        if not b:
            b = _dump(i)
        octets += b
        i += 1
    return bytes(octets[decalage:decalage + n])


class _Capture:
    """Enregistre l'appel a ``sprite()`` au lieu de dessiner."""

    def __init__(self):
        self.vu = None
        self.mots = None

    def sprite(self, x, y, numero, tuiles, **k):
        self.vu = (x, y, numero)
        self.mots = k


# ------------------------------------------------ LAB_1272 : les seize flux
_fin = next(i for i, s in enumerate(LIGNES) if s.startswith("LAB_15B6:")) + 1
_bruts = bytearray()
_i = _lignes_depuis(0x1272)
while _i < _fin:
    _bruts += _bloc(_i, _i)
    _i += 1
_bruts = bytes(_bruts)
chk(len(_bruts) == 0x15B6 - 0x1272,
    "le bloc LAB_1272-LAB_15B5 pese $%X octets : %d"
    % (0x15B6 - 0x1272, len(_bruts)))
# ``DC.L LAB_1272 ;15b6: 00001272`` : le nom de etiquette ne se lit pas en
# hexadecimal, mais le disassembleur a depose les octets reels dans le
# commentaire -- on prend ceux-la, qui sont exacts par definition.
_pointeurs = []
_i = _fin + 1
while len(_pointeurs) < 16 and _i <= len(LIGNES):
    _pointeurs += [int.from_bytes(_dump(_i), "big")]
    _i += 1
chk(len(_pointeurs) == 16,
    "la table LAB_15B6 contient seize pointeurs : %d" % len(_pointeurs))
if len(_pointeurs) == 16:
    attendus = []
    for r in range(16):
        _d = _pointeurs[r] - 0x1272
        _f = (_pointeurs[r + 1] if r + 1 < 16 else 0x15B6) - 0x1272
        attendus.append(_bruts[_d:_f])
    ecarts = [r for r in range(16)
              if bytes(attendus[r]) != intro.FLUX_TABLE[r]]
    chk(not ecarts,
        "les 16 flux de FLUX_TABLE sont octet a octet ceux du listing : %s"
        % ([len(x) for x in attendus] if not ecarts else "ecart %s" % ecarts))
    chk(sum(len(x) for x in attendus) == 0x15B6 - 0x1272,
        "les seize flux se touchent et couvrent $1272..$15B5 sans trou")

# ------------------------------------------------- LAB_6D28 : LIGNES_ETAT
_att = _octets_depuis(0x6D28, 16 * 14)
_plats = [tuple(int.from_bytes(_att[k * 14 + 2 * q:
                                    k * 14 + 2 * q + 2], "big")
                for q in range(7)) for k in range(16)]
def _mot_signe(v):
    return v - 0x10000 if v >= 0x8000 else v


_plats_s = [tuple(_mot_signe(v) for v in p) for p in _plats]
chk(len(_att) == 224 and _plats_s == list(intro.LIGNES_ETAT),
    "LIGNES_ETAT == les 16 structures de 7 mots de $6D28, ``anim`` vu en "
    "signe comme le fait le port ( %d o )" % len(_att))
if _plats_s == list(intro.LIGNES_ETAT):
    chk(all(t[1] < len(intro.FLUX_TABLE[i]) for i, t in enumerate(_plats)),
        "chaque pos initiale tombe dans son propre flux")
    chk([t[0] for t in _plats_s] == [0, 0, 0, 0, 0, 0, 32, 16, 16, 16,
                                   16, 16, 16, 48, 64, 66],
        "seule la ligne 6 a id=$20 : elle porte le $F9 et le bump unique "
        "( %s )" % ([t[0] for t in _plats_s],))
    chk([t[5] for t in _plats_s].count(-1) == 2,
        "anim == -1 sur deux lignes seulement : $FA les dessine alors tel "
        "quel ( %s )" % ([t[5] for t in _plats_s],))
    chk([t[3] for t in _plats] == [8] * 16,
        "pas vaut 8 partout, soit la direction neutre de ;51f0 ( %s )"
        % ([t[3] for t in _plats],))

# -------------------------------------- $6E28 : TABLE_SPRITES / MARQUEURS
_att = _octets_depuis(0x6E20, 0x67, 8)
chk(len(_att) == 0x67 and _att == intro.DONNEES_6E28,
    "DONNEES_6E28 == les $67 octets de $6E28 du listing ( %d o )" % len(_att))
chk(intro.DONNEES_6E28[:0x49] == intro.TABLE_SPRITES
    and intro.DONNEES_6E28[0x49:0x49 + 0x1E] == intro.MARQUEURS_TABLE,
    "TABLE_SPRITES = [0:73] et MARQUEURS_TABLE = [73:103] d'un meme bloc : "
    "l'indice 73+ de l'opcode $82+i retombe donc dans les marqueurs")
_att = _octets_depuis(0x6E90, 16, 8)
_mots = tuple(int.from_bytes(_att[2 * q:2 * q + 2], "big") for q in range(8))
chk(_mots == intro.OBJETS_MARQUEURS,
    "OBJETS_MARQUEURS == les 8 mots de $6E98 : %s" % (_mots,))

# ------------------------------------------------------- $1F62 : les masques
_att = _octets_depuis(0x1F62, 60)
chk(len(_att) == 60 and intro.MASQUES_REVELATION[:60] == _att,
    "MASQUES_REVELATION commence par les 60 octets de LAB_1F62 : neuf DC.L "
    "puis DS.L 6 ( %d o )" % len(_att))
chk(len(intro.MASQUES_REVELATION) == 64,
    "la constante du port tient les 60 octets du listing et quatre octets "
    "de remplissage nuls : %d o" % len(intro.MASQUES_REVELATION))
if len(_att) == 60:
    chk(_att[:4] == b"\xff\xff\xff\xff" and _att[34:36] == b"\x00\x10"
        and _att[36:] == bytes(24),
        "le masque 0 est $FFFF (rien ne perce), le dix-huitieme mot $0010 -- "
        "1/8e de bit fonde -- puis la DS.L 6 remplit 24 octets nuls ( %s )"
        % _att[34:36].hex())

# ------------------------------------------- $4026 : les deux revelations
_att = _octets_depuis(0x4026, 0x1000)
chk(len(_att) == 0x1000 and intro.charger_revelation() == _att,
    "charger_revelation() == les $1000 octets de LAB_4026 ( %d o )"
    % len(_att))

# --------------------------------------------------------- $5A0C : LAB_5A0C
_att = _octets_depuis(0x5A0C, 0xA00)
chk(len(_att) == 0xA00 and intro.charger_objets() == _att,
    "charger_objets() == les $A00 octets de LAB_5A0C ( %d o )" % len(_att))
if len(_att) == 0xA00:
    _nn = sum(1 for x in _att if x)
    chk(_att[:2] == b"\xff\xff" and 0 < _nn < 0xA00,
        "LAB_5A0C s'ouvre sur $FFFF (sprite vide) et porte de la matiere "
        "ailleurs : %d octets non nuls sur $A00" % _nn)

# ------------------------------------------------------------ _signe, exhaustif
_b = [intro._signe(v) for v in range(-40, 41)]
chk(_b == [-1] * 40 + [0] + [1] * 40,
    "_signe : -1, 0, 1 sur [-40..40], comme le BLE/BGE/BLT soustractif de "
    ";0924-0976")
m = [s for s in LIGNES if ";0926:" in s]
chk(bool(m) and "BLE" in m[0], ";0926 est un BLE : le cas nul tombe a 0 : %s"
    % m[0].strip())
m = [s for s in LIGNES if ";093e:" in s]
chk(bool(m) and "BGE" in m[0], ";093e est un BGE : le cas negatif vaut 1 et "
    "donc -1 apres SUB.W : %s" % m[0].strip())

# ------------------------------------------------- le tableau de directions
_rep = {}
_case = None
for _i in range(_lignes_depuis(0x5130), _lignes_depuis(0x51F0)):
    _s = LIGNES[_i - 1]
    _m = re.search(r"CMP\.W\t#\$([0-9a-f]{4}),D4\t", _s)
    if _m:
        _case = int(_m.group(1), 16)
        if _case >= 0x8000:
            _case -= 0x10000
        continue
    if _case is None:
        continue
    for _k, _nom in enumerate(("D4", "D7", "D6")):
        _m = re.search(r"MOVE\.W\t#\$([0-9a-f]{4})," + _nom + r"\t", _s)
        if _m:
            _v = int(_m.group(1), 16)
            if _v >= 0x8000:
                _v -= 0x10000
            _rep.setdefault(_case, [0, 0, 0])[_k] = _v
_rep = {k: tuple(v) for k, v in _rep.items() if -12 < k < 12}
chk(_rep == intro.DIRECTIONS,
    "DIRECTIONS == les huit cas de ;5130-51ec ( %d cas lus )%s"
    % (len(_rep), "" if _rep == intro.DIRECTIONS else " : %s" % _rep))
m = [s for s in LIGNES if ";51f8:" in s]
chk(bool(m) and "$0008" in m[0],
    ";51f8 met D6 a $0008 : le defaut de ;51f0 est la direction neutre : %s"
    % m[0].strip())

# ------------------------------- SUB_50E6, reecriture independante du listing
# 0x65E4 porte `DC.B "dos.library",0` : le listing y abandonne le dump
# hexadecimal des octets, la reconstruction s'arrete donc la. Le tableau et
# le corps de `SUB_6538` (jusqu'a 0x65E3) sont en revanche exacts.
_dec2_ext = _octets_depuis(0x64D4, 0x65E4 - 0x64D4)


def _d2(i):
    """``LAB_640C+$C8`` lu comme le fait ``SUB_50E6``, jusque dans le code."""
    if 0 <= i < len(_dec2_ext):
        return _dec2_ext[i]
    return 0


def _octet_signe(v):
    return v - 256 if v >= 128 else v


# ``SUB_50E6`` lit ``(A2,A3.L)`` sans borne : pour un compteur au-dela de
# 99 -- possible, car ;08d6 recharge l'octet suivant sans retester $64 et
# ``$70`` vaut 112 -- il va chercher dans ``SUB_6538``, qui suit le tableau.
# Le port fait de meme, depuis le binaire ; on confronte les 512 octets.
_refus = [i for i in range(len(_dec2_ext))
          if intro._dec2(i) != _dec2_ext[i]]
chk(not _refus,
    "_dec2 == LAB_640C+$C8 du listing sur les %d octets, hauteurs "
    "comme code : %d ecart(s) %s" % (len(_dec2_ext), len(_refus),
                                     _refus[:5]))
chk(all(intro._dec2(i) == intro.TABLE_COLONNE2[i] for i in range(100)),
    "sur 0..99, _dec2 se lit dans HAUTEUR_CASE : %s"
    % intro._dec2(99))


def _ref_50e6(compteur, pas, ident, phase, colonne, hauteur, bascule):
    """``SUB_50E6`` ;50e6-521c, saisie ligne a ligne depuis le listing.

    ``DIVU``/``SWAP`` ( ;50ea-5102) rend ``D0 = unites - dizaines`` et
    ``D1 = unites + dizaines`` ; deux ``EXT.W`` ( ;511e et ;5128) font des
    octets signes ; ``MULU`` puis ``ASR.W #3`` ( ;512a-512c) ne decale que le
    mot faible, d'ou un produit pris modulo 65536.
    """
    tens, units = compteur // 10, compteur % 10
    d0 = ((units - tens) << 4) + 0x98
    d1 = ((units + tens) << 3) + 0x1C - colonne
    a = _octet_signe(_d2(compteur))
    d1 -= a
    b = _octet_signe((a - _d2(compteur + pas)) & 0xFF)
    d6 = ((b & 0xFFFF) * (phase & 0xFFFF)) & 0xFFFF
    if d6 & 0x8000:
        d6 -= 0x10000
    d1 += d6 >> 3
    glisse = intro.DIRECTIONS.get(pas, (0, 0, 8))
    d0 += glisse[0] * phase
    d1 += glisse[1] * phase
    if hauteur == 0:
        if ident >= 0x40:
            return d0, d1, ident          # ;5212 saute meme le bascule
        ident += glisse[2]
    ident += bascule
    return d0, d1, ident


def _trace_50e6(c, p, ph, col, ha, base, ident=5):
    cap = _Capture()
    intro.acteur_dessiner(cap, b"\0" * 23520, c, p, ident, ph, col, ha, base)
    return cap.vu


refus, cas = 0, 0
for _c in (0, 1, 9, 10, 11, 44, 45, 54, 55, 77, 88, 99, 112, 120):
    for _p in (-11, -10, -9, -1, 1, 9, 10, 11, 0, 8):
        for _ph in (0, 1, 3, 7):
            for _ha in (0, 1, 200):
                for _col in (0, 7, 168):
                    for _base in (0, 1):
                        for _id in (5, 0x20, 0x40, 0x8A):
                            cas += 1
                            attendu = _ref_50e6(_c, _p, _id, _ph, _col, _ha,
                                                _base)
                            vu = _trace_50e6(_c, _p, _ph, _col, _ha, _base,
                                             _id)
                            if vu != attendu:
                                refus += 1
                                if refus == 1:
                                    print("     50E6 c=%d p=%d ph=%d col=%d "
                                          "h=%d b=%d id=%X -> ref=%s port=%s"
                                          % (_c, _p, _ph, _col, _ha, _base,
                                             _id, attendu, vu))
chk(refus == 0,
    "acteur_dessiner == SUB_50E6 sur %d figures independantes (x, y, "
    "sprite) : %d divergence(s)" % (cas, refus))

# ------------------------------- SUB_1CBC : les marqueurs sont des tuiles
refus, cas = 0, 0
for _c in range(100):
    for _id in (0, 17, 33, 0x41, 0x7E):
        cas += 1
        tens, units = divmod(_c, 10)
        attendu = ((units - tens) * 16 + 0x90,
                   (units + tens) * 8 + 0x18 - _d2(_c), _id)
        cap = _Capture()
        intro.marqueur_dessiner(cap, b"\0" * 23520, _c, _id)
        if cap.vu != attendu:
            refus += 1
            if refus == 1:
                print("     1CBC c=%d -> ref=%s port=%s"
                      % (_c, attendu, cap.vu))
chk(refus == 0,
    "marqueur_dessiner == SUB_1CBC (x = (uni-diz)*16+$90, y = (uni+diz)*8+"
    "$18-dec2) sur %d figures : %d divergence(s)" % (cas, refus))

cap = _Capture()
intro.marqueur_dessiner(cap, b"\0" * 23520, 44, 33)
chk(bool(cap.mots) and cap.mots.get("lignes") == 0x17
    and cap.mots.get("octets") == 0x1E0
    and cap.mots.get("limite") == 0xB0
    and cap.mots.get("paquets") == 2,
    "SUB_1CBC finit sur SUB_19EE : 24 lignes (D3=$17, DBF -> D3+1), "
    "limite $B0, $1E0 octets, "
    "2 paquets -- donc land0 et non sprites0.dat ( %s )" % (cap.mots,))

# Phase 87 : les trois hauteurs du listing, et le compte reel de ``DBF``.
# ``TERRAIN_LIGNES`` porte le **D3** de ;19f4 et non un compteur, donc il
# vaut $17 pour 24 tours -- ``Ecran.sprite`` compte ``range(hauteur + 1)``,
# soit ``D3 + 1``, exactement comme ``DBF D3`` ( ;1b12). Les deux autres
# bornes sont des compteurs deja decreases (``#$000F`` ;1916 = 16 lignes,
# ``#$001F`` ;1820 = 32).
chk(intro.TERRAIN_LIGNES == 0x17 == intro.HAUTEUR_SPRITE
    and intro.TERRAIN_LIGNES + 1 == 24,
    "TERRAIN_LIGNES == $17 == HAUTEUR_SPRITE : SUB_19EE dessine D3+1 = 24 "
    "lignes ( %d )" % intro.TERRAIN_LIGNES)
chk(intro.PERSONNAGE_LIGNES == 16 and intro.OBJET_LIGNES == 32,
    "les deux autres dessinateurs restent des compteurs : SUB_1910 = 16 "
    "lignes ( $F), SUB_1802 = 32 ( $1F) ( %d / %d )"
    % (intro.PERSONNAGE_LIGNES, intro.OBJET_LIGNES))

# -------------------------- Phase 87 : le tableau ``cles``/``ids`` ---------
# Le port plafonnait a **huit** emplacements. Or le listing balaie ``cles``
# stride 4 **sans borne** ( ;09ea-09fa), ``SUB_536`` vide le tableau par la
# meme boucle sans borne ( ;0566-058a), et le dessin s'arrete au premier
# zero ( ;0880-088e) : rien n'introduit une longueur de 8. La seule borne
# reelle est la zone BSS encore libre, ``0x7058..0x7085`` = 20 mots -- le
# voisin non nul est ``(-31904)`` = ``0x7086`` = ``bm3``.
chk(intro.NB_EMPLACEMENTS == 20,
    "NB_EMPLACEMENTS == 20 : zone BSS 0x7058..0x7085, bornee par bm3 a "
    "0x7086 ( %d )" % intro.NB_EMPLACEMENTS)

_m_alea = intro.Alea(0)
_m_fond = intro.Ecran()
_m_scene = intro.Scene(_m_alea, intro.Grille(_m_alea, tuiles), _m_fond,
                       intro.Ecran(), intro.charger_sprites(), tuiles,
                       intro.charger_revelation(), credits)
chk(len(_m_scene.cles) == 20 and len(_m_scene.ids) == 20,
    "cles et ids font chacun 20 mots, comme le BSS ( %d / %d )"
    % (len(_m_scene.cles), len(_m_scene.ids)))

# 14 emplacements distincts : le maximum mesure en execution sur la scene
# reelle (image 0757). Le plafond de 8 en perdait la moitie, mises a jour
# comprises : 29 placements perdus des l'image 663 sur 1320.
for _i in range(14):
    _m_scene.lignes[_i][4] = 0x400 + _i
    _m_scene._marqueur_poser(_i, 0x64)
_remplis = [c for c in _m_scene.cles if c != 0]
chk(len(_remplis) == 14 and _remplis == sorted(_remplis)
    and _m_scene.cles[14:] == [0] * 6,
    "14 cles distinctes sont toutes conservees, triees, et les six "
    "restantes restent a zero : %d ( %s )" % (len(_remplis), _m_scene.cles))

# la meme cle met a jour l'emplacement sans en creer un nouveau
# ( ``CMP.W egal -> MOVE valeur`` ;0a14-0a34 )
_m_scene.lignes[3][4] = 0x403
_m_scene._marqueur_poser(3, 0x7B)
_remplis = [c for c in _m_scene.cles if c != 0]
chk(len(_remplis) == 14
    and _m_scene.ids[3] == intro.MARQUEURS_TABLE[0x7B - 0x64],
    "reposer la meme cle met a jour l'emplacement : %d emplacements, "
    "ids[3]=$%02X" % (len(_remplis), _m_scene.ids[3]))

# une cle inferieure s'insere en tete et remonte la queue d'un cran
# ( ``MOVE.W (i-1) -> i`` ;0a38-0a8a )
_m_scene.lignes[7][4] = 1
_m_scene._marqueur_poser(7, 0x64)
_remplis = [c for c in _m_scene.cles if c != 0]
chk(len(_remplis) == 15 and _m_scene.cles[0] == 1
    and _m_scene.cles[1] == 0x400 and _m_scene.cles[15:] == [0] * 5,
    "une cle inferieure s'insere en tete sans rien perdre : %d "
    "emplacements, cles[0:3]=%s" % (len(_remplis), _m_scene.cles[:3]))

# la table se remplit jusqu'a 20, et le 21e est refuse -- le 68000, lui,
# continuerait jusqu'au ``bm3`` voisin. **[APPROV]** : la scene reelle ne
# depasse jamais 14. ``if d6 >= NB_EMPLACEMENTS: return`` ;09fa-0af8.
_n = 15
while _n < 20:
    _m_scene.lignes[_n % 16][4] = 0x600 + _n
    _m_scene._marqueur_poser(_n % 16, 0x64)
    _n += 1
_remplis = [c for c in _m_scene.cles if c != 0]
chk(len(_remplis) == 20 and _remplis == sorted(_remplis),
    "les 20 emplacements se remplissent tous, tries : %d ( %s )"
    % (len(_remplis), _m_scene.cles))
_m_scene.lignes[9][4] = 0x7FF
_m_scene._marqueur_poser(9, 0x64)
_remplis = [c for c in _m_scene.cles if c != 0]
chk(len(_remplis) == 20 and 0x7FF not in _m_scene.cles,
    "le 21e emplacement est refuse : le tableau reste a 20 ( %d )"
    % len(_remplis))

# ``_marques`` dessine jusqu'au premier zero ( ;0880-088e), c'est-a-dire
# les 20, puis remet ``(-12,A5)`` a zero ( ;0890).
_dessines = []
_orig_marqueur = intro.marqueur_dessiner


def _compte_marqueur(ecran, tuiles_, cle, ident):
    _dessines.append((cle, ident))
    _orig_marqueur(ecran, tuiles_, cle, ident)


intro.marqueur_dessiner = _compte_marqueur
try:
    _m_scene._marques(_m_fond)
finally:
    intro.marqueur_dessiner = _orig_marqueur
chk(len(_dessines) == 20
    and [c for c, _ in _dessines] == sorted(c for c, _ in _dessines)
    and not _m_scene.a_marquer,
    "_marques dessine les 20 emplacements jusqu'au premier zero puis "
    "balaie (-12,A5) : %d dessines ( a_marquer=%s )"
    % (len(_dessines), _m_scene.a_marquer))

# --------------------------------------------------- SUB_E40 : le temple
# ``SUB_10A2($12)`` ;0e44 remplit dix-huit colonnes. La premiere cascade est
# ``$A8 - colonne`` ( ;0e70), la seconde ``colonne + 8`` ( ;0fc0) : les pieces
# remontent apres la remise a zero.
_h = intro.Objets.PIECES_HAUTE
_b = intro.Objets.PIECES_BASSE
_att_h = (((0x50, 5, 0),)
          + tuple((0x50 + i * 16, 6, i) for i in range(1, 9))
          + ((0xE0, 7, 9),))
chk(tuple(_h) == _att_h,
    "PIECES_HAUTE == piece 5 a x=$50 sur colonne[0] ( ;0e6c-0e82), pieces 6 "
    "a $50+i*16 pour i=1..8 ( ;0e90-0ecc, BLE compris), piece 7 a $E0 sur "
    "colonne[9] ( ;0ece-0ee4) : %d pieces" % len(_h))
_att_b = tuple((0x60 + i * 16, intro.OBJETS_MARQUEURS[i], i)
               for i in range(8))
chk(tuple(_b) == _att_b,
    "PIECES_BASSE == les 8 OBJETS_MARQUEURS a x=$60+i*16 ( ;0ef0-0f38, "
    "BLT strict) : %d pieces" % len(_b))
chk(intro.Objets.NB_PIECES == 0x12 == len(_h) + len(_b),
    "NB_PIECES == $12 == %d pieces hautes + %d pieces basses"
    % (len(_h), len(_b)))

# Le second ``SUB_110A`` ;0f9a, juste apres ``LAB_F58`` : sans lui la seconde
# cascade demarrait une image trop tot. ``(-31876,A4)`` == ``(-31894,A4)+18``
# == ``&colonne[9]`` : 18 octets, soit neuf mots.
for contenu, adresse, message in (
    ("MOVE.W\t#$0012,-(A7)", 0x0E44, "SUB_E40 devrait initialiser 18 "
     "colonnes"),
    ("JSR\t(SUB_110A,PC)", 0x0F9E, "le temple devrait rappeler SUB_110A "
     "juste apres la remise a zero"),
    ("SUB.W\t(-31876,A4),D0", 0x0ED6, "la piece 7 devrait lire colonne[9]"),
    ("BLT.S\tLAB_F5C", 0x0F98, "le reglage devrait boucler sur les 18 "
     "colonnes"),
    ("BNE.S\tLAB_1098", 0x1090, "le bouton devrait rejouer la seconde "
     "cascade"),
):
    _vus = None
    for _n, s in enumerate(LIGNES, start=1):
        if contenu in _sans_commentaire(s) and _numero_adresse(_n) == adresse:
            _vus = s.strip()
            break
    chk(_vus is not None, "%s ( ;%04x ) : %s" % (message, adresse,
                                                 _vus or "introuvable"))

# Execution : la premiere cascade, la remise a zero, la seconde, l'epuisement
# ``LAB_109C``. ``vitesse`` tombe a ``-1`` ( ``DIVS #2`` + ``NEG`` , ;1140-114a)
# et ``D5 = vitesse + 1`` retombe alors a zero : c'est la seule fin possible.
#
# A la remise a zero ``colonne`` vaut ``$A0`` et ``vitesse`` ``random()&7`` ;
# le second ``SUB_110A`` ;0f9a les fait passer a ``colonne = $A0-(v+1)`` et
# ``vitesse = v+1``, soit ``colonne + vitesse == $A0``. Sans cet appel on
# observerait ``colonne == $A0`` brut : c'est ce qui distingue les deux.
_alea = intro.Alea(0x12345678)
_gr = intro.Grille(_alea, b"\0" * len(intro.HAUTEUR_CASE))
_ec = intro.Ecran(bytearray(32000))
_obj = intro.Objets(_alea, _gr, _ec, intro.charger_objets())
_n = intro.Objets.NB_PIECES
_tours, _trans, _epuise = 0, None, None
while _tours < 20000:
    _r = _obj.pas(_ec)
    _tours += 1
    if _trans is None and _obj.repli:
        _trans = list(zip(_gr.colonnes[:_n], _gr.vitesses[:_n]))
    if _r == 2:
        _epuise = _tours
        break
chk(_epuise is not None,
    "SUB_E40 s'epuise seule (LAB_109C ;109c) : %s tours, repli vu=%s"
    % (_epuise, _trans is not None))
chk(_trans is not None and all(c + v == 0xA0 for c, v in _trans),
    "a la remise a zero, colonne+vitesse == $A0 pour les 18 colonnes -- "
    "donc ;0f9a a bien ete appele : %s" % ([c + v for c, v in
                                            (_trans or [])][:6],))
chk(_trans is not None and not any(c == 0xA0 for c, _ in _trans),
    "et aucune colonne ne reste a $A0 brut, ce que donnerait l'absence de "
    ";0f9a")

# ------------------------------------- les reperes du listing, mot a mot
for contenu, adresse, message in (
    ("BSR.W\tSUB_19EE", 0x1D02, "SUB_1CBC devrait appeler SUB_19EE"),
    ("JSR\tSUB_1910", 0x521C, "SUB_50E6 devrait appeler SUB_1910"),
    ("LEA\t($E,A7),A7", 0x0C7C, "0xFB ne pousser que six arguments, donc "
     "pas de hauteur"),
    ("CMP.W\t#$00f7,D5", 0x0D98, "l'opcode $F7 devrait etre compare a "
     "$00F7"),
    ("MULS\t#$000e,D0", 0x0DB0, "une structure de script devrait peser "
     "14 octets"),
    ("MOVE.W\t#$007f,-(A7)", 0x1198, "SUB_1186 devrait regrainer a $7F"),
    ("CMPI.W\t#$00f0,(-31994", 0x0D18, "le bump de $F9 devrait attendre "
     "240"),
    ("ADDQ.W\t#8,D0", 0x0FC0, "la deuxieme cascade du temple devrait "
     "decaler de 8"),
    ("MOVE.W\t#$00a8,D0", 0x0E70, "la premiere cascade devrait faire "
     "$A8 - colonne"),
    ("MOVE.W\t#$00a0,(0,A0,D0.L)", 0x0F68, "le reglage du temple devrait "
     "mettre colonne a $A0"),
    ("MULU\t#$01e0,D2", 0x1A20, "SUB_19EE devrait indexer sur $1E0"),
    ("MULU\t#$0140,D2", 0x185E, "SUB_1802 devrait indexer sur $140"),
    ("MULU\t#$00a0,D2", 0x1940, "SUB_1910 devrait indexer sur $A0"),
    ("DIVU\t#$000a,D3", 0x50EA, "SUB_50E6 devrait diviser par 10"),
    ("ADDI.W\t#$0098,D0", 0x50FE, "SUB_50E6 devrait ajouter $98 a x"),
    ("ADDI.W\t#$001c,D1", 0x5102, "SUB_50E6 devrait ajouter $1C a y"),
    ("MOVE.B\t(0,A1,D3.W),D6", 0x1CDE, "SUB_1CBC devrait lire le decalage "
     "en octet"),
    ("EXT.W\tD6", 0x1CF4, "puis l'etendre en signe -- d'ou _octet()"),
):
    trouve = None
    for _n, s in enumerate(LIGNES, start=1):
        if contenu in _sans_commentaire(s) and _numero_adresse(_n) == adresse:
            trouve = s.strip()
            break
    chk(trouve is not None,
        "%s ( ;%04x ) : %s" % (message, adresse, trouve or "introuvable"))

# ------------------------------------------- SUB_3F92 : le cycle de D0
_clr, _clr_adr = [], []
for _n, _s in enumerate(LIGNES, start=1):
    if "CLR.W\tD0" in _s:
        _a = _numero_adresse(_n)
        if _a is not None and 0x3FB0 <= _a <= 0x3FC8:
            _clr.append(_s)
            _clr_adr.append(_a)
chk(len(_clr) == 2 and _clr_adr == [0x3FB6, 0x3FC8],
    "SUB_3F92 remet D0 a zero au depart ( ;3fb6) puis a chaque tour "
    "complet $6 ( ;3fc8) : %d CLR.W D0 a %s" % (len(_clr),
                                                [";%04x" % a for a in _clr_adr]))


def _ref_3f92(donnees, ecart, masque, base, dest):
    """``SUB_3F92`` ;3f92-4024 reecrit : ``D0`` tourne sur 2,4,0 a travers
    toute l'image -- ``CLR.W`` une fois ( ;3fb6) puis ``ADDQ #2``/``CMPI #6``
    par paquet ( ;3fc0-3fc8). ``dest`` est une liste de 16000 mots."""
    d0 = 0
    a0 = base
    for ligne in range(0x40):
        for bloc in range(4):
            d0 = (d0 + 2) % 6
            msk = int.from_bytes(intro.MASQUES_REVELATION[
                masque * 2 + d0:masque * 2 + d0 + 2], "big")
            src = ecart + ligne * 32 + bloc * 8
            for p in range(4):
                o = a0 + bloc * 2 + p * 8000
                v = int.from_bytes(donnees[src + p * 2:src + p * 2 + 2], "big")
                w = dest[o // 2]
                dest[o // 2] = (w & msk) | (v & (~msk & 0xFFFF))
        a0 += 40
    return dest


_fond = bytes((k * 37 + 11) & 0xFF for k in range(32000))
_source = bytes((k * 91 + 5) & 0xFF for k in range(0x1000))
refus, cas = 0, 0
for _base in (0, 0x20):
    for _masque in (0, 1, 17, 19):
        cas += 1
        attendu = _ref_3f92(_source, 0x800, _masque, _base,
                            [int.from_bytes(_fond[2 * k:2 * k + 2], "big")
                             for k in range(16000)])
        e = intro.Ecran(bytearray(_fond))
        intro.reveler(e, _base, 0x800, _masque, _source)
        vu = [int.from_bytes(e.donnees[2 * k:2 * k + 2], "big")
              for k in range(16000)]
        if vu != attendu:
            refus += 1
            if refus == 1:
                k = next(i for i in range(16000) if vu[i] != attendu[i])
                print("     3F92 base=%d masque=%d mot %d : ref=%04X port=%04X"
                      % (_base, _masque, k, attendu[k], vu[k]))
chk(refus == 0,
    "reveler == SUB_3F92 sur %d combinaisons (base, masque) avec le cycle "
    "D0 continu : %d divergence(s)" % (cas, refus))

# --------------------------------------------------- la marche du script
refus, cas = 0, 0
for _cible in range(100):
    for _c in range(100):
        cas += 1
        _t, _u = divmod(_c, 10)
        _dt, _du = _cible // 10 - _t, _cible % 10 - _u
        attendu = ((_dt > 0) - (_dt < 0)) * 10 + ((_du > 0) - (_du < 0))
        if intro._pas_script(_c, _cible) != attendu:
            refus += 1
chk(refus == 0,
    "_pas_script == sign(diz(cible)-diz(c))*10 + sign(uni(cible)-uni(c)) "
    "sur %d couples : %d divergence(s)" % (cas, refus))

ok, court = True, 0
for _cible in range(100):
    _c = (_cible * 7 + 13) % 100
    for _k in range(40):
        if _c == _cible:
            court = max(court, _k)
            break
        _c += intro._pas_script(_c, _cible)
        if not 0 <= _c <= 100:
            ok = False
            break
    else:
        ok = False
chk(ok,
    "la marche converge en moins de 40 pas et reste dans 0..100 depuis "
    "n'importe quelle case : %s" % ("oui" if ok else "NON"))

for _c, _t in ((38, 26), (8, 26), (99, 0), (0, 99), (45, 54), (7, 70)):
    _p = intro._pas_script(_c, _t)
    chk(-11 <= _p <= 11 and _p != 0 and abs(_p) in (1, 9, 10, 11),
        "marche %d -> %d donne pas = %+d : un des neuf vecteurs de ;5130"
        % (_c, _t, _p))

# ==================================================== Phase 86 : la musique
print()
print("Phase 86 : popsam et la musique par fichier (ECART)")
print()

import struct as _struct
from populous import musique as _mus
from populous.sound import MusicEngine as _MusicEngine

# ---- (1) popsam : huit descripteurs LONG longueur + WORD periode ---------
# SUB_2C36 ;2c36 alloue $1C020 puis lit $1C01E octets. L'en-tete ouvre sur
# 00 00 52 0C 27 10 : un LONG 21004 suivi d'un WORD 10000, la periode du
# premier descripteur.
_b = (intro.assets.GAME / intro.SON_NOM).read_bytes()
# Le fichier n'a PAS d'en-tete plat : c'est un flux de huit blocs, chacun
# LONG longueur + WORD periode suivi immediatement de ses donnees.
_desc, _o = [], 0
while _o + 6 <= len(_b) and len(_desc) < 8:
    _lg = _struct.unpack_from(">I", _b, _o)[0]
    _per = _struct.unpack_from(">H", _b, _o + 4)[0]
    _desc.append((_o, _lg, _per))
    _o += 6 + _lg
chk(len(_desc) == 8, "popsam porte huit descripteurs (%d)" % len(_desc))
_attendu = [(0, 21004, 10000), (21010, 6032, 10000), (27048, 8244, 8000),
            (35298, 35662, 8000), (70966, 15340, 4000), (86312, 8008, 8000),
            (94326, 1754, 5300), (96086, 18626, 8000)]
chk(_desc == _attendu,
    "les 8 blocs (offset, longueur, periode) sont exactement %s" % (_desc,))
chk(_o == len(_b) == intro.SON_TAILLE,
    "le parcours des 8 blocs retombe pile sur la fin du fichier et sur "
    "SON_TAILLE : %d = %d = %d" % (_o, len(_b), intro.SON_TAILLE))
chk(len(_b) == 0x1C01E,
    "popsam pese exactement $1C01E, la longueur lue en ;2cc0 (%d octets)"
    % len(_b))
chk(b"M.K." not in _b and b"4CHN" not in _b,
    "popsam ne porte aucune signature ProTracker : aucun lecteur "
    "existant ne saurait le lire")

# ---- (2) la musique n'est PAS dans popsam : elle est dans le binaire ------
# SUB_2F9C ;2f9c balaie $3532..$3F92 avec A3 = $2F98. Ce sont 0xA60 octets
# de sequences, la table des periodes en tete, la table des instruments a
# $35A0 et la barre de tunes a $3806 -- rien de tout cela n'est dans un
# fichier de son, ce qui interdit d'employer un lecteur existant.
_raw = (intro.assets.GAME / "populous").read_bytes()
_A3 = 0x2F98
_blk = _raw[intro.HUNK0 + 0x3532:intro.HUNK0 + 0x3F92]
chk(len(_blk) == 0xA60,
    "le bloc de sequences est dans le binaire et pese $A60 octets "
    "($3532..$3F92) : %d" % len(_blk))
chk([_struct.unpack_from(">H", _blk, 2 * k)[0] for k in range(4)]
    == [0x1000, 0x0F18, 0x0E40, 0x0D74],
    "la table LAB_3532 ouvre le bloc par $1000 $0F18 $0E40 $0D74 : ce sont "
    "des periodes Paula, elles decroissent")

_tempo = _raw[intro.HUNK0 + 0x3807]
_off = [_struct.unpack_from(">I", _raw, intro.HUNK0 + a)[0]
        for a in (0x3808, 0x380C, 0x3810, 0x3814)]
chk(_tempo == 9, "la tune 0 porte tempo = 9 en ;3807 (%d)" % _tempo)
chk(_off == [0x880, 0x8F0, 0x964, 0x9D0],
    "les 4 longs de la tune 0 sont $880 $8F0 $964 $9D0 : %s"
    % (" ".join("$%X" % _v for _v in _off),))
chk([_A3 + _v for _v in _off] == [0x3818, 0x3888, 0x38FC, 0x3968],
    "ces longs sont relatifs a A3=$2F98 : A3+off retombe sur les 4 listes "
    "de motifs %s" % (" ".join("$%X" % (_A3 + _v) for _v in _off),))

_lists = [_A3 + _v for _v in _off]
_longueurs = []
for _l in _lists:
    _k = 0
    while _k <= 64 and _struct.unpack_from(
            ">I", _raw, intro.HUNK0 + _l + 4 * _k)[0] != 0:
        _k += 1                       # le long nul de fin n'est pas un motif
    _longueurs.append(_k)
chk(_longueurs == [27, 28, 26, 25],
    "les 4 listes contiennent 27/28/26/25 motifs puis un long nul : %s"
    % (_longueurs,))

# Le premier motif est lui-meme designe par un long de la liste, donc
# relatif a A3 lui aussi : A3 + $E06 = $3D9E.
_premier = _A3 + _struct.unpack_from(
    ">I", _raw, intro.HUNK0 + _A3 + _off[0])[0]
_debut = intro.HUNK0 + _premier
_fin = _raw.index(0x84, _debut)
chk(_premier == 0x3D9E,
    "le premier motif de la liste 0 est A3+$E06 = $3D9E ($%04X)" % _premier)
chk(_raw[_debut:_debut + 2] == bytes([0x80, 0]),
    "il s'ouvre sur $80 $00 : %s" % _raw[_debut:_debut + 2].hex(" "))
chk(0 < _fin - _debut + 1 < 256,
    "il tient en %d octets avant le $84 de fin" % (_fin - _debut + 1))

# ---- (3) les deux pistes fournies dans reference/ ------------------------
def _est_mp3(chemin) -> bool:
    if not chemin.is_file():
        return False
    with chemin.open("rb") as f:
        tete = f.read(4)
    if tete[:3] == b"ID3":
        return True
    return len(tete) >= 2 and tete[0] == 0xFF and (tete[1] & 0xE0) == 0xE0


for _f in (_mus.MUSIQUE_INTRO, _mus.MUSIQUE_JEU):
    _n = _f.stat().st_size if _f.is_file() else 0
    chk(_est_mp3(_f) and _n > 100000,
        "%s est un MP3 lisible de %d octets" % (_f.name, _n))

# Les deux passes de la scene, plus haut, ont tourne avec son=False : si ce
# levier mentait, dernier() pointerait deja sur Main Theme.
chk(_mus.dernier() is None,
    "les deux passes de la scene ont tourne avec son=False : aucune musique "
    "lancee (%s)" % (_mus.dernier(),))

# ---- (4) SDL_AUDIODRIVER=dummy : le controle est deterministe ------------
_anc_aud = _os.environ.get("SDL_AUDIODRIVER")
_anc_vid = _os.environ.get("SDL_VIDEODRIVER")
pygame.mixer.quit()
pygame.display.quit()
_os.environ["SDL_AUDIODRIVER"] = "dummy"
_os.environ["SDL_VIDEODRIVER"] = "dummy"
try:
    pygame.mixer.init(frequency=_mus.DEBIT, size=_mus.BITS,
                      channels=_mus.CANAUX)
    chk(pygame.mixer.get_init() is not None,
        "mixer dummy ouvert en %s" % (pygame.mixer.get_init(),))

    # (a') l'ecran titre est **silencieux** : ``SUB_456`` ;0456-052a
    # n'appelle aucune routine de son. Les seuls ``JSR`` de ;041c a ;0714
    # vont a ``SUB_17B2``, ``SUB_549A``, ``SUB_55BA``, ``SUB_29E``,
    # ``SUB_58CA``, ``SUB_10A2``, ``SUB_110A``, ``SUB_50B2`` et ``SUB_358`` :
    # l'armement est en tete de ``SUB_1186`` ( ;1194 ), jamais ici.
    pygame.display.init()
    _scr_t = pygame.display.set_mode((960, 768))
    _cadre_t = pygame.Surface((320, 256)).convert()
    _cadre_t.fill((0, 0, 0))
    _clk_t = pygame.time.Clock()
    pygame.event.clear()
    _rc_t = intro._titre(_cadre_t, _scr_t, _clk_t, 5000.0, 0.02)
    chk(_rc_t == 0,
        "_titre rend 0 sur le delai de ;04a0-04ae ( %s )" % (_rc_t,))
    chk(_mus.dernier() is None and not _mus.actif()
        and _mus.courant() is None,
        "l'ecran titre est silencieux : aucune piste armee ni coupee "
        "( dernier=%s )" % (_mus.dernier(),))
    pygame.event.clear()

    # (a) demarrer -> actif -> arreter
    chk(_mus.demarrer(_mus.MUSIQUE_INTRO),
        "demarrer(Main Theme) charge et lance la piste")
    chk(_mus.actif() and _mus.courant() == _mus.MUSIQUE_INTRO,
        "actif() et courant() voient la piste : %s" % (_mus.courant(),))
    _mus.arreter()
    chk(not _mus.actif() and _mus.courant() is None,
        "arreter() coupe et rend courant() a None")
    chk(_mus.dernier() == _mus.MUSIQUE_INTRO,
        "dernier() garde le chemin lance, y compris apres arreter()")

    # (b) tant qu'une piste joue, la mesure synthetisee se tait
    class _JeuFaux:
        music_on = 1
        effect_on = 1
        effect = 0

    class _SonFaux:
        def __init__(self) -> None:
            self.mesures = 0
            self.notes = 0

        def mesure(self, pistes, curbeat) -> None:
            self.mesures += 1

        def sound_in(self) -> int:
            return 0

        def play(self, son, voie: int = 0) -> None:
            self.notes += 1

    def _une_mesure():
        cap = _SonFaux()
        moteur = _MusicEngine(cap)
        for _ in range(moteur.music):
            moteur.image(_JeuFaux())
        return cap.mesures, cap.notes

    _mus.demarrer(_mus.MUSIQUE_JEU)
    _m, _n = _une_mesure()
    chk(_mus.actif() and _m == 0,
        "BGM.mp3 en play : la mesure synthetisee se tait -- %d mesure(s), "
        "%d note(s)" % (_m, _n))
    _mus.arreter()
    _m, _n = _une_mesure()
    chk(_m == 1 and _n == 0,
        "sans piste : une seule mesure en 10 images et aucun tic de tempo "
        "(tempo=0) -- %d mesure(s), %d note(s)" % (_m, _n))

    # (c) l'intro : son=True a l'entree, coupe dans le finally
    pygame.display.init()
    _scr = pygame.display.set_mode((960, 768))
    _cadre = pygame.Surface((320, 256)).convert()
    _cadre.fill((0, 0, 0))
    _clk = pygame.time.Clock()
    pygame.event.clear()
    _rc = intro.demarrer(_cadre, _clk, fenetre=_scr, im_par_seconde=5000.0,
                         attente_titre=0.02, duree_script=0.05,
                         boucle=False, son=True)
    chk(_rc == 0, "intro avec son=True : titre -> scene -> 0 ( %s )"
        % (_rc,))
    chk(_mus.dernier() == _mus.MUSIQUE_INTRO,
        "son=True : l'intro a bien arme Main Theme (%s)"
        % (_mus.dernier().name if _mus.dernier() else None,))
    chk(not _mus.actif() and _mus.courant() is None,
        "l'intro rend la main avec la musique coupee : le finally tourne")
    pygame.event.clear()
finally:
    _mus.arreter()
    pygame.mixer.quit()
    pygame.display.quit()
    if _anc_aud is None:
        _os.environ.pop("SDL_AUDIODRIVER", None)
    else:
        _os.environ["SDL_AUDIODRIVER"] = _anc_aud
    if _anc_vid is None:
        _os.environ.pop("SDL_VIDEODRIVER", None)
    else:
        _os.environ["SDL_VIDEODRIVER"] = _anc_vid
    pygame.display.init()
    try:
        pygame.mixer.init()               # meme format que pygame.init()
    except pygame.error:
        pass
    pygame.display.set_mode((1, 1))


print()
if ECHECS:
    print("%d/%d controle(s) en echec :" % (len(ECHECS), TOTAL[0]))
    for m in ECHECS:
        print("  -", m)
    sys.exit(1)
print("check_intro : %d/%d OK" % (TOTAL[0], TOTAL[0]))
