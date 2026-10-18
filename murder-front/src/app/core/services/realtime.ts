import { Injectable } from '@angular/core';
import { Observable, retry, tap, throwError, timer } from 'rxjs';

import { environment } from '../../../environments/environment';
import { GameStateDto, PlayerAuth } from '../models/game.dto';

/** Close codes the server uses when reconnecting cannot help (see api/ws_notifier.py). */
export const FATAL_CLOSE_CODES = [4401, 4403, 4404] as const;

/** Raised when the server closed the socket for good (bad credentials, removed, game gone). */
export class LiveClosedError extends Error {
  constructor(readonly code: number) {
    super(`live connection closed (${code})`);
  }
}

export type LiveEvent =
  { kind: 'state'; state: GameStateDto } | { kind: 'connected' } | { kind: 'disconnected' };

export const PING_INTERVAL_MS = 25_000;
const BACKOFF_BASE_MS = 1_000;
const BACKOFF_MAX_MS = 30_000;

/** Reconnect delay: 1s, 2s, 4s… capped at 30s. */
export function backoffDelay(attempt: number): number {
  return Math.min(BACKOFF_MAX_MS, BACKOFF_BASE_MS * 2 ** Math.max(0, attempt - 1));
}

function isGameState(value: unknown): value is GameStateDto {
  return !!value && typeof value === 'object' && typeof (value as GameStateDto).code === 'string';
}

/**
 * Live game-state stream over WebSocket. On open the client authenticates with its first
 * message, then receives its own view of the game after every change. Connection status is
 * part of the stream so the UI can show a "reconnecting" banner. Transient drops reconnect with
 * exponential backoff; fatal closes (FATAL_CLOSE_CODES) end the stream with LiveClosedError.
 */
@Injectable({ providedIn: 'root' })
export class Realtime {
  connect(code: string, auth: PlayerAuth): Observable<LiveEvent> {
    const base = environment.wsBase || `${this.scheme()}//${location.host}`;
    const url = `${base}/games/${code}/live`;
    // Consecutive failed attempts; only a real (authenticated) connection resets it — the
    // 'disconnected' event emitted on each drop must not.
    let failures = 0;
    return new Observable<LiveEvent>((subscriber) => {
      const socket = this.open(url);
      let ping: ReturnType<typeof setInterval> | null = null;
      socket.onopen = () => {
        socket.send(JSON.stringify({ player_id: auth.playerId, token: auth.token }));
        // Keeps proxies (nginx) from closing an idle connection; the server answers "pong".
        ping = setInterval(() => socket.send('ping'), PING_INTERVAL_MS);
      };
      socket.onmessage = (event) => {
        let data: unknown;
        try {
          data = JSON.parse(event.data as string);
        } catch {
          return; // "pong" or anything else that is not a state
        }
        if (!isGameState(data)) return;
        subscriber.next({ kind: 'connected' });
        subscriber.next({ kind: 'state', state: data });
      };
      // Any close while subscribed is unexpected: surface it as an error so retry() decides
      // between reconnecting and giving up. On our own teardown we unsubscribe first, so this
      // error is harmlessly ignored.
      socket.onclose = (event) => {
        subscriber.next({ kind: 'disconnected' });
        subscriber.error(new LiveClosedError(event.code));
      };
      return () => {
        if (ping) clearInterval(ping);
        socket.onclose = null;
        if (socket.readyState <= WebSocket.OPEN) socket.close();
      };
    }).pipe(
      tap((event) => {
        if (event.kind === 'connected') failures = 0;
      }),
      retry({
        delay: (error: unknown) =>
          error instanceof LiveClosedError &&
          (FATAL_CLOSE_CODES as readonly number[]).includes(error.code)
            ? throwError(() => error)
            : timer(backoffDelay(++failures)),
      }),
    );
  }

  /** Seam for tests. */
  protected open(url: string): WebSocket {
    return new WebSocket(url);
  }

  private scheme(): string {
    return location.protocol === 'https:' ? 'wss:' : 'ws:';
  }
}
