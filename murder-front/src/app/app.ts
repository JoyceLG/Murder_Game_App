import { ChangeDetectionStrategy, Component, effect, inject } from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';
import { TranslocoPipe } from '@jsverse/transloco';

import { GameStore, Screen } from './core/services/game-store';
import { Lang, Language } from './core/services/language';
import { Session } from './core/services/session';
import { Toast } from './core/services/toast';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, TranslocoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app.html',
})
export class App {
  private store = inject(GameStore);
  private router = inject(Router);
  protected readonly session = inject(Session);
  protected readonly toast = inject(Toast);
  protected readonly lang = inject(Language);

  constructor() {
    // The server-pushed game status is the source of truth for which screen (URL) we show.
    effect(() => {
      const target = this.routeFor(this.store.screen(), this.session.code());
      if (target && target !== this.router.url) void this.router.navigateByUrl(target);
    });
  }

  setLang(lang: Lang): void {
    this.lang.set(lang);
  }

  private routeFor(screen: Screen, code: string): string | null {
    switch (screen) {
      case 'home':
        return '/home';
      case 'lobby':
        return code ? `/g/${code}` : '/home';
      case 'game':
        return code ? `/g/${code}/play` : '/home';
      case 'end':
        return code ? `/g/${code}/end` : '/home';
      case 'gone':
        return '/gone';
      default:
        return null;
    }
  }
}
