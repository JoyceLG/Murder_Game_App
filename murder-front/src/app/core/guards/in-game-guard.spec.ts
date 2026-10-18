import { TestBed } from '@angular/core/testing';
import {
  ActivatedRouteSnapshot,
  Router,
  RouterStateSnapshot,
  UrlTree,
  provideRouter,
} from '@angular/router';

import { Session } from '../services/session';
import { inGameGuard } from './in-game-guard';

describe('inGameGuard', () => {
  const run = () =>
    TestBed.runInInjectionContext(() =>
      inGameGuard({} as ActivatedRouteSnapshot, {} as RouterStateSnapshot),
    );

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
  });

  it('lets a player with a session in', () => {
    TestBed.inject(Session).set({ code: 'ABCD', playerId: 'p1', token: 't' });
    expect(run()).toBeTrue();
  });

  it('sends everyone else home', () => {
    const result = run() as UrlTree;
    expect(TestBed.inject(Router).serializeUrl(result)).toBe('/home');
  });
});
