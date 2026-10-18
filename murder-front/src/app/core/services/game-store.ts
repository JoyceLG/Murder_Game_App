import { DOCUMENT } from '@angular/common';
import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { Observable, Subscription, firstValueFrom, timeout } from 'rxjs';

import { ClaimDto, GameStateDto, MissionMode, PlayerAuth } from '../models/game.dto';
import { GameApi, apiFailure } from './game-api';
import { FATAL_CLOSE_CODES, LiveClosedError, Realtime } from './realtime';
import { Session } from './session';

export type Screen = 'home' | 'restoring' | 'lobby' | 'game' | 'end' | 'gone';

/** idle: no game · connecting: first connection · online · offline: lost, reconnecting. */
export type LiveStatus = 'idle' | 'connecting' | 'online' | 'offline';

/** How long app start waits for the server before showing the UI anyway. */
export const REHYDRATE_TIMEOUT_MS = 3_000;

/**
 * Single source of truth for the UI. The server sends each player their own view of the game
 * (REST responses and WebSocket pushes alike); the newest one by `version` wins. Everything the
 * screens need is a `computed` derived from it. The only client-side derivation is the
 * countdown, ticked once a second against the *server* clock (device clock + measured offset).
 */
@Injectable({ providedIn: 'root' })
export class GameStore {
  private api = inject(GameApi);
  private realtime = inject(Realtime);
  private session = inject(Session);
  private document = inject(DOCUMENT);

  readonly state = signal<GameStateDto | null>(null);
  readonly live = signal<LiveStatus>('idle');
  readonly connected = computed(() => this.live() === 'online');
  /** Set when a known session points at a game the server no longer has -> show the gone screen. */
  private readonly gone = signal(false);
  private readonly now = signal(Date.now());
  /** server clock - device clock, measured on every state received. */
  private readonly clockOffset = signal(0);
  private liveSub: Subscription | null = null;
  /** Version for which we already asked the server to settle a timed-out game. */
  private settleAskedAt = -1;

  constructor() {
    const tick = setInterval(() => this.onTick(), 1000);
    const onVisibility = () => this.onVisibilityChange();
    this.document.addEventListener('visibilitychange', onVisibility);
    inject(DestroyRef).onDestroy(() => {
      clearInterval(tick);
      this.document.removeEventListener('visibilitychange', onVisibility);
      this.liveSub?.unsubscribe();
    });
  }

  // --- viewer-relative derived state ---
  readonly serverNow = computed(() => this.now() + this.clockOffset());
  readonly me = computed(() => this.state()?.me ?? null);
  readonly target = computed(() => {
    const s = this.state();
    const targetId = this.me()?.target_id;
    return s && targetId ? (s.players.find((p) => p.id === targetId) ?? null) : null;
  });
  readonly ranking = computed(() => this.state()?.ranking ?? []);
  readonly myRank = computed(() => {
    const id = this.me()?.id;
    const index = this.ranking().findIndex((p) => p.id === id);
    return index < 0 ? 0 : index + 1;
  });
  readonly incoming = computed(() => {
    const id = this.me()?.id;
    return this.state()?.claims.find((c) => c.target === id && c.status === 'pending') ?? null;
  });
  readonly myClaim = computed(() => {
    const id = this.me()?.id;
    return this.state()?.claims.find((c) => c.atk === id) ?? null;
  });
  readonly isPending = computed(() => this.myClaim()?.status === 'pending');
  /** The target's answer to the viewer's claim, until the viewer acknowledges it. */
  readonly myResult = computed(() => {
    const status = this.myClaim()?.status;
    return status === 'ok' || status === 'no' ? status : null;
  });
  readonly isHost = computed(() => {
    const s = this.state();
    return !!s && !!s.me && s.host_id === s.me.id;
  });
  readonly remaining = computed(() => {
    const s = this.state();
    if (!s || !s.end_at) return 0;
    return Math.max(0, Math.floor((s.end_at - this.serverNow()) / 1000));
  });
  readonly screen = computed<Screen>(() => this.deriveScreen());

  private deriveScreen(): Screen {
    if (this.gone()) return 'gone';
    const s = this.state();
    if (!s) return this.session.session() ? 'restoring' : 'home';
    const timeUp = s.end_at > 0 && this.serverNow() >= s.end_at;
    if (s.status === 'lobby') return 'lobby';
    if (s.status === 'running' && !timeUp) return 'game';
    return 'end';
  }

  // --- actions (REST; the response is the caller's fresh view, pushes keep everyone else in sync)
  async create(name: string): Promise<void> {
    const res = await firstValueFrom(this.api.createGame(name));
    this.gone.set(false);
    this.session.set({ code: res.code, playerId: res.player_id, token: res.player_token });
    this.apply(res);
    this.connect();
  }

  async join(code: string, name: string): Promise<void> {
    const res = await firstValueFrom(this.api.joinGame(code, name));
    this.gone.set(false);
    this.session.set({ code, playerId: res.player_id, token: res.player_token });
    this.apply(res);
    this.connect();
  }

  start(durationMin: number): Promise<GameStateDto> {
    return this.call((code, auth) => this.api.start(code, durationMin, auth));
  }

  updateConfig(
    maxPlayers: number,
    maxScore: number | null,
    missionMode: MissionMode,
  ): Promise<GameStateDto> {
    return this.call((code, auth) =>
      this.api.updateConfig(code, auth, maxPlayers, maxScore, missionMode),
    );
  }

  addMission(text: string): Promise<GameStateDto> {
    return this.call((code, auth) => this.api.addMission(code, auth, text));
  }

  removeMission(missionId: string): Promise<GameStateDto> {
    return this.call((code, auth) => this.api.removeMission(code, auth, missionId));
  }

  claimKill(): Promise<ClaimDto> {
    return firstValueFrom(this.api.claim(this.session.code(), this.requireAuth()));
  }

  async confirm(ok: boolean): Promise<GameStateDto | null> {
    const claim = this.incoming();
    if (!claim) return null;
    return this.call((code, auth) => this.api.confirm(code, claim.atk, ok, auth));
  }

  /** Acknowledge the answer to my claim: the server then deals my next target/mission. */
  async acknowledge(): Promise<GameStateDto | null> {
    const claim = this.myClaim();
    if (!claim || claim.status === 'pending') return null;
    try {
      return await this.call((code, auth) => this.api.acknowledge(code, claim.atk, auth));
    } catch (err) {
      // 404/409: nothing left to acknowledge (already done, or the game ended meanwhile, which
      // settles every claim). Not an error for the player: just show the current state.
      const { status } = apiFailure(err);
      if (status !== 404 && status !== 409) throw err;
      await this.refresh();
      return null;
    }
  }

  swap(): Promise<GameStateDto> {
    return this.call((code, auth) => this.api.swap(code, auth));
  }

  /** Host only: end a running game now. */
  end(): Promise<GameStateDto> {
    return this.call((code, auth) => this.api.end(code, auth));
  }

  /**
   * Leave the current game. Once it has ended there is nothing to leave on the server — the
   * final ranking is everyone's record — so we only forget the session on this device.
   */
  async leave(): Promise<void> {
    const code = this.session.code();
    const auth = this.session.auth();
    if (this.state()?.status === 'ended' || this.screen() === 'end') {
      this.reset();
      return;
    }
    try {
      if (code && auth) await firstValueFrom(this.api.leave(code, auth));
    } catch {
      // best-effort: still tear down locally
    } finally {
      this.reset();
    }
  }

  /** Forget the game on this device without telling the server (end and gone screens). */
  exit(): void {
    this.reset();
  }

  /** Re-read the caller's view (e.g. after the clock ran out: the server settles and pushes). */
  async refresh(): Promise<void> {
    const code = this.session.code();
    const auth = this.session.auth();
    if (!code || !auth) return;
    try {
      this.apply(await firstValueFrom(this.api.getState(code, auth)));
    } catch (err) {
      if (this.isGoneError(err)) this.markGone();
    }
  }

  /**
   * Called at app start: if a session exists, revalidate it and reconnect (survives refresh).
   * Only a definite answer (404 game gone, 401 credentials refused) drops the session; a network
   * error, a 5xx during a redeploy or a slow server keep it and let the WebSocket catch up.
   */
  async rehydrate(): Promise<void> {
    const session = this.session.session();
    if (!session) return;
    try {
      const state = await firstValueFrom(
        this.api.getState(session.code, session).pipe(timeout(REHYDRATE_TIMEOUT_MS)),
      );
      this.apply(state);
    } catch (err) {
      if (this.isGoneError(err)) {
        this.markGone();
        return;
      }
      this.live.set('offline');
    }
    this.connect();
  }

  /** Keep a state unless it is older than the one we already hold (REST and WS race). */
  apply(next: GameStateDto): void {
    const current = this.state();
    if (current && current.code === next.code && next.version < current.version) return;
    this.clockOffset.set(next.server_now - Date.now());
    this.now.set(Date.now());
    this.state.set(next);
  }

  private async call(
    request: (code: string, auth: PlayerAuth) => Observable<GameStateDto>,
  ): Promise<GameStateDto> {
    const state = await firstValueFrom(request(this.session.code(), this.requireAuth()));
    this.apply(state);
    return state;
  }

  private requireAuth(): PlayerAuth {
    const auth = this.session.auth();
    if (!auth) throw new Error('no active session');
    return auth;
  }

  private connect(): void {
    const code = this.session.code();
    const auth = this.session.auth();
    if (!code || !auth) return;
    this.liveSub?.unsubscribe();
    if (this.live() !== 'offline') this.live.set('connecting');
    this.liveSub = this.realtime.connect(code, auth).subscribe({
      next: (event) => {
        if (event.kind === 'state') this.apply(event.state);
        else if (event.kind === 'connected') this.live.set('online');
        else this.live.set('offline');
      },
      error: (err: unknown) => {
        if (
          err instanceof LiveClosedError &&
          (FATAL_CLOSE_CODES as readonly number[]).includes(err.code)
        ) {
          this.markGone();
        } else {
          this.live.set('offline');
        }
      },
    });
  }

  private disconnect(): void {
    this.liveSub?.unsubscribe();
    this.liveSub = null;
  }

  private onTick(): void {
    this.now.set(Date.now());
    // No server-side scheduler: when our (server-corrected) clock says time is up, ask the
    // server once; it settles the game to ENDED and pushes that to every player.
    const s = this.state();
    if (
      s?.status === 'running' &&
      s.end_at > 0 &&
      this.serverNow() >= s.end_at &&
      this.settleAskedAt !== s.version
    ) {
      this.settleAskedAt = s.version;
      void this.refresh();
    }
  }

  /** In the background (phone locked, app switched) drop the socket; resync on return. */
  private onVisibilityChange(): void {
    if (!this.session.session()) return;
    if (this.document.visibilityState === 'hidden') {
      this.disconnect();
    } else if (!this.liveSub && !this.gone()) {
      this.connect(); // the server sends a fresh snapshot on connect
    }
  }

  private isGoneError(err: unknown): boolean {
    const { status } = apiFailure(err);
    return status === 404 || status === 401;
  }

  private markGone(): void {
    this.disconnect();
    this.session.clear();
    this.state.set(null);
    this.live.set('idle');
    this.gone.set(true);
  }

  private reset(): void {
    this.disconnect();
    this.session.clear();
    this.state.set(null);
    this.live.set('idle');
    this.gone.set(false);
  }
}
