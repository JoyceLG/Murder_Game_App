import { Injectable, computed, signal } from '@angular/core';

import { PlayerSession } from '../models/game.dto';

const KEY = 'murder.session';

/** Persists the player's identity + current game so a page refresh keeps you in the game. */
@Injectable({ providedIn: 'root' })
export class Session {
  readonly session = signal<PlayerSession | null>(this.read());
  readonly playerId = computed(() => this.session()?.playerId ?? '');
  readonly code = computed(() => this.session()?.code ?? '');

  set(value: PlayerSession): void {
    this.session.set(value);
    localStorage.setItem(KEY, JSON.stringify(value));
  }

  clear(): void {
    this.session.set(null);
    localStorage.removeItem(KEY);
  }

  private read(): PlayerSession | null {
    try {
      const raw = localStorage.getItem(KEY);
      return raw ? (JSON.parse(raw) as PlayerSession) : null;
    } catch {
      return null;
    }
  }
}
