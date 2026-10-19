"""Le tableau des scores de ``_end_game`` (asm L14019-14389).

Ce que l'ecran de fin montre **n'est pas** un empilement de boites de
dialogue : c'est **une** boite et **sept** lignes de texte.

* ``_requester(_d_screen, $10, $10, $120, $A6, titre, NULL)``
  (L14356-14363) -- la meme geometrie que celle de ``_options`` ;
* une boucle de sept ``_text(_d_screen, x + $10, y + $10, chaine)``
  (L14366-14389) sur les sept enregistrements de ``_end_text``
  (L24790-24805).

Les sept chaines ne sont pas des constantes : le ``BRA.W LAB_489DA`` de
L14025 saute dans un tableau d'adresses (``LAB_489CC``, L14283-14290) qui
**construit** chacune d'elles a chaque tour de la boucle ``i = 0..6``
(L14021-14340). C'est ce que reproduit :func:`construire`.

Un enregistrement fait 46 octets (``MULU #$002E`` partout) :

===========  ========  ==================================================
offset       champ     contenu
===========  ========  ==================================================
``+0``       ``x``     abscisse, en **pixels** (``_end_text``)
``+2``       ``y``     ordonnee, en **lignes** (``LAB_5226E``)
``+4``       mot       inutilise ($0048 sur la premiere ligne, $0018
                       ailleurs ; le meme champ vaut $28 sur ``_end_ok``)
``+6``       chaine    40 octets (``strGAME_`` et suivants)
===========  ========  ==================================================

``strScoreboard`` vaut ``strGAME_ + 19`` (L24803) : c'est l'octet 19 des
lignes 2 a 6, ou ``___word_asc`` / ``___long_asc`` ecrasent le gabarit. Le
zero de fin de ``___strcpy`` tronque donc le reste du gabarit : les valeurs
initiales ``"0000 0000"`` et ``"000000000"`` de L24799-24805 ne sont jamais
affichees, elles ne servent qu'a guider la lecture du listing.
"""
from __future__ import annotations

from populous.constants import FRAME_TOWN, ST_VILLAGER

# `_requester(_d_screen, $10, $10, $120, $A6, titre, NULL)` (L14356-14363)
END_BOITE = (0x10, 0x10, 0x120, 0xA6)

TEXT_TRY_IT_AGAIN = "TRY IT AGAIN"     # strTryItAgain (L14445-14452)
TEXT_NEW_GAME = "NEW GAME"             # strNew_Game   (L14453-14456)
TEXT_LOST = "LOST"                     # strLost       (L14441-14444)
TEXT_WON = "WON"                       # strWon        (L14445-14448)

#: `strScoreboard` = `strGAME_` + 19 (L24803) : la ou les chiffres ecritent.
SCORE_DEBUT = 19

#: `_end_text` (L24790) : abscisse, en **pixels**.
END_X = (0x70, 0x10, 0x10, 0x10, 0x10, 0x10, 0x10)

#: `LAB_5226E` (L24792) : ordonnee, en **lignes**.
END_Y = (0x0A, 0x14, 0x23, 0x2D, 0x37, 0x41, 0x50)

#: `strGAME_` (L24794-24805) : les sept gabarits. La ligne 1 n'a pas de
#: chiffre a ecrire (``LAB_489CA``, L14281-14282, ne fait que reboucler).
END_TEXTE = (
    "GAME LOST",                                        # i = 0
    " " * SCORE_DEBUT + "YOU  HIM",                     # i = 1
    "BATTLES WON        0000 0000",                     # i = 2
    "NUMBER OF KNIGHTS  0000 0000",                     # i = 3
    "NUMBER OF TOWNS    0000 0000",                     # i = 4
    "NUMBER OF CASTLES  0000 0000",                     # i = 5
    "YOUR SCORE         000000000",                     # i = 6
)


# --------------------------------------------------------------- conversions
def word_asc(valeur: int) -> str:
    """``_word_asc(buf, valeur)`` (L21054-21101) : le decimal **signe**.

    Le mot empile est ``EXT.L`` (L21057-21058) puis le code tombe dans
    celui de ``_long_asc`` (L21049-21050) : ``"0"`` pour zero (L21071-21077),
    un tiret devant les negatifs (L21082-21087), et **aucun** remplissage
    -- c'est l'appelant qui complete avec des espaces (L14303-14320).
    """
    if valeur == 0:
        return "0"
    signe = "-" if valeur < 0 else ""
    n = -valeur if valeur < 0 else valeur
    chiffres = []
    while n:
        chiffres.append(chr(ord("0") + n % 10))
        n //= 10
    return signe + "".join(reversed(chiffres))


def long_asc(valeur: int) -> str:
    """``_long_asc(buf, valeur)`` (L21046-21052) : identique, sur un long."""
    return word_asc(valeur)


# ------------------------------------------------------------------ compteurs
def _chevalier(p) -> bool:
    """``LAB_48732`` (L14073-14082) : la fiche compte si elle **vise** quelque
    chose et si elle est **vivante**.

    ``LAB_53022`` est `_peeps + 14`, le long que le port appelle ``target`` :
    nul dans l'asm pour ``-1`` du port, donc ``TST.L`` / ``BEQ`` (L14076-14077).
    """
    return p.target >= 0 and p.life != 0


def _ville(p) -> bool:
    """``LAB_487B4`` (L14115-14129) : ``state == 1``, vivant, et **pas** une
    grande ville (``frame != $2A``)."""
    return (p.state == ST_VILLAGER and p.life != 0
            and p.frame != FRAME_TOWN)


def _chateau(p) -> bool:
    """``LAB_4884C`` (L14162-14176) : ``state == 1``, vivant, et **une**
    grande ville (``frame == $2A``)."""
    return (p.state == ST_VILLAGER and p.life != 0
            and p.frame == FRAME_TOWN)


def _compter(sim, garde) -> tuple[int, int]:
    """Le balayage ``i = 0.._no_peeps-1`` qui partage entre les deux tribus.

    Un compteur par camp, en **long** (``(-14,A5)`` pour le joueur,
    ``(-10,A5)`` pour l'adversaire, L14068-14069 et copies), et la decision
    prise sur ``LAB_53015`` = `_peeps + 1` = la tribu (L14085-14093).
    """
    joueur = ennemi = 0
    for i in range(sim.no_peeps):
        p = sim.peeps[i]
        if garde(p):
            if p.tribe == sim.player:
                joueur += 1
            else:
                ennemi += 1
    return joueur, ennemi


# ---------------------------------------------------------------- le calcul
def _mettre(gabarit: str, chiffres: str) -> str:
    """``___word_asc`` / ``___long_asc`` ecrivent a `strScoreboard + i*46`.

    Le buffer pointe donc sur l'octet 19 du gabarit, et le zero que la
    routine pose derriere ses chiffres tronque tout ce qui suivait.
    """
    return gabarit[:SCORE_DEBUT] + chiffres


def _deux(gabarit: str, gauche: str, droite: str) -> str:
    """Le remplissage de L14303-14320 : le premier nombre est complete a
    **cinq** caracteres avec des espaces **derriere** lui (et non devant),
    puis le second est concatene (``___strcat``, L14329-14336)."""
    return _mettre(gabarit, gauche + " " * max(0, 5 - len(gauche)) + droite)


def score_final(perdu: bool, sim, score: int) -> int:
    """Le calcul de `_score` par ``LAB_488DC`` (L14204-14271).

    L'ordre exact du listing, tel quel :

    1. L14205-14217 : ``+5000`` si le joueur a remporte plus de batailles
       que l'adversaire ;
    2. L14219-14241 : la boucle sur les six bits ``8, 10, 20, 40, 80, 100``
       de `_stats[player].power_mask`` (``LAB_516B2`` = `_stats + $0E`) --
       ``+1000`` quand le joueur **n'a pas** le pouvoir, ``+1000`` de plus
       quand l'adversaire **l'a** ;
    3. L14242-14252 : en solo (``_serial_off != 0``), ``+15`` par point de
       ``10 - _stats[adversaire].period`` (``LAB_516B4`` = `_stats + $10`) ;
    4. L14254-14260 : ``x10`` sur une **victoire** uniquement ;
    5. L14263-14270 : bornage a ``500`` en bas, et au-dela de ``555555`` la
       valeur ``515090``.
    """
    if sim.battle_won[sim.player] > sim.battle_won[sim.not_player]:
        score += 5000                                   # L14217
    masque = 8                                          # L14219
    while True:
        if not (sim.stats[sim.player].power_mask & masque & 0xFFFF):
            score += 1000                               # L14228
        if sim.stats[sim.not_player].power_mask & masque & 0xFFFF:
            score += 1000                               # L14237
        masque <<= 1                                    # L14239
        if masque > 0x100:                              # L14240-14241
            break
    if sim.serial_off != 0:                             # L14242-14243
        score += (10 - sim.stats[sim.not_player].period) * 15
    if not perdu:                                       # L14254-14255
        score *= 10                                     # L14256-14260
    if score < 500:                                     # L14263-14265
        score = 500
    if score > 555555:                                  # L14268-14270
        score = 515090
    return score


def titre(perdu: bool, in_conquest: int) -> str:
    """Le texte du bouton de la boite, ``(-54,A5)`` (L14341-14354).

    ``strTryItAgain`` si le joueur a perdu **et** qu'il est en conquete,
    ``strNew_Game`` dans tous les autres cas.
    """
    if perdu and in_conquest != -1:
        return TEXT_TRY_IT_AGAIN
    return TEXT_NEW_GAME


def construire(perdu: bool, sim, score: int,
               in_conquest: int = -1) -> tuple[str, list[str], int]:
    """La boucle ``i = 0..6`` de ``_end_game`` (L14021-14340).

    ``in_conquest`` est `_in_conquest` (L14343) : ``-1`` hors conquete. Le
    port le passe depuis ``self.conquest``, comme le fait deja le test de
    L14408-14416 a la fin de ``_end_game``.

    Les tampons ``(-54,A5)``, ``(-70,A5)`` et ``(-80,A5)`` sont reecrits a
    chaque tour : la construction n'a donc **que** le sens qu'a la fonction
    qui l'appelle, et le port la fait une seule fois, au moment ou l'asm la
    fait, c'est-a-dire avant d'attendre le clic.

    Renvoie ``(titre, sept lignes, score)``.
    """
    j, e = sim.player, sim.not_player
    lignes = list(END_TEXTE)

    # i = 0 : `LAB_486AA` (L14027-14047), `strcpy(strLOST, "LOST"/"WON")`
    # -- `strLOST` = `strGAME_` + 5, d'ou le "GAME " qui reste en tete.
    lignes[0] = "GAME " + (TEXT_LOST if perdu else TEXT_WON)

    # i = 1 : `LAB_489CA` (L14281-14282) ne fait que reboucler : la ligne
    # d'en-tete `YOU  HIM` reste intacte.

    # i = 2 : `LAB_486EC` (L14049-14065), `_battle_won` des deux tribus.
    lignes[2] = _deux(lignes[2], word_asc(sim.battle_won[j]),
                      word_asc(sim.battle_won[e]))

    # i = 3 : `LAB_48724` (L14067-14108), les chevaliers.
    a, b = _compter(sim, _chevalier)
    lignes[3] = _deux(lignes[3], word_asc(a), word_asc(b))

    # i = 4 : `LAB_487A6` (L14109-14155), les villes.
    a, b = _compter(sim, _ville)
    lignes[4] = _deux(lignes[4], word_asc(a), word_asc(b))

    # i = 5 : `LAB_4883E` (L14156-14203), les chateaux. La ligne L14202
    # `MOVE.L (-14,A5),(-10,A5)` recopie le compteur du joueur dans celui de
    # l'adversaire **apres** les deux `word_asc` : elle est morte, les
    # chaines sont deja ecrites. On la note et on ne la reproduit pas.
    a, b = _compter(sim, _chateau)
    lignes[5] = _deux(lignes[5], word_asc(a), word_asc(b))

    # i = 6 : `LAB_488DC` (L14204-14280), le score, ecrit en **long**.
    score = score_final(perdu, sim, score)
    lignes[6] = _mettre(lignes[6], long_asc(score))

    return titre(perdu, in_conquest), lignes, score
