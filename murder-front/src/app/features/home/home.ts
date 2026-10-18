import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';

import { apiFailure } from '../../core/services/game-api';
import { GameStore } from '../../core/services/game-store';
import { Toast } from '../../core/services/toast';

/** Maps a failed join to the message that tells the player what actually went wrong. */
export function joinErrorKey(err: unknown): string {
  const { status, error } = apiFailure(err);
  if (status === 404) return 'home.error.notFound';
  if (error === 'TooManyPlayers') return 'home.error.full';
  if (error === 'GameAlreadyStarted') return 'home.error.started';
  if (status === 429) return 'home.error.rateLimited';
  if (status === 0) return 'home.error.network';
  return 'common.actionFailed';
}

@Component({
  selector: 'app-home',
  imports: [FormsModule, RouterLink, TranslocoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="card">
      <span class="eyebrow">{{ 'home.eyebrow' | transloco }}</span>
      <h1>
        {{ 'home.titleLine1' | transloco }}<br />{{ 'home.titleLine2' | transloco }}<br />{{
          'home.titleLine3' | transloco
        }}
      </h1>
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
      <button class="btn primary" [disabled]="busy()" (click)="create()">
        {{ 'home.create' | transloco }}
      </button>
      <div class="sep">
        <span>{{ 'home.or' | transloco }}</span>
      </div>
      <label class="field">
        <span class="lbl">{{ 'home.gameCode' | transloco }}</span>
        <input
          class="code"
          maxlength="4"
          placeholder="••••"
          autocomplete="off"
          [(ngModel)]="code"
        />
      </label>
      <button class="btn" [disabled]="busy()" (click)="join()">
        {{ 'home.join' | transloco }}
      </button>
    </div>
    <button class="btn ghost" routerLink="/settings">{{ 'home.settings' | transloco }}</button>
  `,
})
export class Home {
  private store = inject(GameStore);
  private toast = inject(Toast);
  private i18n = inject(TranslocoService);

  name = '';
  code = '';
  readonly busy = signal(false);

  async create(): Promise<void> {
    const name = this.name.trim();
    if (!name) {
      this.toast.show(this.i18n.translate('home.error.name'), 'bad');
      return;
    }
    await this.run(
      () => this.store.create(name),
      () => 'home.error.createFailed',
    );
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
    await this.run(() => this.store.join(code, name), joinErrorKey);
  }

  private async run(action: () => Promise<void>, errorKey: (err: unknown) => string) {
    if (this.busy()) return;
    this.busy.set(true);
    try {
      await action();
    } catch (err) {
      this.toast.show(this.i18n.translate(errorKey(err)), 'bad');
    } finally {
      this.busy.set(false);
    }
  }
}
