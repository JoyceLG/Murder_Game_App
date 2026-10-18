import { TestBed } from '@angular/core/testing';

import { fakeStore } from '../../../testing/game-state';
import { translocoTesting } from '../../../testing/transloco-testing';
import { GameStore } from '../../core/services/game-store';
import { Gone } from './gone';

describe('Gone screen', () => {
  it('forgets the dead session without calling the server', () => {
    const store = fakeStore(null);
    TestBed.configureTestingModule({
      imports: [Gone, translocoTesting()],
      providers: [{ provide: GameStore, useValue: store }],
    });
    const fixture = TestBed.createComponent(Gone);
    fixture.detectChanges();
    (fixture.nativeElement as HTMLElement).querySelector('button')!.click();
    expect(store.exit).toHaveBeenCalled();
    expect(store.leave).not.toHaveBeenCalled();
  });
});
