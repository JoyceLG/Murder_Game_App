import { signal } from '@angular/core';

import { GameStateDto, MeDto, PlayerDto } from '../app/core/models/game.dto';

export function player(id: string, score = 0): PlayerDto {
  return { id, name: id.toUpperCase(), score };
}

export function me(
  id: string,
  targetId: string | null,
  score = 0,
  swapCost: number | null = score > 0 ? 1 : 0,
): MeDto {
  return { ...player(id, score), mission: 'm', target_id: targetId, swap_cost: swapCost };
}

/** A running game seen by player `h` (host, hunting `b`), with a server clock in sync. */
export function gameState(partial: Partial<GameStateDto> = {}): GameStateDto {
  const players = [player('h', 2), player('b', 0)];
  const now = Date.now();
  return {
    code: 'ABCD',
    host_id: 'h',
    status: 'running',
    duration_sec: 900,
    start_at: now - 60_000,
    end_at: now + 90_000,
    remaining_sec: 90,
    server_now: now,
    version: 1,
    max_players: 12,
    max_score: null,
    mission_mode: 'augment',
    players,
    me: me('h', 'b', 2),
    claims: [],
    mission_pool: [],
    ranking: [players[0], players[1]],
    ...partial,
  };
}

/** Same rule as GameStore.myResult: only an answered (ok/no) claim of the viewer counts. */
function resultOf(state: GameStateDto | null): 'ok' | 'no' | null {
  const status = state?.claims.find((c) => c.atk === state.me?.id)?.status;
  return status === 'ok' || status === 'no' ? status : null;
}

/** A GameStore stand-in for component specs: real signals, spied actions. */
export function fakeStore(state: GameStateDto | null = gameState()) {
  const s = signal<GameStateDto | null>(state);
  const actions = [
    'create',
    'join',
    'start',
    'updateConfig',
    'addMission',
    'removeMission',
    'claimKill',
    'confirm',
    'acknowledge',
    'swap',
    'end',
    'leave',
    'exit',
  ] as const;
  const spies = jasmine.createSpyObj('GameStore', actions as unknown as string[]);
  for (const name of actions) {
    if (name !== 'exit') (spies[name] as jasmine.Spy).and.resolveTo(undefined);
  }
  const meSig = signal(state?.me ?? null);
  return Object.assign(spies, {
    state: s,
    me: meSig,
    target: signal(state?.players.find((p) => p.id === state?.me?.target_id) ?? null),
    ranking: signal(state?.ranking ?? []),
    myRank: signal(1),
    incoming: signal(state?.claims.find((c) => c.target === state?.me?.id) ?? null),
    isPending: signal(false),
    myResult: signal(resultOf(state)),
    isHost: signal(!!state?.me && state.host_id === state.me.id),
    remaining: signal(90),
    live: signal('online'),
  });
}
