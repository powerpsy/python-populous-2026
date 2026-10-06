# Consignes pour ce projet

## Comment poser une question

Quand une decision me revient — choix d'implementation, arbitrage de
portee, doute sur une intention — je pose la question **avec l'outil de
dialogue** (`question`), en proposant des **choix concrets et chiffres**, et
non en prose.

Deux exigences :

1. **Toujours des options.** Jamais de question ouverte du type « que
   pensez-vous ? ». Au moins deux options realistes, la premiere etant celle
   que je recommande, avec le titre `(Recommande)`.
2. **Un choix par question.** Le dialogue demande une seule chose a la fois ;
   si j'ai trois arbitrages a trancher, j'en fais trois dialogues, pas un
   seul avec trois options melangees.

Une option « Aucune de ces reponses » est ajoutee automatiquement : si
l'utilisateur ne veut pas trancher, il le dit et je continue avec mon
choix par defaut au lieu de bloquer.

Si je n'ai **aucune** decision a lui rendre, je ne pose pas de question : je
travaille et je rends compte du resultat.

## Ce projet

Remake de **Populous** (Amiga, 1989) en Python, reconstruit **a partir du
desassemblage** du binaire original.

- Le code d'origine fait foi. Quand une source tierce et le listing se
  contredisent, **le listing gagne**.
- Le port est valide **par execution**, pas par relecture : un calcul se
  verifie en confrontant le code a une reecriture independante du listing,
  sur plusieurs centaines de cas.
- Toute transcription cite le numero de ligne du listing (`L####`).
- Les ecarts assumes sont marques et documentes, pas caches.

## Documentation et langue

- Les documents du projet sont **en francais** : `docs/`, `README.md`, et les
  commentaires qui caveats l'asm.
- `docs/PROGRESSION.md` est le journal de travail : une section par phase,
  avec ce qui est verifie et ce qui reste ouvert.
- Une decision d'architecture non triviale se justifie par le listing, pas
  par la preference.

## Verification avant de dire « c'est fait »

```bash
python tools\autopilot.py 59 0 3   # 68 controles d'interaction
python tools\check_render.py       # rendu et transparence
python tools\check_assets.py       # decodage des assets
python tools\smoke_sim.py          # 5000 tours de simulation
python tools\stress.py 2000 8      # N graines x M tours, invariants
```

Un travail de simulation est **`[APPROX]`** tant qu'il n'est pas transcrit
ligne a ligne du listing. `[APPROX]` se leve par transcription, pas par
accord — et l'echec d'une verification se signale, il ne s'etouffe pas.