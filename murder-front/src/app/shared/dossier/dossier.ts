import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'app-dossier',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="dossier">
      <div class="drow">
        <span class="stamp">Assignation active</span>
        <span class="eyebrow">N° {{ code() }}-{{ killNo() }}</span>
      </div>
      <div class="mtext">{{ mission() }}</div>
      <div class="target">Cible : <b>{{ targetName() || '—' }}</b></div>
    </div>
  `,
})
export class Dossier {
  readonly mission = input('');
  readonly targetName = input('');
  readonly code = input('');
  readonly killNo = input(1);
}
