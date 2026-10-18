import { TestBed } from '@angular/core/testing';

import { fakeStore, gameState, player } from '../../../testing/game-state';
import { translocoTesting } from '../../../testing/transloco-testing';
import { GameStore } from '../../core/services/game-store';
import { End, outrightWinner } from './end';

describe('End screen', () => {
  describe('outrightWinner', () => {
    it('is the player alone at the top', () => {
      expect(outrightWinner([player('a', 3), player('b', 1)])?.id).toBe('a');
    });

    it('is nobody on a tie', () => {
      expect(outrightWinner([player('a', 2), player('b', 2)])).toBeNull();
    });

    it('is nobody when the best score is zero (or less)', () => {
      expect(outrightWinner([player('a', 0), player('b', -1)])).toBeNull();
      expect(outrightWinner([])).toBeNull();
    });
  });

  function render(ranking = [player('h', 3), player('b', 1)]) {
    const store = fakeStore(gameState({ status: 'ended', ranking }));
    TestBed.configureTestingModule({
      imports: [End, translocoTesting()],
      providers: [{ provide: GameStore, useValue: store }],
    });
    const fixture = TestBed.createComponent(End);
    fixture.detectChanges();
    return { store, fixture, text: (fixture.nativeElement as HTMLElement).textContent ?? '' };
  }

  it('congratulates the winner with a pluralized score', () => {
    const { text } = render();
    expect(text).toContain('end.youWin');
    expect(text).toContain('end.finalScore.other');
  });

  it('announces a tie', () => {
    expect(render([player('h', 2), player('b', 2)]).text).toContain('end.tie');
  });

  it('does not crown anyone at zero points', () => {
    expect(render([player('h', 0), player('b', 0)]).text).toContain('end.gameOver');
  });

  it('going home goes through the store (which keeps the player in the ranking)', () => {
    const { store, fixture } = render();
    (fixture.nativeElement as HTMLElement).querySelector('button')!.click();
    expect(store.leave).toHaveBeenCalled();
  });
});
