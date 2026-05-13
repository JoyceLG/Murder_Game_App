// =============================================================================
// game.js — logique de jeu, INDÉPENDANTE du backend.
// Le client ne connaît qu'une interface temps-réel (voir backend-memory.js) :
//   watchDoc(path, cb) -> unsubscribe        cb(dataOrNull)
//   watchCollection(path, cb) -> unsubscribe  cb(arrayOfDocsWithId)
//   getDoc(path) -> data|null
//   setDoc(path, data), updateDoc(path, partial), deleteDoc(path)
// Chemins (mappent 1:1 sur Firestore) :
//   games/{code}
//   games/{code}/players/{playerId}
//   games/{code}/claims/{attackerId}
// =============================================================================

export const MISSIONS = [
  "Fais dire « oui » trois fois de suite à ta cible.",
  "Prends un selfie avec ta cible.",
  "Fais un compliment à ta cible sur ses chaussures.",
  "Apprends la date de naissance de ta cible.",
  "Fais rire ta cible sans raconter de blague.",
  "Touche le coude de ta cible sans qu'elle s'en aperçoive.",
  "Fais dire le mot « banane » à ta cible.",
  "Échange un objet avec ta cible.",
  "Fais un check (tope-là) à ta cible.",
  "Convaincs ta cible de te suivre dans une autre pièce.",
  "Fais dire « je ne sais pas » à ta cible.",
  "Demande l'heure à ta cible.",
  "Trinque avec ta cible.",
  "Apprends le prénom du premier animal de ta cible.",
  "Fais chanter ta cible, ne serait-ce qu'un mot.",
  "Pose ta main sur l'épaule de ta cible pendant 3 secondes.",
  "Obtiens un « merci » de ta cible.",
  "Fais imiter un animal à ta cible.",
  "Découvre le film préféré de ta cible.",
  "Fais lever les deux mains à ta cible en même temps.",
  "Fais bâiller ta cible.",
  "Fais nommer trois pays à ta cible.",
  "Prends une photo de la main de ta cible.",
  "Fais dire « bien sûr » à ta cible.",
  "Emprunte le téléphone de ta cible 5 secondes.",
  "Fais danser ta cible, un pas suffit.",
  "Apprends la pointure de ta cible.",
  "Fais épeler son prénom à ta cible.",
  "Fais dire « c'est toi le coupable » à ta cible.",
  "Apprends le métier rêvé de ta cible."
];

const rndId = () => Math.random().toString(36).slice(2, 10);
const code4 = () => { const a = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"; let s = ""; for (let i = 0; i < 4; i++) s += a[Math.floor(Math.random() * a.length)]; return s; };
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
const now = () => Date.now();

export class GameClient {
  constructor(backend, { onState } = {}) {
    this.be = backend;
    this.onState = onState || (() => {});
    this._unsub = [];
    this._timer = null;
    this._busyClaim = false;
    this._busyEnd = false;
    this.state = this._empty();
  }

  _empty() {
    return {
      screen: "home", code: null, me: null, isHost: false,
      meta: null, players: [], claims: [],
      myPlayer: null, target: null, ranking: [], myRank: 0, remaining: 0,
      myClaim: null, incoming: null
    };
  }
  _emit() { this.onState(this.state); }

  // ---- entrée dans une partie -------------------------------------------------
  async create(name, myId = rndId()) {
    const code = code4();
    this.state.me = { id: myId, name };
    this.state.code = code;
    this.state.isHost = true;
    this.state.screen = "lobby"; // optimiste : évite un flash "home" en attendant le snapshot
    await this.be.setDoc(`games/${code}`, { code, hostId: myId, status: "lobby", durationSec: 0, startAt: 0, endAt: 0 });
    await this.be.setDoc(`games/${code}/players/${myId}`, { name, score: 0, mission: "", targetId: null, joinedAt: now() });
    this._subscribe(code);
    return code;
  }

  async join(code, name, myId = rndId()) {
    const meta = await this.be.getDoc(`games/${code}`);
    if (!meta) throw new Error("NO_GAME");
    if (meta.status !== "lobby") throw new Error("STARTED");
    this.state.me = { id: myId, name };
    this.state.code = code;
    this.state.isHost = meta.hostId === myId;
    this.state.screen = "lobby";
    await this.be.setDoc(`games/${code}/players/${myId}`, { name, score: 0, mission: "", targetId: null, joinedAt: now() });
    this._subscribe(code);
  }

  _subscribe(code) {
    const g = `games/${code}`;
    this._unsub.push(this.be.watchDoc(g, (m) => { this.state.meta = m; this._recompute(); }));
    this._unsub.push(this.be.watchCollection(`${g}/players`, (ps) => { this.state.players = ps; this._recompute(); }));
    this._unsub.push(this.be.watchCollection(`${g}/claims`, (cs) => { this.state.claims = cs; this._recompute(); }));
    if (!this._timer) this._timer = setInterval(() => this._tick(), 1000);
  }

  _tick() { if (this.state.meta && this.state.meta.status === "running") this._recompute(); }

  // ---- dérivation de l'état + réactions automatiques --------------------------
  _recompute() {
    const s = this.state;
    const meta = s.meta;
    if (!meta) { if (s.code) s.screen = "gone"; this._emit(); return; }

    const me = s.players.find((p) => p.id === s.me.id) || null;
    s.myPlayer = me;
    s.target = me ? (s.players.find((p) => p.id === me.targetId) || null) : null;
    s.ranking = [...s.players].sort((a, b) => (b.score || 0) - (a.score || 0));
    s.myRank = s.ranking.findIndex((p) => p.id === s.me.id) + 1;
    s.remaining = meta.endAt ? Math.max(0, Math.floor((meta.endAt - now()) / 1000)) : 0;
    s.myClaim = s.claims.find((c) => c.id === s.me.id) || null;            // claim.id == attaquant
    s.incoming = s.claims.find((c) => c.target === s.me.id && c.status === "pending") || null;

    const timeUp = meta.endAt && now() >= meta.endAt;
    if (meta.status === "lobby") s.screen = "lobby";
    else if (meta.status === "running" && !timeUp) s.screen = "game";
    else s.screen = "end";

    // l'attaquant traite la résolution de SA claim
    if (s.myClaim && (s.myClaim.status === "ok" || s.myClaim.status === "no")) this._resolveOwnClaim(s.myClaim);

    // l'hôte clôt la partie quand le temps est écoulé
    if (s.isHost && meta.status === "running" && timeUp && !this._busyEnd) {
      this._busyEnd = true;
      this.be.updateDoc(`games/${s.code}`, { status: "ended" }).finally(() => { this._busyEnd = false; });
    }
    this._emit();
  }

  async _resolveOwnClaim(claim) {
    if (this._busyClaim) return;
    this._busyClaim = true;
    try {
      const s = this.state, me = s.myPlayer;
      if (!me) return;
      if (claim.status === "ok") {
        const ids = s.players.map((p) => p.id).filter((i) => i !== me.id);
        let pool = ids.filter((i) => i !== me.targetId);
        if (!pool.length) pool = ids;
        await this.be.updateDoc(`games/${s.code}/players/${me.id}`, {
          score: (me.score || 0) + 1, targetId: pick(pool), mission: pick(MISSIONS)
        });
      } else {
        let m = pick(MISSIONS); if (m === me.mission) m = pick(MISSIONS);
        await this.be.updateDoc(`games/${s.code}/players/${me.id}`, { mission: m });
      }
      await this.be.deleteDoc(`games/${s.code}/claims/${me.id}`);
    } finally {
      this._busyClaim = false;
    }
  }

  // ---- actions ----------------------------------------------------------------
  async start(durationMin) {
    const s = this.state;
    if (!s.isHost) return;
    if (s.players.length < 2) throw new Error("NEED_2");
    const ids = s.players.map((p) => p.id);
    for (const p of s.players) {
      await this.be.updateDoc(`games/${s.code}/players/${p.id}`, {
        targetId: pick(ids.filter((i) => i !== p.id)), mission: pick(MISSIONS)
      });
    }
    const dur = Math.max(1, Math.min(240, durationMin | 0)) * 60;
    const startAt = now();
    await this.be.updateDoc(`games/${s.code}`, { status: "running", durationSec: dur, startAt, endAt: startAt + dur * 1000 });
  }

  async claimKill() {
    const s = this.state, me = s.myPlayer;
    if (!me || !me.targetId) return;
    await this.be.setDoc(`games/${s.code}/claims/${me.id}`, {
      atk: me.id, atkName: me.name, target: me.targetId, mission: me.mission, status: "pending", ts: now()
    });
  }

  async resolveIncoming(ok) {
    const s = this.state, c = s.incoming;
    if (!c) return;
    await this.be.updateDoc(`games/${s.code}/claims/${c.id}`, { status: ok ? "ok" : "no" });
  }

  async swapMission() {
    const s = this.state, me = s.myPlayer;
    if (!me) return;
    let m = pick(MISSIONS); if (m === me.mission) m = pick(MISSIONS);
    await this.be.updateDoc(`games/${s.code}/players/${me.id}`, { mission: m, score: (me.score || 0) - 1 });
  }

  async leave() {
    const s = this.state;
    if (s.code && s.me) {
      await this.be.deleteDoc(`games/${s.code}/players/${s.me.id}`);
      await this.be.deleteDoc(`games/${s.code}/claims/${s.me.id}`);
    }
    this.destroy();
    this.state = this._empty();
    this._emit();
  }

  destroy() {
    this._unsub.forEach((u) => { try { u(); } catch (e) {} });
    this._unsub = [];
    if (this._timer) { clearInterval(this._timer); this._timer = null; }
  }
}
