import { Injectable } from '@angular/core';
import { TestBed, fakeAsync, tick } from '@angular/core/testing';

import { gameState } from '../../../testing/game-state';
import { LiveClosedError, LiveEvent, PING_INTERVAL_MS, Realtime, backoffDelay } from './realtime';

class FakeSocket {
  readyState = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;

  constructor(readonly url: string) {}

  send(data: string): void {
    this.sent.push(data);
  }
  close(): void {
    this.readyState = 3;
  }
  // test drivers
  open(): void {
    this.readyState = 1;
    this.onopen?.();
  }
  receive(data: string): void {
    this.onmessage?.({ data });
  }
  drop(code: number): void {
    this.readyState = 3;
    this.onclose?.({ code });
  }
}

@Injectable()
class TestRealtime extends Realtime {
  sockets: FakeSocket[] = [];
  protected override open(url: string): WebSocket {
    const socket = new FakeSocket(url);
    this.sockets.push(socket);
    return socket as unknown as WebSocket;
  }
  get last(): FakeSocket {
    return this.sockets[this.sockets.length - 1];
  }
}

const AUTH = { playerId: 'p1', token: 'tok' };

describe('Realtime', () => {
  let realtime: TestRealtime;
  let events: LiveEvent[];
  let error: unknown;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [{ provide: Realtime, useClass: TestRealtime }] });
    realtime = TestBed.inject(Realtime) as TestRealtime;
    events = [];
    error = undefined;
  });

  const listen = () =>
    realtime
      .connect('ABCD', AUTH)
      .subscribe({ next: (e) => events.push(e), error: (e) => (error = e) });

  it('authenticates with its first message and emits states', () => {
    const sub = listen();
    expect(realtime.last.url).toContain('/games/ABCD/live');
    realtime.last.open();
    expect(JSON.parse(realtime.last.sent[0])).toEqual({ player_id: 'p1', token: 'tok' });

    realtime.last.receive(JSON.stringify(gameState({ version: 7 })));

    expect(events.map((e) => e.kind)).toEqual(['connected', 'state']);
    expect((events[1] as { state: { version: number } }).state.version).toBe(7);
    sub.unsubscribe();
  });

  it('ignores pong and anything that is not a game state', () => {
    const sub = listen();
    realtime.last.open();
    realtime.last.receive('pong');
    realtime.last.receive('{"hello": 1}');
    expect(events).toEqual([]);
    sub.unsubscribe();
  });

  it('pings periodically to keep proxies from closing the socket', fakeAsync(() => {
    const sub = listen();
    realtime.last.open();
    tick(PING_INTERVAL_MS * 2);
    expect(realtime.last.sent.filter((m) => m === 'ping').length).toBe(2);
    sub.unsubscribe();
    tick(PING_INTERVAL_MS);
    expect(realtime.last.sent.filter((m) => m === 'ping').length).toBe(2); // stopped
  }));

  it('reconnects with a growing delay after a network drop', fakeAsync(() => {
    const sub = listen();
    realtime.last.open();
    realtime.last.drop(1006);
    expect(events.at(-1)).toEqual({ kind: 'disconnected' });
    expect(realtime.sockets.length).toBe(1);

    tick(backoffDelay(1));
    expect(realtime.sockets.length).toBe(2);
    realtime.last.drop(1006);
    tick(backoffDelay(1));
    expect(realtime.sockets.length).toBe(2); // second wait is longer
    tick(backoffDelay(2) - backoffDelay(1));
    expect(realtime.sockets.length).toBe(3);
    expect(error).toBeUndefined();

    // a successful connection resets the delay
    realtime.last.open();
    realtime.last.receive(JSON.stringify(gameState()));
    realtime.last.drop(1006);
    tick(backoffDelay(1));
    expect(realtime.sockets.length).toBe(4);
    sub.unsubscribe();
  }));

  for (const code of [4401, 4403, 4404]) {
    it(`gives up on close code ${code}`, fakeAsync(() => {
      listen();
      realtime.last.open();
      realtime.last.drop(code);
      tick(60_000);
      expect(realtime.sockets.length).toBe(1);
      expect(error).toEqual(jasmine.any(LiveClosedError));
      expect((error as LiveClosedError).code).toBe(code);
    }));
  }

  it('closes the socket on unsubscribe without reporting an error', () => {
    const sub = listen();
    realtime.last.open();
    sub.unsubscribe();
    expect(realtime.last.readyState).toBe(3);
    expect(error).toBeUndefined();
  });

  it('caps the backoff at 30 s', () => {
    expect([1, 2, 3, 4].map(backoffDelay)).toEqual([1000, 2000, 4000, 8000]);
    expect(backoffDelay(20)).toBe(30_000);
  });
});
