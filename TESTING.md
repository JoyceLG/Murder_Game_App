# Tests — en local et en CI

Ce guide décrit comment lancer **toutes** les suites de tests sur un poste Linux (WSL2 Ubuntu
compris), puis ce que la CI exécute. L'environnement local tient dans **un seul venv** à la racine
du dépôt : il n'y a rien à installer sur le système et `sudo` n'est pas nécessaire.

## 1. Installation (une fois)

Prérequis : `git`, `curl` et `make` (présents par défaut sur Ubuntu).

```bash
make setup                 # ou : scripts/setup-dev.sh
source .venv/bin/activate  # facultatif : `make` trouve tout seul le venv
```

`make setup` est idempotent : on peut le relancer après un `git pull` qui change des dépendances.
Il installe tout dans `.venv/` :

| Outil | Version | Rôle | Fourni par |
|---|---|---|---|
| Python | 3.12 (comme la CI et l'image Docker) | API, tests, Alembic | [`uv`](https://docs.astral.sh/uv/) (installé dans `~/.local/bin` s'il manque) |
| Node.js | 20.20.2 | Angular, Karma | `nodeenv` |
| PostgreSQL | 16 | tests d'intégration | wheel `pgserver` (binaires officiels) |
| Chromium | celui de Playwright | tests Angular (Karma) et tests navigateur | `playwright install chromium` |

Les dépendances Python sont épinglées dans [`requirements-dev.txt`](requirements-dev.txt), qui
inclut [`murder-api/requirements.txt`](murder-api/requirements.txt) et
[`requirements-e2e.txt`](requirements-e2e.txt).

> **WSL : si Chromium refuse de démarrer** (bibliothèques système manquantes), `make setup`
> l'indique. Il faut alors lancer une fois, avec sudo :
> `sudo .venv/bin/playwright install-deps chromium`.

## 2. Les suites de tests

```bash
make help        # liste des commandes
make test        # rapide (~15 s) : API sur SQLite + tests unitaires Angular
make test-pg     # API sur un vrai PostgreSQL 16 + migrations + concurrence (~20 s)
make e2e         # bout en bout : API + WebSocket + navigateur (~15 s en local)
make ci          # tout ce que fait la CI : lint, test, test-pg, e2e
```

| Commande | Ce qui est testé | Base de données |
|---|---|---|
| `make lint` | `ruff check` + `ruff format --check` | — |
| `make test-api` | domaine, cas d'usage, API REST et WebSocket (in-process), adapter SQL ; seuil de couverture à 85 % | SQLite en mémoire |
| `make test-front` | services, écrans et composants Angular dans Chromium headless (Karma) | — |
| `make test-pg` | `alembic upgrade head` + `alembic check`, puis **toute** la suite API sur PostgreSQL, plus les tests propres à PostgreSQL (voir ci-dessous) | PostgreSQL 16 local |
| `make e2e` | la vraie stack démarrée, pilotée par le réseau (voir §3) | PostgreSQL 16 |

### Tests propres à PostgreSQL (`-m postgres`)

Ils sont sautés sur SQLite et tournent avec `make test-pg` et en CI :

- `tests/adapters/test_sql_concurrency.py` : de vraies transactions concurrentes sur des
  connexions séparées, **sans** le verrou applicatif (ce qui simule plusieurs workers). On vérifie
  qu'aucune écriture n'est perdue et que les conflits donnent des 409 propres, jamais une erreur 500.
- `tests/migrations/test_migrations.py` : migrations Alembic sur une base créée pour l'occasion.
  On teste l'upgrade jusqu'à `head`, l'absence d'écart avec les modèles, l'aller-retour
  `downgrade base` → `upgrade head`, et qu'une partie enregistrée avant la migration 0002 reste
  jouable après.

### PostgreSQL local

`make test-pg` et `make e2e` démarrent eux-mêmes un PostgreSQL jetable avec
[`scripts/pg.sh`](scripts/pg.sh). Il écoute sur `127.0.0.1:54329` et stocke ses données dans
`.tools/pg`. Le script utilise Docker s'il est disponible, sinon les binaires de `pgserver` du venv.

```bash
scripts/pg.sh url              # démarre si besoin et affiche l'URL de murder_test
make pg-stop                   # arrête et supprime les données
TEST_DATABASE_URL=… make test-api   # pour viser un autre PostgreSQL
```

### Lancer un sous-ensemble

```bash
cd murder-api && ../.venv/bin/pytest tests/domain -q --no-cov
cd murder-api && TEST_DATABASE_URL="$(../scripts/pg.sh url)" ../.venv/bin/pytest -m postgres --no-cov
```

## 3. Tests de bout en bout (`e2e/`)

Ils pilotent une stack **démarrée pour de vrai**, par le réseau, comme le font les clients :

| Fichier | Contenu |
|---|---|
| `e2e/test_api_flow.py` | une partie complète à trois joueurs en REST et WebSocket : vue propre à chaque joueur, cibles en anneau, revendication et confirmation, usurpation refusée (401), fin de partie et classement conservé ; reconnexion, codes de fermeture 4401/4403/4404, ping/pong, arrivées simultanées |
| `e2e/test_browser.py` | deux joueurs jouent une partie complète dans **Chromium**, en interface française : création, arrivée avec le code, lancement, rechargement de page en cours de jeu, kill confirmé, confirmation du changement de mission, fin de partie. Le test échoue si la console affiche une erreur (par exemple une violation de CSP). Vérifie aussi l'interface anglaise. |
| `e2e/test_proxy.py` | ce qu'ajoute nginx : en-têtes de sécurité et CSP, absence de script en ligne, cache (`no-cache` sur `index.html` et les traductions, cache long sur les bundles), liens profonds de la SPA, proxy de l'API |

Deux façons de démarrer la stack ([`scripts/e2e.sh`](scripts/e2e.sh)) :

```bash
make e2e-local     # sans Docker : PostgreSQL (pg.sh) + Alembic + uvicorn + ng serve (build de prod, proxy /games), ports libres
make e2e-compose   # comme la CI : docker compose (nginx :8080 + API + PostgreSQL), images rebâties
make e2e           # compose si Docker répond, sinon local
```

En mode `local`, l'application est le build de **production** servi par `ng serve`, avec un proxy
`/games` (WebSocket compris) vers l'API : même origine et URLs relatives, comme derrière nginx. Les
ports sont choisis libres, donc une stack déjà lancée sur 8000/8080 ne gêne pas. Les vérifications
propres à nginx (`test_proxy.py`) sont **sautées**, faute de nginx. Pour les lancer sur WSL, activez Docker Desktop → *Settings → Resources → WSL integration*
pour votre distribution, puis lancez `make e2e-compose`.

Options utiles (tout argument est transmis à pytest) :

```bash
scripts/e2e.sh local -k browser --headed        # voir le navigateur jouer
scripts/e2e.sh local -k full_game -x -vv
```

En cas d'échec, `e2e/test-results/` contient les captures d'écran, les traces Playwright
(`.venv/bin/playwright show-trace e2e/test-results/**/trace.zip`) et les logs des serveurs
(`api.log`, `front.log` ou `compose.log`).

On peut aussi viser une stack déjà lancée :

```bash
cd e2e && E2E_APP_URL=http://localhost:8080 E2E_NGINX=1 ../.venv/bin/python -m pytest
```

## 4. En CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml))

À chaque push sur `develop` ou `main` et sur chaque PR (déclenchement manuel possible) :

1. **backend** : ruff, `alembic upgrade head` + `alembic check` sur un service PostgreSQL 16, puis
   `pytest` sur ce même PostgreSQL, tests de concurrence et de migration compris.
2. **frontend** : `npm run build` + tests Karma (`ChromeHeadlessNoSandbox`).
3. **e2e** (après les deux précédents) : `scripts/e2e.sh compose`. Ce job construit les deux images
   Docker, démarre la stack compose, joue les trois fichiers de `e2e/` (vérifications nginx
   comprises) et publie `e2e/test-results/` en artefact s'il échoue.
