import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { CreatedGameDto } from '../models/game.dto';
import { GameApi } from './game-api';

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

  it('POSTs /games with host_name and returns the player id', () => {
    let result: CreatedGameDto | undefined;
    api.createGame('Corbeau').subscribe((r) => (result = r));

    const req = http.expectOne((r) => r.method === 'POST' && r.url.endsWith('/games'));
    expect(req.request.body).toEqual({ host_name: 'Corbeau' });
    req.flush({ player_id: 'p1', code: 'ABCD' } as CreatedGameDto);

    expect(result?.player_id).toBe('p1');
  });

  it('sends X-Player-Id and duration when starting', () => {
    api.start('ABCD', 15, 'p1').subscribe();

    const req = http.expectOne((r) => r.url.endsWith('/games/ABCD/start'));
    expect(req.request.headers.get('X-Player-Id')).toBe('p1');
    expect(req.request.body).toEqual({ duration_min: 15 });
    req.flush({});
  });

  it('DELETEs the player on leave', () => {
    api.leave('ABCD', 'p1').subscribe();
    const req = http.expectOne((r) => r.method === 'DELETE' && r.url.endsWith('/games/ABCD/players/me'));
    expect(req.request.headers.get('X-Player-Id')).toBe('p1');
    req.flush({});
  });
});
