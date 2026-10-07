# -*- coding: utf-8 -*-
"""Confrontation de Terrain.rotate_all_map a une reecriture independante.

L'implementation est lue depuis populous/terrain.py. La reference ci-dessous
est reecrite DIRECTEMENT depuis le listing (L6824-6921), avec la semantique
68000 explicite : mots signes sur 16 bits, BGE signe, BCS/BHI non signes.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from populous.terrain import Terrain, N_VERTS, N_CELLS  # noqa: E402


def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def ref(alt, bk2):
    """_rotate_all_map, reecriture independante depuis le listing."""
    # ---- bloc _alt, L6830-6868 ------------------------------------------
    D5 = 0x1080
    D4 = 0
    while True:
        # 43034: MOVE.W D5,D0 / ASR.W #1  puis  CMP.W D0,D4 / BLT
        if not (s16(D4) < (s16(D5) >> 1)):
            break
        i = D4
        j = s16(D5 - D4)                  # MOVE.W D5,D1 / SUB.W D4,D1
        # 42ff0: MOVE.W (0,A0,D0.L),D2     -- D2 = alt[i], mot SIGNE
        D2 = s16(alt[i])
        # 42ff4: CMP.W (0,A1,D1.L),D2      -- alt[i] - alt[j], flags SIGNED
        mem_j = s16(alt[j])
        if not (D2 >= mem_j):             # BGE non pris -> fall-through
            alt[i] = mem_j                # 43010: alt[i] = alt[j]
        alt[j] = s16(alt[i])              # 43016: alt[j] = alt[i] (inconditionnel)
        D4 = (D4 + 1) & 0xFFFF            # 43032: ADDQ.W #1,D4

    # ---- bloc _map_bk2, L6874-6904 ---------------------------------------
    D5 = 0x0FFF
    D4 = 0
    while True:
        # 430a4: MOVE.W D5,D0 / ASR.W #1   puis CMP.W D0,D4 / BLT
        if not (s16(D4) < (s16(D5) >> 1)):
            break
        j = s16(D5 - D4) & 0xFFFF
        # BCS / BHI sont des comparaisons d'octets NON SIGNEES
        v = bk2[D4] & 0xFF
        if v >= 0x32 and v <= 0x37:
            bk2[j] = v                    # 43068: bk2[j] = bk2[D4]
        else:
            w = bk2[j] & 0xFF
            if w >= 0x32 and w <= 0x37:
                bk2[D4] = w               # 4309c: bk2[D4] = bk2[j]
        D4 = (D4 + 1) & 0xFFFF


def copie(t, alt, bk2):
    t.alt = list(alt)
    t.bk2 = bytearray(bk2)
    return t


def main():
    random.seed(20261007)
    essais = 400
    ecarts = []
    for n in range(essais):
        # alt : valeurs signees, pour exercer le BGE signe
        alt_a = [random.randint(-3, 8) for _ in range(N_VERTS)]
        # bk2 : octets complets, avec une proportion realiste d'arbres
        bk2_a = [random.choice(
            [random.randint(0, 255), random.randint(0, 255),
             random.randint(0x30, 0x39), 0, 15])
            for _ in range(N_CELLS)]

        t1 = copie(Terrain(0, 0), alt_a, bk2_a)
        t1.rotate_all_map()

        t2 = copie(Terrain(0, 0), alt_a, bk2_a)
        ref(t2.alt, t2.bk2)
        t2.make_map(0, 0, 0x3F, 0x3F)

        for nom, a, b in (("alt", t1.alt, t2.alt),
                          ("bk2", bytes(t1.bk2), bytes(t2.bk2)),
                          ("blk", bytes(t1.blk), bytes(t2.blk)),
                          ("disp_alt", bytes(t1.disp_alt), bytes(t2.disp_alt)),
                          ("steps", t1.steps, t2.steps)):
            if a != b:
                if len(ecarts) < 6:
                    k = next(i for i in range(len(a)) if a[i] != b[i])
                    ecarts.append("essai %d, %s[%d] : %r != %r"
                                  % (n, nom, k, a[k], b[k]))
                else:
                    ecarts.append("essai %d, %s" % (n, nom))

    # --- proprietes attendues, mesurées sur le dernier essai -------------
    t = copie(Terrain(0, 0), [random.randint(0, 8) for _ in range(N_VERTS)],
              bytearray(random.randint(0, 255) for _ in range(N_CELLS)))
    av = list(t.alt)
    t.rotate_all_map()
    sym = sum(1 for i in range(2112)
              if t.alt[i] == t.alt[4224 - i] and t.alt[i] == max(av[i], av[4224 - i]))
    centre = t.alt[2112] == av[2112]
    # bornes de boucle, arithmetique pure (0x0FFF>>1 = 2047 ; 0x1080>>1 = 2112)
    dernier_i_bk2 = ((0x0FFF >> 1) - 1)
    dernier_i_alt = ((0x1080 >> 1) - 1)

    print("essais                : %d" % essais)
    if ecarts:
        print("ECARTS                : %d" % len(ecarts))
        for e in ecarts[:6]:
            print("   ", e)
        return 1
    print("ECARTS                : 0   (alt, bk2, blk, disp_alt, steps)")
    print()
    print("controles de structure :")
    print("  paires (i,4224-i) au max          : %d / 2112" % sym)
    print("  sommet central 2112 inchange      : %s" % centre)
    print("  derniers i parcourus              : alt=%d  bk2=%d"
          % (dernier_i_alt, dernier_i_bk2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

