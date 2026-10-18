import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Observable } from 'rxjs';

import { CreatedGameDto, PlayerAuth } from '../models/game.dto';
import { GameApi, apiFailure } from './game-api';

const AUTH: PlayerAuth = { playerId: 'p1', token: 'tok' };

describe('GameApi', () => {
  let api: GameApi;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    api = TestBed.inject(GameApi);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('POSTs /games with host_name and returns the player id and secret', () => {
    let result: CreatedGameDto | undefined;
    api.createGame('Corbeau').subscribe((r) => (result = r));

    const req = http.expectOne((r) => r.method === 'POST' && r.url.endsWith('/games'));
    expect(req.request.body).toEqual({ host_name: 'Corbeau' });
    expect(req.request.headers.has('X-Player-Id')).toBeFalse();
    req.flush({ player_id: 'p1', player_token: 'tok', code: 'ABCD' } as CreatedGameDto);

    expect(result?.player_id).toBe('p1');
    expect(result?.player_token).toBe('tok');
  });

  it('POSTs a join without credentials', () => {
    api.joinGame('ABCD', 'Bob').subscribe();
    const req = http.expectOne((r) => r.url.endsWith('/games/ABCD/players'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ name: 'Bob' });
    req.flush({});
  });

  // Every authenticated endpoint: [label, call, method, url suffix, body]
  const cases: [string, (a: GameApi) => Observable<unknown>, string, string, unknown][] = [
    ['start', (a) => a.start('ABCD', 15, AUTH), 'POST', '/games/ABCD/start', { duration_min: 15 }],
    [
      'updateConfig',
      (a) => a.updateConfig('ABCD', AUTH, 6, 3, 'replace'),
      'PATCH',
      '/games/ABCD/config',
      { max_players: 6, max_score: 3, mission_mode: 'replace' },
    ],
    [
      'addMission',
      (a) => a.addMission('ABCD', AUTH, 'x'),
      'POST',
      '/games/ABCD/missions',
      { text: 'x' },
    ],
    [
      'removeMission',
      (a) => a.removeMission('ABCD', AUTH, 'm1'),
      'DELETE',
      '/games/ABCD/missions/m1',
      null,
    ],
    ['claim', (a) => a.claim('ABCD', AUTH), 'POST', '/games/ABCD/claims', {}],
    [
      'confirm',
      (a) => a.confirm('ABCD', 'atk', true, AUTH),
      'POST',
      '/games/ABCD/claims/atk/confirm',
      { confirmed: true },
    ],
    ['swap', (a) => a.swap('ABCD', AUTH), 'POST', '/games/ABCD/swap-mission', {}],
    ['end', (a) => a.end('ABCD', AUTH), 'POST', '/games/ABCD/end', {}],
    ['leave', (a) => a.leave('ABCD', AUTH), 'DELETE', '/games/ABCD/players/me', null],
    ['getState', (a) => a.getState('ABCD', AUTH), 'GET', '/games/ABCD', null],
  ];

  for (const [label, call, method, suffix, body] of cases) {
    it(`${label}: ${method} ${suffix} with both identity headers`, () => {
      call(api).subscribe();
      const req = http.expectOne((r) => r.url.endsWith(suffix));
      expect(req.request.method).toBe(method);
      expect(req.request.headers.get('X-Player-Id')).toBe('p1');
      expect(req.request.headers.get('X-Player-Token')).toBe('tok');
      if (body !== null) expect(req.request.body).toEqual(body);
      req.flush({});
    });
  }

  it('reads the public state anonymously', () => {
    api.getState('ABCD').subscribe();
    const req = http.expectOne((r) => r.url.endsWith('/games/ABCD'));
    expect(req.request.headers.has('X-Player-Token')).toBeFalse();
    req.flush({});
  });

  describe('apiFailure', () => {
    it('extracts status and domain error name', () => {
      const err = new HttpErrorResponse({ status: 409, error: { error: 'TooManyPlayers' } });
      expect(apiFailure(err)).toEqual({ status: 409, error: 'TooManyPlayers' });
    });

    it('tolerates bodies without an error name', () => {
      const err = new HttpErrorResponse({ status: 502, error: '<html>' });
      expect(apiFailure(err)).toEqual({ status: 502, error: null });
    });

    it('treats anything else as a network failure', () => {
      expect(apiFailure(new Error('boom'))).toEqual({ status: 0, error: null });
    });
  });
});
