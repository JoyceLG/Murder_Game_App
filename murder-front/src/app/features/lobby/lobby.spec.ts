import { ComponentFixture, TestBed } from '@angular/core/testing';

import { fakeStore, gameState, me } from '../../../testing/game-state';
import { translocoTesting } from '../../../testing/transloco-testing';
import { GameStore } from '../../core/services/game-store';
import { Toast } from '../../core/services/toast';
import { Lobby } from './lobby';

describe('Lobby screen', () => {
  let store: ReturnType<typeof fakeStore>;
  let toast: jasmine.SpyObj<Toast>;
  let fixture: ComponentFixture<Lobby>;

  function setup(state = gameState({ status: 'lobby', end_at: 0 })) {
    store = fakeStore(state);
    toast = jasmine.createSpyObj<Toast>('Toast', ['show']);
    TestBed.configureTestingModule({
      imports: [Lobby, translocoTesting()],
      providers: [
        { provide: GameStore, useValue: store },
        { provide: Toast, useValue: toast },
      ],
    });
    fixture = TestBed.createComponent(Lobby);
    fixture.detectChanges();
  }

  const el = () => fixture.nativeElement as HTMLElement;

  it('reports a failed start instead of failing silently', async () => {
    setup();
    store.start.and.rejectWith(new Error('409'));
    await fixture.componentInstance.start();
    expect(toast.show).toHaveBeenCalledWith('lobby.startError', 'bad');
  });

  it('starts only once on a double tap', async () => {
    setup();
    await Promise.all([fixture.componentInstance.start(), fixture.componentInstance.start()]);
    expect(store.start).toHaveBeenCalledTimes(1);
  });

  it('marks the active mission mode for assistive tech', () => {
    setup();
    const pressed = [...el().querySelectorAll('button[aria-pressed="true"]')].map((b) =>
      b.textContent?.trim(),
    );
    expect(pressed).toEqual(['lobby.modeAugment']);
  });

  it('labels the mission input', () => {
    setup();
    expect(el().querySelector('input.mission-edit')?.getAttribute('aria-label')).toBe(
      'lobby.poolPlaceholder',
    );
  });

  it('uses the plural form for the score goal', () => {
    setup(gameState({ status: 'lobby', end_at: 0, max_score: 1 }));
    expect(el().textContent).toContain('lobby.rulesGoalPoints.one');
  });

  it('hides host settings from other players', () => {
    setup(gameState({ status: 'lobby', end_at: 0, me: me('b', null) }));
    expect(el().textContent).not.toContain('lobby.settings');
    expect(el().textContent).toContain('lobby.waitingHost');
  });

  it('explains when the viewer is no longer part of the game', () => {
    setup(gameState({ status: 'lobby', me: null }));
    expect(el().textContent).toContain('common.notInGame');
  });
});
