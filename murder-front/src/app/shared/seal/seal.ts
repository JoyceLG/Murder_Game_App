import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'app-seal',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="seal">
      <span class="corner c1"></span><span class="corner c2"></span>
      <span class="corner c3"></span><span class="corner c4"></span>
      <span class="eyebrow">Code d'accès</span>
      <div class="k">{{ code() }}</div>
      <div class="cap muted">Partage ce code pour recruter des agents</div>
    </div>
  `,
})
export class Seal {
  readonly code = input.required<string>();
}
