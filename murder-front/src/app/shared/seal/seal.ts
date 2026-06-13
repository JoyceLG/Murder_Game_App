import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';

@Component({
  selector: 'app-seal',
  imports: [TranslocoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="seal">
      <span class="corner c1"></span><span class="corner c2"></span>
      <span class="corner c3"></span><span class="corner c4"></span>
      <span class="eyebrow">{{ 'seal.accessCode' | transloco }}</span>
      <div class="k">{{ code() }}</div>
      <div class="cap muted">{{ 'seal.share' | transloco }}</div>
    </div>
  `,
})
export class Seal {
  readonly code = input.required<string>();
}
