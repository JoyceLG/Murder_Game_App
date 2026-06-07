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

> **Phases 0→7 (migration) : terminées.** La suite — fondations « mobile-ready » (**Phase 8**, à traiter dès maintenant) puis déploiement des apps Android/iOS — est décrite en fin de document : voir [« Feuille de route — Déploiement mobile (Android + iOS) »](#feuille-de-route--déploiement-mobile-android--ios).

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


# Feuille de route — Déploiement mobile (Android + iOS)

**Objectif final** : distribuer Murder_app comme **apps natives Android + iOS via Capacitor** (le SPA Angular empaqueté dans une WebView native, publiable sur les stores), avec **notifications push** (jeu temps réel : être prévenu d'une élimination réclamée ou d'une confirmation à valider).

**Viabilité : l'architecture est prête, sans refonte.** Le backend FastAPI hexagonal est agnostique au client (une app mobile = un client REST + WebSocket de plus, le CORS est déjà activé) ; le front Angular 20 est exactement ce que Capacitor empaquette en réutilisant 100 % du code UI ; la session en `localStorage` fonctionne telle quelle en WebView. Le travail est donc surtout **opérationnel** (hébergement, durcissement, packaging), pas applicatif.

> **Séquencement** : seule la **Phase 8** est à traiter maintenant (anti-dette). Les **phases 9→13** se lanceront **après la prochaine série de features**.

## Vue d'ensemble (phases mobile)

| Phase | Contenu | Quand |
|------|---------|-------|
| 8 | Fondations « mobile-ready » | **Maintenant** |
| — | **Lot de features (issues #10–#16)** | **En cours** |
| 9 | Héberger le backend (HTTPS/WSS) | Après features |
| 10 | Durcissement multi-origine + auth JWT | Après features |
| 11 | Intégration Capacitor | Après features |
| 12 | Notifications push | Après features |
| 13 | Publication stores | Après features |

---

## Phase 8 — Fondations « mobile-ready » 

**But** : poser le minimum qui évite d'accumuler de la dette technique pendant qu'on développe les prochaines features. Tout le reste peut attendre, **pas ça**.

1. **Garde-fous architecturaux documentés** (fait) dans [CLAUDE.md](CLAUDE.md) — section « Mobile-ready guardrails ». Chaque nouvelle feature les respecte par construction : URLs jamais en dur (toujours via `environment.apiBase`/`wsBase`), identité via header `X-Player-Id`, pas d'API navigateur sans fallback WebView, responsive + safe-areas, backend 12-factor, notifications derrière un port.
2. **CORS par allowlist via env var.** Remplacer `allow_origins=["*"]` ([murder-api/src/api/main.py](murder-api/src/api/main.py)) par une liste lue dans `ALLOWED_ORIGINS` ([murder-api/src/api/config.py](murder-api/src/api/config.py)), incluant à terme les origines WebView (`capacitor://localhost`, `https://localhost`). Changement localisé, supprime le wildcard non-sûr.
3. **Config runtime du front centralisée.** `apiBase`/`wsBase` restent l'unique source des URLs ; interdire tout nouvel usage de `location.host`/`location.origin` hors de `core/services/realtime.ts`.

> Notes : 8.2 et 8.3 sont de petits chantiers à planifier (non bloquants tant que les garde-fous 8.1 sont respectés). L'auth JWT, plus lourde, est repoussée en Phase 10 car elle reste localisée derrière `dependencies.player_id` et n'accumule donc pas de dette.

---

## Lot de features — avant déploiement mobile (issues #10–#16)

**But** : étoffer le jeu avant de lancer le déploiement mobile (Phase 9+). Ce lot s'intercale entre
la Phase 8 et la Phase 9. Toutes les features respectent les garde-fous « mobile-ready » (Phase 8).

**Méthode de travail** (cf. `CLAUDE.md` › *Dev workflow*) : **une branche par issue** cuttée sur
`main` (`feat/<n>-<slug>`), **tests à jour + nouveaux tests** (gate 85 % back, ChromeHeadless front),
**scénarios de validation documentés dans le wiki GitHub** (une page par issue), **PR vers `main`**,
**revue complète + validation utilisateur avant merge** (squash).

| Issue | Feature | Dépend de |
|-------|---------|-----------|
| [#10](https://github.com/JoyceLG/Murder_app/issues/10) | i18n — infrastructure multilingue FR/EN + extraction des textes | — |
| [#11](https://github.com/JoyceLG/Murder_app/issues/11) | Config de partie : max points & max joueurs + endpoint config hôte | — |
| [#12](https://github.com/JoyceLG/Murder_app/issues/12) | Missions : bibliothèque locale (localStorage) + onglet de configuration | #10 |
| [#13](https://github.com/JoyceLG/Murder_app/issues/13) | Missions : pool de partie (contrib. tous joueurs, mode augmenter/remplacer) | #11, #12 |
| [#14](https://github.com/JoyceLG/Murder_app/issues/14) | i18n — traduire le catalogue de missions par défaut (catalogue → clés) | #10, #13 |
| [#15](https://github.com/JoyceLG/Murder_app/issues/15) | Gameplay : accusé de réception attaquant avant la prochaine mission | — |
| [#16](https://github.com/JoyceLG/Murder_app/issues/16) | UX : animations (attaqué / succès / refus / nouvelle mission) | #15 |

**Ordre conseillé** : #10 → #11 → #12 → #13 → #14 → #15 → #16 (l'i18n d'abord pour ne pas
re-traduire les textes ajoutés ensuite). Milestone GitHub : *« Features pré-déploiement mobile »*.

---

## Phase 9 — Héberger le backend en HTTPS/WSS

**But** : rendre l'API joignable par une app mobile (un `docker-compose` local ne suffit pas).

1. Déployer sur un hébergeur qui termine le TLS automatiquement — **Fly.io** ou **Railway** (Docker natif, Postgres managé, gratuit/peu cher). Réutiliser le [murder-api/Dockerfile](murder-api/Dockerfile) existant (déjà prod-ready, healthcheck inclus).
2. Provisionner PostgreSQL et injecter `DATABASE_URL` → bascule in-memory → Postgres sans toucher au code métier.
3. Vérifier le WebSocket derrière le TLS (`wss://…/games/{code}/live`).
4. Garder `uvicorn --workers 1` (contrainte WebSocket en mémoire process) tant que la charge le permet.

---

## Phase 10 — Durcissement multi-origine + auth JWT

**But** : sécuriser avant toute exposition publique.

1. Finaliser l'allowlist CORS (Phase 8.2) avec les vraies origines de prod + WebView.
2. **JWT** : signer le `player_id` côté serveur (uuid4 → JWT signé), vérifié dans `dependencies.player_id` ([murder-api/src/api/dependencies.py](murder-api/src/api/dependencies.py)) — empêche l'usurpation par `X-Player-Id` forgé. Étendre le garde-fou de test existant (« confirm by non-target → 403 »).

---

## Phase 11 — Intégration Capacitor

**But** : produire la première app installable (Android, puis iOS).

1. Dans `murder-front/` (toolchain Node 20 sur le PATH) : ajouter `@capacitor/core`, `@capacitor/cli`, puis `@capacitor/android` et `@capacitor/ios`.
2. `npx cap init` ; `webDir` = `dist/murder-front/browser`.
3. Créer un environnement Capacitor avec des **URLs absolues** (`apiBase: 'https://api.<domaine>'`, `wsBase: 'wss://api.<domaine>'`) — indispensable car en WebView `window.location` pointe sur `capacitor://localhost`.
4. Build Angular → `npx cap sync` → `npx cap add android` / `add ios` ; compiler via Android Studio / Xcode.
5. Tester sur **appareil réel** : créer/rejoindre une partie, réclamer/confirmer une élimination, push live via WebSocket, survie de session après fermeture/réouverture de l'app.
6. iOS : compilation/publication exigent **macOS + Xcode** et un **compte Apple Developer** (99 $/an).

---

## Phase 12 — Notifications push

**But** : prévenir le joueur hors-app (élimination à confirmer, confirmation reçue).

1. Côté app : plugin `@capacitor/push-notifications` ; intégration **FCM** (Android) et **APNs** (iOS).
2. Côté backend : enregistrer les tokens d'appareil par joueur, et **émettre un push** aux moments clés. Ajouter un **port `PushNotifier`** à côté de `RealtimeNotifier` et le déclencher là où le notifier temps réel l'est déjà — dans les cas d'usage `ClaimElimination` / `ConfirmClaim` — pour rester dans le pattern hexagonal.

---

## Phase 13 — Publication stores

**But** : mettre les apps en ligne.

1. **Android** : keystore de signature, build AAB, fiche Google Play Console (~25 $ une fois).
2. **iOS** : provisioning/signing Xcode, App Store Connect, fiche App Store.
3. Icônes / splash via `@capacitor/assets` ; politique de confidentialité ; tests internes avant release publique.
