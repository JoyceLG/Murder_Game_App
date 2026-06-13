import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';

import { PlayerDto } from '../../core/models/game.dto';

@Component({
  selector: 'app-roster',
  imports: [TranslocoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ul class="roster">
      @for (player of players(); track player.id; let i = $index) {
        <li>
          @if (withScore()) {
            <span class="rank">{{ rank(i) }}</span>
          }
          <span class="pname">
            {{ player.name }}
            @if (player.id === meId()) {
              <span class="you-tag">{{ 'roster.you' | transloco }}</span>
            }
            @if (player.id === hostId()) {
              <span class="host-tag">{{ 'roster.host' | transloco }}</span>
            }
          </span>
          @if (withScore()) {
            <span class="pscore">{{ player.score }}</span>
          }
        </li>
      }
    </ul>
  `,
})
export class Roster {
  readonly players = input.required<PlayerDto[]>();
  readonly withScore = input(false);
  readonly meId = input('');
  readonly hostId = input('');

  rank(index: number): string {
    return String(index + 1).padStart(2, '0');
  }
}
