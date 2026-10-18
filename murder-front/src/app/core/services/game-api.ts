import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  ClaimDto,
  CreatedGameDto,
  GameStateDto,
  JoinedGameDto,
  MissionMode,
  PlayerAuth,
} from '../models/game.dto';

/** An API failure reduced to what the UI branches on: HTTP status + domain error name. */
export interface ApiFailure {
  status: number; // 0 = network error / no response
  error: string | null; // e.g. 'GameNotFound', 'TooManyPlayers'
}

export function apiFailure(err: unknown): ApiFailure {
  if (err instanceof HttpErrorResponse) {
    const body = err.error as { error?: unknown } | null;
    return { status: err.status, error: typeof body?.error === 'string' ? body.error : null };
  }
  return { status: 0, error: null };
}

/**
 * Typed wrapper over the REST endpoints. Identity travels in two headers: the public player id
 * (X-Player-Id) and the session secret proving it (X-Player-Token).
 */
@Injectable({ providedIn: 'root' })
export class GameApi {
  private http = inject(HttpClient);
  private base = environment.apiBase;

  createGame(name: string): Observable<CreatedGameDto> {
    return this.http.post<CreatedGameDto>(`${this.base}/games`, { host_name: name });
  }

  joinGame(code: string, name: string): Observable<JoinedGameDto> {
    return this.http.post<JoinedGameDto>(`${this.base}/games/${code}/players`, { name });
  }

  start(code: string, durationMin: number, auth: PlayerAuth): Observable<GameStateDto> {
    return this.http.post<GameStateDto>(
      `${this.base}/games/${code}/start`,
      { duration_min: durationMin },
      { headers: this.authHeaders(auth) },
    );
  }

  updateConfig(
    code: string,
    auth: PlayerAuth,
    maxPlayers: number,
    maxScore: number | null,
    missionMode: MissionMode,
  ): Observable<GameStateDto> {
    return this.http.patch<GameStateDto>(
      `${this.base}/games/${code}/config`,
      { max_players: maxPlayers, max_score: maxScore, mission_mode: missionMode },
      { headers: this.authHeaders(auth) },
    );
  }

  addMission(code: string, auth: PlayerAuth, text: string): Observable<GameStateDto> {
    return this.http.post<GameStateDto>(
      `${this.base}/games/${code}/missions`,
      { text },
      { headers: this.authHeaders(auth) },
    );
  }

  removeMission(code: string, auth: PlayerAuth, missionId: string): Observable<GameStateDto> {
    return this.http.delete<GameStateDto>(`${this.base}/games/${code}/missions/${missionId}`, {
      headers: this.authHeaders(auth),
    });
  }

  claim(code: string, auth: PlayerAuth): Observable<ClaimDto> {
    return this.http.post<ClaimDto>(
      `${this.base}/games/${code}/claims`,
      {},
      { headers: this.authHeaders(auth) },
    );
  }

  confirm(
    code: string,
    attackerId: string,
    confirmed: boolean,
    auth: PlayerAuth,
  ): Observable<GameStateDto> {
    return this.http.post<GameStateDto>(
      `${this.base}/games/${code}/claims/${attackerId}/confirm`,
      { confirmed },
      { headers: this.authHeaders(auth) },
    );
  }

  swap(code: string, auth: PlayerAuth): Observable<GameStateDto> {
    return this.http.post<GameStateDto>(
      `${this.base}/games/${code}/swap-mission`,
      {},
      { headers: this.authHeaders(auth) },
    );
  }

  end(code: string, auth: PlayerAuth): Observable<GameStateDto> {
    return this.http.post<GameStateDto>(
      `${this.base}/games/${code}/end`,
      {},
      { headers: this.authHeaders(auth) },
    );
  }

  leave(code: string, auth: PlayerAuth): Observable<GameStateDto> {
    return this.http.delete<GameStateDto>(`${this.base}/games/${code}/players/me`, {
      headers: this.authHeaders(auth),
    });
  }

  /** The caller's view of the game (public view when `auth` is omitted). */
  getState(code: string, auth?: PlayerAuth): Observable<GameStateDto> {
    return this.http.get<GameStateDto>(`${this.base}/games/${code}`, {
      headers: auth ? this.authHeaders(auth) : {},
    });
  }

  private authHeaders(auth: PlayerAuth): Record<string, string> {
    return { 'X-Player-Id': auth.playerId, 'X-Player-Token': auth.token };
  }
}
