import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { GameStateDto, PlayerDto } from '../models/game.dto';
import { GameStore } from './game-store';
import { Session } from './session';

function player(id: string, score = 0, targetId: string | null = null): PlayerDto {
  return { id, name: id.toUpperCase(), score, mission: 'm', target_id: targetId };
}

function runningState(partial: Partial<GameStateDto> = {}): GameStateDto {
  const players = [player('h', 2, 'b'), player('b', 0, 'h')];
  return {
    code: 'ABCD',
    host_id: 'h',
    status: 'running',
    duration_sec: 900,
    start_at: 0,
    end_at: Date.now() + 90_000,
    remaining_sec: 90,
    max_players: 12,
    max_score: null,
    players,
    claims: [],
    ranking: [players[0], players[1]],
    ...partial,
  };
}

describe('GameStore', () => {
  let store: GameStore;
  let session: Session;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    session = TestBed.inject(Session);
    session.set({ code: 'ABCD', playerId: 'h', isHost: true });
    store = TestBed.inject(GameStore);
  });

  it('derives the home screen when there is no state', () => {
    expect(store.screen()).toBe('home');
  });

  it('derives the lobby screen', () => {
    store.state.set(runningState({ status: 'lobby', end_at: 0 }));
    expect(store.screen()).toBe('lobby');
  });

  it('derives the game screen while running and not expired', () => {
    store.state.set(runningState());
    expect(store.screen()).toBe('game');
  });

  it('derives the end screen once the clock is past end_at', () => {
    store.state.set(runningState({ end_at: Date.now() - 1 }));
    expect(store.screen()).toBe('end');
  });

  it('resolves me, target and rank from the viewer player id', () => {
    store.state.set(runningState());
    expect(store.me()?.id).toBe('h');
    expect(store.target()?.id).toBe('b');
    expect(store.myRank()).toBe(1);
    expect(store.isHost()).toBeTrue();
  });

  it('surfaces an incoming claim targeting the viewer', () => {
    const state = runningState({
      claims: [{ atk: 'b', atk_name: 'B', target: 'h', mission: 'm', status: 'pending' }],
    });
    store.state.set(state);
    expect(store.incoming()?.atk).toBe('b');
  });

  it('computes a positive countdown from end_at', () => {
    store.state.set(runningState({ end_at: Date.now() + 90_000 }));
    expect(store.remaining()).toBeGreaterThan(80);
    expect(store.remaining()).toBeLessThanOrEqual(90);
  });

  it('routes to the gone screen when rehydrating a game the server no longer has', async () => {
    const http = TestBed.inject(HttpTestingController);
    const done = store.rehydrate(); // session set in beforeEach -> GET /games/ABCD
    http
      .expectOne((r) => r.url.endsWith('/games/ABCD'))
      .flush(null, { status: 404, statusText: 'Not Found' });
    await done;
    expect(store.screen()).toBe('gone');
  });
});
