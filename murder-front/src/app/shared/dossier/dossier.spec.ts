import { ComponentFixture, TestBed } from '@angular/core/testing';

import { translocoTesting } from '../../../testing/transloco-testing';
import { Dossier } from './dossier';

describe('Dossier', () => {
  let fixture: ComponentFixture<Dossier>;
  const card = () => (fixture.nativeElement as HTMLElement).querySelector('.dossier')!;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [Dossier, translocoTesting()] });
    fixture = TestBed.createComponent(Dossier);
    fixture.componentRef.setInput('mission', 'core.01');
    fixture.componentRef.setInput('targetName', 'Bob');
    fixture.detectChanges();
  });

  it('does not animate when the screen opens', () => {
    expect(card().classList).not.toContain('anim-deal');
  });

  it('deals a new mission with an animation', () => {
    fixture.componentRef.setInput('mission', 'core.02');
    fixture.detectChanges();
    expect(card().classList).toContain('anim-deal');
  });

  it('deals a new target with an animation too', () => {
    fixture.componentRef.setInput('targetName', 'Carol');
    fixture.detectChanges();
    expect(card().classList).toContain('anim-deal');
  });
});
