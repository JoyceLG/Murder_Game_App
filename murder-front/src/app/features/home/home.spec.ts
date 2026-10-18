import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { translocoTesting } from '../../../testing/transloco-testing';
import { GameStore } from '../../core/services/game-store';
import { Toast } from '../../core/services/toast';
import { Home, joinErrorKey } from './home';

describe('Home', () => {
  let store: jasmine.SpyObj<GameStore>;
  let toast: jasmine.SpyObj<Toast>;

  beforeEach(() => {
    store = jasmine.createSpyObj<GameStore>('GameStore', ['create', 'join']);
    toast = jasmine.createSpyObj<Toast>('Toast', ['show']);
    TestBed.configureTestingModule({
      imports: [Home, translocoTesting()],
      providers: [
        provideRouter([]),
        { provide: GameStore, useValue: store },
        { provide: Toast, useValue: toast },
      ],
    });
  });

  it('refuses to create a game without a name', async () => {
    const home = TestBed.createComponent(Home).componentInstance;
    home.name = '   ';
    await home.create();
    expect(toast.show).toHaveBeenCalledWith('home.error.name', 'bad');
    expect(store.create).not.toHaveBeenCalled();
  });

  it('creates a game with a trimmed name', async () => {
    store.create.and.resolveTo();
    const home = TestBed.createComponent(Home).componentInstance;
    home.name = '  Corbeau  ';
    await home.create();
    expect(store.create).toHaveBeenCalledWith('Corbeau');
  });

  it('rejects a join code that is not four characters', async () => {
    const home = TestBed.createComponent(Home).componentInstance;
    home.name = 'Corbeau';
    home.code = 'AB';
    await home.join();
    expect(toast.show).toHaveBeenCalledWith('home.error.code', 'bad');
    expect(store.join).not.toHaveBeenCalled();
  });

  it('tells why a join failed', async () => {
    store.join.and.rejectWith(
      new HttpErrorResponse({ status: 409, error: { error: 'GameAlreadyStarted' } }),
    );
    const home = TestBed.createComponent(Home).componentInstance;
    home.name = 'Corbeau';
    home.code = 'abcd';
    await home.join();
    expect(store.join).toHaveBeenCalledWith('ABCD', 'Corbeau');
    expect(toast.show).toHaveBeenCalledWith('home.error.started', 'bad');
  });

  it('creates only once on a double tap', async () => {
    store.create.and.resolveTo();
    const home = TestBed.createComponent(Home).componentInstance;
    home.name = 'Corbeau';
    await Promise.all([home.create(), home.create()]);
    expect(store.create).toHaveBeenCalledTimes(1);
  });

  describe('joinErrorKey', () => {
    const failure = (status: number, error?: string) =>
      new HttpErrorResponse({ status, error: error ? { error } : null });

    it('maps each failure to its own message', () => {
      expect(joinErrorKey(failure(404, 'GameNotFound'))).toBe('home.error.notFound');
      expect(joinErrorKey(failure(409, 'TooManyPlayers'))).toBe('home.error.full');
      expect(joinErrorKey(failure(409, 'GameAlreadyStarted'))).toBe('home.error.started');
      expect(joinErrorKey(failure(429))).toBe('home.error.rateLimited');
      expect(joinErrorKey(failure(0))).toBe('home.error.network');
      expect(joinErrorKey(failure(500))).toBe('common.actionFailed');
    });
  });
});
