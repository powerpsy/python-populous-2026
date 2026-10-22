# python-populous

Remake de **Populous** (Amiga, 1989 — Bullfrog Productions / Electronic Arts)
en Python, reconstruit **à partir du désassemblage du binaire original**.

La différence avec une réimplémentation classique : la simulation et
l'interface ne sont pas réinterprétées, elles sont **transcrites instruction
par instruction** depuis le listing. Quand le code source et le
désassemblage se contredisent, c'est le désassemblage qui fait foi.

## Lancer

```bash
pip install -r requirements.txt
python -m populous.game [graine] [sol] [zoom]
```

Par défaut : graine 1, sol 0, zoom 3.

## Commandes

| touche | effet |
|---|---|
| clic gauche | palettes d'outils et d'icônes (comme l'original) |
| flèches | faire défiler la vue d'une case (`scroll_w` ... `scroll_e`, L773-831) |
| clic mini-carte | recentrer la vue |
| `[` / `]` | ouvrir la boîte de conquete / changer de palier |
| `Entrée` | valider la saisie du numéro de palier |
| `Échap` | annuler |

L'interface suit celle de l'original : pas de raccourcis clavier inventés, la
sélection passe par la barre d'icônes et la palette en bas à gauche.

**La vue s'ouvre en (0, 0)** — le coin haut-gauche — car c'est ce que fait
`_animate` (L507-508). L'original **ne recentre jamais** la vue au démarrage :
les flèches et la mini-carte sont les seuls moyens de se déplacer. Les
habitants sont placés par un balayage qui démarre en (0, 2) (L7688), juste
sous cette vue initiale ; ils peuvent donc se trouver hors écran sur une
carte où la première case plane est loin du bord.

## Vérification

Le port est validé par exécution, pas par relecture.

```bash
python tools\autopilot.py 59 0 3   # 84 controles d'interaction
python tools\check_render.py       # rendu et transparence
python tools\check_assets.py       # decodage des assets
python tools\check_funny.py        # _do_place_funny (Phase 56)
python tools\check_do_funny.py     # _do_funny (Phase 88)
python tools\check_equilibre.py    # equilibrage des deux tribus (Phase 88)
python tools\check_powers.py       # les 4 pouvoirs, 37 controles (Phase 89)
python tools\check_intro.py        # intro, 217 controles (Phase 87)
python tools\check_mod.py          # banque popsam (Phase 86)
python tools\smoke_sim.py          # 5000 tours de simulation
python tools\stress.py 2000 8      # N graines x M tours, invariants
```

## Ce qui est porté

| système | état |
|---|---|
| simulation | `_move_peeps`, `_set_frame`, `_set_town`, `_join_battle`, `_set_magnet_to`, `_do_battle` |
| pouvoirs | les 4 pouvoirs de terrain, vérifiés au coût exact de mana |
| interface | `_zoom_map`, `_sculpt`, `_interogate`, `_draw_icon`, `_draw_bar`, `_toggle_icon`, `_text`, `_requester` |
| conquete | `level.dat` (99 paliers), boîte « TRY NUMBER », écran de fin |
| son | horloge audio L19620-19673, tempo dérivé de la population, musique de fond par fichier |

Le détail, phase par phase, avec les numéros de ligne du listing, est dans
[`docs/PROGRESSION.md`](docs/PROGRESSION.md).

## Structure

```
populous/        le jeu
  game.py        fenêtre, boucle d'image, interaction
  sim.py         la simulation (_move_peeps et compagnie)
  render.py      rendu du terrain, des sprites, de l'interface
  powers.py      les pouvoirs
  sound.py       le lecteur audio et son horloge
  musique.py     la musique de fond (reference/*.mp3)
  conquest*.py   la conquete
  assets.py      décodage des assets (PIL)
  terrain.py     génération du relief
assets/          sprites, icônes, polices, cartes extraites
reference/       le listing de référence et les fichiers extraits
tools/           extraction, vérification, autopilot
docs/            notes de progression et de logique
```

## Licence

Le code de ce dépôt est sous licence MIT.

⚠️ **Les données d'origine** (`reference/`) — sprites, sons, polices, cartes —
proviennent du jeu original et restent la propriété d'Electronic Arts. Les
images disque `*.adf` sont exclues du suivi par `.gitignore` : ce sont
l'œuvre elle-même, pas du code.