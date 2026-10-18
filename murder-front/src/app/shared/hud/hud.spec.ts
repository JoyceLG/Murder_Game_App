import { ComponentFixture, TestBed } from '@angular/core/testing';

import { translocoTesting } from '../../../testing/transloco-testing';
import { Hud } from './hud';

describe('Hud', () => {
  let fixture: ComponentFixture<Hud>;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [Hud, translocoTesting()] });
    fixture = TestBed.createComponent(Hud);
  });

  it('formats the remaining seconds as mm:ss', () => {
    fixture.componentRef.setInput('remaining', 125);
    fixture.detectChanges();
    expect(fixture.componentInstance.clock()).toBe('02:05');
  });

  it('flags the warn state at or below 60 seconds', () => {
    fixture.componentRef.setInput('remaining', 45);
    fixture.detectChanges();
    expect(fixture.componentInstance.warn()).toBeTrue();
    expect(fixture.nativeElement.querySelector('.val.warn')).not.toBeNull();
  });

  it('does not warn above 60 seconds', () => {
    fixture.componentRef.setInput('remaining', 61);
    fixture.detectChanges();
    expect(fixture.componentInstance.warn()).toBeFalse();
    expect(fixture.nativeElement.querySelector('.val.warn')).toBeNull();
  });

  it('bumps the score when it goes up and dips it when it goes down, not on first render', () => {
    fixture.componentRef.setInput('score', 1);
    fixture.detectChanges();
    const score = () =>
      (fixture.nativeElement as HTMLElement).querySelectorAll('.stat .val span')[0] as HTMLElement;
    expect(score().className).toBe('');

    fixture.componentRef.setInput('score', 2);
    fixture.detectChanges();
    expect(score().className).toBe('anim-bump');

    fixture.componentRef.setInput('score', 1);
    fixture.detectChanges();
    expect(score().className).toBe('anim-dip');
  });
});
