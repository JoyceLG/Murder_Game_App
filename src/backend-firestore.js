// =============================================================================
// backend-firestore.js — backend de PRODUCTION (Firestore temps réel).
// Même interface que MemoryBackend, donc la logique de jeu ne change pas.
// Utilise l'auth anonyme : l'uid Firebase sert d'identifiant joueur, ce qui
// permet aux security rules de vérifier "un joueur n'écrit que sa propre fiche".
// =============================================================================

import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAuth, signInAnonymously, connectAuthEmulator } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import {
  getFirestore, doc, collection, onSnapshot,
  getDoc as fsGetDoc, setDoc as fsSetDoc, updateDoc as fsUpdateDoc, deleteDoc as fsDeleteDoc,
  connectFirestoreEmulator
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

export async function createFirestoreBackend(config, { emulator = false } = {}) {
  const app = initializeApp(config);
  const db = getFirestore(app);
  const auth = getAuth(app);

  if (emulator) {
    connectFirestoreEmulator(db, "localhost", 8080);
    connectAuthEmulator(auth, "http://localhost:9099", { disableWarnings: true });
  }

  const cred = await signInAnonymously(auth);
  const uid = cred.user.uid;

  const backend = {
    watchDoc(path, cb) {
      return onSnapshot(doc(db, path), (snap) => cb(snap.exists() ? snap.data() : null));
    },
    watchCollection(path, cb) {
      return onSnapshot(collection(db, path), (snap) => cb(snap.docs.map((d) => ({ id: d.id, ...d.data() }))));
    },
    async getDoc(path) { const s = await fsGetDoc(doc(db, path)); return s.exists() ? s.data() : null; },
    async setDoc(path, data) { await fsSetDoc(doc(db, path), data); },
    async updateDoc(path, partial) { await fsUpdateDoc(doc(db, path), partial); },
    async deleteDoc(path) { await fsDeleteDoc(doc(db, path)); }
  };

  return { backend, uid };
}
