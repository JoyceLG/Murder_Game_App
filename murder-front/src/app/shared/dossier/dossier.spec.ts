import { ComponentFixture, TestBed } from '@angular/core/testing';

import { translocoTesting } from '../../../testing/transloco-testing';
import { Dossier } from './dossier';

describe('Dossier', () => {
  let fixture: ComponentFixture<Dossier>;
  const card = () => (fixture.nativeElement as HTMLElement).querySelector('.dossier')!;
  const deal = (key: string) => {
    fixture.componentRef.setInput('dealKey', key);
    fixture.detectChanges();
  };

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [Dossier, translocoTesting()] });
    fixture = TestBed.createComponent(Dossier);
    fixture.componentRef.setInput('mission', 'core.01');
    fixture.componentRef.setInput('targetName', 'Bob');
    deal('0|b|core.01');
  });

  it('does not animate when the screen opens', () => {
    expect(card().classList).not.toContain('anim-deal');
  });

  it('animates every new deal', () => {
    deal('1|b|core.01'); // same mission, same target: still a new deal
    expect(card().classList).toContain('anim-deal');
  });

  it('does not animate for display-only changes', () => {
    fixture.componentRef.setInput('targetName', 'Bobby'); // e.g. a re-render, same deal
    fixture.detectChanges();
    expect(card().classList).not.toContain('anim-deal');
  });
});
