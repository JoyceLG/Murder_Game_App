// =============================================================================
// backend-memory.js — backend temps-réel EN MÉMOIRE.
// Même interface que FirestoreBackend. Tous les clients d'un même onglet
// partagent une instance => synchronisation instantanée, idéale pour simuler
// N joueurs sans aucun déploiement. `latency` simule la latence réseau.
//
// Convention de chemins (comme Firestore) :
//   - segments pairs   => document  (games/ABCD, games/ABCD/players/xyz)
//   - segments impairs => collection (games/ABCD/players)
// =============================================================================

export class MemoryBackend {
  constructor({ latency = 120 } = {}) {
    this.docs = new Map();      // path -> data
    this.docSubs = new Map();   // path -> Set(cb)
    this.colSubs = new Map();   // path -> Set(cb)
    this.latency = latency;
  }

  _clone(o) { return o == null ? null : JSON.parse(JSON.stringify(o)); }
  _later(fn) { if (this.latency > 0) setTimeout(fn, this.latency); else Promise.resolve().then(fn); }

  _children(colPath) {
    const out = [];
    for (const [k, v] of this.docs) {
      const parts = k.split("/");
      if (parts.slice(0, -1).join("/") === colPath) out.push({ id: parts[parts.length - 1], ...this._clone(v) });
    }
    return out;
  }

  _notify(path) {
    const ds = this.docSubs.get(path);
    if (ds) { const v = this._clone(this.docs.get(path) || null); ds.forEach((cb) => this._later(() => cb(v))); }
    const parent = path.split("/").slice(0, -1).join("/");
    const cs = this.colSubs.get(parent);
    if (cs) { const arr = this._children(parent); cs.forEach((cb) => this._later(() => cb(arr))); }
  }

  watchDoc(path, cb) {
    if (!this.docSubs.has(path)) this.docSubs.set(path, new Set());
    this.docSubs.get(path).add(cb);
    this._later(() => cb(this._clone(this.docs.get(path) || null)));
    return () => this.docSubs.get(path)?.delete(cb);
  }

  watchCollection(path, cb) {
    if (!this.colSubs.has(path)) this.colSubs.set(path, new Set());
    this.colSubs.get(path).add(cb);
    this._later(() => cb(this._children(path)));
    return () => this.colSubs.get(path)?.delete(cb);
  }

  async getDoc(path) { return this._clone(this.docs.get(path) || null); }

  async setDoc(path, data) { this.docs.set(path, this._clone(data)); this._notify(path); }

  async updateDoc(path, partial) {
    const cur = this.docs.get(path) || {};
    this.docs.set(path, { ...cur, ...this._clone(partial) });
    this._notify(path);
  }

  async deleteDoc(path) { this.docs.delete(path); this._notify(path); }
}
