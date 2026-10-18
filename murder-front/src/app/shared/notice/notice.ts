import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';

/** A centered card with a message and an optional "home" button (restoring, not in game…). */
@Component({
  selector: 'app-notice',
  imports: [TranslocoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="card center" role="status">
      <p class="lead" style="margin: 0">{{ messageKey() | transloco }}</p>
      @if (withHome()) {
        <button class="btn" style="margin-top: 14px" (click)="home.emit()">
          {{ 'common.home' | transloco }}
        </button>
      }
    </div>
  `,
})
export class Notice {
  readonly messageKey = input.required<string>();
  readonly withHome = input(false);
  readonly home = output<void>();
}
