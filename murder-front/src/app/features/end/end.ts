import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';

import { PlayerDto } from '../../core/models/game.dto';
import { GameStore } from '../../core/services/game-store';
import { Language } from '../../core/services/language';
import { IdLine } from '../../shared/id-line/id-line';
import { Notice } from '../../shared/notice/notice';
import { PluralPipe } from '../../shared/plural/plural';
import { Roster } from '../../shared/roster/roster';

/** The outright winner: alone at the top with at least one point (no winner on a tie or at 0). */
export function outrightWinner(ranking: PlayerDto[]): PlayerDto | null {
  const [first, second] = ranking;
  if (!first || first.score <= 0) return null;
  return second && second.score === first.score ? null : first;
}

@Component({
  selector: 'app-end',
  imports: [TranslocoPipe, IdLine, Roster, Notice, PluralPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (state(); as s) {
      <app-id-line [name]="me()?.name ?? ''" [code]="s.code" />
      <div class="card center">
        <span class="eyebrow">{{ 'end.over' | transloco }}</span>
        <h1 class="anim-stamp" style="margin-top: 8px">
          {{ headlineKey() | transloco: headlineParams() }}
        </h1>
        @if (winner(); as w) {
          <p class="lead" style="margin-top: 8px">
            {{ 'end.finalScore' | plural: w.score : lang() | transloco: { count: w.score } }}
          </p>
        }
      </div>
      <div class="card">
        <h2>{{ 'end.finalRanking' | transloco }}</h2>
        <app-roster
          [players]="ranking()"
          [withScore]="true"
          [meId]="me()?.id ?? ''"
          [hostId]="s.host_id"
        />
      </div>
      <button class="btn ghost" (click)="leave()">{{ 'end.backHome' | transloco }}</button>
    } @else {
      <app-notice messageKey="app.restoring" />
    }
  `,
})
export class End {
  private store = inject(GameStore);
  readonly lang = inject(Language).current;

  readonly state = this.store.state;
  readonly me = this.store.me;
  readonly ranking = this.store.ranking;
  readonly winner = computed(() => outrightWinner(this.ranking()));
  readonly headlineKey = computed(() => {
    const w = this.winner();
    if (w) return w.id === this.me()?.id ? 'end.youWin' : 'end.someoneWins';
    const [first, second] = this.ranking();
    return first && second && first.score > 0 && first.score === second.score
      ? 'end.tie'
      : 'end.gameOver';
  });
  readonly headlineParams = computed(() => {
    const w = this.winner();
    return w ? { name: w.name } : {};
  });

  /** Back home: the game is over, so this only forgets it on this device (see GameStore.leave). */
  leave(): void {
    void this.store.leave();
  }
}
