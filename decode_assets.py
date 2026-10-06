"""Decode tous les graphiques Populous extraits en PNG + WAV.

Formats connus (retro-ingenes depuis la desassemblage du jeu, cf.
reference/tetracorp/populous_prg.asm) :

  ecran        : 320x200, 4 plans, layout "plan-major"
                 plan p = octets [p*8000 .. p*8000+8000], ligne y a p*8000+y*40
  tuile landN  : 114 octets d'entete + 70 tuiles de 480 octets
                 = 24 lignes x [masque.l][p0.l][p1.l][p2.l][p3.l]  (32x24 px)
  sprite 16    : 160 octets = 16 lignes x [masque.w][p0][p1][p2][p3] (16x16 px)
  sprite 32    : 640 octets = 32 lignes x [masque.l][p0.l][p1.l][p2.l][p3.l]
  bouches      : 6 images de 48x35, 35 lignes x 6 octets x 4 plans (sans masque)
  .pic         : 32000 octets = 4 plans x 8000 (plan-major)
  load.pic     : 40000 octets = 5 plans x 8000 + 64 octets de palette (32 mots)
  lord.pic     : 32000 + 32 octets de palette (16 mots)
  font         : 40 octets/glyphe = 8 lignes x [masque.b][p0][p1][p2][p3]
                 (8x8 px), glyphe i = caractere (32+i)
  level.dat    : 99 entrees de 10 octets
"""
import json
import os
import struct
import wave

from PIL import Image

SRC_DATA = r"S:\OpenCode\Populous\extracted"              # disque de donnees
SRC_GAME = r"S:\OpenCode\Populous\reference\original\extracted"  # jeu original
OUT = r"S:\OpenCode\Populous\assets"

# Palette du jeu (symbole _palette, populous_prg.asm ligne 24264)
PALETTE = [0x0000, 0x0444, 0x0666, 0x0888, 0x0aaa, 0x0ccc, 0x0620, 0x0840,
           0x0a00, 0x0a60, 0x0aa0, 0x04a0, 0x0280, 0x0262, 0x0248, 0x026c]


def rgb4(word):
    """Mot de couleur Amiga $0RGB (4 bits par canal) -> RGB 8 bits."""
    return ((word >> 8 & 15) * 17, (word >> 4 & 15) * 17, (word & 15) * 17)


def palette_flat(words):
    flat = []
    for w in words:
        flat += list(rgb4(w))
    return flat


def new_image(w, h, words):
    img = Image.new("P", (w, h))
    img.putpalette(palette_flat(words))
    return img


# ---------------------------------------------------------------- images
def planar(data, w, h, planes, layout="plane_major"):
    """Renvoie une image indices de couleur (0..2^planes-1)."""
    img = Image.new("P", (w, h))
    px = img.load()
    rb = w // 8
    ps = rb * h
    for y in range(h):
        for x in range(w):
            bi, bit = x // 8, 7 - (x % 8)
            val = 0
            for p in range(planes):
                if layout == "plane_major":
                    off = p * ps + y * rb + bi
                else:
                    off = (y * planes + p) * rb + bi
                if off < len(data) and (data[off] >> bit) & 1:
                    val |= 1 << p
            px[x, y] = val
    img.putpalette(palette_flat(PALETTE))
    return img


def masked_rows(data, w, h, mask_bytes, row_bytes):
    """Decode des lignes [masque][4 plans] en big-endian.

    mask_bytes = 1 (mot) ou 2 (long) ; chaque plan a la meme largeur.
    Pixel : couleur = somme des bits des 4 plans ; 0 = transparent.
    """
    plane_bytes = mask_bytes * 2
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    pal = palette_flat(PALETTE)
    for y in range(h):
        base = y * row_bytes
        if base + row_bytes > len(data):
            break
        planes_val = [
            int.from_bytes(
                data[base + mask_bytes * 2 + p * plane_bytes:
                     base + mask_bytes * 2 + (p + 1) * plane_bytes], "big")
            for p in range(4)
        ]
        bits = plane_bytes * 8
        for x in range(min(w, bits)):
            idx = 0
            bp = bits - 1 - x
            for p in range(4):
                if planes_val[p] >> bp & 1:
                    idx |= 1 << p
            if idx:
                px[x, y] = (*pal[idx * 3:idx * 3 + 3], 255)
    return img


def sheet(images, cols, cell, path, zoom=2, labels=False):
    """Assemble des images RGBA dans une planche, avec grille."""
    from PIL import ImageDraw
    n = len(images)
    rows = (n + cols - 1) // cols
    cw, ch = cell
    W = cols * (cw + 2) * zoom
    H = rows * (ch + 2) * zoom
    sh = Image.new("RGBA", (W, H), (40, 40, 40, 255))
    for i, im in enumerate(images):
        big = im.resize((im.width * zoom, im.height * zoom), Image.NEAREST)
        cx = (i % cols) * (cw + 2) * zoom
        cy = (i // cols) * (ch + 2) * zoom
        sh.alpha_composite(big, (cx, cy))
    sh.convert("RGB").save(path)
    return path


# ---------------------------------------------------------------- land
def load_land(path):
    b = open(path, "rb").read()
    hdr = {
        "walk_death": struct.unpack_from(">H", b, 0)[0],
        "population_add": list(struct.unpack_from(">11H", b, 2)),
        "mana_add": list(struct.unpack_from(">11H", b, 24)),
        "weapons_add": list(struct.unpack_from(">11H", b, 46)),
        "battle_add1": list(struct.unpack_from(">11H", b, 68)),
        "battle_add2": list(struct.unpack_from(">3H", b, 90)),
        "map_colour": list(b[96:112]),
        "sprites_no": struct.unpack_from(">H", b, 112)[0],
    }
    body = b[114:]
    ntiles = len(body) // 480
    tiles = [body[i * 480:(i + 1) * 480] for i in range(ntiles)]
    return hdr, tiles


def tile_image(data, mask_bytes=2):
    """Tuile 32x24 (longs) ou 16x16 (mots)."""
    w = 32 if mask_bytes == 2 else 16
    h = 24 if mask_bytes == 2 else 16
    rb = (mask_bytes * 2 + 4 * mask_bytes * 2)
    return masked_rows(data, w, h, mask_bytes, rb)


# ---------------------------------------------------------------- sounds
def load_sound(path):
    """Format _load_sound (populous_prg.asm ligne 20712)."""
    b = open(path, "rb").read()
    i = 0
    measln = list(struct.unpack_from(">64H", b, i)); i += 128
    seqlen = struct.unpack_from(">H", b, i)[0]; i += 2
    seq = b[i:i + seqlen * 4]; i += seqlen * 4
    measure_length = struct.unpack_from(">I", b, i)[0]; i += 4
    measures = b[i:i + 4096]; i += 4096
    if measure_length > 4096:
        # Seek(file, measure_length-4096, OFFSET_CURRENT) : la section des
        # mesures dure mesure_length octets au total (cf. _load_sound).
        i += measure_length - 4096
    no_sounds = struct.unpack_from(">H", b, i)[0]; i += 2
    drumkit = b[i:i + no_sounds * 8]; i += no_sounds * 8
    n_samples = struct.unpack_from(">H", b, i)[0]; i += 2
    sams = b[i:i + n_samples * 8]; i += n_samples * 8
    all_len = struct.unpack_from(">I", b, i)[0]; i += 4
    pcm = b[i:i + all_len]
    lens = [struct.unpack_from(">H", sams, k * 8)[0] for k in range(n_samples)]
    return {"measln": measln, "seqlen": seqlen, "seq": seq,
            "measure_length": measure_length, "measures": measures,
            "no_sounds": no_sounds, "drumkit": drumkit,
            "n_samples": n_samples, "lens": lens, "pcm": pcm,
            "file_len": len(b), "eof": i + all_len}


def write_wav(path, data, rate=16000):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(rate)
        w.writeframes(bytes((d + 128) & 0xFF for d in data))


# ---------------------------------------------------------------- level
LEVEL_DESC = {
    0: "enemy rating", 1: "enemy reaction speed", 2: "powers for enemy",
    3: "powers for you", 4: "game mode", 5: "terrain type",
    6: "your starting population", 7: "enemy starting population",
}


def load_levels(path):
    b = open(path, "rb").read()
    rows = []
    for k in range(len(b) // 10):
        e = b[k * 10:(k + 1) * 10]
        rows.append({
            "n": k, "enemy_rating": e[0], "reaction": e[1],
            "enemy_powers": e[2], "player_powers": e[3],
            "game_mode": e[4], "terrain": e[5],
            "pop_player": e[6], "pop_enemy": e[7],
            "seed": (e[8] << 8) | e[9],
        })
    return rows


# ---------------------------------------------------------------- main
def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(OUT, "sounds"), exist_ok=True)
    rep = {}

    # --- palettes des .pic -------------------------------------------------
    load_pic = open(os.path.join(SRC_GAME, "load.pic"), "rb").read()
    pal32 = list(struct.unpack_from(">32H", load_pic, 40000))
    rep["load.pic palette"] = ["%03x" % w for w in pal32]

    lord = open(os.path.join(SRC_GAME, "lord.pic"), "rb").read()
    pal16_lord = list(struct.unpack_from(">16H", lord, 32000))

    # --- images 4 plans ----------------------------------------------------
    for name in ("qaz.pic", "demo.pic"):
        b = open(os.path.join(SRC_GAME, name), "rb").read()
        img = planar(b, 320, 200, 4)
        img.putpalette(palette_flat(PALETTE))
        img.convert("RGB").save(os.path.join(OUT, name.split(".")[0] + ".png"))
        rep[name] = "320x200 4 plans (ecran principal)"

    img = planar(lord[:32000], 320, 200, 4)
    img.putpalette(palette_flat(pal16_lord))
    img.convert("RGB").save(os.path.join(OUT, "lord.png"))
    rep["lord.pic"] = "320x200 4 plans + palette 16 mots %s" % [
        "%03x" % w for w in pal16_lord]

    # load.pic : 5 plans + palette 32 mots
    img = planar(load_pic[:40000], 320, 200, 5)
    img.putpalette(palette_flat(pal32))
    img.convert("RGB").save(os.path.join(OUT, "load.png"))
    rep["load.pic"] = "320x200 5 plans (EHB) + palette 32 mots"

    # --- bouches -----------------------------------------------------------
    m = open(os.path.join(SRC_GAME, "mouths.pic"), "rb").read()
    frames = []
    for k in range(len(m) // 840):
        blk = m[k * 840:(k + 1) * 840]
        im = Image.new("RGBA", (48, 35), (0, 0, 0, 0))
        px = im.load()
        pal = palette_flat(PALETTE)
        for y in range(35):
            base = y * 24
            for x in range(48):
                bi = x // 8
                bit = 7 - (x % 8)
                idx = 0
                for p in range(4):
                    if blk[base + p * 6 + bi] >> bit & 1:
                        idx |= 1 << p
                if idx:
                    px[x, y] = (*pal[idx * 3:idx * 3 + 3], 255)
        frames.append(im)
    sheet(frames, 6, (48, 35), os.path.join(OUT, "mouths.png"), zoom=4)
    rep["mouths.pic"] = "%d images 48x35, 4 plans, sans masque" % len(frames)

    # --- tuiles de paysage -------------------------------------------------
    for land in ("land0", "land1", "land2", "land3", "land4"):
        for folder, tag in ((SRC_GAME, ""), (SRC_DATA, "")):
            p = os.path.join(folder, land)
            if not os.path.exists(p):
                continue
            hdr, tiles = load_land(p)
            imgs = [tile_image(t, 2) for t in tiles]
            sheet(imgs, 10, (32, 24), os.path.join(OUT, f"{land}_tiles.png"),
                  zoom=3)
            rep[land] = {"header": hdr, "n_tiles": len(tiles)}
            with open(os.path.join(OUT, f"{land}_header.json"), "w") as f:
                json.dump(hdr, f, indent=1)
            break

    # --- sprites -----------------------------------------------------------
    for name, mb in (("sprites0.dat", 1), ("sprites4.dat", 1),
                     ("spr_320.dat", 2)):
        for folder in (SRC_GAME, SRC_DATA):
            p = os.path.join(folder, name)
            if not os.path.exists(p):
                continue
            b = open(p, "rb").read()
            w = 16 if mb == 1 else 32
            h = 16 if mb == 1 else 32
            # une ligne = w/16 blocs de 10 octets : [masque.w][p0][p1][p2][p3]
            # (_draw_s et _draw_s_32 lisent 5 mots par bloc de 16 pixels)
            stride = (w // 16) * 10
            rec = stride * h
            n = len(b) // rec
            imgs = []
            for k in range(n):
                d = b[k * rec:(k + 1) * rec]
                im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                px = im.load()
                pal = palette_flat(PALETTE)
                for y in range(h):
                    for c in range(w // 16):
                        o = y * stride + c * 10
                        pl = [int.from_bytes(d[o + 2 + q * 2:o + 4 + q * 2],
                                             "big") for q in range(4)]
                        for x in range(16):
                            bp = 15 - x
                            idx = sum(((pl[q] >> bp) & 1) << q
                                      for q in range(4))
                            if idx:
                                px[c * 16 + x, y] = (
                                    *pal[idx * 3:idx * 3 + 3], 255)
                imgs.append(im)
            cols = 12
            sheet(imgs, cols, (w, h),
                  os.path.join(OUT, name.replace(".", "_") + ".png"), zoom=4)
            rep[name] = "%d sprites %dx%d" % (n, w, h)
            break

    # --- font --------------------------------------------------------------
    font = open(os.path.join(SRC_GAME, "font.dat"), "rb").read()
    glyphs = []
    for g in range(len(font) // 40):
        d = font[g * 40:(g + 1) * 40]
        im = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        px = im.load()
        pal = palette_flat(PALETTE)
        for y in range(8):
            base = y * 5
            mask = d[base]
            for x in range(8):
                idx = 0
                for q in range(4):
                    if d[base + 1 + q] >> (7 - x) & 1:
                        idx |= 1 << q
                if idx:
                    px[x, y] = (*pal[idx * 3:idx * 3 + 3], 255)
        glyphs.append(im)
    sheet(glyphs, 16, (8, 8), os.path.join(OUT, "font.png"), zoom=6)
    rep["font.dat"] = "%d glyphes 8x8 (40 octets, masque+4 plans)" % len(glyphs)

    # --- level.dat ---------------------------------------------------------
    rows = load_levels(os.path.join(SRC_GAME, "level.dat"))
    with open(os.path.join(OUT, "level_dat.json"), "w") as f:
        json.dump(rows, f, indent=1)
    rep["level.dat"] = "%d entrees de 10 octets" % len(rows)

    # --- sons --------------------------------------------------------------
    for name in ("gmusic1", "gwords"):
        for folder in (SRC_GAME, SRC_DATA):
            p = os.path.join(folder, name)
            if not os.path.exists(p):
                continue
            try:
                s = load_sound(p)
            except Exception as exc:                     # noqa: BLE001
                rep[name] = "ERREUR %s" % exc
                break
            rep[name] = {
                "taille": s["file_len"], "mesures_len": s["seqlen"],
                "sequence": s["seq"][:32].hex(" "),
                "measure_length": s["measure_length"],
                "no_sounds": s["no_sounds"], "n_samples": s["n_samples"],
                "lens": s["lens"][:24], "pcm": len(s["pcm"]),
                "fin_lue": s["eof"],
            }
            write_wav(os.path.join(OUT, "sounds", f"{name}.wav"), s["pcm"])
            # export des echantillons individuels
            off = 0
            d = os.path.join(OUT, "sounds", name)
            os.makedirs(d, exist_ok=True)
            for k, ln in enumerate(s["lens"]):
                if ln and off + ln <= len(s["pcm"]):
                    write_wav(os.path.join(d, f"{k:03d}.wav"),
                              s["pcm"][off:off + ln])
                off += ln
            break

    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(rep, f, indent=1, ensure_ascii=False)
    print(json.dumps(rep, indent=1, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    main()
