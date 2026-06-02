import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { GameStore } from '../../core/services/game-store';
import { Toast } from '../../core/services/toast';

@Component({
  selector: 'app-home',
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="card">
      <span class="eyebrow">Assignations classifiées</span>
      <h1>Une mission.<br />Une cible.<br />Discrétion absolue.</h1>
      <p class="lead">
        Crée une opération, partage le code, élimine ta cible sans te faire griller.
      </p>
      <label class="field">
        <span class="lbl">Ton nom d'agent</span>
        <input maxlength="18" placeholder="Ex. Corbeau" autocomplete="off" [(ngModel)]="name" />
      </label>
      <button class="btn primary" (click)="create()">Créer une partie</button>
      <div class="sep"><span>ou</span></div>
      <label class="field">
        <span class="lbl">Code de partie</span>
        <input class="code" maxlength="4" placeholder="••••" autocomplete="off" [(ngModel)]="code" />
      </label>
      <button class="btn" (click)="join()">Rejoindre</button>
    </div>
  `,
})
export class Home {
  private store = inject(GameStore);
  private toast = inject(Toast);

  name = '';
  code = '';

  async create(): Promise<void> {
    const name = this.name.trim();
    if (!name) {
      this.toast.show('Indique ton nom', 'bad');
      return;
    }
    try {
      await this.store.create(name);
    } catch {
      this.toast.show('Création impossible', 'bad');
    }
  }

  async join(): Promise<void> {
    const name = this.name.trim();
    const code = this.code.trim().toUpperCase();
    if (!name) {
      this.toast.show('Indique ton nom', 'bad');
      return;
    }
    if (code.length !== 4) {
      this.toast.show('Code à 4 caractères', 'bad');
      return;
    }
    try {
      await this.store.join(code, name);
    } catch {
      this.toast.show('Aucune partie pour ce code', 'bad');
    }
  }
}
