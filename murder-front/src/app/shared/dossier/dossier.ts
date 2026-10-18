import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';

import { MissionText } from '../mission-text/mission-text';
import { Replay } from '../replay/replay';

@Component({
  selector: 'app-dossier',
  imports: [TranslocoPipe, MissionText, Replay],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <!-- a new mission or target is dealt: replay the "deal" animation -->
    <div class="dossier" [appReplay]="dealKey()" replayClass="anim-deal">
      <div class="drow">
        <span class="stamp">{{ 'dossier.active' | transloco }}</span>
        <span class="eyebrow">{{
          'dossier.number' | transloco: { code: code(), n: killNo() }
        }}</span>
      </div>
      <div class="mtext"><app-mission-text [mission]="mission()" /></div>
      <div class="target">
        {{ 'dossier.target' | transloco }} <b>{{ targetName() || '—' }}</b>
      </div>
    </div>
  `,
})
export class Dossier {
  readonly mission = input('');
  readonly targetName = input('');
  readonly code = input('');
  readonly killNo = input(1);
  /** Changes on every deal (deal count + target id + mission): drives the deal animation. */
  readonly dealKey = input('');
}
