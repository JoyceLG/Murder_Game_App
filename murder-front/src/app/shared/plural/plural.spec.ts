import { PluralPipe } from './plural';

describe('PluralPipe', () => {
  const pipe = new PluralPipe();

  it('follows French rules (0 and 1 are singular)', () => {
    expect(pipe.transform('k', 0, 'fr')).toBe('k.one');
    expect(pipe.transform('k', 1, 'fr')).toBe('k.one');
    expect(pipe.transform('k', 2, 'fr')).toBe('k.other');
  });

  it('follows English rules (only 1 is singular)', () => {
    expect(pipe.transform('k', 0, 'en')).toBe('k.other');
    expect(pipe.transform('k', 1, 'en')).toBe('k.one');
  });
});
