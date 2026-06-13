// DTOs mirroring the FastAPI contract (snake_case as sent over the wire).

export type GameStatus = 'lobby' | 'running' | 'ended';
export type ClaimStatus = 'pending' | 'ok' | 'no';

export interface PlayerDto {
  id: string;
  name: string;
  score: number;
  mission: string;
  target_id: string | null;
}

export interface ClaimDto {
  atk: string;
  atk_name: string;
  target: string;
  mission: string;
  status: ClaimStatus;
}

/** Full game state: returned by GET /games/{code} and pushed on the live WebSocket. */
export interface GameStateDto {
  code: string;
  host_id: string;
  status: GameStatus;
  duration_sec: number;
  start_at: number;
  end_at: number;
  remaining_sec: number;
  max_players: number;
  max_score: number | null;
  players: PlayerDto[];
  claims: ClaimDto[];
  ranking: PlayerDto[];
}

export interface CreatedGameDto extends GameStateDto {
  player_id: string;
}

export interface JoinedGameDto extends GameStateDto {
  player_id: string;
}

export interface PlayerSession {
  code: string;
  playerId: string;
  isHost: boolean;
}
