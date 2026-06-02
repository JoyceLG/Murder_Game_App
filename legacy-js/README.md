# MURDER — application multijoueur

Jeu du Murder : chaque joueur reçoit une **mission** et une **cible**. Quand il
accomplit sa mission, la cible **confirme** l'élimination ; si oui → +1 point et
nouvelle assignation, si non → nouvelle mission. La partie dure un temps fixé par
l'hôte ; le meilleur score gagne.

## Architecture

La logique de jeu (`src/game.js`) ne dépend que d'une **interface backend
temps-réel** (`watchDoc`, `watchCollection`, `getDoc`, `setDoc`, `updateDoc`,
`deleteDoc`). Deux implémentations interchangeables :

- `src/backend-memory.js` — backend **en mémoire** avec latence simulable, pour
  le **simulateur** (N joueurs dans un seul onglet, sans rien déployer).
- `src/backend-firestore.js` — backend **Firestore** de production (auth anonyme),
  compatible émulateur Firebase.

Le même `GameClient` tourne sur les deux. Migrer de l'un à l'autre ne touche
jamais la logique de jeu.

```
murder-app/
├── index.html              app joueur (Firestore si configuré, sinon mémoire)
├── simulator.html          harnais de test multijoueur (mémoire)
├── firebase-config.js      clés de TON projet Firebase (à remplir)
├── firestore.rules         règles de sécurité
└── src/
    ├── game.js             logique de jeu (agnostique du backend)
    ├── backend-memory.js   backend temps-réel en mémoire
    ├── backend-firestore.js backend Firestore
    ├── ui.js               rendu de l'interface
    └── style.css           thème "dossier d'agence"
```

## 1) Tester le multijoueur SANS rien déployer (simulateur)

Les modules ES nécessitent un serveur HTTP (pas d'ouverture en `file://`).

```bash
cd murder-app
python3 -m http.server 8000
# puis ouvre http://localhost:8000/simulator.html
```

Dans le simulateur : règle le **nombre de joueurs** et la **latence réseau**,
le Joueur 1 est l'hôte (règle la durée, clique « Lancer »). Tous les panneaux se
synchronisent en direct : clique « J'ai éliminé ma cible » sur un panneau, puis
« Confirmer » sur le panneau de la cible, et regarde les scores bouger partout.

## 2) Brancher le vrai backend (Firestore)

1. Crée un projet sur https://console.firebase.google.com
2. **Firestore Database** → créer (mode production).
3. **Authentication** → activer le fournisseur **Anonyme**.
4. Récupère la config SDK (Paramètres du projet → Tes applications → Web) et
   colle-la dans `firebase-config.js`.
5. Déploie les règles : `firestore.rules`.

L'app (`index.html`) détecte la config et bascule automatiquement sur Firestore.
L'identifiant joueur est l'uid d'auth anonyme — c'est ce que vérifient les règles.

### Émulateur Firebase (dev local, sans toucher la prod)

```bash
npm install -g firebase-tools
firebase login
firebase init emulators      # coche Firestore + Authentication
firebase emulators:start
```

Mets `USE_EMULATOR = true` dans `firebase-config.js`, sers le dossier
(`python3 -m http.server`) et ouvre `index.html` dans plusieurs onglets : vrai
temps réel, données jetables, zéro coût.

### Déployer les règles + l'hébergement

```bash
firebase deploy --only firestore:rules
firebase deploy --only hosting       # si tu configures Firebase Hosting
```

## Modèle de données (Firestore)

```
games/{code}                     { code, hostId, status, durationSec, startAt, endAt }
games/{code}/players/{uid}       { name, score, mission, targetId, joinedAt }
games/{code}/claims/{attackerUid}{ atk, atkName, target, mission, status, ts }
```

Anti-conflit : un joueur n'écrit que sa propre fiche `players/{uid}` ; l'hôte
écrit la méta ; seule la cible modifie le `status` d'une `claim`.

## Limites connues / pistes de durcissement

- **Scoring de confiance** : l'attaquant incrémente son propre score. Pour de
  l'anti-triche fort, faire valider le point par une **Cloud Function**
  (transaction serveur) plutôt que côté client.
- **Fin de partie** déclenchée par l'hôte au temps écoulé ; une Cloud Function
  planifiée la rendrait indépendante de la présence de l'hôte.
- **Course** sur la confirmation : avec Firestore, encapsuler la résolution dans
  une `runTransaction` supprime la fenêtre résiduelle.
- Pas d'arrivée en cours de partie ni de re-désignation si un joueur quitte.

## Vers Android

PWA jouable d'abord (manifest + service worker), puis empaquetage :
- **TWA** (Trusted Web Activity) via Bubblewrap → Play Store, ou
- **Capacitor** pour un wrapper natif avec accès device.

La base web reste identique ; seul l'emballage change.
