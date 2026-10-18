import { DOCUMENT } from '@angular/common';
import { TestBed } from '@angular/core/testing';
import { TranslocoService } from '@jsverse/transloco';

import { translocoTesting } from '../../../testing/transloco-testing';
import { Language } from './language';

describe('Language', () => {
  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({ imports: [translocoTesting()] });
  });
  afterEach(() => localStorage.clear());

  it('restores the saved language', () => {
    localStorage.setItem('murder.language', 'en');
    expect(TestBed.inject(Language).current()).toBe('en');
  });

  it('ignores an unsupported saved value', () => {
    localStorage.setItem('murder.language', 'de');
    expect(['fr', 'en']).toContain(TestBed.inject(Language).current());
  });

  it('switches transloco, persists, and updates the document language', () => {
    const lang = TestBed.inject(Language);
    const other = lang.current() === 'fr' ? 'en' : 'fr';
    lang.set(other);
    expect(TestBed.inject(TranslocoService).getActiveLang()).toBe(other);
    expect(localStorage.getItem('murder.language')).toBe(other);
    expect(TestBed.inject(DOCUMENT).documentElement.lang).toBe(other);
  });

  it('keeps the in-memory choice when storage is unavailable', () => {
    spyOn(localStorage, 'getItem').and.throwError('SecurityError');
    spyOn(localStorage, 'setItem').and.throwError('SecurityError');
    const lang = TestBed.inject(Language);
    const other = lang.current() === 'fr' ? 'en' : 'fr';
    expect(() => lang.set(other)).not.toThrow();
    expect(lang.current()).toBe(other);
  });
});
