import { inject, Injectable, signal } from '@angular/core';
import { TranslocoService } from '@jsverse/transloco';

export type Lang = 'fr' | 'en';

const KEY = 'murder.language';
export const SUPPORTED_LANGS: readonly Lang[] = ['fr', 'en'] as const;

/**
 * Owns the active UI language. Persists the choice on-device (localStorage) so it survives a
 * refresh — no account needed, consistent with the mobile-ready guardrails. Default = device
 * locale when supported, otherwise French.
 */
@Injectable({ providedIn: 'root' })
export class Language {
  private transloco = inject(TranslocoService);
  readonly current = signal<Lang>(this.initial());
  readonly supported = SUPPORTED_LANGS;

  constructor() {
    this.transloco.setActiveLang(this.current());
  }

  set(lang: Lang): void {
    if (lang === this.current()) return;
    this.current.set(lang);
    this.transloco.setActiveLang(lang);
    try {
      localStorage.setItem(KEY, lang);
    } catch {
      // Storage unavailable (private mode / WebView quirks) — keep the in-memory choice.
    }
  }

  private initial(): Lang {
    try {
      const saved = localStorage.getItem(KEY);
      if (saved && (SUPPORTED_LANGS as readonly string[]).includes(saved)) return saved as Lang;
    } catch {
      // ignore and fall back to device locale
    }
    const device = (navigator?.language ?? 'fr').slice(0, 2).toLowerCase();
    return (SUPPORTED_LANGS as readonly string[]).includes(device) ? (device as Lang) : 'fr';
  }
}
