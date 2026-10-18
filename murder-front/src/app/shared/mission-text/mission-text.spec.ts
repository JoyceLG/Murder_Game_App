import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TranslocoService } from '@jsverse/transloco';

import { translocoTesting } from '../../../testing/transloco-testing';
import { MissionText } from './mission-text';

describe('MissionText', () => {
  let fixture: ComponentFixture<MissionText>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [
        MissionText,
        translocoTesting({
          langs: {
            fr: { missions: { core: { '07': 'Fais dire « banane » à ta cible.' } } },
            en: { missions: { core: { '07': 'Get your target to say “banana”.' } } },
          },
          // as in app.config.ts: switching language re-renders OnPush views
          translocoConfig: {
            availableLangs: ['fr', 'en'],
            defaultLang: 'fr',
            reRenderOnLangChange: true,
          },
        }),
      ],
    });
    fixture = TestBed.createComponent(MissionText);
  });

  const render = (mission: string) => {
    fixture.componentRef.setInput('mission', mission);
    fixture.detectChanges();
    // No trim: the text must sit flush (it is wrapped in quotes in the claim card).
    return (fixture.nativeElement as HTMLElement).textContent;
  };

  it('translates a catalogue mission in French', () => {
    expect(render('core.07')).toBe('Fais dire « banane » à ta cible.');
  });

  it('translates a catalogue mission in English', () => {
    TestBed.inject(TranslocoService).setActiveLang('en');
    expect(render('core.07')).toBe('Get your target to say “banana”.');
  });

  it('follows a language switch', () => {
    expect(render('core.07')).toContain('banane');
    TestBed.inject(TranslocoService).setActiveLang('en');
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('banana');
  });

  it('shows a custom mission exactly as typed, in any language', () => {
    expect(render('Chante en canon')).toBe('Chante en canon');
    TestBed.inject(TranslocoService).setActiveLang('en');
    expect(render('Chante en canon')).toBe('Chante en canon');
  });

  it('treats lookalikes as custom text, exactly like the API', () => {
    expect(render('core.١٢')).toBe('core.١٢');
    expect(render('\ufeffcore.07')).toBe('\ufeffcore.07');
  });

  it('never interprets custom text as a translation key or template', () => {
    expect(render('missions.core.07')).toBe('missions.core.07');
    expect(render('core.07 est ma préférée')).toBe('core.07 est ma préférée');
    expect(render('Dis {{ name }}')).toBe('Dis {{ name }}');
  });
});
