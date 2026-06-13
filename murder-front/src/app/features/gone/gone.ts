import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';

import { GameStore } from '../../core/services/game-store';

@Component({
  selector: 'app-gone',
  imports: [TranslocoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="card center">
      <span class="eyebrow">{{ 'gone.offline' | transloco }}</span>
      <p class="lead" style="margin-top: 8px">{{ 'gone.noGame' | transloco }}</p>
      <button class="btn" (click)="leave()">{{ 'common.home' | transloco }}</button>
    </div>
  `,
})
export class Gone {
  private store = inject(GameStore);

  leave(): void {
    void this.store.leave();
  }
}
