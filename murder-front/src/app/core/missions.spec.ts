import { isCatalogueKey, missionTranslationKey } from './missions';

describe('mission keys', () => {
  it('recognizes catalogue keys', () => {
    expect(isCatalogueKey('core.01')).toBeTrue();
    expect(isCatalogueKey('core.30')).toBeTrue();
  });

  it('treats everything else as custom text', () => {
    for (const text of [
      'Fais rire ta cible',
      'core.',
      'Core.01',
      'core.01 et plus',
      'score.01',
      ' core.30 ', // dealt values are exact; inputs are trimmed by their callers
      'core.١٢', // same ASCII-only rule as the API
      '\ufeffcore.01',
    ]) {
      expect(isCatalogueKey(text)).withContext(text).toBeFalse();
    }
  });

  it('maps a key to its translation path, custom text to null', () => {
    expect(missionTranslationKey('core.12')).toBe('missions.core.12');
    expect(missionTranslationKey('Trinque')).toBeNull();
    expect(missionTranslationKey('')).toBeNull();
    expect(missionTranslationKey(null)).toBeNull();
  });
});
