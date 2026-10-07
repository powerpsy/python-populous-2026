r"""L'arithmetique du 68000 — ce que le processeur fait vraiment.

Un `int` Python est de taille illimitée. Un registre du 68000 fait **16 ou 32
bits** et **boucle**. Toute valeur calculee dans un registre du listing est
donc censee revenir a zero au passage de la borne — et cela change le
comportement, pas seulement l'affichage.

C'est la source d'ecarts la plus discrete du port : le code Python « fait
sens », donne les memes resultats sur les cas nomines, et diverge des que
l'overflow est atteint. Ce module rend la borne explicite.

Recettes du listing utilisees ici :

.. code-block:: none

    ADD.W D1,(4,A0)      # vie += ...     : MOT   -> boucle a 0x10000
    ADD.L D1,(A0)       # mana += ...     : LONG  -> boucle a 0x100000000
    ADDI.L #$000003e7,D1                                  -> D1 = 32 bits
    MOVE.W D1,(-6,A5)    # copie en mot    : TRONQUE le mot bas
    TST.W D0 / BEQ      # test 16 bits signee
    CMP.W D0,D1 / BGE   # compare 16 bits signee

Deux conversions distinctes, a ne pas confondre :

* **la troncature** (`to_word`) : un mot lu dans un long, ou ecrit depuis un
  long — on garde les 16 bits bas ;
* **l'extension de signe** (`to_long_word`) : un mot lu comme un long
  Arithmetic : `MOVEA.L (8,A5),A0` et non `MOVEA.W`.

Exemple du piège, tire de `check_life` : l'accumulateur `D4` est un mot.
Quatre rochers le font tomber sous zero ; le 68000 le ramene a `0xFFF1`.
Teste ensuite par `CMP.W #$0023 / BGE`, il apparait **tres grand** — donc le
seuil n'est jamais atteint, et le villageois ne se scinde pas. En Python,
sans boucle, le score reste negatif : le resultat parait correct et le
verdict, lui, est oppose.
"""
from __future__ import annotations

MASQUE16 = 0xFFFF
MASQUE32 = 0xFFFFFFFF


def to_word(v: int) -> int:
    """ Tronque a 16 bits : un mot 68000, en valeur non signee.

    C'est ce que fait ``MOVE.W source,destination`` quand la source est plus
    large, et ce que subit une valeurNegative ecrasee dans un champ mot.
    """
    return v & MASQUE16


def to_long_word(v: int) -> int:
    """Etend un mot sur 32 bits **avec signe**.

    C'est le resultat de ``MOVE.W`` vers un long, qui passe par
    ``MOVEA.L (8,A5),A0`` : le bit 15 est repete sur les 16 bits hauts.
    Un parametre passe en `char` dans le listing se lit donc en **signe**.
    """
    v &= MASQUE16
    return v - 0x10000 if v & 0x8000 else v


def s16(v: int) -> int:
    """La valeur d'un mot 68000, lue comme **signee** (-32768..32767)."""
    v &= MASQUE16
    return v - 0x10000 if v & 0x8000 else v


def s32(v: int) -> int:
    """La valeur d'un long 68000, lue comme signee."""
    v &= MASQUE32
    return v - 0x100000000 if v & 0x80000000 else v


def add_word(a: int, b: int) -> int:
    """``ADD.W`` : addition 16 bits qui **boucle**.

    C'est l'operation qui rend le port faux quand on l'omet : une valeur
    qui depasse `0xFFFF` revient a zero au lieu de continuer a monter.
    """
    return (a + b) & MASQUE16


def add_long(a: int, b: int) -> int:
    """``ADD.L`` : addition 32 bits qui boucle."""
    return (a + b) & MASQUE32


def test_word_eq_zero(v: int) -> bool:
    """``TST.W D0 / BEQ`` : le mot vaut-il zero ?"""
    return (v & MASQUE16) == 0


def test_word_neg(v: int) -> bool:
    """``TST.W`` + branchement **negative** : bit 15 a 1."""
    return bool(v & 0x8000)


def cmp_word_ge(a: int, b: int) -> bool:
    """``CMP.W src,Dn / BGE`` : compare **signee** de 16 bits, ``a >= b``.

    `CMP.W source, destination` calcule ``destination - source`` et positionne
    les drapeaux ; ``BGE`` branche donc si ``destination >= source``. Les deux
    operandes sont signes, ce qui compte des qu'un depasse `0x7FFF`.
    """
    return s16(a) >= s16(b)


def cmp_word_lt(a: int, b: int) -> bool:
    """``CMP.W src,Dn / BLT`` : ``destination < source``, en signe."""
    return s16(a) < s16(b)


def cmp_word_gt(a: int, b: int) -> bool:
    """``CMP.W src,Dn / BGT`` : ``destination > source``, en signe.

    Attention, c'est aussi ce que fait `TST.W D0 / BGT` avec une source nulle :
    `TST` ne pose que le bit N, donc `BGT` y teste simplement le **signe**.
    Une vie reboulee sous zero vaut `0xFFxx`, le bit 15 est pose, et `BGT`
    ne passe pas : la valeur est donc comptee comme **morte**.
    """
    return s16(a) > s16(b)


def cmp_byte_ge(a: int, b: int) -> bool:
    """Comparaison d'octets signee (``CMP.B``), 8 bits."""
    def s8(x: int) -> int:
        x &= 0xFF
        return x - 0x100 if x & 0x80 else x
    return s8(a) >= s8(b)


def cmp_byte_le(a: int, b: int) -> bool:
    """``CMP.B`` : ``destination <= source``, en signe."""
    def s8(x: int) -> int:
        x &= 0xFF
        return x - 0x100 if x & 0x80 else x
    return s8(a) <= s8(b)


def mulu_word(a: int, b: int) -> int:
    """``MULU.W`` : produit 16 bits non signes, resultat sur 32 bits.

    Une seule ecriture, donc pas de saturation : le resultat tient sur 32 bits.
    """
    return (a & MASQUE16) * (b & MASQUE16)


def divu_word(a: int, b: int) -> int:
    """``DIVU.W`` : quotient **non signe**, reste dans le mot bas."""
    a &= MASQUE16
    b &= MASQUE16
    if b == 0:
        raise ZeroDivisionError("DIVU.W par zero — l'asm leve une exception")
    return a // b


def divs_word(a: int, b: int) -> int:
    """``DIVS.W`` : quotient signe, tronque vers zero."""
    b &= MASQUE16
    if b == 0:
        raise ZeroDivisionError("DIVS.W par zero")
    q = abs(s16(a)) // abs(s16(b))
    return -q if (s16(a) < 0) != (s16(b) < 0) else q


def divs_long(a: int, b: int) -> int:
    """``_divs`` (L23385-23395) : quotient signe **long**, tronque vers zero.

    .. code-block:: none

        CLR.L  D4
        TST.L  D0 / BPL      ; si D0 < 0 : NEG.L D0, D4 |= 1
        TST.L  D1 / BPL      ; si D1 < 0 : NEG.L D1, D4 ^= 1
        BSR.S  SUB_50EEE     ; division NON SIGNEE de |D0| par |D1|
        TST.W  D4 / BEQ      ; D4 != 0 -> NEG.L D0
        TST.L  D0 / RTS      ; les ports sont les flags de D0

    On normalise les deux signes, on divise en **valeur absolue**, puis on
    re-rend le signe : c'est exactement la troncature vers zero de C, et non
    ``a // b`` de Python (qui tronque vers moins l'infini).

    Le resultat reste **signe** (l'asm laisse un long dans D0) ; c'est
    ``_move_mana`` qui en prend le mot bas via ``MOVE.W D0,D5``.
    """
    a = s32(a)
    b = s32(b)
    if b == 0:
        raise ZeroDivisionError("_divs par zero — l'asm leve une exception")
    q = abs(a) // abs(b)
    if (a < 0) != (b < 0):
        q = -q
    return s32(q)                   # D0 reste signe pour l'appelant


def asr_word(v: int, n: int) -> int:
    """``ASR.W`` : decalage arithmetique a droite, en signee."""
    return to_word(s16(v) >> n)


def asl_word(v: int, n: int) -> int:
    """``ASL.W`` : decalage logique a gauche, sur 16 bits."""
    return to_word((v & MASQUE16) << n)