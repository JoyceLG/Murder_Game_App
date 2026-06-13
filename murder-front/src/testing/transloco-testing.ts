import { TranslocoTestingModule, TranslocoTestingOptions } from '@jsverse/transloco';

/**
 * Transloco for component specs. Languages are left empty on purpose: the missing-key handler
 * echoes the key, so tests assert on stable translation keys (e.g. 'home.error.name') instead of
 * the UI copy, which keeps them decoupled from wording.
 */
export function translocoTesting(options: TranslocoTestingOptions = {}) {
  return TranslocoTestingModule.forRoot({
    langs: { fr: {}, en: {} },
    translocoConfig: { availableLangs: ['fr', 'en'], defaultLang: 'fr' },
    preloadLangs: true,
    ...options,
  });
}
