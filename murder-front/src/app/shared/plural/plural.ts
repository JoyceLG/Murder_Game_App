import { Pipe, PipeTransform } from '@angular/core';

/**
 * Picks the plural form of a translation key for `count` in `lang`: `key.one` or `key.other`.
 * Uses the language's own rules (Intl.PluralRules): French treats 0 as singular, English not.
 *   {{ ('end.finalScore' | plural: score : lang()) | transloco: { count: score } }}
 */
@Pipe({ name: 'plural' })
export class PluralPipe implements PipeTransform {
  transform(key: string, count: number, lang: string): string {
    return `${key}.${new Intl.PluralRules(lang).select(count) === 'one' ? 'one' : 'other'}`;
  }
}
