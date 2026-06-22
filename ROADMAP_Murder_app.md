# Roadmap — Migration Murder_app

**Objectif** : migrer Murder_app vers une stack moderne — **FastAPI · architecture hexagonale · DDD · TDD (pytest) · Docker · Angular · CI/CD** — en capitalisant sur l'architecture déjà écrite.

**Point de départ (état actuel du repo)** : JavaScript vanilla, logique de jeu (`game.js`) isolée derrière une interface backend abstraite (`watchDoc`, `getDoc`, `setDoc`, `updateDoc`, `deleteDoc`), avec deux implémentations interchangeables (mémoire / Firestore). **Cette séparation logique/infra EST le pattern ports & adapters.** On la rejoue proprement en Python.

> Idée directrice : ton `game.js` est un domaine métier qui ne connaît que des *ports*. On le réécrit en Python comme cœur testé en TDD, on rebranche les adapters autour (in-memory, FastAPI, WebSocket), puis on habille en Angular et on conteneurise.

---

## Vue d'ensemble des phases

### Bloc 1 — Migration (Phases 0 → 7)

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

> **Phases 0→7 : terminées.**

### Bloc 2 — Features pré-déploiement mobile (Phases 8 → 15)

| Phase | Issue | Contenu | Durée estimée |
|------|-------|---------|---------------|
| 8 | — | Fondations « mobile-ready » | en cours |
| 9 | [#10](https://github.com/JoyceLG/Murder_app/issues/10) | i18n — infrastructure multilingue FR/EN | 2-3 j |
| 10 | [#11](https://github.com/JoyceLG/Murder_app/issues/11) | Config de partie : max points & max joueurs | 1-2 j |
| 11 | [#12](https://github.com/JoyceLG/Murder_app/issues/12) | Missions : bibliothèque locale + onglet de config | 2-3 j |
| 12 | [#13](https://github.com/JoyceLG/Murder_app/issues/13) | Missions : pool de partie (tous joueurs) | 2-3 j |
| 13 | [#14](https://github.com/JoyceLG/Murder_app/issues/14) | i18n — catalogue de missions par défaut | 1 j |
| 14 | [#15](https://github.com/JoyceLG/Murder_app/issues/15) | Gameplay : accusé de réception attaquant | 1-2 j |
| 15 | [#16](https://github.com/JoyceLG/Murder_app/issues/16) | UX : animations de jeu | 2-3 j |

**Total Bloc 2** : 12–18 jours à temps partiel.

### Bloc 3 — Déploiement mobile (Phases 16 → 20)

| Phase | Contenu | Quand |
|------|---------|-------|
| 16 | Héberger le backend (HTTPS/WSS) | Après Bloc 2 |
| 17 | Durcissement multi-origine + auth JWT | Après Bloc 2 |
| 18 | Intégration Capacitor | Après Bloc 2 |
| 19 | Notifications push | Après Bloc 2 |
| 20 | Publication stores | Après Bloc 2 |

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

**Le principe clé** : les dépendances pointent toujours **vers l'intérieur**. `domain` ne dépend de rien. `application` dépend de `domain` et des `ports` (interfaces). Les `adapters` et `api` dépendent de l'intérieur, jamais l'inverse.

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

### Temps réel (api/websocket.py)
Remplace les `watchDoc`/`watchCollection` de Firestore : un endpoint `WebSocket /games/{code}/live` qui push l'état à chaque changement. Implémente le port `RealtimeNotifier`.

---

## Phase 5 — Conteneurisation Docker (1 j)

**But** : packager l'API.

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

---

## Phase 7 — CI/CD & finition (1 j)

**But** : automatiser.

1. **GitHub Actions** (`.github/workflows/ci.yml`) : sur chaque push → `ruff check`, `pytest --cov`, build Docker. Badge de couverture dans le README.
2. **README** clair : schéma de l'archi hexagonale, comment lancer (`docker compose up`), comment tester (`pytest`), choix techniques expliqués.
3. Optionnel : déployer une démo (Railway, Fly.io, ou Firebase Hosting pour le front).

---


# Features pré-déploiement mobile

**Objectif final** : distribuer Murder_app comme **apps natives Android + iOS via Capacitor**, avec **notifications push**. Avant d'entrer dans la mécanique de déploiement (Bloc 3), ce bloc étoffe le jeu et pose les fondations qui évitent toute dette technique mobile.

---

## Phase 8 — Fondations « mobile-ready »

**But** : poser le minimum qui évite d'accumuler de la dette technique pendant qu'on développe les prochaines features. Tout le reste peut attendre, **pas ça**.

1. **Garde-fous architecturaux documentés** dans [CLAUDE.md](CLAUDE.md) — section « Mobile-ready guardrails ». Chaque nouvelle feature les respecte par construction : URLs jamais en dur (toujours via `environment.apiBase`/`wsBase`), identité via header `X-Player-Id`, pas d'API navigateur sans fallback WebView, responsive + safe-areas, backend 12-factor, notifications derrière un port.
2. **CORS par allowlist via env var.** Remplacer `allow_origins=["*"]` par une liste lue dans `ALLOWED_ORIGINS` ([murder-api/src/api/config.py](murder-api/src/api/config.py)), incluant à terme les origines WebView (`capacitor://localhost`, `https://localhost`).
3. **Config runtime du front centralisée.** `apiBase`/`wsBase` restent l'unique source des URLs ; interdire tout nouvel usage de `location.host`/`location.origin` hors de `core/services/realtime.ts`.

> Notes : 8.2 et 8.3 sont de petits chantiers à planifier (non bloquants tant que les garde-fous 8.1 sont respectés). L'auth JWT, plus lourde, est repoussée en Phase 17.

---

## Phase 9 — i18n : infrastructure multilingue FR/EN (issue #10) — 2-3 j

**But** : poser l'infrastructure de traduction une fois pour toutes, **avant** d'ajouter tout nouveau texte dans l'app. Toutes les phases suivantes bénéficient automatiquement du support FR/EN.

**Dépendances** : aucune.

### Backend
- Ajouter un champ `locale: str = "fr"` à `Player` (préférence linguistique stockée, non encore utilisée).
- Préparer `domain/missions.py` à recevoir des clés de traduction (le catalogue reste en français pour l'instant, la migration vers les clés arrivera en Phase 13).

### Frontend
- Intégrer **`@ngx-translate/core`** + `@ngx-translate/http-loader`.
- Créer `murder-front/src/assets/i18n/fr.json` et `en.json` avec **toutes** les chaînes UI existantes extraites des templates et des services.
- Un `LanguageSwitcherComponent` (header) qui persiste le choix dans `localStorage`.
- Le `GameStore` expose la locale courante ; les messages d'erreur HTTP sont localisés via un intercepteur.

### Tests
- Test unitaire Angular : changement de langue → les clés résolues changent.
- Test de non-régression : aucune chaîne brute en français dans les templates (lint custom ou convention de revue).

### Critères d'acceptation
- Toute l'UI bascule en EN sans recharger la page.
- Toute nouvelle chaîne ajoutée après cette phase doit passer par une clé i18n (bloquant en revue de PR).

---

## Phase 10 — Config de partie : max points & max joueurs (issue #11) — 1-2 j

**But** : permettre à l'hôte de configurer les règles de fin de partie avant de lancer le jeu.

**Dépendances** : aucune (peut tourner en parallèle de Phase 9).

### Backend
- Ajouter `max_score: int = 0` et `max_players: int = 0` à `Game` (`0` = illimité).
- Nouveau cas d'usage `ConfigureGame` (ou extension de `CreateGame`) : appelable par l'hôte tant que le jeu est en `LOBBY`.
- Endpoint `PATCH /games/{code}/config` — body `{ max_score, max_players }`, guard hôte uniquement.
- `settle_end` étendu : une partie se termine aussi quand un joueur atteint `max_score` (si > 0).
- `JoinGame` renvoie `GameFull` (409) si `max_players > 0` et la limite est atteinte.

### Frontend
- Dans `LobbyComponent`, panneau de config visible uniquement par l'hôte : champs `max_score` et `max_players` avec label i18n.
- Appel `PATCH /config` à chaque changement ; les non-hôtes voient les valeurs en lecture seule.

### Tests
- `test_game_ends_when_max_score_reached` (domain/application).
- `test_join_game_fails_when_lobby_full` (application).
- Test d'intégration FastAPI : `PATCH /config` par un non-hôte → 403.

### Critères d'acceptation
- L'hôte peut définir `max_score = 3` → la partie se termine automatiquement au 3e point.
- L'hôte peut définir `max_players = 6` → le 7e joueur qui tente de rejoindre reçoit une erreur explicite.

---

## Phase 11 — Missions : bibliothèque locale (issue #12) — 2-3 j

**But** : permettre à chaque joueur de constituer sa bibliothèque personnelle de missions, stockée localement, et de la gérer via un onglet dédié.

**Dépendances** : Phase 9 (i18n infra — les labels de l'onglet sont localisés).

### Frontend (uniquement — pas de modification backend)
- Nouveau service `MissionLibraryService` : CRUD sur `localStorage` (`murder_missions_lib`), retourne `Mission[]` (`{ id, text, locale }`).
- Onglet **"Mes missions"** accessible depuis `HomeComponent` ou un menu global.
- UI : liste des missions enregistrées, formulaire d'ajout (champ texte + bouton), suppression avec confirmation, export/import JSON (optionnel).
- Les textes de l'onglet passent par les clés i18n de la Phase 9.

### Tests
- Tests Angular unitaires sur `MissionLibraryService` : add/remove/list, persistance entre instances.
- Test de composant : l'onglet affiche les missions stockées et permet l'ajout.

### Critères d'acceptation
- Un joueur peut ajouter "Éliminer en portant un chapeau" → la mission est conservée après rechargement de la page.
- La bibliothèque est totalement locale : aucun appel API n'est émis.

---

## Phase 12 — Missions : pool de partie (issue #13) — 2-3 j

**But** : permettre à tous les joueurs de contribuer des missions au pool de la partie, avec deux modes de fusion (augmenter le catalogue ou le remplacer).

**Dépendances** : Phase 10 (config de partie — le mode de fusion est un paramètre hôte), Phase 11 (la bibliothèque locale est la source de missions à contribuer).

### Backend
- Nouveau champ `mission_pool: list[str]` sur `Game` (initialement vide → catalogue par défaut utilisé).
- Nouveau champ `mission_pool_mode: Literal["append", "replace"] = "append"` sur `Game` (configurable par l'hôte via `PATCH /config`).
- Nouveau cas d'usage `ContributeMissions` + endpoint `POST /games/{code}/missions` : un joueur en `LOBBY` soumet une liste de missions ; elles s'ajoutent à `mission_pool`.
- `StartGame` → `assign_targets` utilise `mission_pool` si non vide, sinon catalogue par défaut ; `rules.py` reçoit le pool en paramètre (injection explicite, pas d'effet de bord global).

### Frontend
- Dans `LobbyComponent` : bouton "Contribuer mes missions" → sélection depuis `MissionLibraryService` + envoi.
- Indicateur du nombre de missions dans le pool (visible par tous).
- L'hôte voit un toggle "mode : augmenter / remplacer".

### Tests
- `test_start_game_uses_custom_pool_when_provided` (domain/rules).
- `test_contribute_missions_appended_to_pool` (application).
- Test d'intégration : contribuer après `start` → 409.

### Critères d'acceptation
- En mode `append` : les missions des joueurs s'ajoutent au catalogue existant.
- En mode `replace` : seules les missions contribuées sont utilisées pendant la partie.
- Contribuer des missions une fois la partie lancée est refusé (409).

---

## Phase 13 — i18n : catalogue de missions par défaut (issue #14) — 1 j

**But** : rendre le catalogue de missions par défaut traduisible, en remplaçant les textes bruts par des clés i18n.

**Dépendances** : Phase 9 (infra i18n), Phase 12 (le pool de partie est stable — le catalogue ne doit plus changer après ça).

### Backend
- `domain/missions.py` : remplacer les chaînes FR brutes par des **clés** (`"mission.shadow"`, `"mission.hat"`, etc.).
- Le backend renvoie les clés dans `player.mission` ; la traduction est à la charge du front.

### Frontend
- `fr.json` et `en.json` : ajouter les entrées de traduction pour toutes les clés du catalogue.
- `GameComponent` : afficher `translate.instant(player.mission)` au lieu de la chaîne brute.
- Fallback : si une clé n'est pas dans le fichier de traduction (mission personnalisée = texte libre), afficher le texte tel quel.

### Tests
- Test Angular : une clé connue est correctement traduite en FR et EN.
- Test Angular : un texte libre (non-clé) est affiché sans transformation.

### Critères d'acceptation
- Passer l'app en EN → les missions du catalogue sont en anglais.
- Une mission personnalisée contribuée par un joueur (texte libre) reste intacte quelle que soit la langue.

---

## Phase 14 — Gameplay : accusé de réception attaquant (issue #15) — 1-2 j

**But** : après qu'une élimination est confirmée, l'attaquant doit accuser réception avant de recevoir sa prochaine mission — évite le "spam d'élimination" et améliore le rythme du jeu.

**Dépendances** : aucune (logique backend + nouveau state front).

### Backend
- Nouveau statut intermédiaire : `Player` reçoit un champ `pending_ack: bool = False` mis à `True` par `resolve_claim` quand la confirmation est positive.
- Nouveau cas d'usage `AcknowledgeKill` + endpoint `POST /games/{code}/ack` : l'attaquant appelle cet endpoint → `pending_ack` repasse à `False`, la nouvelle mission et la nouvelle cible sont assignées **à ce moment-là** (pas avant).
- `ClaimElimination` vérifie que `pending_ack == False` (un attaquant ne peut pas réclamer une nouvelle élimination tant qu'il n'a pas acquitté la précédente).

### Frontend
- `GameComponent` : si `me.pending_ack == True`, afficher un écran interstitiel "Félicitations — tu as éliminé [nom] ! Prêt pour la suite ?" avec un bouton "Continuer".
- Appel `POST /ack` au clic → le WebSocket push la mise à jour et l'écran de jeu normal reprend.

### Tests
- `test_second_claim_blocked_while_ack_pending` (application).
- `test_ack_assigns_new_target_and_mission` (application/domain).
- Test d'intégration FastAPI : `POST /ack` par un non-attaquant → 403.

### Critères d'acceptation
- Après un kill confirmé, l'attaquant voit l'écran interstitiel et ne peut pas réclamer une nouvelle élimination.
- Après "Continuer", l'écran de jeu affiche la nouvelle mission et la nouvelle cible.

---

## Phase 15 — UX : animations de jeu (issue #16) — 2-3 j

**But** : ajouter des animations visuelles pour les moments clés du jeu, renforçant le feedback et l'immersion.

**Dépendances** : Phase 14 (les états du jeu sont tous stables, notamment l'interstitiel d'accusé de réception).

### Animations à implémenter (Angular Animations + CSS)
| Déclencheur | Animation | Durée |
|------------|-----------|-------|
| Élimination reçue (`incoming` claim arrivé) | Pulse rouge + vibration légère sur l'écran | 600 ms |
| Confirmation de kill réussie | Confetti ou flash vert + slide-in du score | 800 ms |
| Kill refusé | Shake + flash orange | 400 ms |
| Nouvelle mission assignée (post-`ack`) | Flip de carte révélant la nouvelle mission | 500 ms |
| Transition lobby → jeu | Fade-in de l'écran de jeu | 300 ms |

### Contraintes mobiles (garde-fous Phase 8)
- Utiliser `@angular/animations` (pas de lib externe).
- Respecter `prefers-reduced-motion` : si activé, remplacer toutes les animations par des transitions instantanées.
- Les animations ne bloquent **jamais** une interaction ; elles sont purement décoratives.

### Tests
- Tests d'existence et de non-régression (Karma) : les composants concernés se rendent correctement en présence des triggers d'animation.
- Pas de test sur le rendu visuel exact — valider manuellement avec les scénarios du wiki.

### Critères d'acceptation
- Chaque animation se déclenche au bon moment, visible sur Chrome desktop et mobile (tester sur un vrai appareil).
- Avec `prefers-reduced-motion: reduce`, aucune animation ne s'exécute (transition instantanée à la place).
- Aucune régression sur les tests existants.

---


# Feuille de route — Déploiement mobile (Android + iOS)

**Objectif final** : distribuer Murder_app comme **apps natives Android + iOS via Capacitor** (le SPA Angular empaqueté dans une WebView native, publiable sur les stores), avec **notifications push**.

**Viabilité : l'architecture est prête, sans refonte.** Le backend FastAPI hexagonal est agnostique au client ; le front Angular est exactement ce que Capacitor empaquette en réutilisant 100 % du code UI ; la session en `localStorage` fonctionne telle quelle en WebView.

> **Séquencement** : les Phases 16→20 se lancent **après le Bloc 2** (Phases 8→15).

---

## Phase 16 — Héberger le backend en HTTPS/WSS

**But** : rendre l'API joignable par une app mobile (un `docker-compose` local ne suffit pas).

1. Déployer sur un hébergeur qui termine le TLS automatiquement — **Fly.io** ou **Railway** (Docker natif, Postgres managé, gratuit/peu cher). Réutiliser le [murder-api/Dockerfile](murder-api/Dockerfile) existant (déjà prod-ready, healthcheck inclus).
2. Provisionner PostgreSQL et injecter `DATABASE_URL` → bascule in-memory → Postgres sans toucher au code métier.
3. Vérifier le WebSocket derrière le TLS (`wss://…/games/{code}/live`).
4. Garder `uvicorn --workers 1` (contrainte WebSocket en mémoire process) tant que la charge le permet.

---

## Phase 17 — Durcissement multi-origine + auth JWT

**But** : sécuriser avant toute exposition publique.

1. Finaliser l'allowlist CORS (Phase 8.2) avec les vraies origines de prod + WebView.
2. **JWT** : signer le `player_id` côté serveur (uuid4 → JWT signé), vérifié dans `dependencies.player_id` ([murder-api/src/api/dependencies.py](murder-api/src/api/dependencies.py)) — empêche l'usurpation par `X-Player-Id` forgé. Étendre le garde-fou de test existant (« confirm by non-target → 403 »).

---

## Phase 18 — Intégration Capacitor

**But** : produire la première app installable (Android, puis iOS).

1. Dans `murder-front/` (toolchain Node 20 sur le PATH) : ajouter `@capacitor/core`, `@capacitor/cli`, puis `@capacitor/android` et `@capacitor/ios`.
2. `npx cap init` ; `webDir` = `dist/murder-front/browser`.
3. Créer un environnement Capacitor avec des **URLs absolues** (`apiBase: 'https://api.<domaine>'`, `wsBase: 'wss://api.<domaine>'`) — indispensable car en WebView `window.location` pointe sur `capacitor://localhost`.
4. Build Angular → `npx cap sync` → `npx cap add android` / `add ios` ; compiler via Android Studio / Xcode.
5. Tester sur **appareil réel** : créer/rejoindre une partie, réclamer/confirmer une élimination, push live via WebSocket, survie de session après fermeture/réouverture de l'app.
6. iOS : compilation/publication exigent **macOS + Xcode** et un **compte Apple Developer** (99 $/an).

---

## Phase 19 — Notifications push

**But** : prévenir le joueur hors-app (élimination à confirmer, confirmation reçue).

1. Côté app : plugin `@capacitor/push-notifications` ; intégration **FCM** (Android) et **APNs** (iOS).
2. Côté backend : enregistrer les tokens d'appareil par joueur, et **émettre un push** aux moments clés. Ajouter un **port `PushNotifier`** à côté de `RealtimeNotifier` et le déclencher là où le notifier temps réel l'est déjà — dans les cas d'usage `ClaimElimination` / `ConfirmClaim` — pour rester dans le pattern hexagonal.

---

## Phase 20 — Publication stores

**But** : mettre les apps en ligne.

1. **Android** : keystore de signature, build AAB, fiche Google Play Console (~25 $ une fois).
2. **iOS** : provisioning/signing Xcode, App Store Connect, fiche App Store.
3. Icônes / splash via `@capacitor/assets` ; politique de confidentialité ; tests internes avant release publique.
