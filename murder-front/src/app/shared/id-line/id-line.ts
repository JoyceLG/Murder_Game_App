import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'app-id-line',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="idline">
      <span>{{ name() }}</span>
      <span class="code">{{ code() }}</span>
    </div>
  `,
})
export class IdLine {
  readonly name = input('');
  readonly code = input('');
}
