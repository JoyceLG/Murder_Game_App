import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { TranslocoPipe } from '@jsverse/transloco';

@Component({
  selector: 'app-hud',
  imports: [TranslocoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="hud">
      <div class="stat">
        <div class="lbl">{{ 'hud.time' | transloco }}</div>
        <div class="val" [class.warn]="warn()">{{ clock() }}</div>
      </div>
      <div class="stat">
        <div class="lbl">{{ 'hud.score' | transloco }}</div>
        <div class="val">{{ score() }}</div>
      </div>
      <div class="stat">
        <div class="lbl">{{ 'hud.rank' | transloco }}</div>
        <div class="val">#{{ rank() }}</div>
      </div>
    </div>
  `,
})
export class Hud {
  readonly remaining = input(0);
  readonly score = input(0);
  readonly rank = input(0);

  readonly warn = computed(() => this.remaining() <= 60);
  readonly clock = computed(() => {
    const seconds = this.remaining();
    const mm = String(Math.floor(seconds / 60)).padStart(2, '0');
    const ss = String(seconds % 60).padStart(2, '0');
    return `${mm}:${ss}`;
  });
}
