import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { ClaimDto, CreatedGameDto, GameStateDto, JoinedGameDto } from '../models/game.dto';

/** Typed wrapper over the REST endpoints. Identity travels in the X-Player-Id header. */
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

  start(code: string, durationMin: number, playerId: string): Observable<GameStateDto> {
    return this.http.post<GameStateDto>(
      `${this.base}/games/${code}/start`,
      { duration_min: durationMin },
      { headers: this.idHeader(playerId) },
    );
  }

  updateConfig(
    code: string,
    playerId: string,
    maxPlayers: number,
    maxScore: number | null,
  ): Observable<GameStateDto> {
    return this.http.patch<GameStateDto>(
      `${this.base}/games/${code}/config`,
      { max_players: maxPlayers, max_score: maxScore },
      { headers: this.idHeader(playerId) },
    );
  }

  claim(code: string, playerId: string): Observable<ClaimDto> {
    return this.http.post<ClaimDto>(
      `${this.base}/games/${code}/claims`,
      {},
      { headers: this.idHeader(playerId) },
    );
  }

  confirm(
    code: string,
    attackerId: string,
    confirmed: boolean,
    playerId: string,
  ): Observable<GameStateDto> {
    return this.http.post<GameStateDto>(
      `${this.base}/games/${code}/claims/${attackerId}/confirm`,
      { confirmed },
      { headers: this.idHeader(playerId) },
    );
  }

  swap(code: string, playerId: string): Observable<GameStateDto> {
    return this.http.post<GameStateDto>(
      `${this.base}/games/${code}/swap-mission`,
      {},
      { headers: this.idHeader(playerId) },
    );
  }

  leave(code: string, playerId: string): Observable<GameStateDto> {
    return this.http.delete<GameStateDto>(`${this.base}/games/${code}/players/me`, {
      headers: this.idHeader(playerId),
    });
  }

  getState(code: string): Observable<GameStateDto> {
    return this.http.get<GameStateDto>(`${this.base}/games/${code}`);
  }

  private idHeader(playerId: string): Record<string, string> {
    return { 'X-Player-Id': playerId };
  }
}
