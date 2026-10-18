import { DOCUMENT } from '@angular/common';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed, fakeAsync, flush, tick } from '@angular/core/testing';
import { Subject } from 'rxjs';

import { gameState, me } from '../../../testing/game-state';
import { GameStore, REHYDRATE_TIMEOUT_MS } from './game-store';
import { LiveClosedError, LiveEvent, Realtime } from './realtime';
import { Session } from './session';

describe('GameStore', () => {
  let store: GameStore;
  let session: Session;
  let http: HttpTestingController;
  let live: Subject<LiveEvent>;
  let realtime: jasmine.SpyObj<Realtime>;

  beforeEach(() => configure());

  function configure(): void {
    localStorage.clear();
    live = new Subject<LiveEvent>();
    realtime = jasmine.createSpyObj<Realtime>('Realtime', ['connect']);
    realtime.connect.and.callFake(() => {
      live = new Subject<LiveEvent>();
      return live.asObservable();
    });
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: Realtime, useValue: realtime },
      ],
    });
    session = TestBed.inject(Session);
    session.set({ code: 'ABCD', playerId: 'h', token: 'tok' });
    store = TestBed.inject(GameStore);
    http = TestBed.inject(HttpTestingController);
  }

  afterEach(() => localStorage.clear());

  // --- screens -------------------------------------------------------------------------

  it('derives the home screen when there is no session', () => {
    session.clear();
    expect(store.screen()).toBe('home');
  });

  it('waits on a restoring screen while a known session has no state yet', () => {
    expect(store.screen()).toBe('restoring');
  });

  it('derives the lobby screen', () => {
    store.apply(gameState({ status: 'lobby', end_at: 0 }));
    expect(store.screen()).toBe('lobby');
  });

  it('derives the game screen while running and not expired', () => {
    store.apply(gameState());
    expect(store.screen()).toBe('game');
  });

  it('derives the end screen once the server clock is past end_at', () => {
    const now = Date.now();
    store.apply(gameState({ end_at: now - 1, server_now: now }));
    expect(store.screen()).toBe('end');
  });

  // --- viewer-relative state -----------------------------------------------------------

  it('resolves me, target and rank from the viewer view', () => {
    store.apply(gameState());
    expect(store.me()?.id).toBe('h');
    expect(store.target()?.id).toBe('b');
    expect(store.myRank()).toBe(1);
    expect(store.isHost()).toBeTrue();
  });

  it('surfaces an incoming claim targeting the viewer', () => {
    store.apply(
      gameState({
        claims: [{ atk: 'b', atk_name: 'B', target: 'h', mission: 'm', status: 'pending' }],
      }),
    );
    expect(store.incoming()?.atk).toBe('b');
    expect(store.isPending()).toBeFalse();
  });

  it('tracks the viewer own pending claim', () => {
    store.apply(
      gameState({
        claims: [{ atk: 'h', atk_name: 'H', target: 'b', mission: 'm', status: 'pending' }],
      }),
    );
    expect(store.isPending()).toBeTrue();
    expect(store.incoming()).toBeNull();
  });

  it('exposes the answer to my claim until I acknowledge it', async () => {
    const mine = (status: 'pending' | 'ok' | 'no') =>
      gameState({ claims: [{ atk: 'h', atk_name: 'H', target: 'b', mission: 'm', status }] });
    store.apply(mine('pending'));
    expect(store.myResult()).toBeNull();
    store.apply({ ...mine('ok'), version: 2 });
    expect(store.myResult()).toBe('ok');
    expect(store.isPending()).toBeFalse();

    const done = store.acknowledge();
    const req = http.expectOne((r) => r.url.endsWith('/games/ABCD/claims/h/ack'));
    expect(req.request.method).toBe('POST');
    req.flush(gameState({ version: 3, claims: [] }));
    await done;
    expect(store.myResult()).toBeNull();
  });

  it('quietly resyncs when there is nothing left to acknowledge (game ended meanwhile)', async () => {
    store.apply(
      gameState({ claims: [{ atk: 'h', atk_name: 'H', target: 'b', mission: 'm', status: 'ok' }] }),
    );
    const done = store.acknowledge();
    http
      .expectOne((r) => r.url.endsWith('/claims/h/ack'))
      .flush({ error: 'GameNotRunning' }, { status: 409, statusText: 'Conflict' });
    await Promise.resolve();
    await Promise.resolve();
    http
      .expectOne((r) => r.method === 'GET' && r.url.endsWith('/games/ABCD'))
      .flush(gameState({ status: 'ended', version: 9, claims: [] }));
    expect(await done).toBeNull();
    expect(store.screen()).toBe('end');
  });

  it('still reports unexpected acknowledgement failures', async () => {
    store.apply(
      gameState({ claims: [{ atk: 'h', atk_name: 'H', target: 'b', mission: 'm', status: 'no' }] }),
    );
    const done = store.acknowledge();
    http
      .expectOne((r) => r.url.endsWith('/claims/h/ack'))
      .flush(null, { status: 500, statusText: 'Server Error' });
    await expectAsync(done).toBeRejected();
  });

  it('has nothing to acknowledge while my claim is pending', async () => {
    store.apply(
      gameState({
        claims: [{ atk: 'h', atk_name: 'H', target: 'b', mission: 'm', status: 'pending' }],
      }),
    );
    expect(await store.acknowledge()).toBeNull();
    http.expectNone(() => true);
  });

  it('is not host when the viewer is someone else', () => {
    store.apply(gameState({ me: me('b', 'h') }));
    expect(store.isHost()).toBeFalse();
  });

  // --- F3: server clock ------------------------------------------------------------------

  it('counts down against the server clock, not the device clock', () => {
    const device = Date.now();
    // The phone runs 2 minutes fast: the server says it is 2 min earlier than the device thinks.
    const serverNow = device - 120_000;
    store.apply(gameState({ server_now: serverNow, end_at: serverNow + 90_000 }));
    expect(store.remaining()).toBeGreaterThan(85);
    expect(store.remaining()).toBeLessThanOrEqual(90);
    expect(store.screen()).toBe('game'); // a naive device-clock check would say 'end'
  });

  // --- F9: newest state wins -------------------------------------------------------------

  it('ignores a state older than the one it holds', () => {
    store.apply(gameState({ version: 5, players: [] }));
    store.apply(gameState({ version: 4 }));
    expect(store.state()?.version).toBe(5);
    store.apply(gameState({ version: 6 }));
    expect(store.state()?.version).toBe(6);
  });

  it('applies the REST response of an action immediately', async () => {
    store.apply(gameState({ version: 1 }));
    const done = store.swap();
    const req = http.expectOne((r) => r.url.endsWith('/games/ABCD/swap-mission'));
    expect(req.request.headers.get('X-Player-Token')).toBe('tok');
    req.flush(gameState({ version: 2, me: me('h', 'b', 1) }));
    await done;
    expect(store.me()?.score).toBe(1);
  });

  // --- create / join ---------------------------------------------------------------------

  it('stores the secret returned on join and connects', async () => {
    session.clear();
    const done = store.join('WXYZ', 'Bob');
    http
      .expectOne((r) => r.url.endsWith('/games/WXYZ/players'))
      .flush({
        ...gameState({ code: 'WXYZ', me: me('b', 'h') }),
        player_id: 'b',
        player_token: 's',
      });
    await done;
    expect(session.session()).toEqual({ code: 'WXYZ', playerId: 'b', token: 's' });
    expect(realtime.connect).toHaveBeenCalledWith('WXYZ', { playerId: 'b', token: 's' });
    expect(store.live()).toBe('connecting');
  });

  // --- F4/F5: rehydrate ------------------------------------------------------------------

  it('routes to the gone screen when the game no longer exists', async () => {
    const done = store.rehydrate();
    http
      .expectOne((r) => r.url.endsWith('/games/ABCD'))
      .flush(null, { status: 404, statusText: 'NF' });
    await done;
    expect(store.screen()).toBe('gone');
    expect(session.session()).toBeNull();
  });

  it('routes to the gone screen when the credentials are refused', async () => {
    const done = store.rehydrate();
    http
      .expectOne((r) => r.url.endsWith('/games/ABCD'))
      .flush(null, { status: 401, statusText: 'U' });
    await done;
    expect(store.screen()).toBe('gone');
  });

  it('keeps the session on a server error and lets the socket catch up', async () => {
    const done = store.rehydrate();
    http
      .expectOne((r) => r.url.endsWith('/games/ABCD'))
      .flush(null, { status: 502, statusText: 'BG' });
    await done;
    expect(session.session()).not.toBeNull();
    expect(store.screen()).toBe('restoring');
    expect(store.live()).toBe('offline');
    expect(realtime.connect).toHaveBeenCalled();

    live.next({ kind: 'connected' });
    live.next({ kind: 'state', state: gameState() });
    expect(store.screen()).toBe('game');
    expect(store.live()).toBe('online');
  });

  it('stops waiting for a silent server', fakeAsync(() => {
    let finished = false;
    void store.rehydrate().then(() => (finished = true));
    tick(REHYDRATE_TIMEOUT_MS);
    flush();
    expect(finished).toBeTrue();
    expect(session.session()).not.toBeNull();
    http.match(() => true); // the request is abandoned
  }));

  it('sends the credentials when rehydrating', async () => {
    const done = store.rehydrate();
    const req = http.expectOne((r) => r.url.endsWith('/games/ABCD'));
    expect(req.request.headers.get('X-Player-Id')).toBe('h');
    req.flush(gameState());
    await done;
    expect(store.screen()).toBe('game');
  });

  // --- live connection -------------------------------------------------------------------

  it('marks the game gone when the server closes the socket for good', async () => {
    const done = store.rehydrate();
    http.expectOne(() => true).flush(gameState());
    await done;
    live.error(new LiveClosedError(4404));
    expect(store.screen()).toBe('gone');
  });

  it('shows the connection as offline while reconnecting', async () => {
    const done = store.rehydrate();
    http.expectOne(() => true).flush(gameState());
    await done;
    live.next({ kind: 'connected' });
    live.next({ kind: 'disconnected' });
    expect(store.live()).toBe('offline');
    expect(store.connected()).toBeFalse();
  });

  it('drops the socket in the background and reconnects on return', async () => {
    const done = store.rehydrate();
    http.expectOne(() => true).flush(gameState());
    await done;
    const doc = TestBed.inject(DOCUMENT);
    const visibility = spyOnProperty(doc, 'visibilityState', 'get');

    visibility.and.returnValue('hidden');
    doc.dispatchEvent(new Event('visibilitychange'));
    expect(live.observed).toBeFalse();

    visibility.and.returnValue('visible');
    doc.dispatchEvent(new Event('visibilitychange'));
    expect(realtime.connect).toHaveBeenCalledTimes(2);
  });

  // --- I3: end at time-up ----------------------------------------------------------------

  it('asks the server once when the clock runs out, so it settles and broadcasts', fakeAsync(() => {
    TestBed.resetTestingModule();
    configure(); // build the store inside fakeAsync so its 1 s ticker is a fake timer
    const now = Date.now();
    store.apply(gameState({ server_now: now, end_at: now + 1500, version: 3 }));
    tick(2000);
    http
      .expectOne((r) => r.method === 'GET' && r.url.endsWith('/games/ABCD'))
      .flush(gameState({ status: 'ended', version: 4 }));
    tick(3000);
    http.expectNone(() => true); // not again for an ended game
    expect(store.screen()).toBe('end');
    TestBed.resetTestingModule(); // stops the store's interval
  }));

  // --- B4: leaving ------------------------------------------------------------------------

  it('leaving a running game tells the server', async () => {
    store.apply(gameState());
    const done = store.leave();
    http.expectOne((r) => r.method === 'DELETE').flush(gameState());
    await done;
    expect(session.session()).toBeNull();
    expect(store.screen()).toBe('home');
  });

  it('leaving an ended game only forgets it locally (stays in everyone ranking)', async () => {
    store.apply(gameState({ status: 'ended' }));
    await store.leave();
    http.expectNone((r) => r.method === 'DELETE');
    expect(session.session()).toBeNull();
  });

  it('host can end the game', async () => {
    store.apply(gameState());
    const done = store.end();
    http
      .expectOne((r) => r.url.endsWith('/games/ABCD/end'))
      .flush(gameState({ status: 'ended', version: 2 }));
    await done;
    expect(store.screen()).toBe('end');
  });
});
