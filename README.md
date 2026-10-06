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
| `[` / `]` | ouvrir la boîte de conquete / changer de palier |
| `Entrée` | valider la saisie du numéro de palier |
| `Échap` | annuler |

L'interface suit celle de l'original : pas de raccourcis clavier inventés, la
sélection passe par la barre d'icônes et la palette en bas à gauche.

## Vérification

Le port est validé par exécution, pas par relecture.

```bash
python tools/autopilot.py 59 0 3    # 68 contrôles d'interaction
python tools/check_render.py        # rendu, blits, transparence
python tools/check_assets.py        # décodage des assets
python tools/smoke_sim.py           # 5000 tours de simulation
```

`autopilot.py` passe 68/68 sur plusieurs graines (1, 7, 42, 59, 99, 200, 314).

## Ce qui est porté

| système | état |
|---|---|
| simulation | `_move_peeps`, `_set_frame`, `_set_town`, `_join_battle`, `_set_magnet_to`, `_do_battle` |
| pouvoirs | les 4 pouvoirs de terrain, vérifiés au coût exact de mana |
| interface | `_zoom_map`, `_sculpt`, `_interogate`, `_draw_icon`, `_draw_bar`, `_toggle_icon`, `_text`, `_requester` |
| conquete | `level.dat` (99 paliers), boîte « TRY NUMBER », écran de fin |
| son | horloge audio L19620-19673, tempo dérivé de la population |

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

## À propos de ce dépôt

Ce dépôt est distinct de
[`powerpsy/python-populous`](https://github.com/powerpsy/python-populous), qui
est une autre implémentation Python du même jeu. Les deux projets partagent le
nom du jeu, pas leur architecture.