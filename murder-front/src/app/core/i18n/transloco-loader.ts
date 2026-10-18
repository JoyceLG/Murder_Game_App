import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Translation, TranslocoLoader } from '@jsverse/transloco';

/**
 * Loads a language file served from `public/i18n/<lang>.json` (bundled as an app asset).
 * The path is relative so it resolves against <base href>: the app keeps working when deployed
 * under a sub-path, and inside a Capacitor WebView.
 */
@Injectable({ providedIn: 'root' })
export class TranslocoHttpLoader implements TranslocoLoader {
  private http = inject(HttpClient);

  getTranslation(lang: string) {
    return this.http.get<Translation>(`i18n/${lang}.json`);
  }
}
