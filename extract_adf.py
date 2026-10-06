"""
Extracteur ADF (Amiga Disk Format / OFS) pour Populous.adf
-----------------------------------------------------------
Structure constatee sur le disque (blocs de 512 octets, tout en big-endian) :

  En-tete (type primaire 2 = T_HEADER) :
    +0   long  type primaire (2)
    +4   long  cle = numero de ce bloc
    +8   long  high_seq  = nombre de blocs de donnees (fichier)
                           / 0 (repertoire)
    +12  long  hash_size = 72 pour le rootblock
    +16  long  1er bloc de donnees (fichier OFS) / hash chain
    +20  long  checksum : somme de tous les mots du bloc == 0 (mod 2^32)
    +24  ...    table de 72 longs : table de hash (repertoire)
                           / pointeurs de blocs de donnees range a l'envers
                             (slot 71 = 1er bloc de donnees, 72-n = dernier)
    +324 long  taille du fichier en octets (fichier seulement)
    +420 long  date : jours depuis le 01/01/1978
    +424 long  date : minutes
    +428 long  date : ticks (1/50 s)
    +432 byte  longueur du nom (0..30)
    +433 chars nom
    +500 long  bloc parent
    +508 long  type secondaire : 1 = root, 2 = repertoire, -3 = fichier

  Bloc de donnees OFS (type primaire 8 = T_DATA) :
    +0   long  8
    +4   long  cle = bloc d'en-tete du fichier
    +8   long  numero de sequence (1..N)
    +12  long  nombre d'octets utiles (<= 488)
    +16  long  bloc de donnees suivant (0 = fin)
    +20  ...    donnees (488 octets max)
"""
import os
import struct
import sys

ADF_PATH = r"S:\OpenCode\Populous\Populous.adf"
OUT_DIR = r"S:\OpenCode\Populous\extracted"
BS = 512

if len(sys.argv) >= 3:          # extract_adf.py <disque.adf> <repertoire>
    ADF_PATH, OUT_DIR = sys.argv[1], sys.argv[2]
elif len(sys.argv) == 2:
    ADF_PATH = sys.argv[1]


def s32(b, o):
    return struct.unpack(">i", b[o:o + 4])[0]


def u32(b, o):
    return struct.unpack(">I", b[o:o + 4])[0]


class ADFFS:
    def __init__(self, path):
        self.data = open(path, "rb").read()
        self.nblocks = len(self.data) // BS

    def blk(self, n):
        return self.data[n * BS:(n + 1) * BS]

    def checksum_ok(self, n):
        b = self.blk(n)
        return sum(struct.unpack(">128i", b)) % (2 ** 32) == 0

    # -- lecture d'en-tete -------------------------------------------------
    def header(self, n):
        b = self.blk(n)
        if s32(b, 0) != 2:
            return None
        namelen = b[432]
        name = b[433:433 + namelen].decode("latin-1")
        return {
            "block": n,
            "high_seq": s32(b, 8),
            "first_data": s32(b, 16),
            "size": u32(b, 324),
            "days": u32(b, 420),
            "mins": u32(b, 424),
            "ticks": u32(b, 428),
            "name": name,
            "parent": s32(b, 500),
            "sec": s32(b, 508),
            "hash_size": s32(b, 12),
            "table": [s32(b, 24 + 4 * i) for i in range(72)],
        }

    # -- contenu d'un fichier ---------------------------------------------
    def read_file(self, hdr):
        out = bytearray()
        n = hdr["first_data"]
        seen = set()
        while n > 0 and n not in seen:
            seen.add(n)
            b = self.blk(n)
            if s32(b, 0) != 8 or u32(b, 4) != hdr["block"]:
                raise ValueError(f"bloc de donnees invalide {n}")
            ln = s32(b, 12)
            out += b[24:24 + ln]
            n = s32(b, 16)
        return bytes(out)

    # -- parcours arborescence --------------------------------------------
    # Plutot que de suivre la table de hash (incomplete sur ce disque :
    # le repertoire 's' n'y figure pas), on scanne tous les en-tetes et
    # on reconstruit l'arbre via le champ parent (+500).
    def all_headers(self):
        out = []
        for n in range(self.nblocks):
            h = self.header(n)
            if h and h["sec"] in (1, 2, -3):
                out.append(h)
        return out

    def walk(self, block=None):
        if block is None:
            headers = self.all_headers()
            root = next(h for h in headers if h["sec"] == 1)
            block = root["block"]
        headers = {h["block"]: h for h in self.all_headers()}
        children = {}
        for h in headers.values():
            if h["block"] == block:
                continue
            children.setdefault(h["parent"], []).append(h)

        results = []

        def rec(blknum, path):
            h = headers[blknum]
            if h["sec"] == -3:
                results.append((path + h["name"], h))
            else:
                sub = path + (h["name"] + "/" if h["sec"] == 2 else "")
                for c in sorted(children.get(blknum, []), key=lambda x: x["block"]):
                    rec(c["block"], sub)

        rec(block, "")
        return results


def main():
    fs = ADFFS(ADF_PATH)
    print(f"ADF : {len(fs.data)} octets, {fs.nblocks} blocs")

    # localise le rootblock (type secondaire 1)
    root = None
    for n in range(fs.nblocks):
        h = fs.header(n)
        if h and h["sec"] == 1:
            root = n
            break
    print(f"rootblock = {root}  checksum OK = {fs.checksum_ok(root)}")

    entries = fs.walk()
    os.makedirs(OUT_DIR, exist_ok=True)

    manifest = []
    for rel, h in entries:
        content = fs.read_file(h)
        assert len(content) == h["size"], (rel, len(content), h["size"])
        dest = os.path.join(OUT_DIR, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(content)
        manifest.append((rel, h["size"], h["days"], h["mins"], h["ticks"], h["block"]))
        print(f"  {rel:32s} {h['size']:>8d}  bloc {h['block']}")

    print(f"\n{len(manifest)} fichiers extraits dans {OUT_DIR}")
    with open(os.path.join(OUT_DIR, "_manifest.txt"), "w") as f:
        for m in manifest:
            f.write(f"{m[0]}\t{m[1]}\tbloc {m[5]}\n")


if __name__ == "__main__":
    main()
