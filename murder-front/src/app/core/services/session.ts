import { Injectable, computed, signal } from '@angular/core';

import { PlayerAuth, PlayerSession } from '../models/game.dto';

const KEY = 'murder.session';

/**
 * Persists the player's identity + current game so a page refresh keeps you in the game.
 * Storage can be unavailable (private browsing, full quota, WebView quirks): the session then
 * lives in memory only, and the game still works until the page is reloaded.
 */
@Injectable({ providedIn: 'root' })
export class Session {
  readonly session = signal<PlayerSession | null>(this.read());
  readonly playerId = computed(() => this.session()?.playerId ?? '');
  readonly code = computed(() => this.session()?.code ?? '');
  readonly auth = computed<PlayerAuth | null>(() => {
    const s = this.session();
    return s ? { playerId: s.playerId, token: s.token } : null;
  });

  set(value: PlayerSession): void {
    this.session.set(value);
    try {
      localStorage.setItem(KEY, JSON.stringify(value));
    } catch {
      // Not persisted: fine for this page's lifetime.
    }
  }

  clear(): void {
    this.session.set(null);
    try {
      localStorage.removeItem(KEY);
    } catch {
      // nothing stored, nothing to remove
    }
  }

  private read(): PlayerSession | null {
    try {
      const raw = localStorage.getItem(KEY);
      return raw ? parseSession(JSON.parse(raw)) : null;
    } catch {
      return null;
    }
  }
}

/** Accept only a well-formed stored session (an old or tampered value is dropped). */
export function parseSession(value: unknown): PlayerSession | null {
  if (!value || typeof value !== 'object') return null;
  const { code, playerId, token } = value as Record<string, unknown>;
  const isText = (v: unknown): v is string => typeof v === 'string' && v.length > 0;
  if (!isText(code) || !/^[A-Z0-9]{4}$/.test(code) || !isText(playerId) || !isText(token)) {
    return null;
  }
  return { code, playerId, token };
}
