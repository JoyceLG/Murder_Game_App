import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { translocoTesting } from '../../../testing/transloco-testing';
import { Language } from '../../core/services/language';
import { MissionLibrary } from '../../core/services/mission-library';
import { Settings } from './settings';

describe('Settings screen', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      imports: [Settings, translocoTesting()],
      providers: [provideRouter([])],
    });
  });
  afterEach(() => localStorage.clear());

  it('names languages in words and marks the active one', () => {
    TestBed.inject(Language).set('en');
    const fixture = TestBed.createComponent(Settings);
    fixture.detectChanges();
    const buttons = [...(fixture.nativeElement as HTMLElement).querySelectorAll('.lang-btn')];
    expect(buttons.map((b) => b.textContent?.trim())).toEqual([
      'settings.langName.fr',
      'settings.langName.en',
    ]);
    expect(buttons.map((b) => b.getAttribute('aria-pressed'))).toEqual(['false', 'true']);
  });

  it('adds a mission to the device library and clears the draft', () => {
    const fixture = TestBed.createComponent(Settings);
    fixture.componentInstance.draft = 'Fais rire ta cible';
    fixture.componentInstance.add();
    fixture.detectChanges();
    expect(
      TestBed.inject(MissionLibrary)
        .missions()
        .map((m) => m.text),
    ).toEqual(['Fais rire ta cible']);
    expect(fixture.componentInstance.draft).toBe('');
    const input = (fixture.nativeElement as HTMLElement).querySelector('.mission-list input');
    expect(input?.getAttribute('aria-label')).toBe('settings.missionLabel');
  });
});
