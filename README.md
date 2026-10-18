# Murder — jeu multijoueur (FastAPI · architecture hexagonale · DDD · TDD · Docker · Angular · CI/CD)

Application web multijoueur de **murder party** : chaque joueur reçoit une cible secrète et une
mission ; on élimine sa cible, la cible confirme, on marque un point et on reçoit une nouvelle
cible. Le tout en temps réel.

Le jeu existait en JavaScript vanilla (voir [`legacy-js/`](legacy-js/)) ; il a été **réécrit en
architecture hexagonale** côté backend (Python/FastAPI) et **Angular 20** côté frontend.

> **Le fil rouge** : dans la version JS, la résolution d'une élimination était calculée *dans le
> navigateur de l'attaquant* (« confiance au client », limite assumée dans l'ancien README). La
> réécriture **centralise cette autorité côté serveur** : c'est le cas d'usage `ConfirmClaim`,
> déclenché par la **cible**, qui résout le score de façon autoritaire. La migration *corrige* le
> défaut, et c'est exactement ce que prouve le test `confirm by non-target → 403`.

---

## Stack

| Couche | Techno |
|--------|--------|
| API | **FastAPI** (async), Pydantic, WebSocket, OpenAPI/Swagger natif |
| Architecture | **Ports & adapters (hexagonale)**, **DDD**, **TDD** (pytest, 100 % de couverture) |
| Persistance | Adapter **in-memory** (tests) **+ PostgreSQL** (SQLAlchemy 2.0 async / asyncpg) |
| Front | **Angular 20** (standalone, signals, control-flow), RxJS pour le flux WebSocket |
| Infra | **Docker** multi-stage, **docker-compose** (front + api + postgres), **GitHub Actions** |

---

## Architecture hexagonale

```
                 driving (entrée)                          driven (sortie)
        ┌───────────────────────────┐          ┌──────────────────────────────┐
HTTP ─► │  api/ (FastAPI, WebSocket) │          │ adapters/                    │
        │  routes · schemas · DI     │          │  InMemoryGameRepository      │
        └─────────────┬─────────────┘          │  SqlGameRepository (Postgres)│
                      │ appelle                 │  WebSocketNotifier           │
                      ▼                          └──────────────▲───────────────┘
        ┌───────────────────────────┐   implémentent les ports │
        │ application/ (cas d'usage) │ ─────────────────────────┘
        │  CreateGame · StartGame …  │   dépend des ports (interfaces)
        └─────────────┬─────────────┘
                      │ utilise
                      ▼
        ┌───────────────────────────┐
        │ domain/  (cœur métier pur) │  AUCUN import de framework
        │  models · rules · missions │
        └───────────────────────────┘
```

**Règle de dépendance** : tout pointe vers l'intérieur. `domain` ne dépend de rien ; `application`
dépend de `domain` + des `ports` (interfaces `Protocol`) ; `adapters` et `api` dépendent vers
l'intérieur, jamais l'inverse. Conséquence concrète : **passer d'in-memory à PostgreSQL ne change
qu'une variable d'environnement** (`DATABASE_URL`) — aucune ligne de métier n'est touchée.

```
Murder_Game_App/
├── legacy-js/      # le prototype JavaScript d'origine (raconte la migration)
├── murder-api/     # backend Python — src/{domain,ports,application,adapters,api} + tests/
├── murder-front/   # front Angular 20 — core/{models,services,guards}, features/, shared/
├── docker-compose.yml
└── .github/workflows/ci.yml
```

---

## Lancer en une commande

```bash
docker compose up --build
```

- Front : <http://localhost:8080>
- API : <http://localhost:8000> · **Swagger : <http://localhost:8000/docs>**
- PostgreSQL : `localhost:5432`

Le front (servi par nginx) reverse-proxie `/games` et le WebSocket vers l'API : une seule origine,
pas de CORS (en dev, l'API accepte les origines listées dans `ALLOWED_ORIGINS`). L'API applique le schéma au démarrage et bascule sur PostgreSQL via `DATABASE_URL`.

---

## Développement & tests

Tout l'outillage (Python 3.12, Node 20, PostgreSQL 16, Chromium) s'installe dans un seul venv,
sans sudo. Le guide complet est dans **[TESTING.md](TESTING.md)**.

```bash
make setup       # une fois
make test        # API (SQLite) + Angular
make test-pg     # API + migrations + concurrence sur PostgreSQL
make e2e         # bout en bout : REST, WebSocket, navigateur
```

### Backend (`murder-api/`)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.api.main:app --reload        # API + Swagger sur :8000 (in-memory par défaut)
pytest                                    # tests + couverture (gate à 85 %, atteint 100 %)
ruff check . && ruff format --check .     # lint + format
```
Les tests d'intégration de l'adapter SQL tournent sur **SQLite** par défaut (rapides, sans Docker) ;
pointez `TEST_DATABASE_URL` sur un PostgreSQL pour exercer le même adapter sur la cible de prod.

### Frontend (`murder-front/`)
```bash
npm install
npm start                                 # ng serve sur :4200 (tape sur l'API :8000)
npm test -- --watch=false --browsers=ChromeHeadlessNoSandbox
npm run build                             # build de prod (bascule sur les URLs relatives)
```

---

## Choix techniques (et pourquoi)

- **FastAPI plutôt que Flask** : typage Pydantic de bout en bout (DTO d'entrée/sortie validés),
  `async` natif (cohérent avec un repository asyncpg et un canal WebSocket), et OpenAPI/Swagger
  généré automatiquement.
- **Ports asynchrones** : `GameRepository` et `RealtimeNotifier` sont des `Protocol` `async`. Le
  domaine reste **synchrone et pur** ; seules les frontières I/O sont asynchrones.
- **Aléa injecté** (`Picker`) : les règles ne connaissent pas `random`, ce qui rend le domaine
  **déterministe en test** (>90 % visé, 100 % atteint sur `domain/`).
- **WebSocket** : remplace les `watchDoc`/`watchCollection` de Firestore. Après chaque changement,
  le serveur pousse à **chaque joueur sa propre vue** : sa mission et sa cible ne sont envoyées qu'à
  lui (personne ne peut lire dans l'onglet réseau qui le chasse). Le socket s'authentifie par son
  premier message ; le client se reconnecte avec un délai croissant et envoie un `ping` régulier.
- **DTO ≠ entités** : un mapper unique (`to_player_view`) est la seule frontière anti-corruption.
- **Identité** : l'`id` d'un joueur est public (il apparaît dans le classement) ; ce qui prouve
  qu'on est ce joueur, c'est un **secret de session** remis une seule fois à la création ou à
  l'arrivée en partie (`player_token`) et renvoyé dans `X-Player-Token`. Le serveur n'en stocke que
  l'empreinte SHA-256.
- **Concurrence** : un verrou par partie sérialise les requêtes, et chaque sauvegarde vérifie la
  `version` de la partie (verrouillage optimiste, 409 en cas de conflit) : aucune mise à jour
  n'est perdue, même sur PostgreSQL.
- **Cibles en anneau** : au lancement, les joueurs forment un cycle (chacun chasse un joueur et est
  chassé par un seul). Après un kill, l'attaquant échange sa cible avec un autre chasseur quand
  c'est possible, pour garder l'anneau.

## Limites assumées

- **WebSocket mono-worker** : les connexions sont en mémoire de processus ⇒ `uvicorn --workers 1`.
  Une mise à l'échelle multi-worker nécessiterait un backplane pub/sub (Redis). Firestore jouait
  ce rôle dans la version JS.
- **Secret de session plutôt que JWT** : le secret est opaque et vérifié en base. Un **JWT signé**
  (phase 17) le remplacera derrière le même point d'entrée (`dependencies.player_id`).
- **Fin de partie paresseuse** : l'état « terminé » est calculé à la lecture (pas de scheduler) puis
  diffusé. Quand son compte à rebours (corrigé de l'écart d'horloge avec le serveur) atteint zéro,
  le client relit l'état, ce qui déclenche la clôture et sa diffusion à tous.
- **Limites de débit en mémoire** : par IP (création de parties, codes inexistants pour freiner
  l'énumération, requêtes globales) ; comme les WebSockets, valables pour un seul worker. Les
  parties de plus de `GAME_TTL_HOURS` (24 h) sont purgées.

---

## CI/CD

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) : sur chaque push/PR →
`ruff` + `alembic check` + `pytest --cov` sur un service **PostgreSQL** (tests de concurrence et de
migration compris), `npm run build` + tests Angular (`ChromeHeadlessNoSandbox`), puis les **tests de
bout en bout** sur la stack `docker compose` (images construites, nginx, REST, WebSocket, Chromium).
Détails : [TESTING.md](TESTING.md).
