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

  it('refuses a pool mission shaped like a catalogue key before calling the server', async () => {
    setup();
    await fixture.componentInstance.addToPool('core.09');
    expect(toast.show).toHaveBeenCalledWith('common.missionReserved', 'bad');
    expect(store.addMission).not.toHaveBeenCalled();
  });

  it('refuses a score goal below 1 instead of silently clearing it', async () => {
    setup(gameState({ status: 'lobby', end_at: 0, max_score: 5 }));
    const lobby = fixture.componentInstance;
    lobby.maxScore = -2;
    await lobby.applyConfig();
    expect(toast.show).toHaveBeenCalledWith('lobby.maxScoreInvalid', 'bad');
    expect(store.updateConfig).not.toHaveBeenCalled();
    expect(lobby.maxScore).toBe(5); // back to the current goal
  });

  it('refuses pasted text that is not a number instead of clearing the goal', async () => {
    setup(gameState({ status: 'lobby', end_at: 0, max_score: 5 }));
    const lobby = fixture.componentInstance;
    lobby.maxScore = null; // what the number input reports for "abc"
    await lobby.applyConfig({ validity: { badInput: true } });
    expect(toast.show).toHaveBeenCalledWith('lobby.maxScoreInvalid', 'bad');
    expect(store.updateConfig).not.toHaveBeenCalled();
    expect(lobby.maxScore as number | null).toBe(5);
  });

  it('blocks signs in every number field of the lobby', () => {
    setup();
    const inputs = (fixture.nativeElement as HTMLElement).querySelectorAll('input[type=number]');
    expect(inputs.length).toBe(3);
    for (const input of Array.from(inputs)) {
      const event = new KeyboardEvent('keydown', { key: '-', cancelable: true });
      input.dispatchEvent(event);
      expect(event.defaultPrevented).toBeTrue();
    }
  });

  it('still allows clearing the goal (no limit)', async () => {
    setup();
    const lobby = fixture.componentInstance;
    lobby.maxScore = null;
    await lobby.applyConfig();
    expect(store.updateConfig).toHaveBeenCalledWith(12, null, 'augment');
  });

  it('does not let a sign be typed in the number fields', () => {
    setup();
    for (const key of ['-', '+', 'e']) {
      const event = new KeyboardEvent('keydown', { key, cancelable: true });
      fixture.componentInstance.blockSign(event);
      expect(event.defaultPrevented).withContext(key).toBeTrue();
    }
    const digit = new KeyboardEvent('keydown', { key: '3', cancelable: true });
    fixture.componentInstance.blockSign(digit);
    expect(digit.defaultPrevented).toBeFalse();
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
