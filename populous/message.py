# -*- coding: utf-8 -*-
"""`_do_message` — la boite « INSERT THE ORIGINAL POPULOUS DISK IN DF0: ».

Sous-systeme transcrit en Phase 82. ``_do_message(texte, annuler)``
(L11098-11139) est la **seule** routine de dialogue que ce port n'avait pas
encore : les deux autres, ``_get_a_message`` (L11143) et
``_serial_message`` (L11185), n'ont pour appelants que les handlers de la
liaison serie, donc hors portee.

Le listing appelle ``_do_message`` a trois endroits, toujours avec la meme
chaine ``strInsertDisk`` (L21255-21256) :

* ``_save_load``, quand ``level.dat`` n'est pas lisible apres une
  sauvegarde — `_do_message(strInsertDisk, 0)` (L10943-10950) ;
* ``_show_world``, quand l'entree voulue de ``level.dat`` n'a pu etre lue
  — `_do_message(strInsertDisk, 0)` (L12370-12376) ;
* ``_load_ground``, quand ``Open("LANDn")`` rend nul —
  `_do_message(strInsertDisk, ($A,A5))` (L16611-16622). C'est le seul
  appel qui peut passer ``annuler = 1`` : L18985 le fait.

``annuler`` decide si le bouton CANCEL existe. Comme ``_end_cancel`` est
pose a zero (L11105-11106), ``_check_cancel(_end_ok, NULL)`` ne peut rendre
que 0 ou 1 : **sans CANCEL la boite est infinie**, et c'est bien ce que
veut le listing, qui boucle jusqu'a ce que le disque soit la.
"""

#: `_requester(_d_screen, $28, $3C, $100, $30, _end_ok, (-4))`
#: (L11108-11116) : x, y, largeur, hauteur.
MESSAGE_BOXE = (0x28, 0x3C, 0x100, 0x30)

#: `_text(_d_screen, $38, $48, texte)` (L11117-11122). `x` est en
#: **pixels** — c'est `_text` qui divise par 8 (L19978).
MESSAGE_X = 0x38
MESSAGE_Y = 0x48

#: Les deux chaines des structures ``_end_ok`` / ``_end_cancel``
#: (L24349-24361). Ce port ne garde que le texte : ``_requester`` ne pose
#: pas les boutons et ``Game._cadres_boutons`` recalcule leurs cadres.
MESSAGE_OK = "OK"
MESSAGE_CANCEL = "CANCEL"

#: `strInsertDisk` (L21255-21256). Le `$0A` du listing est un saut de
#: ligne : `_text` le rend par `+0x140`, soit huit lignes (L19985-19994).
INSERT_DISK = "INSERT THE ORIGINAL\nPOPULOUS DISK IN DF0:"
