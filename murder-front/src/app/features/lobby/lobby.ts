import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { GameStore } from '../../core/services/game-store';
import { Session } from '../../core/services/session';
import { IdLine } from '../../shared/id-line/id-line';
import { Roster } from '../../shared/roster/roster';
import { Seal } from '../../shared/seal/seal';

@Component({
  selector: 'app-lobby',
  imports: [FormsModule, IdLine, Roster, Seal],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (state(); as s) {
      <app-id-line [name]="me()?.name ?? ''" [code]="s.code" />
      <div class="card">
        <h2>Salle d'attente</h2>
        <app-seal [code]="s.code" />
      </div>
      <div class="card">
        <h2>Agents recrutés — {{ s.players.length }}</h2>
        <app-roster [players]="s.players" [meId]="playerId()" [hostId]="s.host_id" />
      </div>
      @if (isHost()) {
        <div class="card">
          <h2>Paramètres</h2>
          <label class="field">
            <span class="lbl">Durée (minutes)</span>
            <input type="number" min="1" max="240" inputmode="numeric" [(ngModel)]="duration" />
          </label>
          <button class="btn danger" [disabled]="s.players.length < 2" (click)="start()">
            Lancer l'opération
          </button>
          @if (s.players.length < 2) {
            <div class="foot">Au moins 2 agents requis</div>
          }
        </div>
      } @else {
        <div class="card center">
          <span class="eyebrow">En attente</span>
          <p class="lead" style="margin: 8px 0 0">L'hôte n'a pas encore lancé…</p>
        </div>
      }
      <button class="btn ghost" (click)="leave()">Quitter</button>
    }
  `,
})
export class Lobby {
  private store = inject(GameStore);
  private session = inject(Session);

  duration = 15;
  readonly state = this.store.state;
  readonly me = this.store.me;
  readonly isHost = this.store.isHost;
  readonly playerId = this.session.playerId;

  start(): void {
    void this.store.start(Number(this.duration) || 15);
  }

  leave(): void {
    void this.store.leave();
  }
}
