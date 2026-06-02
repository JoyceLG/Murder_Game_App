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
Murder_app/
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
pas de CORS. L'API applique le schéma au démarrage et bascule sur PostgreSQL via `DATABASE_URL`.

---

## Développement & tests

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
npm test -- --watch=false --browsers=ChromeHeadless
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
- **WebSocket** : remplace les `watchDoc`/`watchCollection` de Firestore. Le serveur pousse l'état
  complet ; le client Angular dérive sa propre vue (cible, mission, réclamation entrante) — port
  fidèle du `_recompute` JS, via des signals.
- **DTO ≠ entités** : un mapper unique (`to_game_out`) est la seule frontière anti-corruption.

## Limites assumées

- **WebSocket mono-worker** : les connexions sont en mémoire de processus ⇒ `uvicorn --workers 1`.
  Une mise à l'échelle multi-worker nécessiterait un backplane pub/sub (Redis). Firestore jouait
  ce rôle dans la version JS.
- **Identité non signée** : le `player_id` est généré serveur (uuid4 inguessable) et transmis via
  l'en-tête `X-Player-Id`. Suffisant pour la démo ; un **JWT signé** est l'étape de durcissement.
- **Fin de partie paresseuse** : l'état « terminé » est calculé à la lecture (pas de scheduler).
  En production, une tâche de fond gérerait l'expiration sans lecture.

---

## CI/CD

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) : sur chaque push/PR →
`ruff` + `pytest --cov` (avec un service **PostgreSQL** pour les tests d'intégration), `npm run build`
+ tests Angular en ChromeHeadless, puis **build des images Docker**.
