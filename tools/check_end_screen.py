"""Controle d'execution de l'ecran de fin : `_end_game` (etape A).

Ce que l'original fait, et que l'on verifie ici
------------------------------------------------

* **Une seule boite**, et non quatre : ``_requester(_d_screen, $10, $10,
  $120, $A6, titre, NULL)`` (L14356-14363), la meme geometrie que celle de
  ``_options``. Le ``NULL`` est un ``CLR.L -(A7)`` (L14356) : aucun message.
* **Sept lignes de texte**, et non sept boites : la boucle de L14366-14389
  appelle ``_text(_d_screen, x + $10, y + $10, chaine)`` sept fois, en
  ``LSR.W #3`` pres, sur les sept enregistrements de ``_end_text``
  (L24790-24805). ``LEA ($C,A7),A7`` (L14386) rend 12 octets : **quatre**
  arguments.
* Les sept chaines sont **construites au moment de l'affichage** par la
  boucle ``i = 0..6`` de L14021-14340, dispatchee par le tableau
  ``LAB_489CC`` (L14283-14290).
* ``___word_asc`` (L21054) complete le premier nombre avec des espaces
  **derriere** lui jusqu'a cinq caracteres (L14303-14320), puis
  ``___strcpy`` + ``___strcat`` (L14321-14336) posent le second.

Le binaire original confirme le tout
------------------------------------

``reference/original/extracted/DAD`` contient les sept gabarits **tels
qu'ecrits par l'assembleur**, et meme legerement salis par une execution
anterieure. Ce salissage est une preuve de plus : les octets qu'il laisse
sont precisement ceux que produisent ``_deux`` et ``long_asc`` avec les
valeurs qu'avait la partie interrompue.

::

    python tools\\check_end_screen.py
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

from populous import endtext  # noqa: E402
from populous.constants import FRAME_TOWN, ST_VILLAGER  # noqa: E402
from populous.game import Game  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ASM = ROOT / "reference" / "tetracorp" / "populous_prg.asm"
DAD = ROOT / "reference" / "original" / "extracted" / "DAD"

ECHECS = []
TOTAL = [0]


def chk(cond, msg):
    TOTAL[0] += 1
    print(("  ok    " if cond else "  ECHEC ") + msg)
    if not cond:
        ECHECS.append(msg)


lignes_asm = ASM.read_text(encoding="utf-8").splitlines()


def asm(n):
    return lignes_asm[n - 1].strip()


# --- 1 : le listing : une boite, sept `_text` -------------------------------
chk("CLR.L\t-(A7)" in asm(14356) and "(-60,A5)" in asm(14357),
    "L14356-14357 : le message est NULL (`CLR.L -(A7)`) et le titre est "
    "la structure locale (-60,A5)")
chk("#$00a6" in asm(14358) and "#$0120" in asm(14359),
    "L14358-14359 : hauteur = $A6 = 166 lignes, largeur = $120 = 288 px")
chk("#$0010" in asm(14360) and "#$0010" in asm(14361),
    "L14360-14361 : y = $10 puis x = $10")
chk("(_requester,PC)" in asm(14363) and "($14,A7),A7" in asm(14364),
    "L14363-14364 : un seul `_requester`, et `LEA ($14,A7),A7` rend 20 "
    "octets = les 7 arguments de L11108-11116")
chk("(strGAME_,A4)" in asm(14369) and "(LAB_5226E,A4)" in asm(14374)
    and "(_end_text,A4)" in asm(14380),
    "L14369/L14374/L14380 : chaine, ordonnee et abscisse se lisent toutes "
    "les trois par `MULU #$002e` : stride 46 octets")
chk("#$0010,D1" in asm(14376) and "#$0010,D1" in asm(14382),
    "L14376 et L14382 : les deux coordonnees sont **augmentees de $10** "
    "avant l'appel, soit de la demi-hauteur du bandeau haut")
chk("(___text,A4)" in asm(14385) and "($C,A7),A7" in asm(14386),
    "L14385-14386 : sept `_text`, et `LEA ($C,A7),A7` = 4 arguments "
    "(_text(dest, x, y, chaine))")
chk("#$0007" in asm(14388) and "LAB_48ACA" in asm(14389),
    "L14388-14389 : la boucle s'arrete a 7")
chk("(_requester,PC)" not in "".join(lignes_asm[14364:14389]),
    "L14365-14389 : aucun autre `_requester` dans la boucle : le tableau "
    "des scores n'est pas fait de sept boites")

# le dispatch
ordonne = [lignes_asm[n - 1].strip() for n in range(14284, 14291)]
attendu = ["LAB_486AA", "LAB_489CA", "LAB_486EC", "LAB_48724",
           "LAB_487A6", "LAB_4883E", "LAB_488DC"]
ok = all("(%s)" % attendu[i] in ordonne[i] for i in range(7))
chk(ok, "L14284-14290 : le tableau de saut place bien les sept branches "
        "dans l'ordre i = 0..6 : %s" % attendu)
chk("CMP.L\t#$00000007,D0" in asm(14292) and "BCC.S\tLAB_489CA" in asm(14293),
    "L14292-14293 : un i >= 7 retombe sur LAB_489CA, donc rien")

# les trois tables
chk("_end_text:" in asm(24790) and "DC.W\t$0070" in asm(24791),
    "L24790-24791 : `_end_text` = $0070, l'abscisse de '' GAME LOST ''")
chk("LAB_5226E:" in asm(24792) and "DC.L\t$000a0048" in asm(24793),
    "L24792-24793 : `LAB_5226E` suit a $000A (l'ordonnee) + $0048")
chk("strGAME_:" in asm(24794) and '"GAME "' in asm(24797),
    "L24794-24797 : `strGAME_` = '' GAME '', cinq caracteres")
chk("strLOST:" in asm(24798) and "DC.B\t$4c" in asm(24799)
    and "$4f535400" in asm(24800),
    "L24798-24800 : `strLOST` = `strGAME_ + 5` = '' LOST\\0 '' : c'est bien le "
    "suffixe qui change, pas la ligne")
chk("strScoreboard:" in asm(24803),
    "L24803 : `strScoreboard` est la ou `___word_asc`/`___long_asc` "
    "ecrivent, soit l'octet 19 de chaque gabarit")
chk('"                   YOU  HIM",0' in asm(24811),
    "L24811 : la ligne d'en-tete porte bien 19 espaces puis '' YOU  HIM ''")

# la conversion
chk("MOVE.W\t($C,A5),D0" in asm(21057) and "EXT.L\tD0" in asm(21058),
    "L21057-21058 : `_word_asc` prend un mot **signe** (EXT.L) puis tombe "
    "dans le code de `_long_asc` : meme algorithme, sans remplissage")

# le magot mort de L14202
chk("MOVE.L\t(-14,A5),(-10,A5)" in asm(14202)
    and "(___word_asc,A4)" in asm(14196) and "(___word_asc,A4)" in asm(14200),
    "L14202 : dans la branche CHATEAUX, `MOVE.L (-14),(-10)` arrive "
    "**apres** les deux `word_asc` : c'est une ecriture morte, sans effet "
    "a l'ecran (relevee, non reproduite)")

# --- 2 : les sept gabarits, confrontes au binaire --------------------------
donnees = DAD.read_bytes()
BASE = 0x15218                      # `_end_text` = asm $5226C, decalage -$3D054
chk(int.from_bytes(donnees[BASE:BASE + 2], "big") == 0x0070
    and int.from_bytes(donnees[BASE + 2:BASE + 4], "big") == 0x000A,
    "DAD+%#x : x = $70, y = $0A pour i = 0, comme L24791/L24793" % BASE)
for i in range(7):
    o = BASE + 46 * i
    x = int.from_bytes(donnees[o:o + 2], "big")
    y = int.from_bytes(donnees[o + 2:o + 4], "big")
    chk(x == endtext.END_X[i] and y == endtext.END_Y[i],
        "DAD+%#x : enregistrement %d -> x = %#x, y = %#x, "
        "conforme a END_X/END_Y" % (o, i, x, y))

for i in range(7):
    o = BASE + 46 * i + 6
    gabarit = donnees[o:o + 40].split(b"\x00")[0].decode("latin-1")
    if i == 0:
        chk(gabarit == "GAME LOST",
            "DAD+%#x : la chaine initiale est '' %s '', le gabarit ecrit par "
            "l'assembleur" % (o, gabarit))
    elif i == 1:
        chk(gabarit == endtext.END_TEXTE[1],
            "DAD+%#x : la ligne d'en-tete est intacte : %r" % (o, gabarit))
    elif i == 6:
        chk(gabarit == "YOUR SCORE         6115"
            and donnees[o + 24:o + 26] == b"00",
            "DAD+%#x : '' 6115 '' est le reste d'un `long_asc` deja passe, et "
            "les deux '' 0 '' qui suivent le zero sont le bout du gabarit "
            "'' 000000000 '' : le nombre de chiffres du gabarit est confirme "
            "par le binaire" % o)
    else:
        chk(gabarit == endtext._deux(endtext.END_TEXTE[i], "0", "0"),
            "DAD+%#x : le salissage de la ligne %d vaut exactement "
            "`_deux(gabarit, word_asc(0), word_asc(0))` = %r : le "
            "remplissage a cinq caracteres et le strcat sont confirmes par "
            "le binaire" % (o, i, gabarit))
        chk("0    0" in gabarit,
            "DAD+%#x : ... dont les cinq caracteres '' 0    '' viennent du "
            "gabarit et non du remplissage" % o)

# --- 3 : word_asc / long_asc ------------------------------------------------
ATTENDU = {0: "0", 1: "1", 9: "9", 10: "10", 42: "42", 99: "99", 100: "100",
           255: "255", 1234: "1234", 32767: "32767", 500: "500",
           555555: "555555", 515090: "515090",
           -1: "-1", -7: "-7", -42: "-42", -100: "-100", -32768: "-32768"}
mauvais = [(v, endtext.word_asc(v), e) for v, e in ATTENDU.items()
           if endtext.word_asc(v) != e]
chk(not mauvais,
    "`word_asc`/`long_asc` : les %d valeurs de reference, signees et "
    "non signees : %s" % (len(ATTENDU), mauvais or "toutes correctes"))
chk(endtext.long_asc(6115) == "6115",
    "`long_asc(6115)` = '' 6115 '', exactement ce que DAD a gele en reserve "
    "de la ligne YOUR SCORE")

# --- 4 : le calcul du score -------------------------------------------------
def score_independant(perdu, sim, score):
    """Reecriture **différente** de L14204-14270, pour confronter."""
    total = score
    if sim.battle_won[sim.player] - sim.battle_won[sim.not_player] > 0:
        total += 5000
    for rang in range(3, 9):                     # les six bits 3..8
        joueur = (sim.stats[sim.player].power_mask >> rang) & 1
        ennemi = (sim.stats[sim.not_player].power_mask >> rang) & 1
        if joueur == 0:
            total += 1000
        if ennemi == 1:
            total += 1000
    if sim.serial_off != 0:
        total += 15 * (10 - sim.stats[sim.not_player].period)
    if not perdu:
        total = total * 10
    if total < 500:
        total = 500
    if total > 0x87A23:
        total = 0x7DC12
    return total


g = Game(60, 0, 3)
g.load_conquest(1)
sim = g.sim
cas = 0
ecarts = []
for perdu in (False, True):
    for bw in ((0, 0), (1, 0), (0, 3), (7, 7), (99, 1)):
        for masque in (0xFFFF, 0x0000, 0x00F7, 0x0008, 0x0100):
            for serial in (0, 1):
                for periode in (0, 1, 3, 9, 10):
                    sim.battle_won = list(bw)
                    for t in (0, 1):
                        sim.stats[t].power_mask = masque
                        sim.stats[t].period = periode
                    sim.serial_off = serial
                    a = endtext.score_final(perdu, sim, 0)
                    b = score_independant(perdu, sim, 0)
                    cas += 1
                    if a != b:
                        ecarts.append((perdu, bw, masque, serial, periode,
                                       a, b))
chk(not ecarts,
    "`score_final` == une reecriture independante de L14204-14270 sur %d "
    "configurations : %s" % (cas, ecarts[:3] or "aucun ecart"))

sim.battle_won = [0, 0]
sim.serial_off = 1
sim.stats[0].power_mask = sim.stats[1].power_mask = 0xFFFF
sim.stats[0].period, sim.stats[1].period = 1, 3
chk(endtext.score_final(False, sim, 0) == (6000 + 105) * 10,
    "victoire seule : +6000 (les six pouvoirs de l'adversaire) + 105 "
    "(15 x (10 - 3)), puis x10 -> %d" % endtext.score_final(False, sim, 0))
chk(endtext.score_final(True, sim, 0) == 6105,
    "defaite seule : pas de x10 -> %d" % endtext.score_final(True, sim, 0))
chk(endtext.score_final(True, sim, 10) == 6115,
    "`_score = 10` + defaite -> 6115 : c'est le nombre gele dans DAD "
    "en reserve de '' YOUR SCORE ''")
chk(endtext.score_final(False, sim, 999999) == 515090,
    "au-dela de 555555, la valeur est ramenee a 515090 (L14268-14270)")
chk(endtext.score_final(True, sim, -10000) == 500,
    "en dessous de 500, la valeur est ramenee a 500 (L14263-14265)")

# --- 5 : les compteurs, face a un balayage independant -----------------------
def compte_independant(sim, filtre):
    """Balayage **différent** de L14095-14099 et de ses deux copies."""
    a = b = 0
    for p in list(sim.peeps)[:sim.no_peeps]:
        if not filtre(p):
            continue
        if p.tribe == sim.player:
            a += 1
        elif p.tribe != sim.player:
            b += 1
    return a, b


FILTRES = {
    # LAB_48732 (L14073-14082)
    "chevalier": lambda p: p.target >= 0 and p.life != 0,
    # LAB_487B4 (L14115-14129)
    "ville": lambda p: (p.state == ST_VILLAGER and p.life != 0
                        and p.frame != FRAME_TOWN),
    # LAB_4884C (L14162-14176)
    "chateau": lambda p: (p.state == ST_VILLAGER and p.life != 0
                          and p.frame == FRAME_TOWN),
}
PORT = {"chevalier": endtext._chevalier, "ville": endtext._ville,
        "chateau": endtext._chateau}

for nom in ("chevalier", "ville", "chateau"):
    a, b = endtext._compter(sim, PORT[nom])
    c, d2 = compte_independant(sim, FILTRES[nom])
    chk((a, b) == (c, d2),
        "`_compter`/%s == un balayage independant de `_peeps` : %s"
        % (nom, (a, b)))

# un cas construit, ou les trois comptes sont connus d'avance
for p in sim.peeps:
    p.state, p.life, p.frame, p.target, p.tribe = 0, 0, 0, -1, 0
sim.no_peeps = 6
for i in range(6):
    sim.peeps[i].tribe = i % 2                  # 0,1,0,1,0,1
sim.peeps[0].state = ST_VILLAGER
sim.peeps[0].life = 5
sim.peeps[0].frame = 0                          # tribu 0, ville
sim.peeps[1].state = ST_VILLAGER
sim.peeps[1].life = 5
sim.peeps[1].frame = FRAME_TOWN                 # tribu 1, chateau
sim.peeps[2].state = ST_VILLAGER
sim.peeps[2].life = 0                           # mort : rien ne compte
sim.peeps[3].target = 4
sim.peeps[3].life = 5                           # tribu 1, chevalier
sim.peeps[4].target = 0
sim.peeps[4].life = 0                           # vise, mais mort
sim.peeps[5].state = ST_VILLAGER
sim.peeps[5].life = 5
sim.peeps[5].frame = 0                          # tribu 1, ville
sim.player, sim.not_player = 0, 1
chk(endtext._compter(sim, endtext._ville) == (1, 1),
    "villes : peeps 0 (tribu 0) et 5 (tribu 1) -> %s"
    % (endtext._compter(sim, endtext._ville),))
chk(endtext._compter(sim, endtext._chateau) == (0, 1),
    "chateaux : seul le peep 1, frame $2A, en compte un -> %s"
    % (endtext._compter(sim, endtext._chateau),))
chk(endtext._compter(sim, endtext._chevalier) == (0, 1),
    "chevaliers : seuls 3 et 4 ont une cible, mais 4 n'est pas vivant -> %s"
    % (endtext._compter(sim, endtext._chevalier),))
for p in sim.peeps:
    p.state, p.life, p.frame, p.target, p.tribe = 0, 0, 0, -1, 0
sim.no_peeps = 0

# --- 6 : les sept lignes, en execution --------------------------------------
sim.battle_won = [3, 7]
titre, lignes, score = endtext.construire(False, sim, 0)
chk(lignes[0] == "GAME WON", "i = 0 : `GAME ` + strWon -> %r" % lignes[0])
chk(lignes[1] == endtext.END_TEXTE[1],
    "i = 1 : LAB_489CA ne touche a rien -> %r" % lignes[1])
chk(lignes[2] == "BATTLES WON        3    7",
    "i = 2 : batailles 3 et 7, le premier complete a cinq caracteres -> %r"
    % lignes[2])
chk(titre == endtext.TEXT_NEW_GAME,
    "victoire : titre = strNew_Game (L14341-14342 : BEQ sur `perdu == 0`)")
titre, lignes, score = endtext.construire(True, sim, 0, in_conquest=1)
chk(lignes[0] == "GAME LOST", "perdu : `GAME ` + strLost -> %r" % lignes[0])
chk(titre == endtext.TEXT_TRY_IT_AGAIN,
    "defaite **en conquete** : titre = strTryItAgain (L14343-14345)")
chk(endtext.construire(True, sim, 0)[0] == endtext.TEXT_NEW_GAME,
    "defaite **hors conquete** : titre = strNew_Game (L14345 : BEQ sur "
    "`_in_conquest == -1`)")
chk(all(19 < len(e) <= 28 for e in lignes[2:]),
    "les lignes 2 a 6 font de 20 a 28 caracteres : elles tiennent dans la "
    "boite de 288 px (28 x 8 = 224) : %s" % [len(e) for e in lignes[2:]])

# --- 7 : le rendu : une boite, sept lignes, rien en dessous -----------------
def espionne(g):
    """Enregistre les appels de `draw_text` et `draw_icon`."""
    texte, icones = [], []
    ot, oi = g.ren.draw_text, g.ren.draw_icon

    def ft(dest, x, y, t, palette=None):
        texte.append((x, y, t))
        return ot(dest, x, y, t, palette)

    def fi(dest, col, row, n):
        icones.append((col, row, n))
        return oi(dest, col, row, n)

    g.ren.draw_text, g.ren.draw_icon = ft, fi
    return texte, icones, ot, oi


# le bas de la boite, recalcule depuis la boucle de L9949-9996
d5, hauteur = 0x10, 0xA6
bas = d5 + 0x10
while bas < d5 + hauteur - 0x10:
    bas += 0x10

g2 = Game(60, 0, 3)
g2._end_game(True)                       # hors conquete : pas de discours
chk(g2.game_ended and not g2.victory, "`_end_game(True)` fige la partie")
texte, icones, ot, oi = espionne(g2)
g2.draw_end_screen()
g2.ren.draw_text, g2.ren.draw_icon = ot, oi

corners = [c for c in icones if c[2] == 0x0C]
chk(len(corners) == 1 and corners[0] == (1, 0x10, 0x0C),
    "une **seule** icone 0x0C = un seul coin haut-gauche = une seule "
    "boite, en colonne 1 (x = $10 >> 4) et ligne $10 : %s" % corners)
chk(min(row for _, row, _ in icones) == 0x10
    and max(row for _, row, _ in icones) == bas,
    "les icones couvrent les lignes $10 .. %d, c'est-a-dire le bandeau bas "
    "pose a `y + hauteur` : %d..%d"
    % (bas, min(r for _, r, _ in icones), max(r for _, r, _ in icones)))

attendus = [((((0x10 >> 4) + 1) * 2), 0x10 + 16 + 2, g2.end_titre)]
attendus += [((endtext.END_X[i] + 0x10) // 8, endtext.END_Y[i] + 0x10, s)
             for i, s in enumerate(g2.end_lignes)]
chk(texte == attendus,
    "les appels de `_text` sont exactement le titre de la boite puis les "
    "sept lignes en (x + $10, y + $10) : %s" % (texte,))

# ... et chaque ligne se retrouve bien **en pixels** a sa place
g2.frame.fill((0, 0, 0))
g2.draw_end_screen()
vides = []
for i, s in enumerate(g2.end_lignes):
    x0 = ((endtext.END_X[i] + 0x10) // 8) * 8
    y0 = endtext.END_Y[i] + 0x10
    n = sum(1 for y in range(y0, y0 + 8)
            for x in range(x0, x0 + 8 * len(s))
            if g2.frame.get_at((x, y))[:3] != (0, 0, 0))
    if n == 0:
        vides.append((i, x0, y0))
chk(not vides,
    "les sept lignes sont toutes rendues en pixels a l'interieur de la "
    "boite, en (x = END_X + $10, y = END_Y + $10) : %s"
    % (vides or "aucune manquante"))

g2.frame.fill((0, 0, 0))
g2.draw_end_screen()
hors = sum(1 for y in range(bas + 16, 200) for x in range(320)
           if g2.frame.get_at((x, y))[:3] != (0, 0, 0))
chk(hors == 0,
    "rien sous la ligne %d : les quatre boites inventees, en y = $A6, "
    "$B2, $BA et $C8 (lignes 166 a 263), ont bien disparu "
    "(%d pixel(s) hors boite)" % (bas + 16, hors))

# le meme ecran, en conquete, doit garder le tableau **et** ajouter les deux
# lignes d'en-tete en (8, $B2) et (8, $BA)
g3 = Game(60, 0, 3)
g3.load_conquest(1)
g3._end_game(True)                       # defaite en conquete, pas de discours
chk(not g3.victory_speech, "defaite en conquete : pas de discours")
texte3, icones3, ot3, oi3 = espionne(g3)
g3.draw_end_screen()
g3.ren.draw_text, g3.ren.draw_icon = ot3, oi3
chk(len([c for c in icones3 if c[2] == 0x0C]) == 1,
    "en conquete non plus il n'y a qu'une boite")
chk(texte3[-2:] == [(1, 0xB2, g3.victory_texte[0]),
                    (1, 0xBA, g3.victory_texte[1])],
    "les deux lignes de `_won_conquest` passent **par-dessus** le tableau, "
    "en `_text` nus (x = 8 >> 3) : %s" % (texte3[-2:],))
chk(len(texte3) == 10, "1 titre + 7 lignes + 2 lignes d'en-tete = 10 appels")

print()
if ECHECS:
    print("%d/%d controle(s) en echec :" % (len(ECHECS), TOTAL[0]))
    for m in ECHECS:
        print("  -", m)
    sys.exit(1)
print("check_end_screen : %d/%d OK" % (TOTAL[0], TOTAL[0]))
