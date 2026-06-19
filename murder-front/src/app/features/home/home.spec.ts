import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { translocoTesting } from '../../../testing/transloco-testing';
import { GameStore } from '../../core/services/game-store';
import { Toast } from '../../core/services/toast';
import { Home } from './home';

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
});
