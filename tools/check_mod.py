"""Verifie si les fichiers de son sont des modules ProTracker.

Le format ProTracker commence par une signature de 20 octets :

    "M.K." / "M!K!" / "4CHN" / "6CHN" / "8CHN" / "FLT4" / "FLT8" / "CD81"
    puis 31 mots de noms de samples, 1 octet "restart", puis le titre
    sur 20 octets, puis 1 octet "number of samples" (a partir de offset 600).

On cherche cette signature dans les trois fichiers extraits.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "reference" / "original" / "extracted"

SIGS = (b"M.K.", b"M!K!", b"M&K!", b"N.T.", b"FLT4", b"FLT8", b"CD81",
        b"OKTA", b"OCTA", b"2CHN", b"4CHN", b"6CHN", b"8CHN")


def main() -> None:
    for name in ("popsam", "gmusic1", "gwords"):
        d = (SRC / name).read_bytes()
        print("=== %s (%d octets) ===" % (name, len(d)))
        found = [(s.decode("latin-1"), d.find(s)) for s in SIGS]
        for sig, pos in found:
            if pos >= 0:
                print("  signature %-5s a l offset %d" % (sig, pos))
        if not any(p >= 0 for _, p in found):
            print("  aucune signature ProTracker")
        # les 4 premiers octets, pour reconnaissance
        print("  4 premiers : %r  (%s)"
              % (d[:4], d[:4].hex(" ")))


if __name__ == "__main__":
    main()