import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { Subscription, firstValueFrom } from 'rxjs';

import { GameStateDto } from '../models/game.dto';
import { GameApi } from './game-api';
import { Realtime } from './realtime';
import { Session } from './session';

export type Screen = 'home' | 'lobby' | 'game' | 'end' | 'gone';

/**
 * Single source of truth for the UI. The WebSocket feeds `state`; everything the screens need is
 * a `computed` derived from it (the Angular port of game.js `_recompute`). The only genuinely
 * client-side derivation is the countdown, ticked once a second.
 */
@Injectable({ providedIn: 'root' })
export class GameStore {
  private api = inject(GameApi);
  private realtime = inject(Realtime);
  private session = inject(Session);

  readonly state = signal<GameStateDto | null>(null);
  readonly connected = signal(false);
  /** Set when a known session points at a game the server no longer has -> show the gone screen. */
  private readonly gone = signal(false);
  private readonly now = signal(Date.now());
  private liveSub: Subscription | null = null;

  constructor() {
    const tick = setInterval(() => this.now.set(Date.now()), 1000);
    inject(DestroyRef).onDestroy(() => clearInterval(tick));
  }

  // --- viewer-relative derived state ---
  readonly me = computed(() => {
    const s = this.state();
    const id = this.session.playerId();
    return s ? (s.players.find((p) => p.id === id) ?? null) : null;
  });
  readonly target = computed(() => {
    const s = this.state();
    const me = this.me();
    return s && me?.target_id ? (s.players.find((p) => p.id === me.target_id) ?? null) : null;
  });
  readonly ranking = computed(() => this.state()?.ranking ?? []);
  readonly myRank = computed(() => {
    const id = this.session.playerId();
    const index = this.ranking().findIndex((p) => p.id === id);
    return index < 0 ? 0 : index + 1;
  });
  readonly incoming = computed(() => {
    const s = this.state();
    const id = this.session.playerId();
    return s?.claims.find((c) => c.target === id && c.status === 'pending') ?? null;
  });
  readonly myClaim = computed(() => {
    const s = this.state();
    const id = this.session.playerId();
    return s?.claims.find((c) => c.atk === id) ?? null;
  });
  readonly isPending = computed(() => this.myClaim()?.status === 'pending');
  readonly isHost = computed(() => {
    const s = this.state();
    return !!s && s.host_id === this.session.playerId();
  });
  readonly remaining = computed(() => {
    const s = this.state();
    if (!s || !s.end_at) return 0;
    return Math.max(0, Math.floor((s.end_at - this.now()) / 1000));
  });
  readonly screen = computed<Screen>(() => this.deriveScreen());

  private deriveScreen(): Screen {
    if (this.gone()) return 'gone';
    const s = this.state();
    if (!s) return 'home';
    const timeUp = s.end_at > 0 && this.now() >= s.end_at;
    if (s.status === 'lobby') return 'lobby';
    if (s.status === 'running' && !timeUp) return 'game';
    return 'end';
  }

  // --- actions (orchestrate REST; the WebSocket push refreshes `state`) ---
  async create(name: string): Promise<void> {
    const res = await firstValueFrom(this.api.createGame(name));
    this.gone.set(false);
    this.session.set({ code: res.code, playerId: res.player_id, isHost: true });
    this.state.set(res);
    this.connect(res.code);
  }

  async join(code: string, name: string): Promise<void> {
    const res = await firstValueFrom(this.api.joinGame(code, name));
    this.gone.set(false);
    this.session.set({ code, playerId: res.player_id, isHost: res.host_id === res.player_id });
    this.state.set(res);
    this.connect(code);
  }

  start(durationMin: number): Promise<GameStateDto> {
    return firstValueFrom(this.api.start(this.session.code(), durationMin, this.session.playerId()));
  }

  updateConfig(maxPlayers: number, maxScore: number | null): Promise<GameStateDto> {
    return firstValueFrom(
      this.api.updateConfig(this.session.code(), this.session.playerId(), maxPlayers, maxScore),
    );
  }

  claimKill(): Promise<unknown> {
    return firstValueFrom(this.api.claim(this.session.code(), this.session.playerId()));
  }

  confirm(ok: boolean): Promise<unknown> {
    const claim = this.incoming();
    if (!claim) return Promise.resolve(null);
    return firstValueFrom(
      this.api.confirm(this.session.code(), claim.atk, ok, this.session.playerId()),
    );
  }

  swap(): Promise<unknown> {
    return firstValueFrom(this.api.swap(this.session.code(), this.session.playerId()));
  }

  async leave(): Promise<void> {
    const code = this.session.code();
    const id = this.session.playerId();
    try {
      if (code && id) await firstValueFrom(this.api.leave(code, id));
    } catch {
      // best-effort: still tear down locally
    } finally {
      this.reset();
    }
  }

  /** Called at app start: if a session exists, revalidate it and reconnect (survives refresh). */
  async rehydrate(): Promise<void> {
    const session = this.session.session();
    if (!session) return;
    try {
      const state = await firstValueFrom(this.api.getState(session.code));
      this.state.set(state);
      this.connect(session.code);
    } catch {
      // The session refers to a game the server no longer has -> route to the gone screen.
      this.session.clear();
      this.state.set(null);
      this.gone.set(true);
    }
  }

  private connect(code: string): void {
    this.liveSub?.unsubscribe();
    this.liveSub = this.realtime.connect(code).subscribe({
      next: (state) => {
        this.state.set(state);
        this.connected.set(true);
      },
      error: () => this.connected.set(false),
      complete: () => this.connected.set(false),
    });
  }

  private reset(): void {
    this.liveSub?.unsubscribe();
    this.liveSub = null;
    this.session.clear();
    this.state.set(null);
    this.connected.set(false);
    this.gone.set(false);
  }
}
