import { TestBed } from '@angular/core/testing';

import { Session, parseSession } from './session';

const VALID = { code: 'ABCD', playerId: 'p1', token: 'tok' };

describe('Session', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => localStorage.clear());

  it('persists and restores the session', () => {
    TestBed.inject(Session).set(VALID);
    const reloaded = TestBed.runInInjectionContext(() => new Session());
    expect(reloaded.session()).toEqual(VALID);
    expect(reloaded.auth()).toEqual({ playerId: 'p1', token: 'tok' });
    expect(reloaded.code()).toBe('ABCD');
  });

  it('clears the session', () => {
    const session = TestBed.inject(Session);
    session.set(VALID);
    session.clear();
    expect(session.session()).toBeNull();
    expect(session.auth()).toBeNull();
    expect(localStorage.getItem('murder.session')).toBeNull();
  });

  it('keeps working in memory when storage refuses writes', () => {
    spyOn(localStorage, 'setItem').and.throwError('QuotaExceededError');
    spyOn(localStorage, 'removeItem').and.throwError('SecurityError');
    const session = TestBed.inject(Session);
    expect(() => session.set(VALID)).not.toThrow();
    expect(session.playerId()).toBe('p1');
    expect(() => session.clear()).not.toThrow();
  });

  it('drops a stored session from before the secret existed', () => {
    localStorage.setItem('murder.session', JSON.stringify({ code: 'ABCD', playerId: 'p1' }));
    expect(TestBed.inject(Session).session()).toBeNull();
  });

  it('drops corrupt storage', () => {
    localStorage.setItem('murder.session', '{oops');
    expect(TestBed.inject(Session).session()).toBeNull();
  });

  describe('parseSession', () => {
    it('accepts a well-formed value', () => {
      expect(parseSession({ ...VALID, extra: 1 })).toEqual(VALID);
    });

    it('rejects malformed values', () => {
      expect(parseSession(null)).toBeNull();
      expect(parseSession('ABCD')).toBeNull();
      expect(parseSession({ ...VALID, code: 'abc' })).toBeNull();
      expect(parseSession({ ...VALID, token: '' })).toBeNull();
      expect(parseSession({ ...VALID, playerId: 42 })).toBeNull();
    });
  });
});
