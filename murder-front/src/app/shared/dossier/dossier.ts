import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';

@Component({
  selector: 'app-dossier',
  imports: [TranslocoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="dossier">
      <div class="drow">
        <span class="stamp">{{ 'dossier.active' | transloco }}</span>
        <span class="eyebrow">{{
          'dossier.number' | transloco: { code: code(), n: killNo() }
        }}</span>
      </div>
      <div class="mtext">{{ mission() }}</div>
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
}
