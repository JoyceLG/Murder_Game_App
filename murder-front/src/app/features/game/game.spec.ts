import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';

import { fakeStore, gameState, me } from '../../../testing/game-state';
import { translocoTesting } from '../../../testing/transloco-testing';
import { GameStore } from '../../core/services/game-store';
import { Toast } from '../../core/services/toast';
import { Dossier } from '../../shared/dossier/dossier';
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
        claims: [
          { atk: 'b', atk_name: 'B', target: 'h', mission: 'Chante en canon', status: 'pending' },
        ],
      }),
    );
    expect(text()).toContain('game.attempt');
    expect(text()).toContain('game.quoteOpenChante en canongame.quoteClose');
  });

  it('after a confirmation, shows the success and waits for me to start the next mission', () => {
    setup(
      gameState({ claims: [{ atk: 'h', atk_name: 'H', target: 'b', mission: 'm', status: 'ok' }] }),
    );
    expect(text()).toContain('game.resultOk');
    expect(button('game.kill')).toBeUndefined(); // nothing else until acknowledged
    expect(button('game.swap')).toBeUndefined();
    button('game.nextMission').click();
    expect(store.acknowledge).toHaveBeenCalled();
  });

  it('keeps the kill number on the elimination just confirmed until acknowledged', () => {
    setup(
      gameState({
        me: me('h', 'b', 1),
        claims: [{ atk: 'h', atk_name: 'H', target: 'b', mission: 'm', status: 'ok' }],
      }),
    );
    const dossier = fixture.debugElement.query(By.directive(Dossier)).componentInstance as Dossier;
    expect(dossier.killNo()).toBe(1); // not 2: the confirmed kill is still on screen
  });

  it('a pending claim of mine shows the waiting card, not a result', () => {
    setup(
      gameState({
        claims: [{ atk: 'h', atk_name: 'H', target: 'b', mission: 'm', status: 'pending' }],
      }),
    );
    store.isPending.set(true);
    fixture.detectChanges();
    expect(text()).not.toContain('game.resultNo');
    expect(text()).toContain('game.waitingFor');
  });

  it('after a refusal, offers a new mission', () => {
    setup(
      gameState({ claims: [{ atk: 'h', atk_name: 'H', target: 'b', mission: 'm', status: 'no' }] }),
    );
    expect(text()).toContain('game.resultNo');
    button('game.newMission').click();
    expect(store.acknowledge).toHaveBeenCalled();
  });

  // --- #20 -----------------------------------------------------------------------------

  it('offers the one free swap at 0 points, with its own confirmation', () => {
    setup(gameState({ me: me('h', 'b', 0, 0) }));
    expect(button('game.swap').textContent).toContain('game.swapFree');
    button('game.swap').click();
    fixture.detectChanges();
    expect(text()).toContain('game.swapConfirmFree');
    button('game.swapYesFree').click();
    expect(store.swap).toHaveBeenCalled();
  });

  it('shows the 1-point cost when the player has points', () => {
    setup(gameState({ me: me('h', 'b', 2, 1) }));
    expect(button('game.swap').textContent).toContain('game.swapCost');
    button('game.swap').click();
    fixture.detectChanges();
    expect(text()).toContain('game.swapConfirm');
    expect(text()).not.toContain('game.swapConfirmFree');
  });

  it('locks the swap once the free one is used at 0 points, and says why', () => {
    setup(gameState({ me: me('h', 'b', 0, null) }));
    expect(button('game.swap').disabled).toBeTrue();
    expect(button('game.swap').textContent).not.toContain('game.swapFree'); // no "free" on a lock
    expect(button('game.swap').textContent).not.toContain('game.swapCost');
    expect(text()).toContain('game.swapLocked');
  });

  it('keeps showing my own pending claim when a claim on me arrives', () => {
    setup(
      gameState({
        claims: [
          { atk: 'h', atk_name: 'H', target: 'b', mission: 'x', status: 'pending' },
          { atk: 'b', atk_name: 'B', target: 'h', mission: 'y', status: 'pending' },
        ],
      }),
    );
    store.isPending.set(true);
    fixture.detectChanges();
    expect(text()).toContain('game.waitingFor');
    expect(button('game.confirm')).toBeDefined();
    expect(button('game.kill')).toBeUndefined();
  });

  it('an elimination attempt on me blocks claiming and swapping until I answer', () => {
    setup(
      gameState({
        claims: [{ atk: 'b', atk_name: 'B', target: 'h', mission: 'x', status: 'pending' }],
      }),
    );
    expect(button('game.kill')).toBeUndefined();
    expect(button('game.swap')).toBeUndefined();
    expect(text()).toContain('game.answerFirst');
    expect(button('game.confirm')).toBeDefined();
  });

  // --- #15 animations --------------------------------------------------------------------

  it('an elimination attempt on me drops in', () => {
    setup(
      gameState({
        claims: [{ atk: 'b', atk_name: 'B', target: 'h', mission: 'x', status: 'pending' }],
      }),
    );
    expect(fixture.nativeElement.querySelector('.card.confirm').classList).toContain(
      'anim-attacked',
    );
  });

  it('a confirmed claim pops in as a success, a refused one shakes', () => {
    setup(
      gameState({ claims: [{ atk: 'h', atk_name: 'H', target: 'b', mission: 'm', status: 'ok' }] }),
    );
    const ok = fixture.nativeElement.querySelector('.card.result') as HTMLElement;
    expect(ok.classList).toContain('anim-success');
    expect(ok.classList).not.toContain('anim-refused');

    TestBed.resetTestingModule();
    setup(
      gameState({ claims: [{ atk: 'h', atk_name: 'H', target: 'b', mission: 'm', status: 'no' }] }),
    );
    const no = fixture.nativeElement.querySelector('.card.result') as HTMLElement;
    expect(no.classList).toContain('anim-refused');
    expect(no.classList).not.toContain('anim-success');
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
