import { ComponentFixture, TestBed } from '@angular/core/testing';

import { fakeStore, gameState, me } from '../../../testing/game-state';
import { translocoTesting } from '../../../testing/transloco-testing';
import { GameStore } from '../../core/services/game-store';
import { Toast } from '../../core/services/toast';
import { Game } from './game';

describe('Game screen', () => {
  let store: ReturnType<typeof fakeStore>;
  let toast: jasmine.SpyObj<Toast>;
  let fixture: ComponentFixture<Game>;

  function setup(state = gameState()) {
    store = fakeStore(state);
    toast = jasmine.createSpyObj<Toast>('Toast', ['show']);
    TestBed.configureTestingModule({
      imports: [Game, translocoTesting()],
      providers: [
        { provide: GameStore, useValue: store },
        { provide: Toast, useValue: toast },
      ],
    });
    fixture = TestBed.createComponent(Game);
    fixture.detectChanges();
  }

  const text = () => (fixture.nativeElement as HTMLElement).textContent ?? '';
  const button = (label: string) =>
    [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find((b) =>
      b.textContent?.includes(label),
    ) as HTMLButtonElement;

  it('asks for confirmation before swapping a mission (it costs a point)', () => {
    setup();
    button('game.swap').click();
    fixture.detectChanges();
    expect(store.swap).not.toHaveBeenCalled();
    expect(text()).toContain('game.swapConfirm');

    button('game.swapYes').click();
    expect(store.swap).toHaveBeenCalledTimes(1);
  });

  it('can cancel the swap', () => {
    setup();
    button('game.swap').click();
    fixture.detectChanges();
    button('common.cancel').click();
    fixture.detectChanges();
    expect(text()).not.toContain('game.swapConfirm');
  });

  it('ignores a double tap while an action is in flight', async () => {
    setup();
    let release!: () => void;
    store.claimKill.and.returnValue(new Promise<void>((r) => (release = r)));
    const first = fixture.componentInstance.kill();
    const second = fixture.componentInstance.kill();
    fixture.detectChanges();
    expect(button('game.kill').disabled).toBeTrue();
    release();
    await Promise.all([first, second]);
    expect(store.claimKill).toHaveBeenCalledTimes(1);
  });

  it('reports a refused claim', async () => {
    setup();
    store.claimKill.and.rejectWith(new Error('409'));
    await fixture.componentInstance.kill();
    expect(toast.show).toHaveBeenCalledWith('game.claimFailed', 'bad');
  });

  it('reports any other failed action', async () => {
    setup();
    store.confirm.and.rejectWith(new Error('boom'));
    await fixture.componentInstance.confirm(true);
    expect(toast.show).toHaveBeenCalledWith('common.actionFailed', 'bad');
  });

  it('lets the host end the game after confirming', async () => {
    setup();
    button('game.endGame').click();
    fixture.detectChanges();
    button('game.endYes').click();
    expect(store.end).toHaveBeenCalled();
  });

  it('does not offer ending the game to other players', () => {
    setup(gameState({ me: me('b', 'h') }));
    expect(button('game.endGame')).toBeUndefined();
  });

  it('shows the incoming claim with the quoted mission', () => {
    setup(
      gameState({
        claims: [{ atk: 'b', atk_name: 'B', target: 'h', mission: 'x', status: 'pending' }],
      }),
    );
    expect(text()).toContain('game.attempt');
    expect(text()).toContain('game.quoteOpen');
    expect(text()).toContain('x');
  });

  it('explains when the viewer is no longer part of the game', () => {
    setup(gameState({ me: null }));
    expect(text()).toContain('common.notInGame');
    button('common.home').click();
    expect(store.exit).toHaveBeenCalled();
  });

  it('shows a restoring notice without state instead of a blank page', () => {
    setup(null as never);
    expect(text()).toContain('app.restoring');
  });
});
