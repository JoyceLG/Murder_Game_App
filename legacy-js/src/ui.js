// =============================================================================
// ui.js — rendu de l'interface "dossier d'agence".
// mountClient(container, client, { compact, myId }) branche le rendu sur les
// changements d'état du GameClient. Réutilisé par l'app (1 client plein écran)
// et le simulateur (N clients compacts).
// =============================================================================

const esc = (s) => (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

let toastEl = null, toastT = null;
export function toast(msg, kind) {
  if (!toastEl) { toastEl = document.createElement("div"); toastEl.id = "toast"; document.body.appendChild(toastEl); }
  toastEl.textContent = msg;
  toastEl.className = "show" + (kind ? " " + kind : "");
  clearTimeout(toastT);
  toastT = setTimeout(() => (toastEl.className = ""), 2200);
}

export function mountClient(container, client, opts = {}) {
  const myId = opts.myId;
  container.classList.add("client");
  if (opts.compact) container.classList.add("compact");

  const $ = (sel) => container.querySelector(sel);
  const on = (sel, ev, fn) => { const el = $(sel); if (el) el.addEventListener(ev, fn); };

  function render(s) {
    if (s.screen === "home") return home(s);
    if (s.screen === "lobby") return lobby(s);
    if (s.screen === "game") return game(s);
    if (s.screen === "end") return end(s);
    if (s.screen === "gone") return gone(s);
  }

  function idline(s) {
    return `<div class="idline"><span>${esc(s.me ? s.me.name : "")}</span><span class="code">${s.code || ""}</span></div>`;
  }

  function home(s) {
    container.innerHTML = `
      <div class="card">
        <span class="eyebrow">Assignations classifiées</span>
        <h1>Une mission.<br>Une cible.<br>Discrétion absolue.</h1>
        <p class="lead">Crée une opération, partage le code, élimine ta cible sans te faire griller.</p>
        <label class="field"><span class="lbl">Ton nom d'agent</span>
          <input id="nm" maxlength="18" placeholder="Ex. Corbeau" autocomplete="off"></label>
        <button class="btn primary" id="create">Créer une partie</button>
        <div class="sep"><span>ou</span></div>
        <label class="field"><span class="lbl">Code de partie</span>
          <input id="cd" class="code" maxlength="4" placeholder="••••" autocapitalize="characters" autocomplete="off"></label>
        <button class="btn" id="join">Rejoindre</button>
      </div>`;
    on("#create", "click", async () => {
      const name = $("#nm").value.trim(); if (!name) return toast("Indique ton nom", "bad");
      try { await client.create(name, myId); } catch (e) { console.error(e); toast("Création impossible", "bad"); }
    });
    on("#join", "click", async () => {
      const name = $("#nm").value.trim(); const code = $("#cd").value.trim().toUpperCase();
      if (!name) return toast("Indique ton nom", "bad");
      if (code.length !== 4) return toast("Code à 4 caractères", "bad");
      try { await client.join(code, name, myId); }
      catch (e) { toast(e.message === "STARTED" ? "Partie déjà lancée" : "Aucune partie pour ce code", "bad"); }
    });
  }

  function lobby(s) {
    const enough = s.players.length >= 2;
    container.innerHTML = `
      ${idline(s)}
      <div class="card">
        <h2>Salle d'attente</h2>
        <div class="seal">
          <span class="corner c1"></span><span class="corner c2"></span><span class="corner c3"></span><span class="corner c4"></span>
          <span class="eyebrow">Code d'accès</span>
          <div class="k">${s.code}</div>
          <div class="cap muted">Partage ce code pour recruter des agents</div>
        </div>
      </div>
      <div class="card">
        <h2>Agents recrutés — ${s.players.length}</h2>
        <ul class="roster">${s.players.map((p) => row(s, p, false)).join("")}</ul>
      </div>
      ${s.isHost ? `
        <div class="card">
          <h2>Paramètres</h2>
          <label class="field"><span class="lbl">Durée (minutes)</span>
            <input id="dur" type="number" min="1" max="240" value="15" inputmode="numeric"></label>
          <button class="btn danger" id="start" ${enough ? "" : "disabled"}>Lancer l'opération</button>
          ${enough ? "" : `<div class="foot">Au moins 2 agents requis</div>`}
        </div>` : `
        <div class="card center"><span class="eyebrow">En attente</span>
          <p class="lead" style="margin:8px 0 0">L'hôte n'a pas encore lancé…</p></div>`}
      <button class="btn ghost" id="leave">Quitter</button>`;
    if (s.isHost) on("#start", "click", async () => {
      try { await client.start(parseInt($("#dur").value || "15", 10)); }
      catch (e) { toast("Au moins 2 agents requis", "bad"); }
    });
    on("#leave", "click", () => client.leave());
  }

  function game(s) {
    const me = s.myPlayer; if (!me) return;
    const mm = String(Math.floor(s.remaining / 60)).padStart(2, "0");
    const ss = String(s.remaining % 60).padStart(2, "0");
    const warn = s.remaining <= 60;
    const pending = s.myClaim && s.myClaim.status === "pending";
    container.innerHTML = `
      ${idline(s)}
      <div class="hud">
        <div class="stat"><div class="lbl">Temps</div><div class="val ${warn ? "warn" : ""}">${mm}:${ss}</div></div>
        <div class="stat"><div class="lbl">Score</div><div class="val">${me.score || 0}</div></div>
        <div class="stat"><div class="lbl">Rang</div><div class="val">#${s.myRank}</div></div>
      </div>
      <div class="dossier">
        <div class="drow"><span class="stamp">Assignation active</span><span class="eyebrow">N° ${s.code}-${(me.score || 0) + 1}</span></div>
        <div class="mtext">${esc(me.mission)}</div>
        <div class="target">Cible : <b>${s.target ? esc(s.target.name) : "—"}</b></div>
      </div>
      ${s.incoming ? `
        <div class="card confirm">
          <span class="stamp">Tentative d'élimination</span>
          <p class="ctext"><b>${esc(s.incoming.atkName)}</b> prétend t'avoir éliminé.<br>
            <span class="muted">« ${esc(s.incoming.mission)} »</span></p>
          <div class="btn-row"><button class="btn ghost" id="no">Refuser</button><button class="btn ok" id="yes">Confirmer</button></div>
        </div>` : ""}
      ${pending ? `
        <div class="card"><div class="pending"><span class="pulse"></span> En attente de ${esc(s.target ? s.target.name : "ta cible")}…</div></div>` : `
        <div class="card">
          <button class="btn danger" id="kill">J'ai éliminé ma cible</button>
          <button class="btn ghost" id="swap">Changer de mission&nbsp;&nbsp;<span class="muted">−1 pt</span></button>
        </div>`}
      <div class="card">
        <h2>Classement</h2>
        <ul class="roster">${s.ranking.map((p, i) => row(s, p, true, i + 1)).join("")}</ul>
      </div>
      <button class="btn ghost" id="leave">Quitter</button>`;
    if (s.incoming) { on("#yes", "click", () => client.resolveIncoming(true)); on("#no", "click", () => client.resolveIncoming(false)); }
    if (!pending) { on("#kill", "click", () => client.claimKill()); on("#swap", "click", () => client.swapMission()); }
    on("#leave", "click", () => client.leave());
  }

  function end(s) {
    const w = s.ranking[0];
    const won = w && s.me && w.id === s.me.id;
    container.innerHTML = `
      ${idline(s)}
      <div class="card center"><span class="eyebrow">Opération terminée</span>
        <h1 style="margin-top:8px">${won ? "Tu remportes l'opération." : (w ? esc(w.name) + " l'emporte." : "Fin de partie")}</h1>
        ${w ? `<p class="lead" style="margin-top:8px">Score final : ${w.score || 0} élimination(s).</p>` : ""}</div>
      <div class="card"><h2>Classement final</h2>
        <ul class="roster">${s.ranking.map((p, i) => row(s, p, true, i + 1)).join("")}</ul></div>
      <button class="btn ghost" id="leave">Retour à l'accueil</button>`;
    on("#leave", "click", () => client.leave());
  }

  function gone(s) {
    container.innerHTML = `<div class="card center"><span class="eyebrow">Hors ligne</span>
      <p class="lead" style="margin-top:8px">La partie n'existe plus.</p>
      <button class="btn" id="leave">Accueil</button></div>`;
    on("#leave", "click", () => client.leave());
  }

  function row(s, p, withScore, rank) {
    const me = p.id === (s.me && s.me.id);
    const host = s.meta && p.id === s.meta.hostId;
    return `<li>
      ${withScore ? `<span class="rank">${rank != null ? String(rank).padStart(2, "0") : ""}</span>` : ""}
      <span class="pname">${esc(p.name)} ${me ? '<span class="you-tag">TOI</span>' : ""} ${host ? '<span class="host-tag">HÔTE</span>' : ""}</span>
      ${withScore ? `<span class="pscore">${p.score || 0}</span>` : ""}
    </li>`;
  }

  client.onState = render;
  render(client.state);
}
