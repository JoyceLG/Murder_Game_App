import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';

import { GameStore } from '../../core/services/game-store';
import { Session } from '../../core/services/session';
import { IdLine } from '../../shared/id-line/id-line';
import { Roster } from '../../shared/roster/roster';

@Component({
  selector: 'app-end',
  imports: [TranslocoPipe, IdLine, Roster],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (state(); as s) {
      <app-id-line [name]="me()?.name ?? ''" [code]="s.code" />
      <div class="card center">
        <span class="eyebrow">{{ 'end.over' | transloco }}</span>
        <h1 style="margin-top: 8px">{{ headlineKey() | transloco: headlineParams() }}</h1>
        @if (winner(); as w) {
          <p class="lead" style="margin-top: 8px">
            {{ 'end.finalScore' | transloco: { count: w.score } }}
          </p>
        }
      </div>
      <div class="card">
        <h2>{{ 'end.finalRanking' | transloco }}</h2>
        <app-roster
          [players]="ranking()"
          [withScore]="true"
          [meId]="playerId()"
          [hostId]="s.host_id"
        />
      </div>
      <button class="btn ghost" (click)="leave()">{{ 'end.backHome' | transloco }}</button>
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
  readonly headlineKey = computed(() => {
    const w = this.winner();
    if (!w) return 'end.gameOver';
    return w.id === this.session.playerId() ? 'end.youWin' : 'end.someoneWins';
  });
  readonly headlineParams = computed(() => {
    const w = this.winner();
    return w ? { name: w.name } : {};
  });

  leave(): void {
    void this.store.leave();
  }
}
