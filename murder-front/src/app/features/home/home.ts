import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';

import { GameStore } from '../../core/services/game-store';
import { Toast } from '../../core/services/toast';

@Component({
  selector: 'app-home',
  imports: [FormsModule, TranslocoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="card">
      <span class="eyebrow">{{ 'home.eyebrow' | transloco }}</span>
      <h1 [innerHTML]="'home.title' | transloco"></h1>
      <p class="lead">{{ 'home.lead' | transloco }}</p>
      <label class="field">
        <span class="lbl">{{ 'home.agentName' | transloco }}</span>
        <input
          maxlength="18"
          [placeholder]="'home.agentPlaceholder' | transloco"
          autocomplete="off"
          [(ngModel)]="name"
        />
      </label>
      <button class="btn primary" (click)="create()">{{ 'home.create' | transloco }}</button>
      <div class="sep"><span>{{ 'home.or' | transloco }}</span></div>
      <label class="field">
        <span class="lbl">{{ 'home.gameCode' | transloco }}</span>
        <input class="code" maxlength="4" placeholder="••••" autocomplete="off" [(ngModel)]="code" />
      </label>
      <button class="btn" (click)="join()">{{ 'home.join' | transloco }}</button>
    </div>
  `,
})
export class Home {
  private store = inject(GameStore);
  private toast = inject(Toast);
  private i18n = inject(TranslocoService);

  name = '';
  code = '';

  async create(): Promise<void> {
    const name = this.name.trim();
    if (!name) {
      this.toast.show(this.i18n.translate('home.error.name'), 'bad');
      return;
    }
    try {
      await this.store.create(name);
    } catch {
      this.toast.show(this.i18n.translate('home.error.createFailed'), 'bad');
    }
  }

  async join(): Promise<void> {
    const name = this.name.trim();
    const code = this.code.trim().toUpperCase();
    if (!name) {
      this.toast.show(this.i18n.translate('home.error.name'), 'bad');
      return;
    }
    if (code.length !== 4) {
      this.toast.show(this.i18n.translate('home.error.code'), 'bad');
      return;
    }
    try {
      await this.store.join(code, name);
    } catch {
      this.toast.show(this.i18n.translate('home.error.notFound'), 'bad');
    }
  }
}
