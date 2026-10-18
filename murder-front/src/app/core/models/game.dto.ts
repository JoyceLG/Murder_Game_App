// DTOs mirroring the FastAPI contract (snake_case as sent over the wire).

export type GameStatus = 'lobby' | 'running' | 'ended';
export type ClaimStatus = 'pending';
export type MissionMode = 'augment' | 'replace';

export interface PooledMissionDto {
  id: string;
  text: string;
  by: string;
}

/** What every player may know about any player. */
export interface PlayerDto {
  id: string;
  name: string;
  score: number;
}

/** The viewer's own secrets — only ever sent to that player. */
export interface MeDto extends PlayerDto {
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

/**
 * One player's view of a game: returned by the REST endpoints and pushed on the live WebSocket.
 * `claims` only holds the claims the viewer made or must answer.
 */
export interface GameStateDto {
  code: string;
  host_id: string;
  status: GameStatus;
  duration_sec: number;
  start_at: number;
  end_at: number;
  remaining_sec: number;
  /** Server clock (unix ms) when the view was built — used to correct the device's clock. */
  server_now: number;
  /** Increases with every change: a view older than the one we hold is ignored. */
  version: number;
  max_players: number;
  max_score: number | null;
  mission_mode: MissionMode;
  players: PlayerDto[];
  me: MeDto | null;
  claims: ClaimDto[];
  mission_pool: PooledMissionDto[];
  ranking: PlayerDto[];
}

export interface CreatedGameDto extends GameStateDto {
  player_id: string;
  player_token: string;
}

export interface JoinedGameDto extends GameStateDto {
  player_id: string;
  player_token: string;
}

/** Who the device plays as: public id + the session secret proving it. */
export interface PlayerAuth {
  playerId: string;
  token: string;
}

export interface PlayerSession extends PlayerAuth {
  code: string;
}
