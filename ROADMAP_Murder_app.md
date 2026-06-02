# Roadmap — Migration Murder_app

**Objectif** : migrer Murder_app vers une stack moderne — **FastAPI · architecture hexagonale · DDD · TDD (pytest) · Docker · Angular · CI/CD** — en capitalisant sur l'architecture déjà écrite.

**Point de départ (état actuel du repo)** : JavaScript vanilla, logique de jeu (`game.js`) isolée derrière une interface backend abstraite (`watchDoc`, `getDoc`, `setDoc`, `updateDoc`, `deleteDoc`), avec deux implémentations interchangeables (mémoire / Firestore). **Cette séparation logique/infra EST le pattern ports & adapters.** On la rejoue proprement en Python.

> Idée directrice : ton `game.js` est un domaine métier qui ne connaît que des *ports*. On le réécrit en Python comme cœur testé en TDD, on rebranche les adapters autour (in-memory, FastAPI, WebSocket), puis on habille en Angular et on conteneurise.

---

## Vue d'ensemble des phases

| Phase | Contenu | Durée estimée |
|------|---------|---------------|
| 0 | Setup projet & outillage | 0,5 j |
| 1 | Domaine en TDD | 2-3 j |
| 2 | Ports & adapter in-memory | 1 j |
| 3 | Cas d'usage (application) | 1-2 j |
| 4 | API REST FastAPI + WebSocket | 2-3 j |
| 5 | Conteneurisation Docker | 1 j |
| 6 | Front Angular | 3-4 j |
| 7 | CI/CD & finition | 1 j |

Total réaliste en projet perso : **3 à 4 semaines** à temps partiel. Les phases 1 à 4 couvrent l'essentiel ; Angular (6) est le bonus.

---

## Architecture cible (hexagonale)

```
murder-api/
├── src/
│   ├── domain/                 # cœur métier — AUCUN import de framework
│   │   ├── models.py           # Game, Player, Claim, enums (dataclasses)
│   │   ├── missions.py         # catalogue de missions
│   │   ├── rules.py            # règles pures : assignation, résolution, scoring
│   │   └── errors.py           # exceptions métier (GameNotFound, AlreadyStarted…)
│   ├── ports/                  # interfaces (contrats) — Protocol
│   │   ├── repository.py       # GameRepository (get/save/delete)
│   │   └── notifier.py         # RealtimeNotifier (push d'état aux joueurs)
│   ├── application/            # cas d'usage — orchestrent domaine + ports
│   │   ├── create_game.py
│   │   ├── join_game.py
│   │   ├── start_game.py
│   │   ├── claim_elimination.py
│   │   ├── confirm_claim.py
│   │   └── end_game.py
│   ├── adapters/               # implémentations concrètes des ports
│   │   ├── memory_repository.py
│   │   └── ws_notifier.py
│   └── api/                    # adapter "driving" : FastAPI
│       ├── main.py             # app FastAPI, wiring (dependency injection)
│       ├── routes.py           # endpoints REST
│       ├── websocket.py        # canal temps réel
│       └── schemas.py          # DTO Pydantic (entrée/sortie API)
├── tests/
│   ├── domain/                 # tests unitaires purs (rapides, sans I/O)
│   ├── application/            # tests des cas d'usage (avec repo in-memory)
│   └── api/                    # tests d'intégration (TestClient FastAPI)
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── README.md
```

**Le principe clé** : les dépendances pointent toujours **vers l'intérieur**. `domain` ne dépend de rien. `application` dépend de `domain` et des `ports` (interfaces). Les `adapters` et `api` dépendent de l'intérieur, jamais l'inverse. On peut remplacer FastAPI ou la persistance sans toucher au métier — exactement ce que tu fais déjà entre `backend-memory` et `backend-firestore`.

---

## Phase 0 — Setup & outillage (0,5 j)

**But** : un projet Python propre, testable, prêt pour le TDD.

Tâches :
1. Créer une branche `python-rewrite` (on garde la version JS dans l'historique — montre la migration).
2. Initialiser le projet :
   ```bash
   mkdir murder-api && cd murder-api
   python -m venv .venv && source .venv/bin/activate
   pip install fastapi "uvicorn[standard]" pydantic pytest pytest-cov httpx ruff
   pip freeze > requirements.txt
   ```
3. `pyproject.toml` avec config `ruff` (lint + format) et `pytest` (`--cov=src`).
4. Premier test bidon qui passe (`tests/test_smoke.py`) pour valider la tuyauterie.


---

## Phase 1 — Le domaine en TDD (2-3 j)

**But** : porter la logique de `game.js` en Python pur, **en écrivant les tests d'abord**.

### Modèle (domain/models.py)
Reprends ton modèle Firestore existant, typé :
```python
from dataclasses import dataclass, field
from enum import Enum

class GameStatus(str, Enum):
    LOBBY = "lobby"; RUNNING = "running"; ENDED = "ended"

class ClaimStatus(str, Enum):
    PENDING = "pending"; OK = "ok"; NO = "no"

@dataclass
class Player:
    id: str
    name: str
    score: int = 0
    mission: str = ""
    target_id: str | None = None

@dataclass
class Game:
    code: str
    host_id: str
    status: GameStatus = GameStatus.LOBBY
    duration_sec: int = 0
    players: dict[str, Player] = field(default_factory=dict)
    # claims, timestamps…
```

### Règles (domain/rules.py)
Les fonctions pures que tu as déjà en JS, à porter en TDD :
- **assignation des cibles** (`assign_targets`) : chaque joueur reçoit une cible et une mission ; pas d'auto-ciblage ; gestion du cas "2 joueurs".
- **résolution d'une élimination** (`resolve_claim`) : si confirmée → +1 point, nouvelle cible (différente de l'ancienne si possible), nouvelle mission ; si refusée → nouvelle mission seulement.
- **classement** (`ranking`) : tri par score décroissant.

### Boucle TDD à appliquer pour chaque règle
1. **Rouge** : écris le test qui décrit le comportement attendu.
   ```python
   def test_resolve_claim_ok_increments_score_and_reassigns():
       game = a_running_game_with(["alice", "bob", "carol"])
       resolve_claim(game, attacker_id="alice", confirmed=True)
       assert game.players["alice"].score == 1
       assert game.players["alice"].target_id != "alice"
       assert game.players["alice"].mission != ""
   ```
2. **Vert** : écris le minimum de code pour faire passer le test.
3. **Refactor** : nettoie sans casser les tests.

**Objectif de couverture** : >90% sur `domain/` (c'est du code pur, c'est atteignable).

---

## Phase 2 — Ports & adapter in-memory (1 j)

**But** : formaliser les interfaces et fournir une première implémentation — l'équivalent Python de ton `backend-memory.js`.

### Port (ports/repository.py)
```python
from typing import Protocol
from domain.models import Game

class GameRepository(Protocol):
    def get(self, code: str) -> Game | None: ...
    def save(self, game: Game) -> None: ...
    def delete(self, code: str) -> None: ...
```

### Adapter (adapters/memory_repository.py)
```python
class InMemoryGameRepository:
    def __init__(self) -> None:
        self._games: dict[str, Game] = {}
    def get(self, code): return self._games.get(code)
    def save(self, game): self._games[game.code] = game
    def delete(self, code): self._games.pop(code, None)
```


---

## Phase 3 — Cas d'usage / application (1-2 j)

**But** : orchestrer domaine + ports dans des cas d'usage testés (toujours en TDD, avec le repo in-memory comme double de test).

Un cas d'usage = une intention métier :
```python
class CreateGame:
    def __init__(self, repo: GameRepository):
        self.repo = repo
    def execute(self, host_name: str) -> Game:
        game = Game(code=generate_code(), host_id=generate_id())
        # … ajoute l'hôte comme premier joueur
        self.repo.save(game)
        return game
```
Cas à couvrir : `CreateGame`, `JoinGame`, `StartGame` (déclenche `assign_targets`), `ClaimElimination`, `ConfirmClaim` (déclenche `resolve_claim`), `EndGame`.

Tests d'application : on injecte `InMemoryGameRepository`, on appelle `execute`, on vérifie l'état. Rapides, sans réseau.


---

## Phase 4 — API REST FastAPI + temps réel (2-3 j)

**But** : exposer les cas d'usage via FastAPI. C'est l'adapter "driving" — il dépend de l'application, jamais l'inverse.

### Endpoints REST (api/routes.py)
| Méthode | Route | Cas d'usage |
|---------|-------|-------------|
| POST | `/games` | CreateGame |
| POST | `/games/{code}/players` | JoinGame |
| POST | `/games/{code}/start` | StartGame |
| POST | `/games/{code}/claims` | ClaimElimination |
| POST | `/games/{code}/claims/{id}/confirm` | ConfirmClaim |
| GET | `/games/{code}` | état courant |

### Schémas (api/schemas.py)
DTO Pydantic en entrée/sortie — ne jamais exposer directement les entités du domaine. Ça montre que tu sépares le contrat d'API du modèle interne.

### Temps réel (api/websocket.py)
Remplace les `watchDoc`/`watchCollection` de Firestore : un endpoint `WebSocket /games/{code}/live` qui push l'état à chaque changement. Implémente le port `RealtimeNotifier`.

### Wiring (api/main.py)
Injection des dépendances via `Depends` de FastAPI : c'est ici, et seulement ici, qu'on choisit `InMemoryGameRepository` (ou autre demain).

### Tests d'intégration
```python
from fastapi.testclient import TestClient
def test_create_then_join_game():
    r = client.post("/games", json={"host_name": "Alice"})
    code = r.json()["code"]
    r2 = client.post(f"/games/{code}/players", json={"name": "Bob"})
    assert r2.status_code == 201
```


---

## Phase 5 — Conteneurisation Docker (1 j)

**But** : packager l'API.

`Dockerfile` (multi-stage, image légère) :
```dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`docker-compose.yml` pour lancer API (+ front Angular plus tard) en une commande.

---

## Phase 6 — Front Angular (3-4 j, bonus "apprécié")

**But** : remplacer le front vanilla par Angular, consommant l'API REST + WebSocket.

Tâches :
1. `ng new murder-front` (Angular CLI).
2. Un **service** `GameService` qui appelle l'API REST (HttpClient) et écoute le WebSocket.
3. Composants : `HomeComponent` (créer/rejoindre), `LobbyComponent`, `GameComponent` (ma mission, ma cible, bouton "j'ai éliminé"), `EndComponent` (classement).
4. Reprends ton thème "dossier d'agence" (`style.css`) — l'identité visuelle est déjà là.

> Astuce : commence par traduire ton `ui.js` actuel composant par composant. La logique d'affichage existe déjà, tu la restructures en Angular.


---

## Phase 7 — CI/CD & finition (1 j)

**But** : automatiser.

1. **GitHub Actions** (`.github/workflows/ci.yml`) : sur chaque push → `ruff check`, `pytest --cov`, build Docker. Tu peux afficher un badge de couverture dans le README.
2. **README** clair : schéma de l'archi hexagonale, comment lancer (`docker compose up`), comment tester (`pytest`), choix techniques expliqués.
3. Optionnel : déployer une démo (Railway, Fly.io, ou Firebase Hosting pour le front).

**Prouve** : CI/CD (GitHub Actions cette fois, en plus de ton Bitbucket pro), souci de la qualité et de la transmission (un README qui explique = posture de référent).

---

## Conseils de séquencement

- **Ne saute pas le TDD des phases 1 et 3** : c'est le cœur de l'architecture hexagonale.
- Fais des **commits petits et parlants** (`test: assignation cible`, `feat: endpoint create game`).
- **Documente tes choix au fil de l'eau** dans le README, pas à la fin.
- Priorité phases 1→4 ; les phases suivantes enrichissent progressivement le projet.
