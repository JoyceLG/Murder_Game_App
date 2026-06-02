import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';

import { GameStore } from '../../core/services/game-store';
import { Session } from '../../core/services/session';
import { IdLine } from '../../shared/id-line/id-line';
import { Roster } from '../../shared/roster/roster';

@Component({
  selector: 'app-end',
  imports: [IdLine, Roster],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (state(); as s) {
      <app-id-line [name]="me()?.name ?? ''" [code]="s.code" />
      <div class="card center">
        <span class="eyebrow">Opération terminée</span>
        <h1 style="margin-top: 8px">{{ headline() }}</h1>
        @if (winner(); as w) {
          <p class="lead" style="margin-top: 8px">Score final : {{ w.score }} élimination(s).</p>
        }
      </div>
      <div class="card">
        <h2>Classement final</h2>
        <app-roster
          [players]="ranking()"
          [withScore]="true"
          [meId]="playerId()"
          [hostId]="s.host_id"
        />
      </div>
      <button class="btn ghost" (click)="leave()">Retour à l'accueil</button>
    }
  `,
})
export class End {
  private store = inject(GameStore);
  private session = inject(Session);

  readonly state = this.store.state;
  readonly me = this.store.me;
  readonly ranking = this.store.ranking;
  readonly playerId = this.session.playerId;
  readonly winner = computed(() => this.ranking()[0] ?? null);
  readonly headline = computed(() => {
    const w = this.winner();
    if (w && w.id === this.session.playerId()) return "Tu remportes l'opération.";
    return w ? `${w.name} l'emporte.` : 'Fin de partie';
  });

  leave(): void {
    void this.store.leave();
  }
}
