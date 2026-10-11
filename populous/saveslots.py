# -*- coding: utf-8 -*-
"""Le tiroir de sauvegardes — ``_get_a_dir`` (L16841) et ``_sort`` (L11016).

`_save_load` (L10493) n'affiche jamais le disque : il affiche le **tiroir**,
c'est-a-dire la liste des fichiers de sauvegarde que `_get_a_dir` y recopie,
puis que `_sort` range. Ce sont ces deux fonctions qui decident de ce que le
joueur voit dans les douze emplacements.

**`_get_a_dir(cible, tiroir)`** (L16841-16947) : liste le contenu du tiroir
dans un tampon d'entrees de **32 octets**, et rend le nombre d'entrees.

* seuls les **fichiers** sont pris : `TST.L (4,A0) ; BGT` (L16863-16864) ecarte
  ce qui a un type positif, c'est-a-dire les dossiers ;
* le nom est recopie **en majuscules** : un caractere entre `$61` et `$7A`
  voit `$20` retranche (L16870-16881) ;
* la copie s'arrete a **$1D = 29** caracteres ou au zero final (L16896) ;
* si le nom fait **au moins quatre** caracteres et finit par `.GAM`, les
  **quatre derniers sont effaces** et l'entree est comptee (L16908-16929) -
  c'est donc la qu'on distingue une vraie sauvegarde d'un autre fichier ;
* une entree trop courte pour porter `.GAM` est garde telle quelle, suffixe
  compris ;
* le rendu est `octet_depart >> 5`, c'est-a-dire le nombre d'entrees de 32
  octets (L16944-16945).

La lecture du disque lui-meme etait `Lock` / `Examine` / `ExNext` / `IoErr`
d'AmigaDOS ; la fin de boucle est `IoErr() == $E8` (L16937). Cote port c'est
`os.listdir`, et un repertoire est ce que `entry.is_dir()` designe.

**`_sort(cible, n)`** (L11016-11094) est un **tri par coquilles** : le pas
`(-2,A5)` commence a `n` et est divise par deux a chaque passe (`ASR`, L11021),
et chaque passe balaie avec un ecart egal a ce pas (L11030, L11079). Les
comparaisons se font sur des entrees de 32 octets (L11033, L11040).
"""
from __future__ import annotations

import os

TAILLE_ENTREE = 0x20      # 32, `ASL.W #5` partout (L11033, L11040, L11079)
NOM_MAX = 0x1D            # 29, `CMPI.W #$001D` (L16896)
SUFFIXE = ".GAM"


def get_a_dir(dossier: str) -> list[bytes]:
    """`_get_a_dir` (L16841-16947) : les sauvegardes du dossier, sans `.GAM`.

    Chaque entree fait 32 octets comme dans le listing, majuscules, et le
    suffixe `.GAM` est retire quand le nom en porte un - a la position 4 ou
    plus loin, c'est-a-dire quand le nom fait au moins quatre caracteres
    (L16908).
    """
    entrees: list[bytes] = []
    try:
        noms = os.listdir(dossier)
    except OSError:
        return entrees                  # `Lock` qui echoue (L16849)
    for nom in noms:
        if os.path.isdir(os.path.join(dossier, nom)):
            continue                    # `TST.L (4,A0) ; BGT` (L16863)
        brut = nom.upper().encode("latin-1", "replace")
        # L16895-16900 : on s'arrete a $1D caracteres ou au zero final
        i = 0
        while i < NOM_MAX and i < len(brut):
            i += 1
        haut = brut[:i]
        if len(haut) >= 4 and haut[-4:] == SUFFIXE.encode("latin-1"):
            haut = haut[:-4]             # L16922-16928 : on efface le suffixe
        else:
            continue                    # pas une sauvegarde : non comptee
        entrees.append(haut.ljust(TAILLE_ENTREE, b"\x00"))
    return entrees


def sort(entrees: list[bytes]) -> list[bytes]:
    """``_sort(cible, n)`` (L11016-11094) : tri par coquilles, en place.

    .. code-block:: none

        pas = n
        while (pas >>= 1) != 0:            # ASR, division entiere
            for i in range(1, n - pas + 1):     # D6 de 1 a n-pas
                j = i                             # D5
                while True:
                    k = j + pas                   # D4
                    if base[(k-1)*32] <= base[(j-1)*32]:
                        break                       # BLE : deja en ordre
                    base[(k-1)*32], base[(j-1)*32] = \\
                        base[(j-1)*32], base[(k-1)*32]
                    j -= pas
                    if j < 1:
                        break

    Le tri est donc **stable en fin de course** sur des noms distincts, mais
    l'egalite passe par `BLE` (L11046) : deux noms egaux ne sont jamais
    echange.
    """
    n = len(entrees)
    pas = n
    while True:
        pas >>= 1
        if pas == 0:                       # BEQ LAB_4628A (L11022)
            break
        d6 = 1                              # MOVEQ #1,D6 (L11025)
        while True:
            d5 = d6
            while True:
                d4 = d5 + pas               # L11030
                if entrees[d4 - 1] <= entrees[d5 - 1]:
                    break                   # BLE (L11046)
                entrees[d4 - 1], entrees[d5 - 1] = \
                    entrees[d5 - 1], entrees[d4 - 1]
                d5 -= pas                   # L11079
                if d5 < 1:                   # CMP #1 ; BGE (L11084)
                    break
            d6 += 1                          # L11087
            if d6 > n - pas:                 # CMP D7 ; BLE (L11088)
                break
    return entrees


def chemin_complet(dossier: str, nom: str) -> str:
    """Le collage de `(-80,A5)` avec `_filename` (L10832-L10872, L10884-10886).

    L10837-10863 : on prend le tiroir saisi, on cherche son **dernier**
    caractere, et s'il n'est ni `:` ni `/` on y ecrase un `/` ; puis on
    termine la chaine et on concatene le nom de fichier. C'est la seule
    fabrication de chemin du port.
    """
    base = dossier
    j = len(base) - 1                     # `strlen - 1` (L10860-10863)
    if j > 0:                             # `TST.W ; BLE` : rien a faire si 0 (L10864)
        if base[j] in (":", "/"):         # deja un separateur (L10868-L10873)
            base = base[:j + 1]           # LAB_4605A : NUL juste apres
        else:
            # L10874 `ADDQ #1` puis L10880 `MOVE.B #$2f` : le separateur est
            # ecrit a l'indice `strlen`, donc **par-dessus le zero** - aucun
            # caractere n'est perdu.
            base = base[:j + 1] + "/"     # LAB_4605A : NUL apres le '/'
    return base + nom                      # L10884-10886 `strcat`