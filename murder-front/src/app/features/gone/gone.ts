import { ChangeDetectionStrategy, Component, inject } from '@angular/core';

import { GameStore } from '../../core/services/game-store';

@Component({
  selector: 'app-gone',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="card center">
      <span class="eyebrow">Hors ligne</span>
      <p class="lead" style="margin-top: 8px">La partie n'existe plus.</p>
      <button class="btn" (click)="leave()">Accueil</button>
    </div>
  `,
})
export class Gone {
  private store = inject(GameStore);

  leave(): void {
    void this.store.leave();
  }
}
